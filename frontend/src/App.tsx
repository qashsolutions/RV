import React, { useState, useEffect, useCallback } from 'react'
import { loadModels, predict, predictDepreciationCurve, getActiveScenarioEvents, getSentimentData, DEFAULT_FI_PARAMS, type LaptopInput, type PredictionResult, type ScenarioEvent, type FIParams } from './predictor'
import { PredictionCard } from './components/PredictionCard'
import { DepreciationChart } from './components/DepreciationChart'
import { LaptopForm } from './components/LaptopForm'
import { Dashboard } from './components/Dashboard'
import { FleetView } from './components/FleetView'
import { ScenarioPanel } from './components/ScenarioPanel'
import { FIParamsPanel } from './components/FIParamsPanel'
import { ThemeToggle } from './components/ThemeToggle'

type Tab = 'predict' | 'dashboard' | 'fleet'
type Theme = 'dark' | 'light'

export default function App() {
  const [modelsLoaded, setModelsLoaded] = useState(false)
  const [activeTab, setActiveTab] = useState<Tab>('predict')
  const [prediction, setPrediction] = useState<PredictionResult | null>(null)
  const [depCurve, setDepCurve] = useState<any[]>([])
  const [currentInput, setCurrentInput] = useState<LaptopInput | null>(null)
  const [precomputed, setPrecomputed] = useState<any>(null)

  // Theme state (persisted in localStorage)
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('equipval-theme')
    return (saved === 'light' || saved === 'dark') ? saved : 'dark'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('equipval-theme', theme)
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark')
  }, [])

  // v2: scenario & FI state
  const [scenarioEvents, setScenarioEvents] = useState<ScenarioEvent[]>([])
  const [fiParams, setFIParams] = useState<FIParams>(DEFAULT_FI_PARAMS)
  const [showFI, setShowFI] = useState(false)

  useEffect(() => {
    const base = import.meta.env.BASE_URL + 'models'
    Promise.all([
      loadModels(base),
      fetch(`${base}/precomputed.json`).then(r => r.json()),
    ]).then(([_, pc]) => {
      setPrecomputed(pc)
      setModelsLoaded(true)
      setScenarioEvents(getActiveScenarioEvents())
    }).catch(err => {
      console.error('Failed to load models:', err)
      setModelsLoaded(true)
      setScenarioEvents(getActiveScenarioEvents())
    })
  }, [])

  const handlePredict = useCallback((input: LaptopInput) => {
    try {
      const fiToUse = showFI ? fiParams : undefined
      const result = predict(input, scenarioEvents, fiToUse)
      setPrediction(result)
      setCurrentInput(input)
      const curve = predictDepreciationCurve(input, undefined, scenarioEvents, fiToUse)
      setDepCurve(curve)
    } catch (err) {
      console.error('Prediction error:', err)
    }
  }, [scenarioEvents, fiParams, showFI])

  // Re-predict when scenarios toggle
  const handleScenarioChange = useCallback((events: ScenarioEvent[]) => {
    setScenarioEvents(events)
    if (currentInput) {
      try {
        const fiToUse = showFI ? fiParams : undefined
        const result = predict(currentInput, events, fiToUse)
        setPrediction(result)
        const curve = predictDepreciationCurve(currentInput, undefined, events, fiToUse)
        setDepCurve(curve)
      } catch (err) {
        console.error('Scenario prediction error:', err)
      }
    }
  }, [currentInput, fiParams, showFI])

  // Re-predict when FI params change
  const handleFIChange = useCallback((fi: FIParams) => {
    setFIParams(fi)
    if (currentInput) {
      try {
        const result = predict(currentInput, scenarioEvents, fi)
        setPrediction(result)
        const curve = predictDepreciationCurve(currentInput, undefined, scenarioEvents, fi)
        setDepCurve(curve)
      } catch (err) {
        console.error('FI prediction error:', err)
      }
    }
  }, [currentInput, scenarioEvents])

  const sentiment = getSentimentData()

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-slate-700 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-blue-700 flex items-center justify-center font-bold text-sm">RV</div>
            <div>
              <h1 className="text-lg font-bold text-white leading-tight">EquipVal AI</h1>
              <p className="text-xs text-slate-400">Laptop Residual Value Predictor</p>
            </div>
          </div>
          <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-0.5">
            {([
              ['predict', 'Predict'],
              ['dashboard', 'Portfolio Analysis'],
              ['fleet', 'Fleet'],
            ] as [Tab, string][]).map(([tab, label]) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? 'bg-blue-700 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <span className={`tag ${modelsLoaded ? 'tag-green' : 'tag-yellow'}`}>
              {modelsLoaded ? 'Models Ready' : 'Loading...'}
            </span>
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {activeTab === 'predict' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left column: Form + Scenarios + FI */}
            <div className="space-y-6">
              <LaptopForm onSubmit={handlePredict} disabled={!modelsLoaded} />

              {/* FI toggle */}
              <button
                onClick={() => setShowFI(!showFI)}
                className="w-full text-left text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
              >
                <svg className={`w-3 h-3 transition-transform ${showFI ? 'rotate-90' : ''}`} fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                </svg>
                {showFI ? 'Hide' : 'Show'} financial institution parameters
              </button>
              {showFI && <FIParamsPanel params={fiParams} onChange={handleFIChange} />}

              <ScenarioPanel
                events={scenarioEvents}
                onChange={handleScenarioChange}
                sentimentScore={sentiment?.score}
                sentimentConfidence={sentiment?.confidence}
                sentimentHeadlines={sentiment?.headlines}
              />
            </div>

            {/* Right columns: Results (spans 2 cols) */}
            <div className="lg:col-span-2 space-y-6 fade-in">
              {prediction && currentInput ? (
                <>
                  <PredictionCard prediction={prediction} input={currentInput} depCurve={depCurve} />
                  <DepreciationChart data={depCurve} purchasePrice={currentInput.purchasePrice} />
                </>
              ) : (
                <div className="card flex flex-col items-center justify-center min-h-[400px] text-slate-500">
                  <svg className="w-16 h-16 mb-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="text-lg font-medium">Enter laptop details</p>
                  <p className="text-sm mt-1">Fill the form to get AI-powered residual value predictions</p>
                  <p className="text-xs text-slate-600 mt-3">Toggle market scenarios on the left to see how events impact price</p>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'dashboard' && (
          <Dashboard precomputed={precomputed} />
        )}

        {activeTab === 'fleet' && (
          <FleetView onPredict={handlePredict} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 mt-12">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between text-xs text-slate-500">
          <span>EquipVal AI - ASEAN B2B Laptop Leasing Intelligence</span>
          <span>Model: XGBoost + LightGBM + MDT Ensemble | R2: 0.937</span>
        </div>
      </footer>
    </div>
  )
}
