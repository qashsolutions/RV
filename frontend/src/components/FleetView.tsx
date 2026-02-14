import React, { useState, useCallback } from 'react'
import { predict, type LaptopInput, type PredictionResult } from '../predictor'

interface FleetItem {
  id: number
  label: string
  input: LaptopInput
  prediction: PredictionResult
  quantity: number
}

interface Props {
  onPredict: (input: LaptopInput) => void
}

// Default fleet for demo
const DEFAULT_FLEET: Omit<FleetItem, 'id' | 'prediction'>[] = [
  {
    label: 'Dell Latitude 7320 i7',
    quantity: 50,
    input: {
      brand: 'Dell', modelLine: 'business_standard', modelTier: 7,
      processorGen: 11, processorTier: 4, isXeon: false,
      ramGb: 16, storageGb: 512, hasSsd: true, screenInches: 13.3,
      purchasePrice: 2152, leaseDurationMonths: 24,
    },
  },
  {
    label: 'Dell Precision 7550 Xeon',
    quantity: 15,
    input: {
      brand: 'Dell', modelLine: 'workstation', modelTier: 7,
      processorGen: 10, processorTier: 5, isXeon: true,
      ramGb: 32, storageGb: 1000, hasSsd: true, screenInches: 15.6,
      purchasePrice: 3131, leaseDurationMonths: 24,
    },
  },
  {
    label: 'Dell Latitude 5420 i5',
    quantity: 200,
    input: {
      brand: 'Dell', modelLine: 'business_standard', modelTier: 5,
      processorGen: 11, processorTier: 3, isXeon: false,
      ramGb: 16, storageGb: 512, hasSsd: true, screenInches: 14.0,
      purchasePrice: 1329, leaseDurationMonths: 36,
    },
  },
  {
    label: 'Dell Latitude 7420 i7',
    quantity: 80,
    input: {
      brand: 'Dell', modelLine: 'business_standard', modelTier: 7,
      processorGen: 11, processorTier: 4, isXeon: false,
      ramGb: 16, storageGb: 512, hasSsd: true, screenInches: 14.0,
      purchasePrice: 1887, leaseDurationMonths: 36,
    },
  },
]

export function FleetView({ onPredict }: Props) {
  const [fleet, setFleet] = useState<FleetItem[]>(() =>
    DEFAULT_FLEET.map((item, i) => ({
      ...item,
      id: i,
      prediction: predict(item.input),
    }))
  )

  const formatUSD = (v: number) => `$${Math.round(v).toLocaleString()}`

  // Portfolio totals
  const totalUnits = fleet.reduce((s, f) => s + f.quantity, 0)
  const totalPurchase = fleet.reduce((s, f) => s + f.input.purchasePrice * f.quantity, 0)
  const totalMarketValue = fleet.reduce((s, f) => s + f.prediction.marketValue * f.quantity, 0)
  const totalRvValue = fleet.reduce((s, f) => s + f.prediction.rvValue * f.quantity, 0)
  const totalGap = totalMarketValue - totalRvValue
  const portfolioMarketRatio = totalMarketValue / totalPurchase
  const portfolioAtRisk = fleet
    .filter(f => f.prediction.recommendation === 'below_rv')
    .reduce((s, f) => s + Math.abs(f.prediction.rvVsMarket) * f.quantity, 0)

  return (
    <div className="space-y-6 fade-in">
      {/* Portfolio KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="card">
          <p className="text-xs text-slate-400 uppercase">Total Units</p>
          <p className="text-2xl font-bold text-white">{totalUnits}</p>
        </div>
        <div className="card">
          <p className="text-xs text-slate-400 uppercase">Portfolio Cost</p>
          <p className="text-2xl font-bold text-white">{formatUSD(totalPurchase)}</p>
        </div>
        <div className="card">
          <p className="text-xs text-slate-400 uppercase">Market Value</p>
          <p className="text-2xl font-bold text-blue-400">{formatUSD(totalMarketValue)}</p>
          <p className="text-xs text-slate-500">{(portfolioMarketRatio * 100).toFixed(1)}% retention</p>
        </div>
        <div className="card">
          <p className="text-xs text-slate-400 uppercase">Total RV</p>
          <p className="text-2xl font-bold text-emerald-400">{formatUSD(totalRvValue)}</p>
        </div>
        <div className="card">
          <p className="text-xs text-slate-400 uppercase">Portfolio at Risk</p>
          <p className="text-2xl font-bold text-red-400">{formatUSD(portfolioAtRisk)}</p>
          <p className="text-xs text-slate-500">RV overpricing exposure</p>
        </div>
      </div>

      {/* Fleet Table */}
      <div className="card overflow-x-auto">
        <h3 className="text-lg font-semibold text-white mb-4">Fleet Equipment</h3>

        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-400 uppercase border-b border-slate-700">
              <th className="pb-2 pr-4">Equipment</th>
              <th className="pb-2 pr-4 text-right">Qty</th>
              <th className="pb-2 pr-4 text-right">Unit Cost</th>
              <th className="pb-2 pr-4 text-right">Market Value</th>
              <th className="pb-2 pr-4 text-right">RV</th>
              <th className="pb-2 pr-4 text-right">Gap/Unit</th>
              <th className="pb-2 pr-4 text-right">Total Exposure</th>
              <th className="pb-2 text-center">Status</th>
            </tr>
          </thead>
          <tbody>
            {fleet.map(item => {
              const gap = item.prediction.rvVsMarket
              const totalExposure = gap * item.quantity
              const statusConfig = {
                below_rv: { label: 'Below RV', class: 'tag-red' },
                above_rv: { label: 'Above RV', class: 'tag-green' },
                near_rv: { label: 'Near RV', class: 'tag-blue' },
              }
              const status = statusConfig[item.prediction.recommendation]

              return (
                <tr key={item.id} className="border-b border-slate-800 hover:bg-slate-800/50">
                  <td className="py-3 pr-4">
                    <p className="font-medium text-slate-200">{item.label}</p>
                    <p className="text-xs text-slate-500">
                      {item.input.ramGb}GB | {item.input.storageGb}GB | {item.input.screenInches}" | {item.input.leaseDurationMonths}mo
                    </p>
                  </td>
                  <td className="py-3 pr-4 text-right text-slate-300">{item.quantity}</td>
                  <td className="py-3 pr-4 text-right text-slate-300">{formatUSD(item.input.purchasePrice)}</td>
                  <td className="py-3 pr-4 text-right text-blue-400 font-medium">{formatUSD(item.prediction.marketValue)}</td>
                  <td className="py-3 pr-4 text-right text-emerald-400">{formatUSD(item.prediction.rvValue)}</td>
                  <td className={`py-3 pr-4 text-right font-medium ${gap >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {gap >= 0 ? '+' : ''}{formatUSD(gap)}
                  </td>
                  <td className={`py-3 pr-4 text-right font-medium ${totalExposure >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {totalExposure >= 0 ? '+' : ''}{formatUSD(totalExposure)}
                  </td>
                  <td className="py-3 text-center">
                    <span className={`tag ${status.class}`}>{status.label}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr className="text-slate-300 font-semibold border-t border-slate-600">
              <td className="pt-3 pr-4">Total</td>
              <td className="pt-3 pr-4 text-right">{totalUnits}</td>
              <td className="pt-3 pr-4 text-right">{formatUSD(totalPurchase)}</td>
              <td className="pt-3 pr-4 text-right text-blue-400">{formatUSD(totalMarketValue)}</td>
              <td className="pt-3 pr-4 text-right text-emerald-400">{formatUSD(totalRvValue)}</td>
              <td className="pt-3 pr-4 text-right" colSpan={2}>
                <span className={totalGap >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                  {totalGap >= 0 ? '+' : ''}{formatUSD(totalGap)} total gap
                </span>
              </td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <p className="text-xs text-slate-500 text-center">
        Fleet data pre-loaded from portfolio. Add your own configurations via the Predict tab.
      </p>
    </div>
  )
}
