import React from 'react'
import type { PredictionResult, LaptopInput } from '../predictor'

interface CurvePoint {
  month: number
  marketValue: number
  marketValueLow: number
  marketValueHigh: number
  marketValueLow50: number
  marketValueHigh50: number
  rvValue: number
  marketRatio: number
  rvRatio: number
}

interface Props {
  prediction: PredictionResult
  input: LaptopInput
  depCurve?: CurvePoint[]
}

export function PredictionCard({ prediction, input, depCurve }: Props) {
  const {
    marketRatio, marketRatioLow, marketRatioHigh,
    marketRatioLow50, marketRatioHigh50,
    rvRatio, marketValue, marketValueLow, marketValueHigh,
    marketValueLow50, marketValueHigh50,
    rvValue, rvVsMarket, recommendation,
  } = prediction

  const formatUSD = (v: number) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
  const formatPct = (v: number) => `${(v * 100).toFixed(1)}%`

  // Proposed RV range: conservative (80% CI low) to moderate (5% below predicted sale)
  const proposedRVLow = marketValueLow50
  const proposedRVHigh = Math.round(marketValue * 0.95)
  const profitPctLow = proposedRVHigh > 0 ? ((marketValue - proposedRVHigh) / proposedRVHigh) : 0
  const profitPctHigh = proposedRVLow > 0 ? ((marketValue - proposedRVLow) / proposedRVLow) : 0

  const recConfig = {
    below_rv: {
      label: 'High Profit Opportunity',
      desc: 'Predicted sale price is well above proposed RV. The seller has strong margin at lease end.',
      color: 'text-emerald-400',
      bg: 'bg-emerald-900/30 border-emerald-800',
      tag: 'tag-green',
    },
    above_rv: {
      label: 'Moderate Margin',
      desc: 'Predicted sale price exceeds proposed RV. The seller can realize a reasonable profit.',
      color: 'text-blue-400',
      bg: 'bg-blue-900/30 border-blue-800',
      tag: 'tag-blue',
    },
    near_rv: {
      label: 'Tight Margin',
      desc: 'Sale price is close to the proposed RV. Thin profit margin — consider a lower RV to reduce risk.',
      color: 'text-amber-400',
      bg: 'bg-amber-900/30 border-amber-800',
      tag: 'tag-yellow',
    },
  }

  const rec = recConfig[recommendation]

  // Range bar positioning: shows where proposed RV range sits within the market prediction range
  const rangeMin = Math.min(marketValueLow, proposedRVLow) * 0.9
  const rangeMax = Math.max(marketValueHigh, proposedRVHigh) * 1.1
  const rangeSpan = rangeMax - rangeMin
  const lowPct = ((marketValueLow - rangeMin) / rangeSpan) * 100
  const highPct = ((marketValueHigh - rangeMin) / rangeSpan) * 100
  const low50Pct = ((marketValueLow50 - rangeMin) / rangeSpan) * 100
  const high50Pct = ((marketValueHigh50 - rangeMin) / rangeSpan) * 100
  const midPct = ((marketValue - rangeMin) / rangeSpan) * 100
  const rvLowPct = ((proposedRVLow - rangeMin) / rangeSpan) * 100
  const rvHighPct = ((proposedRVHigh - rangeMin) / rangeSpan) * 100

  return (
    <div className="space-y-4 fade-in">
      {/* Main prediction */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Prediction Results</h2>
          <span className={`tag ${rec.tag}`}>{rec.label}</span>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="bg-slate-800 rounded-lg p-4">
            <p className="text-xs text-slate-400 uppercase tracking-wider">Predicted Sale Price</p>
            <p className="text-2xl font-bold text-blue-400 mt-1">{formatUSD(marketValue)}</p>
            <p className="text-sm text-slate-400">{formatPct(marketRatio)} of purchase price</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-4">
            <p className="text-xs text-slate-400 uppercase tracking-wider">Proposed RV Range</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">
              {formatUSD(proposedRVLow)} - {formatUSD(proposedRVHigh)}
            </p>
            <p className="text-sm text-emerald-400 font-medium">
              {formatPct(profitPctLow)} - {formatPct(profitPctHigh)} profit
            </p>
          </div>
        </div>

        {/* Prediction Range Visual */}
        <div className="bg-slate-800 rounded-lg p-4 mb-4">
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs text-slate-400 uppercase tracking-wider">Sale Price Range</p>
            <p className="text-xs text-slate-500">
              {formatUSD(marketValueLow)} - {formatUSD(marketValueHigh)}
            </p>
          </div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-blue-400 font-medium">Most Likely Range (80% CI)</p>
            <p className="text-xs text-blue-400">
              {formatUSD(marketValueLow50)} - {formatUSD(marketValueHigh50)}
            </p>
          </div>

          {/* Range bar visualization */}
          <div className="relative h-8 mt-3 mb-6">
            {/* Background track */}
            <div className="absolute inset-x-0 top-3 h-2 bg-slate-700 rounded-full" />

            {/* 90% outer prediction range band */}
            <div
              className="absolute top-2 h-4 bg-blue-900/40 border border-blue-700/30 rounded-full"
              style={{ left: `${lowPct}%`, width: `${highPct - lowPct}%` }}
            />

            {/* 80% inner confidence band — most likely range */}
            <div
              className="absolute top-1.5 h-5 bg-blue-600/40 border border-blue-500/60 rounded-full"
              style={{ left: `${low50Pct}%`, width: `${high50Pct - low50Pct}%` }}
            />

            {/* Market value marker */}
            <div
              className="absolute top-0 w-3 h-8 -ml-1.5"
              style={{ left: `${midPct}%` }}
            >
              <div className="w-3 h-3 rounded-full bg-blue-500 border-2 border-blue-300 mx-auto" />
              <div className="w-0.5 h-5 bg-blue-400 mx-auto" />
            </div>

            {/* Proposed RV range band */}
            <div
              className="absolute top-1 h-6 bg-emerald-600/30 border border-emerald-500/50 rounded"
              style={{ left: `${rvLowPct}%`, width: `${rvHighPct - rvLowPct}%` }}
            />
            <div
              className="absolute top-0 w-3 h-8 -ml-1.5"
              style={{ left: `${rvLowPct}%` }}
            >
              <div className="w-2.5 h-2.5 rounded-sm bg-emerald-500 border-2 border-emerald-300 mx-auto" />
              <div className="w-0.5 h-5 bg-emerald-400 mx-auto" />
            </div>
            <div
              className="absolute top-0 w-3 h-8 -ml-1.5"
              style={{ left: `${rvHighPct}%` }}
            >
              <div className="w-2.5 h-2.5 rounded-sm bg-emerald-500 border-2 border-emerald-300 mx-auto" />
              <div className="w-0.5 h-5 bg-emerald-400 mx-auto" />
            </div>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-blue-500 border border-blue-300" />
              <span className="text-slate-400">Predicted Sale ({formatUSD(marketValue)})</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-6 h-2.5 rounded bg-emerald-600/40 border border-emerald-500/60" />
              <span className="text-slate-400">Proposed RV ({formatUSD(proposedRVLow)} - {formatUSD(proposedRVHigh)})</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-6 h-2.5 rounded bg-blue-600/40 border border-blue-500/60" />
              <span className="text-slate-400">80% Most Likely</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-6 h-2 rounded bg-blue-900/40 border border-blue-700/30" />
              <span className="text-slate-400">90% Range</span>
            </div>
          </div>

          {/* CI Methodology Notes */}
          <div className="mt-4 pt-3 border-t border-slate-700/50">
            <p className="text-[10px] text-slate-500 italic mb-1.5">How we arrived at these confidence ranges:</p>
            <ul className="space-y-0.5 text-[10px] text-slate-500 italic pl-3">
              <li>Based on 7,210 actual Dell laptop resale prices in the ASEAN B2B market (2021-2024)</li>
              <li>Ranges are set so that 80% (or 90%) of past sales actually fell within these bands</li>
              <li>{input.modelLine === 'workstation'
                ? 'Workstation segment: trained on 298 units, 79.5% of past sales fell within the 80% band'
                : input.modelLine === 'business_standard'
                ? 'Business laptop segment: trained on 6,912 units, 83.6% of past sales fell within the 80% band'
                : 'Using conservative wider bands as a safety margin for this segment'}</li>
              <li>Prediction uses 3 models combined (XGBoost, LightGBM, Decision Tree) for better accuracy</li>
              <li>Factors in USD/SGD exchange rate, Singapore inflation, and global semiconductor costs</li>
              <li>Assumes market conditions stay broadly similar to the 2021-2024 period</li>
              <li>Currently calibrated for Dell only — accuracy may vary for other brands</li>
            </ul>
          </div>
        </div>

        {/* Gain/Loss */}
        <div className={`rounded-lg p-4 border ${rec.bg}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wider">Seller Profit Range</p>
              <p className="text-xl font-bold mt-1 text-emerald-400">
                {formatPct(profitPctLow)} - {formatPct(profitPctHigh)}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-400">Per Unit Gain</p>
              <p className={`text-sm font-medium ${rec.color}`}>
                {formatUSD(marketValue - proposedRVHigh)} - {formatUSD(marketValue - proposedRVLow)}
              </p>
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-2">{rec.desc}</p>
        </div>

        {/* Scenario adjustment display */}
        {prediction.scenarioAdjustment && prediction.scenarioAdjustment.eventDetails.length > 0 && (
          <div className="bg-slate-800 rounded-lg p-4 border border-amber-700/30">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-amber-400 uppercase tracking-wider font-medium">Scenario-Adjusted Forecast</p>
              <span className="text-xs text-slate-500">
                {(prediction.scenarioAdjustment.combinedConfidence * 100).toFixed(0)}% confidence
              </span>
            </div>
            <div className="grid grid-cols-3 gap-3 mb-3">
              <div>
                <p className="text-[10px] text-slate-500">Adjusted Value</p>
                <p className="text-lg font-bold text-amber-400">
                  {formatUSD(prediction.adjustedMarketValue ?? marketValue)}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500">Low End</p>
                <p className="text-sm font-medium text-slate-400">
                  {formatUSD(prediction.adjustedMarketValueLow ?? marketValueLow)}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500">High End</p>
                <p className="text-sm font-medium text-slate-400">
                  {formatUSD(prediction.adjustedMarketValueHigh ?? marketValueHigh)}
                </p>
              </div>
            </div>
            {/* Per-event breakdown */}
            <div className="space-y-1">
              {prediction.scenarioAdjustment.eventDetails.map((ed, i) => (
                <div key={i} className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-400 truncate mr-2">{ed.title}</span>
                  <span className={ed.impactLowPct + ed.impactHighPct > 0 ? 'text-emerald-400' : 'text-red-400'}>
                    {ed.impactLowPct > 0 ? '+' : ''}{ed.impactLowPct.toFixed(1)}% to {ed.impactHighPct > 0 ? '+' : ''}{ed.impactHighPct.toFixed(1)}%
                  </span>
                </div>
              ))}
              {prediction.scenarioAdjustment.sentimentContrib !== 0 && (
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-400">Market sentiment</span>
                  <span className={prediction.scenarioAdjustment.sentimentContrib > 0 ? 'text-emerald-400' : 'text-red-400'}>
                    {prediction.scenarioAdjustment.sentimentContrib > 0 ? '+' : ''}{prediction.scenarioAdjustment.sentimentContrib.toFixed(2)}%
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* FI financial summary */}
        {prediction.fiNetProceeds !== undefined && (
          <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
            <p className="text-xs text-slate-400 uppercase tracking-wider font-medium mb-3">Financial Institution View</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="text-[10px] text-slate-500">Net Proceeds (after costs & tax)</p>
                <p className={`text-lg font-bold ${(prediction.fiNetProceeds ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {formatUSD(prediction.fiNetProceeds ?? 0)}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500">Net Present Value</p>
                <p className={`text-lg font-bold ${(prediction.fiNPV ?? 0) >= 0 ? 'text-blue-400' : 'text-red-400'}`}>
                  {formatUSD(prediction.fiNPV ?? 0)}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500">Total Costs (disposal + holding + insurance)</p>
                <p className="text-sm font-medium text-slate-300">{formatUSD(prediction.fiTotalCosts ?? 0)}</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500">Meets Target Margin?</p>
                <p className={`text-sm font-bold ${prediction.fiBreakeven ? 'text-emerald-400' : 'text-red-400'}`}>
                  {prediction.fiBreakeven ? 'Yes' : 'No'}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Yearly Price Outlook — from Month 24 onwards for FI planning */}
      {depCurve && depCurve.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-1">Future Market Value Forecast</h3>
          <p className="text-xs text-slate-500 mb-4">Projected resale value from Year 2 onwards — for lease-end planning</p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[24, 36, 48].map(month => {
              const point = depCurve.find(d => d.month === month)
              if (!point) return null
              const year = month / 12
              const retention = point.marketRatio * 100
              const depFromPrev = month === 24 ? null :
                depCurve.find(d => d.month === month - 12)
              const yoyDrop = depFromPrev
                ? ((depFromPrev.marketRatio - point.marketRatio) / depFromPrev.marketRatio * 100)
                : null

              // Mini range bar positions
              const barMin = point.marketValueLow * 0.95
              const barMax = point.marketValueHigh * 1.05
              const barSpan = barMax - barMin
              const bar90Left = ((point.marketValueLow - barMin) / barSpan) * 100
              const bar90Width = ((point.marketValueHigh - point.marketValueLow) / barSpan) * 100
              const bar80Left = ((point.marketValueLow50 - barMin) / barSpan) * 100
              const bar80Width = ((point.marketValueHigh50 - point.marketValueLow50) / barSpan) * 100
              const barMid = ((point.marketValue - barMin) / barSpan) * 100

              return (
                <div key={month} className="bg-slate-800 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-semibold text-slate-200">Year {year}</span>
                    <div className="flex items-center gap-2">
                      {yoyDrop !== null && (
                        <span className="text-[10px] text-red-400">-{yoyDrop.toFixed(0)}% YoY</span>
                      )}
                      <span className="text-xs text-slate-500">{retention.toFixed(0)}% of purchase</span>
                    </div>
                  </div>

                  <p className="text-xl font-bold text-blue-400">{formatUSD(point.marketValue)}</p>

                  {/* Confidence band bar */}
                  <div className="relative h-5 mt-3 mb-2">
                    <div className="absolute inset-x-0 top-2 h-1 bg-slate-700 rounded-full" />
                    {/* 90% band */}
                    <div
                      className="absolute top-1 h-3 bg-blue-900/40 border border-blue-700/30 rounded-full"
                      style={{ left: `${bar90Left}%`, width: `${bar90Width}%` }}
                    />
                    {/* 80% band */}
                    <div
                      className="absolute top-0.5 h-4 bg-blue-600/50 border border-blue-500/60 rounded-full"
                      style={{ left: `${bar80Left}%`, width: `${bar80Width}%` }}
                    />
                    {/* Center marker */}
                    <div
                      className="absolute top-0 w-2.5 h-5 -ml-1"
                      style={{ left: `${barMid}%` }}
                    >
                      <div className="w-2 h-2 rounded-full bg-blue-400 border border-blue-300 mx-auto" />
                    </div>
                  </div>

                  {/* Ranges text */}
                  <div className="space-y-1 mt-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] text-blue-400 font-medium">80% CI</span>
                      <span className="text-[11px] text-blue-400 font-medium">
                        {formatUSD(point.marketValueLow50)} - {formatUSD(point.marketValueHigh50)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-slate-500">90% CI</span>
                      <span className="text-[10px] text-slate-500">
                        {formatUSD(point.marketValueLow)} - {formatUSD(point.marketValueHigh)}
                      </span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Configuration summary */}
      <div className="card">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">Configuration</h3>
        <div className="grid grid-cols-3 gap-2 text-xs">
          <Detail label="Brand" value={input.brand} />
          <Detail label="Line" value={input.modelLine} />
          <Detail label="Series" value={`${input.modelTier}000`} />
          <Detail label="CPU" value={`${input.isXeon ? 'Xeon' : `i${input.processorTier+2}`} Gen ${input.processorGen}`} />
          <Detail label="RAM" value={`${input.ramGb} GB`} />
          <Detail label="Storage" value={input.storageGb > 0 ? `${input.storageGb} GB SSD` : 'No SSD'} />
          <Detail label="Screen" value={`${input.screenInches}"`} />
          <Detail label="Purchase" value={formatUSD(input.purchasePrice)} />
          <Detail label="Lease" value={`${input.leaseDurationMonths}mo`} />
        </div>
      </div>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-800/50 rounded px-2 py-1.5">
      <span className="text-slate-500">{label}: </span>
      <span className="text-slate-300 font-medium">{value}</span>
    </div>
  )
}
