import React from 'react'
import type { PredictionResult, LaptopInput } from '../predictor'

interface Props {
  prediction: PredictionResult
  input: LaptopInput
}

export function PredictionCard({ prediction, input }: Props) {
  const {
    marketRatio, marketRatioLow, marketRatioHigh,
    rvRatio, marketValue, marketValueLow, marketValueHigh,
    rvValue, rvVsMarket, recommendation,
  } = prediction

  const formatUSD = (v: number) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
  const formatPct = (v: number) => `${(v * 100).toFixed(1)}%`

  const recConfig = {
    below_rv: {
      label: 'Likely Sells Below RV',
      desc: 'Market price is below the contractual residual value. The lessor faces a potential loss at lease end.',
      color: 'text-red-400',
      bg: 'bg-red-900/30 border-red-800',
      tag: 'tag-red',
    },
    above_rv: {
      label: 'Likely Sells Above RV',
      desc: 'Market price exceeds the contractual RV. The lessor can realize a gain by selling at market.',
      color: 'text-emerald-400',
      bg: 'bg-emerald-900/30 border-emerald-800',
      tag: 'tag-green',
    },
    near_rv: {
      label: 'Near Contractual RV',
      desc: 'Market value is close to the contractual residual value. Minimal risk exposure.',
      color: 'text-blue-400',
      bg: 'bg-blue-900/30 border-blue-800',
      tag: 'tag-blue',
    },
  }

  const rec = recConfig[recommendation]

  // Range bar positioning: shows where RV sits within the market prediction range
  const rangeMin = Math.min(marketValueLow, rvValue) * 0.9
  const rangeMax = Math.max(marketValueHigh, rvValue) * 1.1
  const rangeSpan = rangeMax - rangeMin
  const lowPct = ((marketValueLow - rangeMin) / rangeSpan) * 100
  const highPct = ((marketValueHigh - rangeMin) / rangeSpan) * 100
  const midPct = ((marketValue - rangeMin) / rangeSpan) * 100
  const rvPct = ((rvValue - rangeMin) / rangeSpan) * 100

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
            <p className="text-xs text-slate-400 uppercase tracking-wider">Contractual RV</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">{formatUSD(rvValue)}</p>
            <p className="text-sm text-slate-400">{formatPct(rvRatio)} of purchase price</p>
          </div>
        </div>

        {/* Prediction Range Visual */}
        <div className="bg-slate-800 rounded-lg p-4 mb-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-slate-400 uppercase tracking-wider">Sale Price Range (90% CI)</p>
            <p className="text-xs text-slate-500">
              {formatUSD(marketValueLow)} - {formatUSD(marketValueHigh)}
            </p>
          </div>

          {/* Range bar visualization */}
          <div className="relative h-8 mt-3 mb-6">
            {/* Background track */}
            <div className="absolute inset-x-0 top-3 h-2 bg-slate-700 rounded-full" />

            {/* Prediction range band */}
            <div
              className="absolute top-2 h-4 bg-blue-900/60 border border-blue-700/50 rounded-full"
              style={{ left: `${lowPct}%`, width: `${highPct - lowPct}%` }}
            />

            {/* Market value marker */}
            <div
              className="absolute top-0 w-3 h-8 -ml-1.5"
              style={{ left: `${midPct}%` }}
            >
              <div className="w-3 h-3 rounded-full bg-blue-500 border-2 border-blue-300 mx-auto" />
              <div className="w-0.5 h-5 bg-blue-400 mx-auto" />
            </div>

            {/* RV marker */}
            <div
              className="absolute top-0 w-3 h-8 -ml-1.5"
              style={{ left: `${rvPct}%` }}
            >
              <div className="w-3 h-3 rounded-full bg-emerald-500 border-2 border-emerald-300 mx-auto" />
              <div className="w-0.5 h-5 bg-emerald-400 mx-auto" />
            </div>
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-blue-500 border border-blue-300" />
              <span className="text-slate-400">Predicted Sale ({formatUSD(marketValue)})</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 border border-emerald-300" />
              <span className="text-slate-400">Contractual RV ({formatUSD(rvValue)})</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-6 h-2 rounded bg-blue-900/60 border border-blue-700/50" />
              <span className="text-slate-400">90% Range</span>
            </div>
          </div>
        </div>

        {/* Gain/Loss */}
        <div className={`rounded-lg p-4 border ${rec.bg}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wider">Market vs RV Gap</p>
              <p className={`text-xl font-bold mt-1 ${rvVsMarket >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {rvVsMarket >= 0 ? '+' : ''}{formatUSD(rvVsMarket)}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-400">Per Unit</p>
              <p className={`text-sm font-medium ${rec.color}`}>{rec.label}</p>
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-2">{rec.desc}</p>
        </div>
      </div>

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
