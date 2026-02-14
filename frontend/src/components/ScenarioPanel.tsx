import React from 'react'
import type { ScenarioEvent } from '../predictor'

interface Props {
  events: ScenarioEvent[]
  onChange: (events: ScenarioEvent[]) => void
  sentimentScore?: number
  sentimentConfidence?: number
  sentimentHeadlines?: string[]
}

const CATEGORY_ICONS: Record<string, string> = {
  competitor_launch: 'CL',
  model_discontinuation: 'DC',
  supply_chain: 'SC',
  macro_economic: 'ME',
  technology_shift: 'TS',
  regulatory: 'RG',
}

const CATEGORY_COLORS: Record<string, string> = {
  competitor_launch: 'border-orange-600/40 bg-orange-900/20',
  model_discontinuation: 'border-red-600/40 bg-red-900/20',
  supply_chain: 'border-emerald-600/40 bg-emerald-900/20',
  macro_economic: 'border-blue-600/40 bg-blue-900/20',
  technology_shift: 'border-purple-600/40 bg-purple-900/20',
  regulatory: 'border-yellow-600/40 bg-yellow-900/20',
}

export function ScenarioPanel({ events, onChange, sentimentScore, sentimentConfidence, sentimentHeadlines }: Props) {
  const toggleEvent = (id: string) => {
    onChange(events.map(e => e.id === id ? { ...e, enabled: !e.enabled } : e))
  }

  const enabledCount = events.filter(e => e.enabled).length

  // Compute net impact preview
  const enabledEvents = events.filter(e => e.enabled)
  let netLow = 0, netHigh = 0
  for (const e of enabledEvents) {
    netLow += e.impactLowPct
    netHigh += e.impactHighPct
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Market Scenarios</h2>
          <p className="text-xs text-slate-400 mt-0.5">Toggle events to see how they impact the predicted resale value</p>
        </div>
        {enabledCount > 0 && (
          <span className="tag tag-yellow">{enabledCount} active</span>
        )}
      </div>

      {/* Sentiment indicator */}
      {sentimentScore !== undefined && (
        <div className="bg-slate-800 rounded-lg p-3 mb-4">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-slate-400 uppercase tracking-wider">Market Sentiment</span>
            <span className={`text-sm font-bold ${
              sentimentScore > 0.1 ? 'text-emerald-400' : sentimentScore < -0.1 ? 'text-red-400' : 'text-slate-300'
            }`}>
              {sentimentScore > 0.1 ? 'Positive' : sentimentScore < -0.1 ? 'Negative' : 'Neutral'}
              {' '}({(sentimentScore * 100).toFixed(0)}%)
            </span>
          </div>
          {/* Sentiment bar */}
          <div className="relative h-2 bg-slate-700 rounded-full mt-2">
            <div
              className="absolute top-0 h-2 rounded-full"
              style={{
                left: `${Math.max(0, 50 + sentimentScore * 50)}%`,
                width: `${Math.abs(sentimentScore * 50)}%`,
                backgroundColor: sentimentScore > 0 ? '#34d399' : '#f87171',
                ...(sentimentScore < 0 ? { right: '50%', left: 'auto', width: `${Math.abs(sentimentScore * 50)}%` } : {}),
              }}
            />
            <div className="absolute top-0 left-1/2 w-0.5 h-2 bg-slate-500" />
          </div>
          <div className="flex justify-between text-[10px] text-slate-500 mt-1">
            <span>Bearish</span>
            <span>Neutral</span>
            <span>Bullish</span>
          </div>
          {sentimentHeadlines && sentimentHeadlines.length > 0 && (
            <div className="mt-2 space-y-0.5">
              {sentimentHeadlines.slice(0, 2).map((h, i) => (
                <p key={i} className="text-[10px] text-slate-500 italic truncate">{h}</p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Net impact summary */}
      {enabledCount > 0 && (
        <div className="bg-slate-800 rounded-lg p-3 mb-4 border border-slate-700">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Net scenario impact</span>
            <span className={`text-sm font-bold ${netLow + netHigh > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {netLow > 0 ? '+' : ''}{netLow.toFixed(1)}% to {netHigh > 0 ? '+' : ''}{netHigh.toFixed(1)}%
            </span>
          </div>
        </div>
      )}

      {/* Event toggles */}
      <div className="space-y-2">
        {events.map(event => {
          const colors = CATEGORY_COLORS[event.category] || 'border-slate-600/40 bg-slate-800/50'
          const icon = CATEGORY_ICONS[event.category] || '??'
          const isPositive = event.impactHighPct > 0 && event.impactLowPct >= 0

          return (
            <button
              key={event.id}
              onClick={() => toggleEvent(event.id)}
              className={`w-full text-left rounded-lg p-3 border transition-all ${
                event.enabled
                  ? `${colors} ring-1 ring-white/10`
                  : 'border-slate-700/50 bg-slate-800/30 opacity-60 hover:opacity-80'
              }`}
            >
              <div className="flex items-start gap-3">
                <div className={`w-8 h-8 rounded flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${
                  event.enabled ? 'bg-white/10 text-white' : 'bg-slate-700 text-slate-400'
                }`}>
                  {icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className={`text-sm font-medium truncate ${event.enabled ? 'text-white' : 'text-slate-400'}`}>
                      {event.title}
                    </p>
                    <div className={`flex-shrink-0 w-8 h-4 rounded-full transition-colors ${
                      event.enabled ? 'bg-blue-600' : 'bg-slate-600'
                    }`}>
                      <div className={`w-3.5 h-3.5 rounded-full bg-white shadow transition-transform mt-[1px] ${
                        event.enabled ? 'translate-x-[17px]' : 'translate-x-[1px]'
                      }`} />
                    </div>
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    <span className={`text-xs font-medium ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
                      {event.impactLowPct > 0 ? '+' : ''}{event.impactLowPct}% to {event.impactHighPct > 0 ? '+' : ''}{event.impactHighPct}%
                    </span>
                    <span className="text-[10px] text-slate-500">
                      {(event.impactConfidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
