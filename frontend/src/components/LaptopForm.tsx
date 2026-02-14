import React, { useState } from 'react'
import type { LaptopInput } from '../predictor'

interface Props {
  onSubmit: (input: LaptopInput) => void
  disabled: boolean
}

const BRANDS = ['Dell', 'Lenovo', 'HP', 'Apple', 'ASUS', 'Acer', 'Microsoft', 'MSI', 'Samsung', 'Fujitsu', 'Huawei', 'Xiaomi']

const MODEL_LINES = [
  { value: 'business_standard', label: 'Business (Latitude/ThinkPad/EliteBook)' },
  { value: 'workstation', label: 'Workstation (Precision/ZBook)' },
  { value: 'premium', label: 'Premium (XPS/MacBook/Surface)' },
  { value: 'sme', label: 'SME (Vostro/ProBook)' },
  { value: 'consumer', label: 'Consumer (Inspiron)' },
]

const PROCESSORS = [
  { value: '3', tier: 3, label: 'Intel Core i5' },
  { value: '4', tier: 4, label: 'Intel Core i7' },
  { value: '5', tier: 5, label: 'Intel Core i9' },
  { value: '5x', tier: 5, label: 'Intel Xeon', isXeon: true },
]

const PROC_GENS = [
  { value: 14, label: '14th Gen (2024)' },
  { value: 13, label: '13th Gen (2023)' },
  { value: 12, label: '12th Gen (2022)' },
  { value: 11, label: '11th Gen (2021)' },
  { value: 10, label: '10th Gen (2020)' },
]

const RAM_OPTIONS = [4, 8, 16, 32, 64, 128]
const STORAGE_OPTIONS = [0, 128, 256, 512, 1000, 2000]
const SCREEN_OPTIONS = [12.3, 13.3, 14.0, 15.6, 17.3]
const TERM_OPTIONS = [12, 24, 36, 48]

export function LaptopForm({ onSubmit, disabled }: Props) {
  const [brand, setBrand] = useState('Dell')
  const [modelLine, setModelLine] = useState('business_standard')
  const [modelTier, setModelTier] = useState(7)
  const [processor, setProcessor] = useState('4')
  const [processorGen, setProcessorGen] = useState(11)
  const [ram, setRam] = useState(16)
  const [storage, setStorage] = useState(512)
  const [screen, setScreen] = useState(14.0)
  const [price, setPrice] = useState(2000)
  const [term, setTerm] = useState(36)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const proc = PROCESSORS.find(p => p.value === processor)
    onSubmit({
      brand,
      modelLine,
      modelTier,
      processorGen,
      processorTier: proc?.tier ?? 4,
      isXeon: proc?.isXeon ?? false,
      ramGb: ram,
      storageGb: storage,
      hasSsd: storage > 0,
      screenInches: screen,
      purchasePrice: price,
      leaseDurationMonths: term,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="card space-y-4">
      <h2 className="text-lg font-semibold text-white mb-2">Laptop Configuration</h2>

      <div className="grid grid-cols-2 gap-4">
        {/* Brand */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Brand</label>
          <select value={brand} onChange={e => setBrand(e.target.value)} className="w-full">
            {BRANDS.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>

        {/* Model Line */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Product Line</label>
          <select value={modelLine} onChange={e => setModelLine(e.target.value)} className="w-full">
            {MODEL_LINES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>

        {/* Model Tier */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Model Series (e.g. 5000/7000)</label>
          <select value={modelTier} onChange={e => setModelTier(Number(e.target.value))} className="w-full">
            {[3, 5, 7, 9].map(t => (
              <option key={t} value={t}>{t}000 Series</option>
            ))}
          </select>
        </div>

        {/* Processor */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Processor</label>
          <select value={processor} onChange={e => setProcessor(e.target.value)} className="w-full">
            {PROCESSORS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>

        {/* Processor Gen */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Processor Generation</label>
          <select value={processorGen} onChange={e => setProcessorGen(Number(e.target.value))} className="w-full">
            {PROC_GENS.map(g => <option key={g.value} value={g.value}>{g.label}</option>)}
          </select>
        </div>

        {/* RAM */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">RAM (GB)</label>
          <select value={ram} onChange={e => setRam(Number(e.target.value))} className="w-full">
            {RAM_OPTIONS.map(r => <option key={r} value={r}>{r} GB</option>)}
          </select>
        </div>

        {/* Storage */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Storage (GB)</label>
          <select value={storage} onChange={e => setStorage(Number(e.target.value))} className="w-full">
            {STORAGE_OPTIONS.map(s => (
              <option key={s} value={s}>{s === 0 ? 'No SSD' : s >= 1000 ? `${s/1000} TB` : `${s} GB`}</option>
            ))}
          </select>
        </div>

        {/* Screen */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Display Size</label>
          <select value={screen} onChange={e => setScreen(Number(e.target.value))} className="w-full">
            {SCREEN_OPTIONS.map(s => <option key={s} value={s}>{s}"</option>)}
          </select>
        </div>

        {/* Purchase Price */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Purchase Price (USD)</label>
          <input
            type="number"
            value={price}
            onChange={e => setPrice(Number(e.target.value))}
            min={100}
            max={15000}
            step={50}
            className="w-full"
          />
        </div>

        {/* Lease Term */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Lease Term (Months)</label>
          <select value={term} onChange={e => setTerm(Number(e.target.value))} className="w-full">
            {TERM_OPTIONS.map(t => <option key={t} value={t}>{t} months ({t/12} yr)</option>)}
          </select>
        </div>
      </div>

      <button type="submit" disabled={disabled} className="btn-primary w-full mt-4 disabled:opacity-50">
        {disabled ? 'Loading Models...' : 'Predict Residual Value'}
      </button>
    </form>
  )
}
