/**
 * Browser-side ML prediction engine.
 * Uses the MDT (Decision Tree) model for real-time inference.
 * Tree structure is loaded from JSON exported by Python training pipeline.
 */

export interface LaptopInput {
  brand: string
  modelLine: string
  modelTier: number
  processorGen: number
  processorTier: number
  isXeon: boolean
  ramGb: number
  storageGb: number
  hasSsd: boolean
  screenInches: number
  purchasePrice: number
  leaseDurationMonths: number
}

export interface PredictionResult {
  marketRatio: number
  marketRatioLow: number
  marketRatioHigh: number
  rvRatio: number
  marketValue: number
  marketValueLow: number
  marketValueHigh: number
  rvValue: number
  confidence: number
  rvVsMarket: number
  recommendation: 'below_rv' | 'above_rv' | 'near_rv'
}

interface TreeData {
  feature: number[]
  threshold: number[]
  children_left: number[]
  children_right: number[]
  value: number[]
  n_features: number
}

// Brand mappings (must match Python features.py)
const BRAND_TIER: Record<string, number> = {
  Apple: 4, Microsoft: 4,
  Lenovo: 3, Dell: 3, HP: 3, Fujitsu: 3, Panasonic: 3,
  ASUS: 2, Acer: 2, MSI: 2, Samsung: 2, LG: 2,
  Huawei: 1, Xiaomi: 1, Honor: 1,
}

const BRAND_RETENTION: Record<string, number> = {
  Apple: 1.15, Microsoft: 1.05,
  Lenovo: 1.00, Dell: 0.98, HP: 0.97,
  Fujitsu: 0.95, Panasonic: 0.96,
  ASUS: 0.92, Acer: 0.88, MSI: 0.90,
  Samsung: 0.91, LG: 0.89,
  Huawei: 0.80, Xiaomi: 0.78,
}

const MODEL_LINE_ENCODING: Record<string, number> = {
  workstation: 5, premium: 4, business_standard: 3,
  sme: 2, consumer: 1, desktop: 1, unknown: 2,
}

let marketTree: TreeData | null = null
let rvTree: TreeData | null = null
let manifestData: any = null

export async function loadModels(basePath: string): Promise<void> {
  const [mt, rt, mf] = await Promise.all([
    fetch(`${basePath}/market_mdt.json`).then(r => r.json()),
    fetch(`${basePath}/rv_mdt.json`).then(r => r.json()),
    fetch(`${basePath}/manifest.json`).then(r => r.json()),
  ])
  marketTree = mt
  rvTree = rt
  manifestData = mf
}

function traverseTree(tree: TreeData, features: number[]): number {
  let nodeId = 0
  while (tree.children_left[nodeId] !== -1) {
    const featureIdx = tree.feature[nodeId]
    const threshold = tree.threshold[nodeId]
    if (features[featureIdx] <= threshold) {
      nodeId = tree.children_left[nodeId]
    } else {
      nodeId = tree.children_right[nodeId]
    }
  }
  return tree.value[nodeId]
}

function buildFeatureVector(input: LaptopInput): number[] {
  const age = input.leaseDurationMonths / 12.0
  const brandTier = BRAND_TIER[input.brand] ?? 3
  const brandRet = BRAND_RETENTION[input.brand] ?? 0.90
  const modelLineEnc = MODEL_LINE_ENCODING[input.modelLine] ?? 3
  const ramLog = Math.log2(Math.max(1, input.ramGb))
  const storageLog = Math.log2(Math.max(1, input.storageGb))
  const screenBucket = input.screenInches < 12.5 ? 1 : input.screenInches <= 13.5 ? 2 : input.screenInches <= 14.5 ? 3 : input.screenInches <= 16 ? 4 : 5
  const priceLog = Math.log1p(input.purchasePrice)
  const priceTier = input.purchasePrice < 1000 ? 1 : input.purchasePrice < 1500 ? 2 : input.purchasePrice < 2000 ? 3 : input.purchasePrice < 3000 ? 4 : 5
  const specScore = (input.ramGb / 64.0 + input.storageGb / 2000.0 + input.processorGen / 13.0 + input.processorTier / 5.0) / 4

  // Must match get_feature_columns() order in features.py
  return [
    age,                        // age_years
    age * age,                  // age_squared
    input.leaseDurationMonths,  // lease_duration_months
    brandTier,                  // brand_tier_encoded
    brandRet,                   // brand_retention
    modelLineEnc,               // model_line_encoded
    input.modelTier,            // model_tier
    input.processorGen,         // processor_gen
    input.processorTier,        // processor_tier
    input.isXeon ? 1 : 0,       // is_xeon
    input.ramGb,                // ram_gb
    ramLog,                     // ram_log
    input.storageGb,            // storage_gb
    storageLog,                 // storage_log
    input.hasSsd ? 1 : 0,       // has_ssd
    input.screenInches,         // screen_inches
    screenBucket,               // screen_bucket
    priceLog,                   // price_log
    priceTier,                  // price_tier
    specScore,                  // spec_score
  ]
}

// Calibrated residual std from training (market model MAE ~0.024, std ~0.045)
const MARKET_RESIDUAL_STD = 0.045
const CI_MULTIPLIER = 1.645 // 90% confidence interval

export function predict(input: LaptopInput): PredictionResult {
  if (!marketTree || !rvTree) {
    throw new Error('Models not loaded. Call loadModels() first.')
  }

  const features = buildFeatureVector(input)
  const marketRatio = Math.max(0.05, Math.min(0.95, traverseTree(marketTree, features)))
  const rvRatio = Math.max(0.05, Math.min(0.95, traverseTree(rvTree, features)))

  // Prediction range: calibrated 90% CI from training residuals
  const uncertainty = CI_MULTIPLIER * MARKET_RESIDUAL_STD
  const marketRatioLow = Math.max(0.03, marketRatio - uncertainty)
  const marketRatioHigh = Math.min(0.95, marketRatio + uncertainty)

  const marketValue = marketRatio * input.purchasePrice
  const marketValueLow = marketRatioLow * input.purchasePrice
  const marketValueHigh = marketRatioHigh * input.purchasePrice
  const rvValue = rvRatio * input.purchasePrice
  const rvVsMarket = marketValue - rvValue
  const confidence = 0.85 // MDT single-model confidence

  let recommendation: PredictionResult['recommendation']
  const diff = Math.abs(rvVsMarket) / rvValue
  if (rvVsMarket < 0 && diff > 0.1) {
    recommendation = 'below_rv'
  } else if (rvVsMarket > 0 && diff > 0.1) {
    recommendation = 'above_rv'
  } else {
    recommendation = 'near_rv'
  }

  return {
    marketRatio, marketRatioLow, marketRatioHigh,
    rvRatio, marketValue, marketValueLow, marketValueHigh,
    rvValue, confidence, rvVsMarket, recommendation,
  }
}

export function predictDepreciationCurve(
  input: LaptopInput,
  months: number[] = [6, 12, 18, 24, 30, 36, 42, 48]
): Array<{
  month: number
  marketValue: number
  marketValueLow: number
  marketValueHigh: number
  rvValue: number
  marketRatio: number
  rvRatio: number
}> {
  return months.map(m => {
    const adjusted = { ...input, leaseDurationMonths: m }
    const result = predict(adjusted)
    return {
      month: m,
      marketValue: result.marketValue,
      marketValueLow: result.marketValueLow,
      marketValueHigh: result.marketValueHigh,
      rvValue: result.rvValue,
      marketRatio: result.marketRatio,
      rvRatio: result.rvRatio,
    }
  })
}

export function getModelMetrics() {
  return manifestData
}
