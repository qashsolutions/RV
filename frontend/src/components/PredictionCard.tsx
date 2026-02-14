import React from 'react'
import type { PredictionResult, LaptopInput } from '../predictor'

interface Props {
  prediction: PredictionResult
  input: LaptopInput
}

export function PredictionCard({ prediction, input }: Props) {
  const { marketRatio, rvRatio, marketValue, rvValue, rvVsMarket, recommendation } = prediction

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
            <p className="text-xs text-slate-400 uppercase tracking-wider">Market Value</p>
            <p className="text-2xl font-bold text-blue-400 mt-1">{formatUSD(marketValue)}</p>
            <p className="text-sm text-slate-400">{formatPct(marketRatio)} of purchase price</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-4">
            <p className="text-xs text-slate-400 uppercase tracking-wider">Contractual RV</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">{formatUSD(rvValue)}</p>
            <p className="text-sm text-slate-400">{formatPct(rvRatio)} of purchase price</p>
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
