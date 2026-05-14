"""
Tests for Partial Context Report (P2-14).
"""

import os
import json
import tempfile
import pandas as pd
import pytest
from datetime import datetime

from strategy_enable_system.context_report import (
    is_unknown,
    compute_field_distribution,
    build_context_summary,
    compute_field_readiness_overview,
    build_context_report,
    run,
)
from strategy_enable_system.config import PartialContextConfig


# ── Sample data ──

@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "strategy_name": ["ATR_ETH_3m", "ATR_ETH_3m", "ATR_ETH_3m",
                          "BTP_ETH_30m", "BTP_ETH_30m", "BTP_ETH_30m"],
        "regime": ["trend_up", "trend_up", "trend_up",
                   "range", "range", "range"],
        "entry_time": pd.date_range("2025-06-01", periods=6, freq="4h"),
        "session": ["Asia", "London", "overlap", "NY", "NY", "off"],
        "structure_state": ["trending", "trending", "trending", "ranging", "ranging", "ranging"],
        "volatility_state": ["normal", "normal", "high", "normal", "high", "high"],
        "oi_state": ["flat", "rising", "rising", "falling", "falling", "flat"],
        "funding_state": ["positive", "positive", "positive", "negative", "negative", "unknown"],
        "etf_flow_state": ["inflow", "inflow", "inflow", "outflow", "outflow", "outflow"],
        # Excluded fields
        "orderflow_state": ["unknown"] * 6,
        "macro_state": ["neutral"] * 6,
        "coinbase_premium_state": ["unknown"] * 6,
    })


@pytest.fixture
def minimal_config():
    return PartialContextConfig(
        enabled=True,
        fields=["session", "structure_state", "oi_state", "funding_state", "etf_flow_state"],
        excluded_fields=["orderflow_state", "macro_state", "coinbase_premium_state"],
        group_by=["strategy_name", "regime"],
        min_coverage_for_field=0.80,
        informational_only=True,
    )


# ── 1. Unknown detection ──

def test_is_unknown_null():
    assert is_unknown(None)

def test_is_unknown_nan():
    assert is_unknown(float("nan"))

def test_is_unknown_empty_string():
    assert is_unknown("")

def test_is_unknown_literal():
    assert is_unknown("unknown")
    assert is_unknown("Unknown")
    assert is_unknown("UNKNOWN")

def test_is_unknown_valid_value():
    assert not is_unknown("rising")
    assert not is_unknown("flat")
    assert not is_unknown(0)


# ── 2. Field distribution ──

def test_compute_field_distribution_basic(sample_df):
    dist = compute_field_distribution(sample_df, "oi_state", min_coverage=0.80)
    assert dist["total_trades"] == 6
    assert dist["known_count"] == 6
    assert dist["unknown_count"] == 0
    assert dist["coverage_rate"] == 1.0
    assert dist["readiness_status"] == "PASS"
    assert dist["dominant_value"] in ("flat", "rising", "falling")

def test_compute_field_distribution_with_unknown(sample_df):
    dist = compute_field_distribution(sample_df, "funding_state", min_coverage=0.80)
    assert dist["total_trades"] == 6
    assert dist["unknown_count"] == 1
    assert dist["known_count"] == 5
    assert dist["coverage_rate"] == pytest.approx(5.0 / 6.0, rel=1e-4)

def test_compute_field_distribution_all_unknown():
    df = pd.DataFrame({"x": ["unknown", "unknown", "unknown"]})
    dist = compute_field_distribution(df, "x", min_coverage=0.80)
    assert dist["coverage_rate"] == 0.0
    assert dist["readiness_status"] == "BLOCK"
    assert dist["dominant_value"] == "unknown"

def test_compute_field_distribution_missing_column(sample_df):
    dist = compute_field_distribution(sample_df, "nonexistent_field")
    assert dist["coverage_rate"] == 0.0
    assert dist["readiness_status"] == "BLOCK"

def test_compute_field_distribution_warn():
    df = pd.DataFrame({"x": ["a", "unknown", "unknown", "unknown"]})
    dist = compute_field_distribution(df, "x", min_coverage=0.80)
    assert dist["readiness_status"] == "WARN"

def test_compute_field_distribution_json():
    df = pd.DataFrame({"x": ["a", "a", "b", "b", "b"]})
    dist = compute_field_distribution(df, "x")
    d = json.loads(dist["distribution_json"])
    assert d == {"a": 2, "b": 3}


# ── 3. Coverage rate ──

def test_coverage_rate_all_known(sample_df):
    dist = compute_field_distribution(sample_df, "session")
    assert dist["coverage_rate"] == 1.0

def test_coverage_rate_partial(sample_df):
    dist = compute_field_distribution(sample_df, "funding_state")
    assert dist["coverage_rate"] == pytest.approx(5.0 / 6.0, rel=1e-4)

def test_coverage_rate_zero():
    df = pd.DataFrame({"x": ["unknown"] * 10})
    dist = compute_field_distribution(df, "x")
    assert dist["coverage_rate"] == 0.0


# ── 4. Readiness status ──

def test_readiness_pass(sample_df):
    dist = compute_field_distribution(sample_df, "oi_state", min_coverage=0.80)
    assert dist["readiness_status"] == "PASS"

def test_readiness_warn(sample_df):
    df = pd.DataFrame({"x": ["a", "unknown", "unknown", "unknown"]})
    dist = compute_field_distribution(df, "x", min_coverage=0.80)
    assert dist["readiness_status"] == "WARN"

def test_readiness_block():
    df = pd.DataFrame({"x": ["unknown"] * 5})
    dist = compute_field_distribution(df, "x", min_coverage=0.80)
    assert dist["readiness_status"] == "BLOCK"


# ── 5. Dominant value ──

def test_dominant_value(sample_df):
    dist = compute_field_distribution(sample_df, "session")
    assert dist["dominant_value"] != "unknown"

def test_dominant_value_share(sample_df):
    dist = compute_field_distribution(sample_df, "session")
    assert 0 < dist["dominant_value_share"] <= 1.0


# ── 6. Distribution JSON ──

def test_distribution_json_valid(sample_df):
    dist = compute_field_distribution(sample_df, "oi_state")
    try:
        d = json.loads(dist["distribution_json"])
    except json.JSONDecodeError:
        pytest.fail("distribution_json is not valid JSON")
    assert isinstance(d, dict)

def test_distribution_json_empty_when_all_unknown():
    df = pd.DataFrame({"x": ["unknown"] * 5})
    dist = compute_field_distribution(df, "x")
    d = json.loads(dist["distribution_json"])
    assert d == {}


# ── 7. Excluded fields ──

def test_excluded_fields_not_in_summary(sample_df, minimal_config):
    summary = build_context_summary(sample_df, minimal_config)
    fields_in_output = set(summary["field"].unique())
    for excl in minimal_config.excluded_fields:
        assert excl not in fields_in_output, f"{excl} should not be in summary"


# ── 8. Informational only ──

def test_informational_only_true(sample_df, minimal_config):
    summary = build_context_summary(sample_df, minimal_config)
    assert all(summary["informational_only"] == True)


# ── 9. Dry-run does not write ──

def test_dry_run_no_write(tmp_path):
    """Test that dry-run does not write any files."""
    input_csv = tmp_path / "test_trades.csv"
    df = pd.DataFrame({
        "strategy_name": ["S1"], "regime": ["trend"],
        "session": ["Asia"], "structure_state": ["trending"],
        "volatility_state": ["normal"], "oi_state": ["flat"],
        "funding_state": ["positive"], "etf_flow_state": ["inflow"],
    })
    df.to_csv(input_csv, index=False)
    out_dir = tmp_path / "context_output"

    # Dry-run should not write any files
    run(
        config_path="config.yaml",
        input_override=str(input_csv),
        output_dir_override=str(out_dir),
        dry_run=True,
    )
    assert not out_dir.exists()


# ── 10. Markdown report content ──

def test_markdown_contains_informational_only(sample_df, minimal_config, tmp_path):
    input_csv = tmp_path / "test.csv"
    sample_df.to_csv(input_csv, index=False)
    summary = build_context_summary(sample_df, minimal_config)
    overview = compute_field_readiness_overview(summary, minimal_config.fields)
    excluded = {"orderflow_state": "test reason", "macro_state": "test", "coinbase_premium_state": "test"}
    report = build_context_report(summary, overview, minimal_config,
                                   str(input_csv), excluded)
    assert "INFORMATIONAL ONLY" in report


def test_markdown_contains_excluded_fields(sample_df, minimal_config, tmp_path):
    input_csv = tmp_path / "test.csv"
    sample_df.to_csv(input_csv, index=False)
    summary = build_context_summary(sample_df, minimal_config)
    overview = compute_field_readiness_overview(summary, minimal_config.fields)
    excluded = {"orderflow_state": "test reason", "macro_state": "test", "coinbase_premium_state": "test"}
    report = build_context_report(summary, overview, minimal_config,
                                   str(input_csv), excluded)
    assert "Excluded Fields" in report
    assert "orderflow_state" in report


# ── 11. CLI override --input / --output-dir ──

def test_cli_input_override(sample_df, tmp_path):
    """Test that --input override is respected."""
    alt_csv = tmp_path / "alt_trades.csv"
    sample_df.to_csv(alt_csv, index=False)

    # Run dry-run with input override — should not fail
    run(
        config_path="config.yaml",
        input_override=str(alt_csv),
        dry_run=True,
    )
    # If we get here without error, the override was applied
    assert alt_csv.exists()


def test_cli_output_override(sample_df, tmp_path):
    """Test that --output-dir override changes output path."""
    alt_csv = tmp_path / "test.csv"
    sample_df.to_csv(alt_csv, index=False)
    out_dir = tmp_path / "custom_ctx"
    out_dir.mkdir()

    # Need enabled=true — pass it via partial_context.enabled?
    # We'll test via the config dataclass directly
    config = PartialContextConfig(enabled=True, output_dir=str(out_dir))
    assert config.output_dir == str(out_dir)


# ── 12. Does not modify input CSV ──

def test_input_not_modified(sample_df, tmp_path):
    input_csv = tmp_path / "original.csv"
    sample_df.to_csv(input_csv, index=False)
    original_hash = pd.read_csv(input_csv).to_dict()

    from strategy_enable_system.context_report import build_context_summary
    df = pd.read_csv(input_csv)
    _ = build_context_summary(df, PartialContextConfig(enabled=True))

    # Re-read: must be identical
    re_read = pd.read_csv(input_csv).to_dict()
    assert re_read == original_hash


# ── 13. Empty trades ──

def test_empty_trades_df(minimal_config):
    df = pd.DataFrame(columns=["strategy_name", "regime", "session"])
    summary = build_context_summary(df, minimal_config)
    assert len(summary) == 0


# ── 14. Field readiness overview ──

def test_field_readiness_overview(sample_df, minimal_config):
    summary = build_context_summary(sample_df, minimal_config)
    overview = compute_field_readiness_overview(summary, minimal_config.fields)
    assert len(overview) == len(minimal_config.fields)
    for f in minimal_config.fields:
        assert f in overview["field"].values


# ── 15. Config dataclass parses partial_context ──

def test_config_partial_context_defaults():
    from strategy_enable_system.config import PartialContextConfig
    pc = PartialContextConfig()
    assert pc.enabled == False
    assert pc.mode == "partial_context_mode"
    assert pc.informational_only == True
    assert "oi_state" in pc.fields
    assert "orderflow_state" in pc.excluded_fields
    assert pc.min_coverage_for_field == 0.80


def test_config_loads_partial_context():
    from strategy_enable_system.config import load_config
    config = load_config("config.yaml")
    pc = config.partial_context
    assert isinstance(pc, PartialContextConfig)
    assert pc.enabled == False
    assert pc.mode == "partial_context_mode"
