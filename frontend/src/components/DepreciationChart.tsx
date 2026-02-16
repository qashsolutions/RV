import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, Area, AreaChart
} from 'recharts'

interface DataPoint {
  month: number
  marketValue: number
  marketValueLow: number
  marketValueHigh: number
  rvValue: number
  marketRatio: number
  rvRatio: number
}

interface Props {
  data: DataPoint[]
  purchasePrice: number
}

export function DepreciationChart({ data, purchasePrice }: Props) {
  const chartData = data.map(d => ({
    ...d,
    month: d.month,
    Market: Math.round(d.marketValue),
    'Market Range': [Math.round(d.marketValueLow), Math.round(d.marketValueHigh)] as [number, number],
    'Proposed RV': Math.round(d.rvValue),
    'Market %': Math.round(d.marketRatio * 100),
    'RV %': Math.round(d.rvRatio * 100),
    gap: Math.round(d.marketValue - d.rvValue),
  }))

  const formatUSD = (v: number) => `$${v.toLocaleString()}`

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-white mb-1">Depreciation Curve</h3>
      <p className="text-xs text-slate-400 mb-4">Predicted value over lease term (Purchase: {formatUSD(purchasePrice)})</p>

      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <defs>
              <linearGradient id="marketGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="rvGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="rangeGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis
              dataKey="month"
              stroke="#64748b"
              tick={{ fill: '#94a3b8', fontSize: 12 }}
              label={{ value: 'Months', position: 'insideBottom', offset: -5, fill: '#64748b', fontSize: 12 }}
            />
            <YAxis
              stroke="#64748b"
              tick={{ fill: '#94a3b8', fontSize: 12 }}
              tickFormatter={v => `$${(v/1000).toFixed(1)}k`}
            />
            <Tooltip
              contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}
              labelStyle={{ color: '#94a3b8' }}
              formatter={(value: any, name: any) => {
                if (Array.isArray(value)) return [`${formatUSD(value[0])} - ${formatUSD(value[1])}`, String(name)]
                return [formatUSD(Number(value)), String(name)]
              }}
              labelFormatter={(label: any) => `Month ${label}`}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Area type="monotone" dataKey="Market Range" stroke="none" fill="url(#rangeGrad)" strokeWidth={0} />
            <Area type="monotone" dataKey="Market" stroke="#3b82f6" fill="url(#marketGrad)" strokeWidth={2} />
            <Area type="monotone" dataKey="Proposed RV" stroke="#10b981" fill="url(#rvGrad)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Ratio summary */}
      <div className="grid grid-cols-4 gap-2 mt-4">
        {chartData.filter((_, i) => i % 2 === 1 || i === chartData.length - 1).map(d => (
          <div key={d.month} className="text-center bg-slate-800/50 rounded p-2">
            <p className="text-xs text-slate-500">{d.month}mo</p>
            <p className="text-sm font-bold text-blue-400">{d['Market %']}%</p>
            <p className="text-xs text-slate-500">mkt</p>
          </div>
        ))}
      </div>
    </div>
  )
}
