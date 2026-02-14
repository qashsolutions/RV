-- ============================================================
-- EquipVal AI  —  Supabase PostgreSQL Schema
-- Migration 001: Core tables for sentiment, events, macro,
--                FI configuration, and prediction history
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";          -- fuzzy text search for events

-- ============================================================
-- 1. SENTIMENT SCORES
--    Daily sentiment index from news/social for the used
--    laptop resale market, per brand.
-- ============================================================
CREATE TABLE sentiment_scores (
    id            UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    scored_date   DATE NOT NULL,
    brand         TEXT NOT NULL DEFAULT 'dell',      -- brand this score applies to
    source        TEXT NOT NULL,                      -- 'news', 'social', 'combined'
    score         NUMERIC(5,4) NOT NULL,              -- -1.0000 to +1.0000
    confidence    NUMERIC(5,4) NOT NULL DEFAULT 0.5,  -- model confidence in the score
    article_count INT NOT NULL DEFAULT 0,             -- number of articles analyzed
    sample_headlines TEXT[],                           -- top 3 representative headlines
    raw_payload   JSONB,                              -- full model output for debugging
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_sentiment_date_brand_source
        UNIQUE (scored_date, brand, source)
);

CREATE INDEX idx_sentiment_date   ON sentiment_scores (scored_date DESC);
CREATE INDEX idx_sentiment_brand  ON sentiment_scores (brand);

-- ============================================================
-- 2. MARKET EVENTS
--    Catalog of events that impact laptop resale values.
--    Each event has a predefined impact range + confidence.
-- ============================================================
CREATE TYPE event_category AS ENUM (
    'competitor_launch',       -- Apple/Lenovo launches competing product
    'model_discontinuation',   -- Dell discontinues a line
    'supply_chain',            -- chip shortage, logistics disruption
    'macro_economic',          -- recession, currency shock, tariff
    'regulatory',              -- import ban, e-waste law, tariff change
    'technology_shift'         -- new standard (DDR5, WiFi 7, ARM transition)
);

CREATE TYPE event_status AS ENUM (
    'detected',      -- auto-detected from news, not yet verified
    'confirmed',     -- manually verified by analyst
    'active',        -- currently impacting market
    'expired'        -- impact window has passed
);

CREATE TABLE market_events (
    id                UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    title             TEXT NOT NULL,
    description       TEXT,
    category          event_category NOT NULL,
    status            event_status NOT NULL DEFAULT 'detected',

    -- Impact modeling
    impact_low_pct    NUMERIC(5,2) NOT NULL,          -- e.g. -12.00 means -12%
    impact_high_pct   NUMERIC(5,2) NOT NULL,          -- e.g. -5.00  means -5%
    impact_confidence NUMERIC(5,4) NOT NULL DEFAULT 0.7, -- P(impact in range)
    affected_brands   TEXT[] DEFAULT '{}',             -- empty = all brands
    affected_segments TEXT[] DEFAULT '{}',             -- empty = all segments

    -- Time window
    detected_at       TIMESTAMPTZ DEFAULT NOW(),
    effective_from    DATE,
    effective_until    DATE,
    decay_months      INT DEFAULT 6,                   -- months for impact to halve

    -- Provenance
    source_url        TEXT,
    source_type       TEXT,                             -- 'news', 'analyst', 'manual'
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_events_status    ON market_events (status);
CREATE INDEX idx_events_category  ON market_events (category);
CREATE INDEX idx_events_effective ON market_events (effective_from, effective_until);

-- ============================================================
-- 3. MACRO INDICATORS
--    Time series of FRED economic data used as model features.
-- ============================================================
CREATE TABLE macro_indicators (
    id              UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    indicator_date  DATE NOT NULL,
    series_id       TEXT NOT NULL,                     -- FRED series ID

    -- Values
    value           NUMERIC(12,4) NOT NULL,
    yoy_change      NUMERIC(8,6),                      -- year-over-year % change
    mom_change      NUMERIC(8,6),                      -- month-over-month % change

    -- Metadata
    source          TEXT DEFAULT 'fred',
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_macro_date_series
        UNIQUE (indicator_date, series_id)
);

CREATE INDEX idx_macro_date   ON macro_indicators (indicator_date DESC);
CREATE INDEX idx_macro_series ON macro_indicators (series_id);

-- Pre-seed the FRED series we track
COMMENT ON TABLE macro_indicators IS
    'Tracked series: SGPCPIALLMINMEI (Singapore CPI), '
    'DEXSIUS (USD/SGD rate), PCU33443344 (Semiconductor PPI)';

-- ============================================================
-- 4. FI CONFIGURATIONS
--    Per-institution settings for financial institutions
--    using the platform.
-- ============================================================
CREATE TABLE fi_profiles (
    id                UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name              TEXT NOT NULL,
    short_code        TEXT UNIQUE NOT NULL,              -- e.g. 'DBS', 'OCBC'

    -- Financial parameters
    discount_rate     NUMERIC(6,4) DEFAULT 0.0500,       -- 5.00% default
    disposal_cost_pct NUMERIC(6,4) DEFAULT 0.0300,       -- 3.00% of sale price
    tax_rate          NUMERIC(6,4) DEFAULT 0.1700,       -- 17.00% (SG corporate)
    insurance_pct     NUMERIC(6,4) DEFAULT 0.0100,       -- 1.00% annual premium
    target_margin_pct NUMERIC(6,4) DEFAULT 0.0200,       -- 2.00% min profit margin
    holding_cost_monthly NUMERIC(10,2) DEFAULT 15.00,    -- per-unit warehousing $/month

    -- Risk preferences
    risk_tolerance    TEXT DEFAULT 'moderate',            -- conservative, moderate, aggressive
    ci_level_pct      INT DEFAULT 80,                    -- preferred CI: 80 or 90
    max_lease_months  INT DEFAULT 48,

    -- Metadata
    currency          TEXT DEFAULT 'USD',
    region            TEXT DEFAULT 'ASEAN',
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 5. PREDICTION HISTORY
--    Log of predictions made, for audit trail and retraining.
-- ============================================================
CREATE TABLE prediction_log (
    id                 UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    fi_profile_id      UUID REFERENCES fi_profiles(id),

    -- Input snapshot
    input_payload      JSONB NOT NULL,                    -- full LaptopInput

    -- Model output
    market_ratio       NUMERIC(6,4) NOT NULL,
    market_value       NUMERIC(10,2) NOT NULL,
    rv_ratio           NUMERIC(6,4),
    rv_value           NUMERIC(10,2),
    ci_low_80          NUMERIC(10,2),
    ci_high_80         NUMERIC(10,2),
    ci_low_90          NUMERIC(10,2),
    ci_high_90         NUMERIC(10,2),
    confidence         NUMERIC(5,4),

    -- Scenario adjustments applied
    active_events      UUID[],                            -- market_events IDs applied
    scenario_adjustment NUMERIC(6,4) DEFAULT 0,           -- net % adjustment from events
    sentiment_score    NUMERIC(5,4),                      -- sentiment at time of prediction

    -- FI-specific outputs
    net_proceeds       NUMERIC(10,2),                     -- after disposal cost + tax
    npv                NUMERIC(10,2),                     -- net present value
    recommendation     TEXT,

    -- Model version
    model_version      TEXT,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pred_fi      ON prediction_log (fi_profile_id);
CREATE INDEX idx_pred_created ON prediction_log (created_at DESC);

-- ============================================================
-- 6. MODEL VERSIONS
--    Track each retrained model for reproducibility.
-- ============================================================
CREATE TABLE model_versions (
    id               UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    version_tag      TEXT UNIQUE NOT NULL,               -- e.g. 'v2.1.0-20260214'
    training_rows    INT NOT NULL,
    market_r2        NUMERIC(6,4),
    rv_r2            NUMERIC(6,4),
    market_mae       NUMERIC(6,4),
    rv_mae           NUMERIC(6,4),
    features_used    TEXT[],
    training_config  JSONB,                               -- hyperparams snapshot
    artifact_path    TEXT,                                 -- path in repo or release URL
    is_active        BOOLEAN DEFAULT FALSE,
    trained_at       TIMESTAMPTZ DEFAULT NOW(),
    promoted_at      TIMESTAMPTZ
);

-- Only one active model at a time
CREATE UNIQUE INDEX idx_model_active
    ON model_versions (is_active) WHERE is_active = TRUE;

-- ============================================================
-- 7. ROW-LEVEL SECURITY (Supabase)
--    Each FI can only see their own predictions/config.
-- ============================================================
ALTER TABLE fi_profiles       ENABLE ROW LEVEL SECURITY;
ALTER TABLE prediction_log    ENABLE ROW LEVEL SECURITY;

-- Public read for market data (sentiment, events, macro)
ALTER TABLE sentiment_scores  ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE macro_indicators  ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_versions    ENABLE ROW LEVEL SECURITY;

-- Allow anonymous read on market data
CREATE POLICY "Public read sentiment"
    ON sentiment_scores FOR SELECT USING (true);

CREATE POLICY "Public read events"
    ON market_events FOR SELECT USING (true);

CREATE POLICY "Public read macro"
    ON macro_indicators FOR SELECT USING (true);

CREATE POLICY "Public read model versions"
    ON model_versions FOR SELECT USING (true);

-- Service role (GitHub Actions) can write everything
-- (Supabase service_role key bypasses RLS by default)
