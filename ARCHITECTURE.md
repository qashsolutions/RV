# Architecture & Technical Design

## System Overview

EquipVal AI is a **fully static PWA** — no backend servers required. The ML model is trained offline in Python, exported to ONNX format, and runs entirely in the browser via ONNX Runtime Web.

```
┌──────────────────────────────────────────────────────────┐
│                    GitHub Pages (Static Host)             │
│  ┌────────────────────────────────────────────────────┐  │
│  │              React PWA (Vite Build)                 │  │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────────────┐ │  │
│  │  │ Equipment │ │Prediction│ │  Fleet Portfolio   │ │  │
│  │  │Input Form │ │Dashboard │ │     Analytics      │ │  │
│  │  └────┬─────┘ └────┬─────┘ └────────┬───────────┘ │  │
│  │       │             │                │              │  │
│  │  ┌────▼─────────────▼────────────────▼───────────┐ │  │
│  │  │         Feature Engineering (JS)               │ │  │
│  │  │  • Encodes categoricals (brand, type, country) │ │  │
│  │  │  • Computes derived features (age, util rate)  │ │  │
│  │  │  • Normalizes numeric inputs                   │ │  │
│  │  └────────────────────┬──────────────────────────┘ │  │
│  │                       │                             │  │
│  │  ┌────────────────────▼──────────────────────────┐ │  │
│  │  │        ONNX Runtime Web (Inference)            │ │  │
│  │  │  • Loads .onnx model from /public/models/      │ │  │
│  │  │  • Runs prediction in WebAssembly              │ │  │
│  │  │  • Returns residual value + confidence         │ │  │
│  │  └───────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘

OFFLINE (Development / Training)
┌──────────────────────────────────────────────────────────┐
│                    Python ML Pipeline                     │
│  ┌──────────┐  ┌───────────┐  ┌────────────┐  ┌──────┐ │
│  │  Excel   │→ │  Feature   │→ │  Train     │→ │Export│ │
│  │  Data    │  │Engineering │  │ XGB/LGBM/  │  │ ONNX │ │
│  │  (.xlsx) │  │  (Pandas)  │  │  Ensemble  │  │      │ │
│  └──────────┘  └───────────┘  └────────────┘  └──────┘ │
└──────────────────────────────────────────────────────────┘
```

## ML Pipeline Design

### Feature Engineering

Features are computed identically in Python (training) and JavaScript (inference):

```
Raw Input → Derived Features → Encoded Features → Model Input
```

**Derived Features:**
| Feature | Formula | Rationale |
|---------|---------|-----------|
| `age_years` | `sale_year - manufacture_year` | Primary depreciation driver |
| `annual_hours` | `operating_hours / age_years` | Usage intensity proxy |
| `utilization_rate` | `annual_hours / 2000` | Normalized usage (2000h = full year) |
| `age_hours_interaction` | `age_years × operating_hours` | Combined wear factor |
| `brand_tier` | mapping table | Premium/Mid/Economy brand class |
| `brand_origin_factor` | mapping table | Japan=1.0, Europe=0.95, Korea=0.85, China=0.70 |
| `climate_factor` | mapping table | Tropical degradation multiplier |
| `retention_ratio` | `sale_price / purchase_price` | Target variable (what we predict) |

### Model Architecture

**Ensemble of 3 models** (proven best in literature for equipment valuation):

1. **XGBoost** — Gradient boosted trees, strong on tabular data
2. **LightGBM** — Faster training, handles categoricals natively
3. **Model Decision Tree (MDT)** — Interpretable, highest accuracy per research (R²=0.9284)

**Ensemble Strategy:**
- Weighted average of predictions
- Weights determined by validation performance
- Confidence interval from prediction variance across models

### ONNX Export

The trained ensemble is exported to ONNX format:
- Each model → individual ONNX file
- Ensemble weights → JSON config
- Feature encoding maps → JSON config
- Total model size target: <5MB (fast PWA load)

## Frontend Architecture

### Component Structure

```
src/
├── App.tsx                    # Main app shell + routing
├── components/
│   ├── EquipmentForm/         # Input form for equipment details
│   │   ├── EquipmentForm.tsx
│   │   ├── BrandSelector.tsx
│   │   └── ConditionSlider.tsx
│   ├── PredictionResult/      # Prediction display
│   │   ├── PredictionCard.tsx
│   │   ├── ConfidenceGauge.tsx
│   │   └── DepreciationChart.tsx
│   ├── FleetView/             # Portfolio-level analytics
│   │   ├── FleetDashboard.tsx
│   │   └── FleetTable.tsx
│   ├── OptimalTiming/         # When-to-sell recommendation
│   │   └── TimingAdvisor.tsx
│   └── common/                # Shared UI components
│       ├── Header.tsx
│       ├── Layout.tsx
│       └── LoadingSpinner.tsx
├── models/
│   ├── ModelLoader.ts         # ONNX model loading + caching
│   ├── Predictor.ts           # Run inference, compute ensemble
│   └── FeatureEncoder.ts      # JS-side feature engineering
├── utils/
│   ├── constants.ts           # Brand mappings, equipment types
│   ├── currency.ts            # MYR/USD conversion
│   └── formatting.ts         # Number/date formatting
├── hooks/
│   ├── useModel.ts            # React hook for model loading
│   └── usePrediction.ts      # React hook for running predictions
├── data/
│   └── types.ts               # TypeScript type definitions
└── sw.ts                      # Service worker (Workbox)
```

### PWA Configuration

- **Service Worker**: Workbox with precache for app shell + ONNX models
- **Manifest**: Standalone display, ASEAN-themed branding
- **Offline**: Full offline capability after first load
- **Install**: Add-to-homescreen prompt for mobile B2B users

### State Management

- React Context for global state (loaded model, fleet data)
- Local state for form inputs
- IndexedDB for persisting fleet equipment list (offline)

## Phase II Foundation (Built Now)

### Credit Scoring Data Model Extensions

The equipment data types include optional fields that map to credit scoring:

```typescript
// Built into the data model now, activated in Phase II
interface LesseeProfile {
  companySize: 'Micro' | 'Small' | 'Medium' | 'Large';
  industry: string;
  yearsInBusiness: number;
  fleetSize: number;
  paymentHistory?: PaymentRecord[];  // Phase II
  creditScore?: number;              // Phase II - gamified
}
```

### Gamification Hooks

- Achievement/badge system types defined
- Score progression framework
- Leaderboard data structures
- All activated in Phase II, but interfaces defined now

## Deployment

### GitHub Pages

```bash
# Build frontend
cd frontend && npm run build

# Deploy to GitHub Pages
# Configured via GitHub Actions or manual push to gh-pages branch
```

### Model Update Flow

1. New data arrives → add to `data/`
2. Run `python ml/train.py` → produces new ONNX model
3. Copy model to `frontend/public/models/`
4. Rebuild and redeploy frontend
5. PWA auto-updates via service worker
