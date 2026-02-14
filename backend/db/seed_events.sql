-- ============================================================
-- Seed: Market event templates with historical impact ranges
-- These are research-backed defaults that the scenario engine
-- uses when no live data is available.
-- ============================================================

INSERT INTO market_events (title, description, category, status,
    impact_low_pct, impact_high_pct, impact_confidence,
    affected_brands, affected_segments, source_type, decay_months)
VALUES

-- Competitor launches
('Apple launches new MacBook',
 'New MacBook generation launch typically pulls enterprise buyers toward Apple, reducing demand for competing Windows laptops in the used market.',
 'competitor_launch', 'confirmed',
 -8.00, -3.00, 0.75,
 '{Dell,Lenovo,HP}', '{premium,business_standard}',
 'analyst', 6),

('Lenovo ThinkPad refresh',
 'Major ThinkPad line refresh increases supply of previous-gen used ThinkPads, creating indirect pricing pressure across business laptop segment.',
 'competitor_launch', 'confirmed',
 -4.00, -1.50, 0.70,
 '{Dell,HP}', '{business_standard}',
 'analyst', 4),

-- Model discontinuation
('Dell discontinues laptop line',
 'Discontinued models lose parts/support pipeline, reducing buyer confidence. Short-term scarcity bump fades as support concerns dominate.',
 'model_discontinuation', 'confirmed',
 -12.00, -5.00, 0.80,
 '{Dell}', '{}',
 'analyst', 12),

('Dell refreshes Latitude line',
 'New Latitude generation makes previous generation immediately older-spec, accelerating depreciation of current fleet.',
 'model_discontinuation', 'confirmed',
 -6.00, -2.00, 0.75,
 '{Dell}', '{business_standard}',
 'analyst', 6),

-- Supply chain
('Semiconductor shortage',
 'Chip supply constraints reduce new laptop availability, increasing used laptop demand and resale prices.',
 'supply_chain', 'confirmed',
 2.00, 8.00, 0.70,
 '{}', '{}',
 'analyst', 9),

('Logistics disruption (shipping/ports)',
 'Shipping delays increase lead times for new equipment, temporarily boosting used laptop prices in ASEAN market.',
 'supply_chain', 'confirmed',
 1.50, 5.00, 0.65,
 '{}', '{}',
 'analyst', 4),

-- Macro-economic
('Regional recession / demand slowdown',
 'Economic downturn reduces corporate IT budgets and used laptop demand across all segments.',
 'macro_economic', 'confirmed',
 -15.00, -8.00, 0.75,
 '{}', '{}',
 'analyst', 12),

('USD strengthens significantly vs SGD',
 'Stronger USD makes USD-priced used laptops more expensive in local currency, reducing ASEAN buyer demand.',
 'macro_economic', 'confirmed',
 -6.00, -2.00, 0.70,
 '{}', '{}',
 'analyst', 6),

('USD weakens significantly vs SGD',
 'Weaker USD makes USD-priced used laptops cheaper in local currency, boosting ASEAN buyer demand.',
 'macro_economic', 'confirmed',
 2.00, 5.00, 0.70,
 '{}', '{}',
 'analyst', 6),

-- Regulatory
('New e-waste regulation in ASEAN',
 'Stricter disposal rules increase compliance costs for used equipment resale, reducing net proceeds.',
 'regulatory', 'confirmed',
 -4.00, -1.00, 0.60,
 '{}', '{}',
 'analyst', 12),

('Import tariff change on electronics',
 'Tariff increases on new imports boost used laptop demand as buyers seek domestic alternatives.',
 'regulatory', 'confirmed',
 1.00, 4.00, 0.60,
 '{}', '{}',
 'analyst', 8),

-- Technology shifts
('DDR5 / new memory standard adoption',
 'New memory standard makes DDR4 laptops feel outdated faster, accelerating depreciation of current fleet.',
 'technology_shift', 'confirmed',
 -5.00, -2.00, 0.65,
 '{}', '{}',
 'analyst', 12),

('ARM-based Windows laptops gain traction',
 'If ARM laptops prove viable for enterprise, x86 used laptop demand may soften over time.',
 'technology_shift', 'confirmed',
 -7.00, -2.00, 0.55,
 '{}', '{}',
 'analyst', 18);
