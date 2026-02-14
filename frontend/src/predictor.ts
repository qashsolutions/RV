/**
 * Browser-side ML prediction engine.
 * Uses the MDT (Decision Tree) model for real-time inference.
 * Tree structure is loaded from JSON exported by Python training pipeline.
 *
 * v2: Adds price-dependent CI, scenario adjustments, FI financial parameters,
 *     and forward curve generation.
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

export interface FIParams {
  discountRate: number       // annual discount rate (e.g. 0.05 = 5%)
  disposalCostPct: number    // % of sale price (e.g. 0.03 = 3%)
  taxRate: number            // corporate tax rate (e.g. 0.17 = 17%)
  insurancePct: number       // annual insurance premium as % of purchase (e.g. 0.01)
  holdingCostMonthly: number // $/month warehousing per unit
  targetMarginPct: number    // minimum profit margin (e.g. 0.02 = 2%)
}

export const DEFAULT_FI_PARAMS: FIParams = {
  discountRate: 0.05,
  disposalCostPct: 0.03,
  taxRate: 0.17,
  insurancePct: 0.01,
  holdingCostMonthly: 15,
  targetMarginPct: 0.02,
}

export interface ScenarioEvent {
  id: string
  title: string
  category: string
  impactLowPct: number
  impactHighPct: number
  impactConfidence: number
  effectiveFrom?: string
  decayMonths: number
  affectedBrands: string[]
  affectedSegments: string[]
  enabled: boolean  // toggled by user in UI
}

export interface ScenarioAdjustment {
  adjustmentLowPct: number
  adjustmentHighPct: number
  adjustmentMidPct: number
  combinedConfidence: number
  sentimentContrib: number
  eventDetails: Array<{
    title: string
    category: string
    impactLowPct: number
    impactHighPct: number
    confidence: number
    decay: number
  }>
}

export interface PredictionResult {
  marketRatio: number
  marketRatioLow: number
  marketRatioHigh: number
  marketRatioLow50: number
  marketRatioHigh50: number
  rvRatio: number
  marketValue: number
  marketValueLow: number
  marketValueHigh: number
  marketValueLow50: number
  marketValueHigh50: number
  rvValue: number
  confidence: number
  rvVsMarket: number
  recommendation: 'below_rv' | 'above_rv' | 'near_rv'
  // v2: scenario-adjusted values
  scenarioAdjustment?: ScenarioAdjustment
  adjustedMarketValue?: number
  adjustedMarketValueLow?: number
  adjustedMarketValueHigh?: number
  // v2: FI financial outputs
  fiNetProceeds?: number
  fiNPV?: number
  fiBreakeven?: boolean
  fiTotalCosts?: number
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

// Live data caches (loaded from static JSON files updated by GitHub Actions)
let sentimentData: { score: number; confidence: number; headlines: string[] } | null = null
let scenarioData: { activeEvents: ScenarioEvent[]; scenarios: Record<string, any> } | null = null

// FRED ASEAN macro-economic defaults
const FRED_DEFAULTS = {
  cpiIndex: 117.5,
  cpiYoyChange: 0.028,
  consumerSentiment: 1.34,
  fedFundsRate: 107.0,
  macroScore: 0.6525,
}

export async function loadModels(basePath: string): Promise<void> {
  const [mt, rt, mf] = await Promise.all([
    fetch(`${basePath}/market_mdt.json`).then(r => r.json()),
    fetch(`${basePath}/rv_mdt.json`).then(r => r.json()),
    fetch(`${basePath}/manifest.json`).then(r => r.json()),
  ])
  marketTree = mt
  rvTree = rt
  manifestData = mf

  // Try loading live data (non-blocking — falls back gracefully)
  const dataBase = basePath.replace('/models', '/data')
  try {
    const sentResp = await fetch(`${dataBase}/latest_sentiment.json`)
    if (sentResp.ok) {
      const d = await sentResp.json()
      sentimentData = d.sentiment
    }
  } catch { /* fallback: no live sentiment */ }

  try {
    const scenResp = await fetch(`${dataBase}/active_scenarios.json`)
    if (scenResp.ok) {
      const d = await scenResp.json()
      scenarioData = {
        activeEvents: (d.active_events || []).map((e: any) => ({
          id: e.id || '',
          title: e.title || '',
          category: e.category || '',
          impactLowPct: e.impact_low_pct ?? 0,
          impactHighPct: e.impact_high_pct ?? 0,
          impactConfidence: e.impact_confidence ?? 0.5,
          effectiveFrom: e.effective_from,
          decayMonths: e.decay_months ?? 6,
          affectedBrands: e.affected_brands || [],
          affectedSegments: e.affected_segments || [],
          enabled: false,
        })),
        scenarios: d.scenarios || {},
      }
    }
  } catch { /* fallback: no live scenarios */ }
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

  const fredMeta = manifestData?.fred_defaults
  const cpiIndex = fredMeta?.cpi_index ?? FRED_DEFAULTS.cpiIndex
  const cpiYoyChange = fredMeta?.cpi_yoy_change ?? FRED_DEFAULTS.cpiYoyChange
  const consumerSentiment = fredMeta?.consumer_sentiment ?? FRED_DEFAULTS.consumerSentiment
  const fedFundsRate = fredMeta?.fed_funds_rate ?? FRED_DEFAULTS.fedFundsRate
  const macroScore = fredMeta?.macro_score ?? FRED_DEFAULTS.macroScore

  return [
    age, age * age, input.leaseDurationMonths,
    brandTier, brandRet, modelLineEnc, input.modelTier,
    input.processorGen, input.processorTier, input.isXeon ? 1 : 0,
    input.ramGb, ramLog, input.storageGb, storageLog, input.hasSsd ? 1 : 0,
    input.screenInches, screenBucket,
    priceLog, priceTier, specScore,
    cpiIndex, cpiYoyChange, consumerSentiment, fedFundsRate, macroScore,
    0,  // is_estimated_price: 0=actual MSRP (browser predictions use known prices)
  ]
}

// ── Price-Dependent CI ─────────────────────────────────────────
// CI bands widen for expensive laptops (more variance in resale)
// and tighten for cheaper ones (closer to floor value).
//
// Formula: ci_width = base_ci * (price / median_price) ^ elasticity
// Capped at [0.5x, 2.0x] of base CI to avoid extreme bands.

const EMPIRICAL_CI: Record<string, { q80: number; q90: number }> = {
  workstation: { q80: 0.0350, q90: 0.0420 },
  business_standard: { q80: 0.0348, q90: 0.0608 },
  default: { q80: 0.0608, q90: 0.1195 },
}

const MEDIAN_PRICE = 1600  // from training data statistics
const CI_ELASTICITY = 0.3  // how quickly CI scales with price

function getCI(modelLine: string, purchasePrice: number): { q80: number; q90: number; priceScale: number } {
  const base = EMPIRICAL_CI[modelLine] ?? EMPIRICAL_CI['default']
  const priceRatio = purchasePrice / MEDIAN_PRICE
  const scale = Math.max(0.5, Math.min(2.0, Math.pow(priceRatio, CI_ELASTICITY)))

  return {
    q80: base.q80 * scale,
    q90: base.q90 * scale,
    priceScale: scale,
  }
}

// ── Scenario adjustment (client-side) ──────────────────────────

function computeEventDecay(effectiveFrom: string | undefined, decayMonths: number): number {
  if (!effectiveFrom) return 1.0
  const now = new Date()
  const start = new Date(effectiveFrom)
  const daysElapsed = (now.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)
  if (daysElapsed < 0) return 0.0
  const halfLifeDays = decayMonths * 30.44
  return Math.exp(-0.693 * daysElapsed / halfLifeDays)
}

export function computeScenarioAdjustment(
  enabledEvents: ScenarioEvent[],
  brand: string,
  segment: string,
  sentimentScore: number = 0,
  sentimentConfidence: number = 0.5,
): ScenarioAdjustment {
  const brandLower = brand.toLowerCase()
  let totalLow = 0
  let totalHigh = 0
  let totalWeightedMid = 0
  let totalWeight = 0
  const details: ScenarioAdjustment['eventDetails'] = []

  for (const event of enabledEvents) {
    if (!event.enabled) continue

    const affBrands = event.affectedBrands.map(b => b.toLowerCase())
    if (affBrands.length > 0 && !affBrands.includes(brandLower)) continue
    if (event.affectedSegments.length > 0 && !event.affectedSegments.includes(segment)) continue

    const decay = computeEventDecay(event.effectiveFrom, event.decayMonths)
    if (decay < 0.05) continue

    const impLow = event.impactLowPct * decay
    const impHigh = event.impactHighPct * decay
    const mid = (impLow + impHigh) / 2

    totalLow += impLow
    totalHigh += impHigh
    totalWeightedMid += mid * event.impactConfidence
    totalWeight += event.impactConfidence

    details.push({
      title: event.title,
      category: event.category,
      impactLowPct: Math.round(impLow * 100) / 100,
      impactHighPct: Math.round(impHigh * 100) / 100,
      confidence: event.impactConfidence,
      decay: Math.round(decay * 1000) / 1000,
    })
  }

  // Sentiment: ±3% max
  const sentimentContrib = sentimentScore * sentimentConfidence * 3.0
  if (sentimentContrib < 0) totalLow += sentimentContrib
  else totalHigh += sentimentContrib
  totalWeightedMid += sentimentContrib * sentimentConfidence
  totalWeight += sentimentConfidence

  const combinedConfidence = totalWeight / (details.length + 1) || sentimentConfidence
  const adjustmentMid = totalWeight > 0 ? totalWeightedMid / totalWeight : 0

  return {
    adjustmentLowPct: Math.round(totalLow * 100) / 100,
    adjustmentHighPct: Math.round(totalHigh * 100) / 100,
    adjustmentMidPct: Math.round(adjustmentMid * 100) / 100,
    combinedConfidence: Math.round(combinedConfidence * 10000) / 10000,
    sentimentContrib: Math.round(sentimentContrib * 10000) / 10000,
    eventDetails: details,
  }
}

// ── FI financial calculations ──────────────────────────────────

function computeFIOutputs(
  marketValue: number,
  purchasePrice: number,
  leaseDurationMonths: number,
  fi: FIParams,
): { netProceeds: number; npv: number; breakeven: boolean; totalCosts: number } {
  const disposalCost = marketValue * fi.disposalCostPct
  const holdingCost = fi.holdingCostMonthly * 3 // assume 3-month remarketing period
  const insuranceCost = purchasePrice * fi.insurancePct * (leaseDurationMonths / 12)
  const totalCosts = disposalCost + holdingCost + insuranceCost

  const grossProceeds = marketValue - totalCosts
  const taxOnGain = Math.max(0, grossProceeds) * fi.taxRate
  const netProceeds = grossProceeds - taxOnGain

  // NPV: discount net proceeds back to lease start
  const years = leaseDurationMonths / 12
  const npv = netProceeds / Math.pow(1 + fi.discountRate, years)

  const breakeven = netProceeds >= purchasePrice * fi.targetMarginPct

  return { netProceeds, npv, breakeven, totalCosts }
}

// ── Main predict function ──────────────────────────────────────

export function predict(
  input: LaptopInput,
  enabledEvents?: ScenarioEvent[],
  fiParams?: FIParams,
): PredictionResult {
  if (!marketTree || !rvTree) {
    throw new Error('Models not loaded. Call loadModels() first.')
  }

  const features = buildFeatureVector(input)
  const marketRatio = Math.max(0.05, Math.min(0.95, traverseTree(marketTree, features)))
  const rvRatio = Math.max(0.05, Math.min(0.95, traverseTree(rvTree, features)))

  // Price-dependent CI
  const ci = getCI(input.modelLine, input.purchasePrice)

  const marketRatioLow = Math.max(0.03, marketRatio - ci.q90)
  const marketRatioHigh = Math.min(0.95, marketRatio + ci.q90)
  const marketRatioLow50 = Math.max(0.03, marketRatio - ci.q80)
  const marketRatioHigh50 = Math.min(0.95, marketRatio + ci.q80)

  const marketValue = marketRatio * input.purchasePrice
  const marketValueLow = marketRatioLow * input.purchasePrice
  const marketValueHigh = marketRatioHigh * input.purchasePrice
  const marketValueLow50 = marketRatioLow50 * input.purchasePrice
  const marketValueHigh50 = marketRatioHigh50 * input.purchasePrice
  const rvValue = rvRatio * input.purchasePrice
  const rvVsMarket = marketValue - rvValue

  // Confidence: base segment score adjusted for price scaling
  const baseConfidence = input.modelLine === 'workstation' ? 0.91 :
    input.modelLine === 'business_standard' ? 0.84 : 0.80
  // Tighter CI (lower price) → higher effective confidence
  const confidence = Math.min(0.95, baseConfidence / ci.priceScale)

  let recommendation: PredictionResult['recommendation']
  const diff = Math.abs(rvVsMarket) / rvValue
  if (rvVsMarket < 0 && diff > 0.1) recommendation = 'below_rv'
  else if (rvVsMarket > 0 && diff > 0.1) recommendation = 'above_rv'
  else recommendation = 'near_rv'

  const result: PredictionResult = {
    marketRatio, marketRatioLow, marketRatioHigh,
    marketRatioLow50, marketRatioHigh50,
    rvRatio, marketValue, marketValueLow, marketValueHigh,
    marketValueLow50, marketValueHigh50,
    rvValue, confidence, rvVsMarket, recommendation,
  }

  // Scenario adjustments
  if (enabledEvents && enabledEvents.some(e => e.enabled)) {
    const sentScore = sentimentData?.score ?? 0
    const sentConf = sentimentData?.confidence ?? 0.5
    const adj = computeScenarioAdjustment(enabledEvents, input.brand, input.modelLine, sentScore, sentConf)
    result.scenarioAdjustment = adj

    const midMult = 1 + adj.adjustmentMidPct / 100
    const lowMult = 1 + adj.adjustmentLowPct / 100
    const highMult = 1 + adj.adjustmentHighPct / 100

    result.adjustedMarketValue = marketValue * midMult
    result.adjustedMarketValueLow = marketValueLow * lowMult
    result.adjustedMarketValueHigh = marketValueHigh * highMult
  }

  // FI financial outputs
  if (fiParams) {
    const effectiveMarket = result.adjustedMarketValue ?? marketValue
    const fi = computeFIOutputs(effectiveMarket, input.purchasePrice, input.leaseDurationMonths, fiParams)
    result.fiNetProceeds = fi.netProceeds
    result.fiNPV = fi.npv
    result.fiBreakeven = fi.breakeven
    result.fiTotalCosts = fi.totalCosts
  }

  return result
}

export function predictDepreciationCurve(
  input: LaptopInput,
  months: number[] = [6, 12, 18, 24, 30, 36, 42, 48],
  enabledEvents?: ScenarioEvent[],
  fiParams?: FIParams,
): Array<{
  month: number
  marketValue: number
  marketValueLow: number
  marketValueHigh: number
  marketValueLow50: number
  marketValueHigh50: number
  rvValue: number
  marketRatio: number
  rvRatio: number
  adjustedMarketValue?: number
}> {
  return months.map(m => {
    const adjusted = { ...input, leaseDurationMonths: m }
    const result = predict(adjusted, enabledEvents, fiParams)
    return {
      month: m,
      marketValue: result.marketValue,
      marketValueLow: result.marketValueLow,
      marketValueHigh: result.marketValueHigh,
      marketValueLow50: result.marketValueLow50,
      marketValueHigh50: result.marketValueHigh50,
      rvValue: result.rvValue,
      marketRatio: result.marketRatio,
      rvRatio: result.rvRatio,
      adjustedMarketValue: result.adjustedMarketValue,
    }
  })
}

export function getModelMetrics() {
  return manifestData
}

export function getSentimentData() {
  return sentimentData
}

export function getActiveScenarioEvents(): ScenarioEvent[] {
  return scenarioData?.activeEvents ?? getDefaultScenarioEvents()
}

/** Fallback scenario events when no live data is available */
export function getDefaultScenarioEvents(): ScenarioEvent[] {
  return [
    {
      id: 'apple-launch',
      title: 'Apple launches new MacBook',
      category: 'competitor_launch',
      impactLowPct: -8, impactHighPct: -3, impactConfidence: 0.75,
      decayMonths: 6,
      affectedBrands: ['Dell', 'Lenovo', 'HP'],
      affectedSegments: ['premium', 'business_standard'],
      enabled: false,
    },
    {
      id: 'dell-discontinue',
      title: 'Dell discontinues this model line',
      category: 'model_discontinuation',
      impactLowPct: -12, impactHighPct: -5, impactConfidence: 0.80,
      decayMonths: 12,
      affectedBrands: ['Dell'],
      affectedSegments: [],
      enabled: false,
    },
    {
      id: 'dell-refresh',
      title: 'Dell refreshes Latitude/Precision line',
      category: 'model_discontinuation',
      impactLowPct: -6, impactHighPct: -2, impactConfidence: 0.75,
      decayMonths: 6,
      affectedBrands: ['Dell'],
      affectedSegments: ['business_standard', 'workstation'],
      enabled: false,
    },
    {
      id: 'chip-shortage',
      title: 'Semiconductor shortage / chip supply delay',
      category: 'supply_chain',
      impactLowPct: 2, impactHighPct: 8, impactConfidence: 0.70,
      decayMonths: 9,
      affectedBrands: [],
      affectedSegments: [],
      enabled: false,
    },
    {
      id: 'logistics-disruption',
      title: 'Shipping / logistics disruption',
      category: 'supply_chain',
      impactLowPct: 1.5, impactHighPct: 5, impactConfidence: 0.65,
      decayMonths: 4,
      affectedBrands: [],
      affectedSegments: [],
      enabled: false,
    },
    {
      id: 'recession',
      title: 'Regional recession / demand slowdown',
      category: 'macro_economic',
      impactLowPct: -15, impactHighPct: -8, impactConfidence: 0.75,
      decayMonths: 12,
      affectedBrands: [],
      affectedSegments: [],
      enabled: false,
    },
    {
      id: 'usd-strong',
      title: 'USD strengthens significantly vs SGD',
      category: 'macro_economic',
      impactLowPct: -6, impactHighPct: -2, impactConfidence: 0.70,
      decayMonths: 6,
      affectedBrands: [],
      affectedSegments: [],
      enabled: false,
    },
    {
      id: 'arm-windows',
      title: 'ARM-based Windows laptops gain traction',
      category: 'technology_shift',
      impactLowPct: -7, impactHighPct: -2, impactConfidence: 0.55,
      decayMonths: 18,
      affectedBrands: [],
      affectedSegments: [],
      enabled: false,
    },
  ]
}
