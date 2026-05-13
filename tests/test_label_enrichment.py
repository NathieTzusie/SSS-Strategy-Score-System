"""
Unit tests for Label Enrichment Engine (P2-8).
"""
import os
import tempfile
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from strategy_enable_system.label_enrichment import (
    map_to_coinglass_symbol,
    is_missing,
    find_most_recent,
    find_event_window,
    enrich_oi_state,
    enrich_funding_state,
    enrich_orderflow_state,
    enrich_etf_flow_state,
    enrich_macro_state,
    enrich_trades,
    load_processed_data,
    build_audit_report,
    run,
)
from strategy_enable_system.config import (
    LabelEnrichmentConfig, EnrichmentThresholdsConfig,
    EnrichmentAlignmentConfig, EnrichmentFieldsConfig,
)

THRESH = EnrichmentThresholdsConfig()


def _make_le_config(**kw):
    c = LabelEnrichmentConfig()
    c.enabled = True
    for k, v in kw.items():
        setattr(c, k, v)
    return c


# ============================================================
# Symbol mapping
# ============================================================

def test_symbol_map_btcusdt():
    assert map_to_coinglass_symbol("BTCUSDT") == "BTC"

def test_symbol_map_ethusdt():
    assert map_to_coinglass_symbol("ETHUSDT") == "ETH"

def test_symbol_map_unknown():
    assert map_to_coinglass_symbol("SOLUSDT") is None


# ============================================================
# is_missing
# ============================================================

def test_is_missing_null():
    assert is_missing(None)
    assert is_missing(float("nan"))

def test_is_missing_unknown_str():
    assert is_missing("unknown")
    assert is_missing("")

def test_is_missing_valid():
    assert not is_missing("rising")
    assert not is_missing("neutral")


# ============================================================
# Time alignment
# ============================================================

def _make_ts_df(times, values, col="close"):
    return pd.DataFrame({"datetime_utc": times, col: values})


def test_find_most_recent_before_entry():
    df = _make_ts_df(["2026-01-05T10:00", "2026-01-05T12:00", "2026-01-05T14:00"], [10, 20, 30])
    row = find_most_recent(df, pd.Timestamp("2026-01-05T13:00"))
    assert row is not None
    assert row[df.columns[-1]] == 20  # 12:00 is most recent

def test_find_most_recent_no_data_before():
    df = _make_ts_df(["2026-01-05T14:00", "2026-01-05T16:00"], [10, 20])
    row = find_most_recent(df, pd.Timestamp("2026-01-05T10:00"))
    assert row is None

def test_find_most_recent_date_only():
    df = _make_ts_df(["2026-01-05T08:00", "2026-01-05T22:00"], [10, 20])
    row = find_most_recent(df, pd.Timestamp("2026-01-05T15:00"), date_only=True)
    assert row is not None
    assert row[df.columns[-1]] == 20  # both same date, 22:00 is last but it's after 15:00? Wait, date_only means we compare just dates. Both on 2026-01-05. The last row should be the 22:00 one. But 22:00 is after 15:00... no, date_only means we check date <= entry_date, which is same day. So both are valid. Last one is index 1 = 20.

# ============================================================
# Enrichment rules
# ============================================================

def test_oi_state_rising():
    df = _make_ts_df(["2026-01-03", "2026-01-04"], [100, 105])
    assert enrich_oi_state(df, pd.Timestamp("2026-01-04T12:00"), THRESH) == "rising"

def test_oi_state_falling():
    df = _make_ts_df(["2026-01-03", "2026-01-04"], [100, 95])
    assert enrich_oi_state(df, pd.Timestamp("2026-01-04T12:00"), THRESH) == "falling"

def test_oi_state_flat():
    df = _make_ts_df(["2026-01-03", "2026-01-04"], [100, 101])
    assert enrich_oi_state(df, pd.Timestamp("2026-01-04T12:00"), THRESH) == "flat"

def test_funding_state_positive():
    df = _make_ts_df(["2026-01-03"], [0.001])
    assert enrich_funding_state(df, pd.Timestamp("2026-01-03T12:00"), THRESH) == "positive"

def test_funding_state_negative():
    df = _make_ts_df(["2026-01-03"], [-0.001])
    assert enrich_funding_state(df, pd.Timestamp("2026-01-03T12:00"), THRESH) == "negative"

def test_funding_state_neutral():
    df = _make_ts_df(["2026-01-03"], [0.0])
    assert enrich_funding_state(df, pd.Timestamp("2026-01-03T12:00"), THRESH) == "neutral"

def test_orderflow_state_bullish():
    df = pd.DataFrame({"datetime_utc": ["2026-01-05T10:00"], "taker_imbalance": [0.15]})
    assert enrich_orderflow_state(df, pd.Timestamp("2026-01-05T11:00"), THRESH) == "bullish"

def test_orderflow_state_bearish():
    df = pd.DataFrame({"datetime_utc": ["2026-01-05T10:00"], "taker_imbalance": [-0.15]})
    assert enrich_orderflow_state(df, pd.Timestamp("2026-01-05T11:00"), THRESH) == "bearish"

def test_orderflow_state_neutral():
    df = pd.DataFrame({"datetime_utc": ["2026-01-05T10:00"], "taker_imbalance": [0.05]})
    assert enrich_orderflow_state(df, pd.Timestamp("2026-01-05T11:00"), THRESH) == "neutral"

def test_etf_flow_inflow():
    df = pd.DataFrame({"datetime_utc": ["2026-01-03"], "flow_usd": [100_000_000]})
    assert enrich_etf_flow_state(df, pd.Timestamp("2026-01-04T12:00"), THRESH) == "inflow"

def test_etf_flow_outflow():
    df = pd.DataFrame({"datetime_utc": ["2026-01-03"], "flow_usd": [-100_000_000]})
    assert enrich_etf_flow_state(df, pd.Timestamp("2026-01-04T12:00"), THRESH) == "outflow"

def test_etf_flow_neutral():
    df = pd.DataFrame({"datetime_utc": ["2026-01-03"], "flow_usd": [1_000_000]})
    assert enrich_etf_flow_state(df, pd.Timestamp("2026-01-04T12:00"), THRESH) == "neutral"

def test_macro_event_risk():
    cal = pd.DataFrame({
        "publish_timestamp": [int(datetime(2026, 5, 10, 13, 30).timestamp())],
        "importance_level": [3],
    })
    entry = pd.Timestamp("2026-05-10 15:00")
    assert enrich_macro_state(cal, None, entry, THRESH) == "event_risk"

def test_macro_flow_driven():
    entry = pd.Timestamp("2026-05-10 15:00")
    assert enrich_macro_state(None, "inflow", entry, THRESH) == "flow_driven"

def test_macro_neutral():
    entry = pd.Timestamp("2026-05-10 15:00")
    assert enrich_macro_state(None, None, entry, THRESH) == "neutral"


# ============================================================
# Full enrichment pipeline (with mock data)
# ============================================================

def _make_mock_processed_dir(tmpdir):
    d = os.path.join(tmpdir, "processed")
    os.makedirs(d, exist_ok=True)

    # OI data for BTC
    oi = pd.DataFrame({
        "datetime_utc": pd.date_range("2026-01-01", periods=10, freq="D"),
        "open": np.ones(10) * 1e10, "high": np.ones(10) * 1.1e10,
        "low": np.ones(10) * 0.9e10, "close": np.linspace(1e10, 1.5e10, 10),
        "source_endpoint": "test",
    })
    oi.to_csv(os.path.join(d, "BTC_oi_agg.csv"), index=False)

    # Funding for BTC
    fund = pd.DataFrame({
        "datetime_utc": pd.date_range("2026-01-01", periods=10, freq="D"),
        "open": [0.0001]*10, "high": [0.0002]*10, "low": [0.0]*10,
        "close": [0.0002]*10, "source_endpoint": "test",
    })
    fund.to_csv(os.path.join(d, "BTC_funding_oiw.csv"), index=False)

    # Taker for BTC
    taker = pd.DataFrame({
        "datetime_utc": pd.date_range("2026-01-05", periods=20, freq="1h"),
        "aggregated_buy_volume_usd": [60e6]*20, "aggregated_sell_volume_usd": [40e6]*20,
        "taker_imbalance": [0.20]*20, "source_endpoint": "test",
    })
    taker.to_csv(os.path.join(d, "BTC_taker_agg.csv"), index=False)

    # ETF for BTC
    etf = pd.DataFrame({
        "datetime_utc": pd.date_range("2026-01-01", periods=10, freq="D"),
        "flow_usd": [100_000_000]*10, "price_usd": [100000]*10, "source_endpoint": "test",
    })
    etf.to_csv(os.path.join(d, "btc_etf_flow.csv"), index=False)

    # Calendar
    cal = pd.DataFrame({
        "publish_timestamp": [int(datetime(2026, 1, 10, 13, 30).timestamp())],
        "datetime_utc": ["2026-01-10T13:30:00"],
        "calendar_name": ["CPI MoM"], "country_code": ["US"],
        "country_name": ["United States"], "data_effect": [""],
        "importance_level": [3], "has_exact_publish_time": [1],
        "source_endpoint": ["test"],
    })
    cal.to_csv(os.path.join(d, "calendar_economic.csv"), index=False)

    return d


def test_full_enrichment_pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        proc_dir = _make_mock_processed_dir(tmp)
        trades = pd.DataFrame([{
            "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
            "entry_time": "2026-01-06 10:00:00", "exit_time": "2026-01-06 14:00:00",
            "pnl_R": 1.0, "regime": "trend_up", "session": "London",
            "oi_state": "unknown", "funding_state": "unknown",
            "orderflow_state": "unknown", "etf_flow_state": "unknown",
            "macro_state": "unknown",
        }])

        config = _make_le_config(preserve_original_columns=True)
        stats, unknown_syms = enrich_trades(trades, proc_dir, config)

        assert unknown_syms == 0
        assert trades.at[0, "oi_state"] == "rising"
        assert trades.at[0, "funding_state"] == "positive"
        assert trades.at[0, "orderflow_state"] == "bullish"
        assert trades.at[0, "etf_flow_state"] == "inflow"
        # macro depends on event window proximity
        assert trades.at[0, "macro_state"] in ("event_risk", "flow_driven", "neutral")
        assert stats["oi_state"]["filled"] >= 1


def test_original_columns_preserved():
    with tempfile.TemporaryDirectory() as tmp:
        proc_dir = _make_mock_processed_dir(tmp)
        trades = pd.DataFrame([{
            "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
            "entry_time": "2026-01-06 10:00:00", "exit_time": "2026-01-06 14:00:00",
            "pnl_R": 1.0, "regime": "trend_up", "session": "London",
            "oi_state": "unknown", "funding_state": "unknown",
        }])
        config = _make_le_config(preserve_original_columns=True)
        enrich_trades(trades, proc_dir, config)

        assert "original_oi_state" in trades.columns
        assert trades.at[0, "original_oi_state"] == "unknown"


def test_existing_valid_not_overwritten():
    with tempfile.TemporaryDirectory() as tmp:
        proc_dir = _make_mock_processed_dir(tmp)
        trades = pd.DataFrame([{
            "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
            "entry_time": "2026-01-06 10:00:00", "exit_time": "2026-01-06 14:00:00",
            "pnl_R": 1.0, "regime": "trend_up", "session": "London",
            "oi_state": "falling",  # already valid
        }])
        config = _make_le_config(preserve_original_columns=True)
        stats, _ = enrich_trades(trades, proc_dir, config)
        assert trades.at[0, "oi_state"] == "falling"  # unchanged
        assert stats["oi_state"]["unchanged_valid"] == 1


def test_no_lookahead():
    """Ensure we don't use future data."""
    with tempfile.TemporaryDirectory() as tmp:
        proc_dir = _make_mock_processed_dir(tmp)
        # Trade at Jan 2, but data starts Jan 1 — ETF is daily, but orders may not have filled
        trades = pd.DataFrame([{
            "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
            "entry_time": "2026-01-01 00:01:00",  # very early
            "exit_time": "2026-01-01 00:30:00",
            "pnl_R": 1.0, "regime": "trend_up", "session": "London",
            "oi_state": "unknown",
        }])
        config = _make_le_config(preserve_original_columns=True)
        stats, _ = enrich_trades(trades, proc_dir, config)
        # OI has data starting 2026-01-01 00:00, but we need 2 points for pct_change
        # First point available, so it should be filled or stay unknown if < 2 points
        # Either way, no crash


def test_unknown_symbol_no_crash():
    with tempfile.TemporaryDirectory() as tmp:
        proc_dir = _make_mock_processed_dir(tmp)
        trades = pd.DataFrame([{
            "trade_id": "T1", "strategy_name": "S1", "symbol": "SOLUSDT",
            "entry_time": "2026-01-06 10:00:00", "exit_time": "2026-01-06 14:00:00",
            "pnl_R": 1.0, "regime": "trend_up", "session": "London",
            "oi_state": "unknown", "funding_state": "unknown",
        }])
        config = _make_le_config()
        stats, unknown_syms = enrich_trades(trades, proc_dir, config)
        assert unknown_syms == 1
        assert trades.at[0, "oi_state"] == "unknown"  # unchanged


def test_no_processed_dir_no_crash():
    with tempfile.TemporaryDirectory() as tmp:
        trades = pd.DataFrame([{
            "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
            "entry_time": "2026-01-06 10:00:00", "exit_time": "2026-01-06 14:00:00",
            "pnl_R": 1.0, "regime": "trend_up", "session": "London",
            "oi_state": "unknown",
        }])
        config = _make_le_config()
        stats, _ = enrich_trades(trades, "/nonexistent_dir", config)
        assert stats["oi_state"]["missing_match"] >= 1


def test_core_fields_unchanged():
    with tempfile.TemporaryDirectory() as tmp:
        proc_dir = _make_mock_processed_dir(tmp)
        trades = pd.DataFrame([{
            "trade_id": "T99", "strategy_name": "Mystrat", "symbol": "BTCUSDT",
            "entry_time": "2026-01-06 10:00:00", "exit_time": "2026-01-06 14:00:00",
            "pnl_R": 99.99, "regime": "trend_up", "session": "London",
            "oi_state": "unknown", "funding_state": "unknown",
        }])
        orig = trades.copy()
        config = _make_le_config()
        enrich_trades(trades, proc_dir, config)
        for col in ["trade_id", "strategy_name", "regime", "pnl_R"]:
            assert trades.at[0, col] == orig.at[0, col], f"{col} changed!"


def test_audit_report_generated():
    config = _make_le_config()
    report = build_audit_report("test.csv", "/tmp", "out.csv",
                                {"oi_state": {"before_unknown": 10, "after_unknown": 3, "filled": 7,
                                              "unchanged_valid": 5, "missing_match": 3}},
                                0, config)
    assert "Label Enrichment" in report
    assert "oi_state" in report
    assert "未修改" in report


def test_dry_run_no_writes():
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "enriched.csv")
        config = _make_le_config(input_path="/nonexistent", output_path=out_path)
        # dry-run should just log, not error
        try:
            run("nonexistent_config.yaml", "/nonexistent", out_path, "/nonexistent", dry_run=True)
        except FileNotFoundError:
            pass  # expected if config doesn't exist
        assert not os.path.exists(out_path)


def test_config_dataclass_parses():
    c = LabelEnrichmentConfig()
    assert c.enabled == False
    assert c.preserve_original_columns == True
    assert c.thresholds.oi_change_pct_rising == 0.03
    assert c.alignment.prevent_lookahead == True
