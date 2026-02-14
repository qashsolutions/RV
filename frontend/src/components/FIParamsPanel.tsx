import React from 'react'
import type { FIParams } from '../predictor'
import { DEFAULT_FI_PARAMS } from '../predictor'

interface Props {
  params: FIParams
  onChange: (params: FIParams) => void
}

const FIELDS: Array<{
  key: keyof FIParams
  label: string
  hint: string
  min: number
  max: number
  step: number
  pct: boolean  // display as percentage
}> = [
  { key: 'discountRate', label: 'Discount Rate', hint: 'Annual rate to discount future cash flows', min: 0, max: 0.20, step: 0.005, pct: true },
  { key: 'disposalCostPct', label: 'Disposal Cost', hint: '% of sale price for remarketing/broker fees', min: 0, max: 0.15, step: 0.005, pct: true },
  { key: 'taxRate', label: 'Corporate Tax Rate', hint: 'Tax on resale gain (e.g. 17% SG)', min: 0, max: 0.40, step: 0.01, pct: true },
  { key: 'insurancePct', label: 'Annual Insurance', hint: 'Annual premium as % of purchase price', min: 0, max: 0.05, step: 0.002, pct: true },
  { key: 'holdingCostMonthly', label: 'Holding Cost', hint: '$/month per unit for warehousing', min: 0, max: 100, step: 5, pct: false },
  { key: 'targetMarginPct', label: 'Target Margin', hint: 'Minimum profit margin to break even', min: 0, max: 0.10, step: 0.005, pct: true },
]

export function FIParamsPanel({ params, onChange }: Props) {
  const update = (key: keyof FIParams, value: number) => {
    onChange({ ...params, [key]: value })
  }

  const isDefault = JSON.stringify(params) === JSON.stringify(DEFAULT_FI_PARAMS)

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Financial Parameters</h2>
          <p className="text-xs text-slate-400 mt-0.5">Customize for your institution's cost structure</p>
        </div>
        {!isDefault && (
          <button
            onClick={() => onChange(DEFAULT_FI_PARAMS)}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            Reset defaults
          </button>
        )}
      </div>

      <div className="space-y-3">
        {FIELDS.map(field => {
          const value = params[field.key]
          const displayValue = field.pct ? `${(value * 100).toFixed(1)}%` : `$${value}`

          return (
            <div key={field.key}>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-slate-300">{field.label}</label>
                <span className="text-xs font-mono text-blue-400">{displayValue}</span>
              </div>
              <input
                type="range"
                min={field.min}
                max={field.max}
                step={field.step}
                value={value}
                onChange={e => update(field.key, parseFloat(e.target.value))}
                className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer
                  [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5
                  [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:border-2
                  [&::-webkit-slider-thumb]:border-blue-300 [&::-webkit-slider-thumb]:cursor-pointer"
              />
              <p className="text-[10px] text-slate-500 mt-0.5">{field.hint}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
