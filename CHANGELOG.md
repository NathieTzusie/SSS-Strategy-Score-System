# Changelog

## v1.1.0 — Stable (2026-05-15)

### Added
- **Strategy Enable Score pipeline** — 4-factor scoring (regime edge + recent health + MC stability + risk control)
- **Regime Performance Matrix** — 14 metrics × 12 strategy/regime combinations
- **Monte Carlo validation** — Bootstrap simulation with tail risk analysis
- **Enable Score** — 4 sub-scores + 3 penalty multipliers + risk categorization
- **Label Quality tool** — Session backfill + structure_state + regime_snapshot_id normalization
- **CoinGlass fetch/cache layer** — Live/mock/dry-run modes, 6 endpoints, BTC+ETH
- **Label Enrichment engine** — Lookahead-safe OI/Funding/Taker/ETF/Macro state backfill
- **Partial Context Report** — INFORMATIONAL ONLY, 6 field distributions × 12 groups
- **Data Quality Monitor** — 6 dimensions: Field Coverage, Enrichment, CoinGlass Fetch, Partial Context, Feature Gates, Baseline
- **Release Candidate validation** — 6 CLI verification, 22/22 output inventory
- **User Acceptance Review** — 7 categories × checklist format (PASS/WARN/FAIL)

### Changed
- `config.py`: Added PartialContextConfig, DataQualityMonitorConfig, MonitorInputsConfig, MonitorThresholdsConfig, FeatureGatesConfig, + parsers
- `coinglass_fetch.py`: Added --symbols/--endpoints/--output-suffix CLI arguments; endpoint-specific interval support
- `label_enrichment.py`: _find_file supports glob wildcard matching
- `label_quality.py`: Added --input/--output-dir CLI overrides
- README.md: Updated with stable workflow, Partial Context Report, Data Quality Monitor sections

### Validated
- 230/230 tests passed
- Baseline stable: 12/12 enable_score delta = 0.0000000000, status_changed = 0
- Status distribution: 强开启 0 / 中等开启 3 / 弱开启 3 / 禁用 6
- Enrichment regression: Score delta=0, Performance identical, Monte Carlo identical
- CoinGlass live fetch: 8/9 endpoints success (financial_calendar 401 under Hobbyist)
- OI 97.3% / Funding 97.5% / ETF 100% / Macro 100% trade coverage
- 22/22 output files verified

### Known Limitations
- **orderflow_state**: 14% coverage (Hobbyist taker 4h limit=365 → ~60 days)
- **Financial Calendar**: 401 under Hobbyist plan — macro_state event_risk labels unavailable
- **macro_state**: 32.8% fallback neutral (not true event coverage)
- **Enriched CSV**: Not set as default input (no scoring benefit, delta=0)
- **No live realtime monitoring**: Manual or cron-driven execution only

### Blocked Features
- **Automatic Regime Classifier** — orderflow 86% unknown, macro true event unavailable
- **Full Market Opportunity Score** — Requires orderflow + calendar + near-realtime data
