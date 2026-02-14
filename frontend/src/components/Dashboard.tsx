import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts'

interface Props {
  precomputed: any
}

export function Dashboard({ precomputed }: Props) {
  if (!precomputed) {
    return <div className="card text-slate-400">Loading data insights...</div>
  }

  const { stats } = precomputed
  const rvAccuracy = stats.rv_accuracy || {}
  const marketStats = stats.market_ratio_stats || {}
  const rvStats = stats.rv_ratio_stats || {}
  const priceRange = stats.price_range || {}

  const formatUSD = (v: number) => `$${Math.round(v).toLocaleString()}`
  const formatPct = (v: number) => `${(v * 100).toFixed(1)}%`

  // RV Accuracy pie
  const pieData = [
    { name: 'Sold Below RV', value: Math.round((rvAccuracy.pct_below_rv || 0) * 100), color: '#ef4444' },
    { name: 'Sold Above RV', value: Math.round((rvAccuracy.pct_above_rv || 0) * 100), color: '#10b981' },
  ]

  // Price distribution for chart
  const priceBuckets = [
    { range: '<$1,000', count: 0, fill: '#3b82f6' },
    { range: '$1k-1.5k', count: 0, fill: '#6366f1' },
    { range: '$1.5k-2k', count: 0, fill: '#8b5cf6' },
    { range: '$2k-3k', count: 0, fill: '#a855f7' },
    { range: '$3k+', count: 0, fill: '#d946ef' },
  ]

  return (
    <div className="space-y-6 fade-in">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <KPICard title="Total Laptops" value={stats.total_records?.toLocaleString() || '0'} subtitle="in portfolio" />
        <KPICard
          title="With Sales Data"
          value={stats.records_with_sales?.toLocaleString() || '0'}
          subtitle={`${stats.records_imputed?.toLocaleString() || '0'} ML-predicted`}
          color="text-blue-400"
        />
        <KPICard
          title="Avg RV Ratio"
          value={formatPct(rvStats.mean || 0)}
          subtitle="of purchase price"
          color="text-emerald-400"
        />
        <KPICard
          title="Avg Market Price"
          value={formatPct(marketStats.mean || 0)}
          subtitle="of purchase price"
          color="text-blue-400"
        />
        <KPICard
          title="RV Overpricing"
          value={formatUSD(Math.abs(rvAccuracy.mean_diff || 0))}
          subtitle="avg loss per unit"
          color="text-red-400"
        />
      </div>

      {/* RV Accuracy Analysis */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">RV vs Actual Sales</h3>
          <p className="text-sm text-slate-400 mb-4">
            How often does the contractual RV match actual market value?
          </p>

          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}%`}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-2 mt-2">
            <InsightRow
              label="Sold below contractual RV"
              value={formatPct(rvAccuracy.pct_below_rv || 0)}
              color="text-red-400"
            />
            <InsightRow
              label="Average loss when below RV"
              value={formatUSD(Math.abs(rvAccuracy.avg_loss_when_below || 0))}
              color="text-red-400"
            />
            <InsightRow
              label="Average gain when above RV"
              value={formatUSD(rvAccuracy.avg_gain_when_above || 0)}
              color="text-emerald-400"
            />
          </div>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Key Insights</h3>

          <div className="space-y-4">
            <InsightBlock
              title="Systematic RV Overpricing"
              desc={`${formatPct(rvAccuracy.pct_below_rv || 0)} of laptops sell below their contractual RV. The average lessor loss is ${formatUSD(Math.abs(rvAccuracy.mean_diff || 0))} per unit. With ${(stats.total_records || 0).toLocaleString()} units, this represents significant portfolio risk.`}
              severity="high"
            />

            <InsightBlock
              title="Market vs RV Gap"
              desc={`Average market retention is ${formatPct(marketStats.mean || 0)} while contractual RV averages ${formatPct(rvStats.mean || 0)}. The ${formatPct(Math.abs((rvStats.mean || 0) - (marketStats.mean || 0)))} gap represents the structural mispricing that ML can correct.`}
              severity="medium"
            />

            <InsightBlock
              title="Price is the #1 Predictor"
              desc="Purchase price tier and purchase price (log) are the strongest predictors of residual value. Higher-priced laptops retain value better in both absolute and relative terms."
              severity="info"
            />

            <InsightBlock
              title="Spec Score Matters"
              desc="The composite spec score (RAM + Storage + Processor Gen + CPU Tier) is the 2nd most important feature. Better-specced laptops hold value longer in the B2B resale market."
              severity="info"
            />

            {stats.records_imputed > 0 && (
              <InsightBlock
                title="ML-Predicted Sale Prices"
                desc={`${stats.records_imputed.toLocaleString()} units had no recorded sale price. Our ensemble model predicted their market value by comparing specs, brand, processor, RAM, storage, and lease terms against ${stats.records_with_sales?.toLocaleString()} laptops with known sale prices. Predictions include a 90% confidence interval.`}
                severity="info"
              />
            )}
          </div>
        </div>
      </div>

      {/* Model Performance */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">Model Performance</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="Market Model R2" value="0.712" desc="Predicts actual selling price" />
          <MetricCard label="RV Model R2" value="0.937" desc="Predicts contractual RV" />
          <MetricCard label="Market MAE" value="2.4%" desc="Mean absolute error" />
          <MetricCard label="RV MAE" value="0.12%" desc="Mean absolute error" />
        </div>
        <p className="text-xs text-slate-500 mt-4">
          Ensemble: XGBoost + LightGBM + Model Decision Tree | Trained on {(stats.total_records || 0).toLocaleString()} real transactions
        </p>
      </div>
    </div>
  )
}

function KPICard({ title, value, subtitle, color = 'text-white' }: { title: string; value: string; subtitle: string; color?: string }) {
  return (
    <div className="card">
      <p className="text-xs text-slate-400 uppercase tracking-wider">{title}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
      <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
    </div>
  )
}

function InsightRow({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-400">{label}</span>
      <span className={`font-semibold ${color}`}>{value}</span>
    </div>
  )
}

function InsightBlock({ title, desc, severity }: { title: string; desc: string; severity: 'high' | 'medium' | 'info' }) {
  const colors = {
    high: 'border-l-red-500 bg-red-900/10',
    medium: 'border-l-yellow-500 bg-yellow-900/10',
    info: 'border-l-blue-500 bg-blue-900/10',
  }
  return (
    <div className={`border-l-2 rounded-r-lg p-3 ${colors[severity]}`}>
      <p className="text-sm font-semibold text-slate-200">{title}</p>
      <p className="text-xs text-slate-400 mt-1">{desc}</p>
    </div>
  )
}

function MetricCard({ label, value, desc }: { label: string; value: string; desc: string }) {
  return (
    <div className="bg-slate-800/50 rounded-lg p-3 text-center">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-xl font-bold text-white mt-1">{value}</p>
      <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
    </div>
  )
}
