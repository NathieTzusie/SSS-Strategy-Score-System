# TradingView Conversion Report

- input_path: `data/2026-05-15/BB_Alpha_BINANCE_ETHUSDT.P_2026-05-15_6a53f.csv`
- output_path: `data/ETH_BAW_2025_01_2026_05.csv`
- detected_format: `paired`
- raw_rows: 554
- converted_trades: 277
- strategy_name: `ETH_BAW`
- symbol: `ETHUSDT`
- regime: `unknown`
- risk_usd: `200.0`

This converter does not infer market regime or orderflow labels.
Missing state fields are filled with `unknown` for downstream label tools.

## Label Quality Auto-Fix

- enabled: `False`
- cleaned_output_path: `data/ETH_BAW_2025_01_2026_05_cleaned.csv`
- session_fixed: 277
- structure_state_fixed: 0
- snapshot_normalized: 277
- trade_id_deduplicated: 0

For multiple converted TradingView files, run the standalone label quality tool on all files together before scoring.

## Label Enrichment Auto-Fill

- enabled: `True`
- processed_dir: `data/external/coinglass/processed`
- enriched_output_path: `data/ETH_BAW_2025_01_2026_05_enriched.csv`
- enrichment_audit_report_path: `data/ETH_BAW_2025_01_2026_05_enrichment_audit_report.md`
- unknown_symbols: 0
- oi_state_filled: 64
- funding_state_filled: 66
- orderflow_state_filled: 64
- etf_flow_state_filled: 66
- macro_state_filled: 277

Enrichment uses already processed external market data only; it does not fetch live API data.

## Config Input Update

- enabled: `True`
- config_path: `config.yaml`
- input_path_added: `data/ETH_BAW_2025_01_2026_05_enriched.csv`
- changed: `True`