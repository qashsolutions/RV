# EquipVal AI - Laptop Residual Value Predictor

ML-powered Progressive Web App that predicts residual values for B2B leased laptops in the ASEAN market. Built for leasing companies, fleet operators, and IT asset managers in Malaysia and Southeast Asia.

## The Problem

- **84.7% of laptops sell BELOW their contractual Residual Value (RV)**
- Average loss per unit: **$172.78** when selling below RV
- Contractual RV is set at ~22.8% of purchase price -- a static rule that ignores specs, market conditions, or depreciation curves
- No AI-powered residual value platform exists for ASEAN IT equipment leasing

## What This Solves

EquipVal AI replaces rule-of-thumb RV estimation with ML-powered predictions:

| Feature | Description |
|---------|-------------|
| **Market Value Prediction** | Predicts actual selling price using ensemble ML (R2=0.712) |
| **RV Prediction** | Predicts optimal contractual RV (R2=0.937) |
| **Depreciation Curves** | Interactive visual forecasts per asset configuration |
| **Fleet Portfolio View** | Portfolio-level risk assessment and exposure analysis |
| **RV Accuracy Insights** | Shows exactly how much current RV methodology is losing |

## Model Performance

Trained on **11,184 real laptop transactions** from ASEAN B2B leasing portfolio.

| Model | Market Value R2 | RV R2 |
|-------|----------------|-------|
| XGBoost | 0.7124 | 0.9390 |
| LightGBM | 0.7117 | 0.9361 |
| MDT | 0.7115 | 0.9309 |
| **Ensemble** | **0.7121** | **0.9371** |

**Top Predictive Features:** Purchase price tier, Spec score (RAM+Storage+CPU), Age, Model line (Latitude vs Precision)

## Architecture

```
Browser (PWA)                    Offline Training
+----------------------+        +----------------------+
| React + Vite + TW    |        | Python ML Pipeline   |
| - Laptop Form        |        | - features.py        |
| - Prediction Card    |        | - train.py           |
| - Depreciation Chart |        | - augment.py         |
| - Fleet Portfolio    |        | - export_onnx.py     |
| - Dashboard Insights |        |                      |
+----------------------+        | XGBoost + LightGBM   |
| MDT Tree Inference   |<-------| + MDT Ensemble       |
| (Decision Tree JSON) |  JSON  | Trained on 11,184    |
+----------------------+  export| real transactions     |
  Hosted on GitHub Pages        +----------------------+
```

## Quick Start

### Frontend (PWA)
```bash
cd frontend
npm install
npm run dev      # Dev server at localhost:5173
npm run build    # Production build
```

### ML Training
```bash
cd ml
pip install -r requirements.txt
python train.py --data ../data/LaptopPortfolio.xlsx
```

## Project Structure

```
RV/
├── frontend/              # React PWA
│   ├── src/
│   │   ├── App.tsx        # Main app with 3 tabs
│   │   ├── predictor.ts   # Browser-side ML inference (MDT)
│   │   └── components/    # LaptopForm, PredictionCard, DepreciationChart,
│   │                      # Dashboard, FleetView
│   └── public/models/     # Exported model files (JSON)
├── ml/                    # Python ML pipeline
│   ├── train.py           # Main training (XGBoost+LightGBM+MDT ensemble)
│   ├── features.py        # Feature engineering (20 features)
│   ├── augment.py         # Synthetic data augmentation
│   ├── export_onnx.py     # ONNX export for production
│   └── evaluate.py        # Model evaluation
├── data/                  # Training data
│   └── LaptopPortfolio.xlsx  # 11,184 real transactions
└── docs/
```

## Key Insights from Data

- **RV Overpricing**: 84.7% of laptops sell below contractual RV
- **Avg Loss**: $172.78 per unit when below RV, $121.69 mean gap
- **Price is King**: Purchase price tier is the #1 predictor of residual value
- **Specs Matter**: Composite spec score (RAM+Storage+CPU Gen+CPU Tier) is #2
- **Age Curve**: Non-linear -- first 2 years see steepest depreciation

## Phase II Roadmap

- Gamified AI Credit Scoring for equipment lessees
- Multi-brand data ingestion (currently 99.6% Dell)
- Real-time market feed integration
- API for ERP/lease management system integration

## Market Context

- ASEAN construction equipment rental: USD 5.05B (2025) -> USD 7.21B (2030)
- SEA financial leasing: USD 3.43B (2024), 15% CAGR
- Zero dedicated AI residual value platforms in the region
