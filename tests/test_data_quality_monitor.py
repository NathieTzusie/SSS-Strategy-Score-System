"""
Tests for Data Quality Monitor (P2-15).
"""

import os
import json
import tempfile
import pandas as pd
import pytest
from unittest.mock import patch

from strategy_enable_system.data_quality_monitor import (
    field_coverage_monitor,
    enrichment_monitor,
    coinglass_fetch_monitor,
    partial_context_monitor,
    feature_gate_monitor,
    baseline_stability_monitor,
    build_monitor_report,
    run,
    MONITOR_FIELDS,
)
from strategy_enable_system.config import (
    DataQualityMonitorConfig,
    MonitorThresholdsConfig,
    FeatureGatesConfig,
)


@pytest.fixture
def thresholds():
    return MonitorThresholdsConfig(pass_coverage=0.80, warn_coverage=0.50)


@pytest.fixture
def gates_config():
    return FeatureGatesConfig()


@pytest.fixture
def monitor_config():
    return DataQualityMonitorConfig(enabled=True)


# ── 1. Missing input files do not crash ──

def test_field_coverage_missing_input_does_not_crash(thresholds):
    rows = field_coverage_monitor(None, None, thresholds)
    assert len(rows) == len(MONITOR_FIELDS)
    for r in rows:
        assert r["category"] == "field_coverage"
        # All should be WARN (missing data)
        assert r["status"] in ("WARN", "BLOCK", "NOT_AVAILABLE", "DEGRADED")


# ── 2. Field coverage PASS / WARN / BLOCK rules ──

def test_field_coverage_pass(thresholds):
    df = pd.DataFrame({
        "field": ["session", "oi_state"],
        "unknown_ratio_after": [0.0, 0.1],
        "readiness_status": ["PASS", "PASS"],
    })
    rows = field_coverage_monitor(df, None, thresholds)
    session = [r for r in rows if r["item"] == "session"][0]
    assert session["status"] == "PASS"

def test_field_coverage_warn(thresholds):
    df = pd.DataFrame({
        "field": ["oi_state"],
        "unknown_ratio_after": [0.3],  # coverage=0.7 < 0.80, > 0.50
        "readiness_status": ["WARN"],
    })
    rows = field_coverage_monitor(df, None, thresholds)
    r = rows[0]
    assert r["status"] == "WARN"

def test_field_coverage_block(thresholds):
    df = pd.DataFrame({
        "field": ["orderflow_state"],
        "unknown_ratio_after": [0.9],  # coverage=0.1
        "readiness_status": ["BLOCK"],
    })
    rows = field_coverage_monitor(df, None, thresholds)
    r = [r for r in rows if r["item"] == "orderflow_state"][0]
    assert r["status"] == "BLOCK"


# ── 3. Macro fallback → DEGRADED ──

def test_macro_state_degraded(thresholds):
    """Even at 100% coverage, macro_state should be DEGRADED because of fallback neutral."""
    df = pd.DataFrame({
        "field": ["macro_state"],
        "unknown_ratio_after": [0.0],
        "readiness_status": ["PASS"],
    })
    rows = field_coverage_monitor(df, None, thresholds)
    r = [r for r in rows if r["item"] == "macro_state"][0]
    assert r["status"] == "DEGRADED"


# ── 4. Orderflow coverage → classifier BLOCK ──

def test_orderflow_causes_classifier_block(thresholds, gates_config):
    df = pd.DataFrame({
        "field": ["orderflow_state", "macro_state", "etf_flow_state"],
        "unknown_ratio_after": [0.86, 0.0, 0.0],
        "readiness_status": ["BLOCK", "PASS", "PASS"],
    })
    fc_rows = field_coverage_monitor(df, None, thresholds)
    fg_rows = feature_gate_monitor(fc_rows, gates_config, ctx_ready=True)
    c = [r for r in fg_rows if r["item"] == "automatic_regime_classifier"][0]
    assert c["status"] == "BLOCK"
    assert "orderflow" in c["reason"].lower() or "86" in c["reason"] or "0%" in c["reason"]


# ── 5. Market opportunity gate BLOCK ──

def test_market_opportunity_block(thresholds, gates_config):
    df = pd.DataFrame({
        "field": ["orderflow_state", "macro_state", "etf_flow_state"],
        "unknown_ratio_after": [0.86, 0.0, 0.0],
        "readiness_status": ["BLOCK", "DEGRADED", "PASS"],
    })
    fc_rows = field_coverage_monitor(df, None, thresholds)
    fg_rows = feature_gate_monitor(fc_rows, gates_config, ctx_ready=True)
    mo = [r for r in fg_rows if r["item"] == "full_market_opportunity_score"][0]
    assert mo["status"] == "BLOCK"


# ── 6. Partial context → READY ──

def test_partial_context_ready(thresholds, gates_config):
    df = pd.DataFrame({
        "field": ["oi_state", "funding_state", "etf_flow_state", "session", "structure_state", "volatility_state"],
        "unknown_ratio_after": [0.03, 0.03, 0.0, 0.0, 0.0, 0.0],
        "readiness_status": ["PASS"] * 6,
    })
    fc_rows = field_coverage_monitor(df, None, thresholds)
    fg_rows = feature_gate_monitor(fc_rows, gates_config, ctx_ready=True)
    ctx = [r for r in fg_rows if r["item"] == "partial_context_report"][0]
    assert ctx["status"] == "PASS"


# ── 7. Baseline comparison 0 delta PASS ──

def test_baseline_zero_delta_pass(tmp_path):
    base_dir = tmp_path / "baseline"
    curr_dir = tmp_path / "current"
    base_dir.mkdir(); curr_dir.mkdir()

    es = pd.DataFrame({
        "strategy_name": ["S1", "S1"],
        "regime": ["trend", "range"],
        "enable_score": [70.0, 50.0],
        "status": ["中等开启", "弱开启"],
    })
    es.to_csv(base_dir / "enable_score.csv", index=False)
    es.to_csv(curr_dir / "enable_score.csv", index=False)

    rows = baseline_stability_monitor(str(base_dir), str(curr_dir), 0.000001)
    main = [r for r in rows if r["item"] == "baseline_comparison"][0]
    assert main["status"] == "PASS"


# ── 8. Baseline status changed → BLOCK ──

def test_baseline_status_changed_blocks(tmp_path):
    base_dir = tmp_path / "baseline"
    curr_dir = tmp_path / "current"
    base_dir.mkdir(); curr_dir.mkdir()

    base_es = pd.DataFrame({
        "strategy_name": ["S1"], "regime": ["trend"],
        "enable_score": [70.0], "status": ["中等开启"],
    })
    curr_es = pd.DataFrame({
        "strategy_name": ["S1"], "regime": ["trend"],
        "enable_score": [49.0], "status": ["禁用"],
    })
    base_es.to_csv(base_dir / "enable_score.csv", index=False)
    curr_es.to_csv(curr_dir / "enable_score.csv", index=False)

    rows = baseline_stability_monitor(str(base_dir), str(curr_dir), 0.000001)
    main = [r for r in rows if r["item"] == "baseline_comparison"][0]
    assert main["status"] == "BLOCK"


# ── 9. Summary CSV field integrity ──

def test_summary_csv_fields(thresholds, gates_config):
    df = pd.DataFrame({
        "field": ["oi_state", "funding_state"],
        "unknown_ratio_after": [0.03, 0.03],
        "readiness_status": ["PASS", "PASS"],
    })
    fc_rows = field_coverage_monitor(df, None, thresholds)
    fg = feature_gate_monitor(fc_rows, gates_config, ctx_ready=True)
    df_out = pd.DataFrame(fc_rows + fg)
    for col in ["category", "item", "metric", "value", "status", "reason", "recommendation"]:
        assert col in df_out.columns, f"Missing column: {col}"


# ── 10. Markdown report contains Feature Gates ──

def test_markdown_contains_feature_gates(monitor_config):
    rows = pd.DataFrame([
        {"category": "feature_gate", "item": "automatic_regime_classifier",
         "metric": "readiness", "value": "block", "status": "BLOCK",
         "reason": "orderflow insufficient", "recommendation": "Upgrade plan"},
        {"category": "feature_gate", "item": "partial_context_report",
         "metric": "readiness", "value": "pass", "status": "PASS",
         "reason": "All included fields PASS", "recommendation": "Use it"},
        {"category": "baseline_stability", "item": "baseline_comparison",
         "metric": "max_enable_score_delta", "value": "0.0000000000",
         "status": "PASS", "reason": "stable", "recommendation": ""},
    ])
    report = build_monitor_report(rows, monitor_config)
    assert "Feature Gates" in report
    assert "automatic_regime_classifier" in report
    assert "BLOCK" in report
    assert "PASS" in report


# ── 11. Dry-run does not write ──

def test_dry_run_no_write(tmp_path):
    out_dir = tmp_path / "monitor_out"
    run(config_path="config.yaml", output_dir_override=str(out_dir), dry_run=True)
    assert not out_dir.exists()


# ── 12. CLI --output-dir override ──

def test_output_dir_override_respected(monitor_config):
    cfg = DataQualityMonitorConfig(enabled=True, output_dir="/custom/path")
    assert "custom" in cfg.output_dir


# ── 13. Config dataclass parses data_quality_monitor ──

def test_config_parses_monitor():
    from strategy_enable_system.config import load_config
    config = load_config("config.yaml")
    dqm = config.data_quality_monitor
    assert dqm.enabled == False
    assert dqm.output_dir == "outputs/monitor"
    assert dqm.thresholds.pass_coverage == 0.80
    assert "orderflow_state_coverage" in dqm.feature_gates.classifier_requires


# ── 14. API key not in monitor report ──

def test_monitor_report_no_api_key(monitor_config):
    rows = pd.DataFrame([
        {"category": "field_coverage", "item": "session",
         "metric": "coverage_rate", "value": 1.0, "status": "PASS",
         "reason": "", "recommendation": ""},
    ])
    report = build_monitor_report(rows, monitor_config)
    assert "CG-API-KEY" not in report
    assert "api_key" not in report.lower()
    assert "48785b" not in report


# ── 15. enrichment_monitor with missing files ──

def test_enrichment_missing_files(tmp_path):
    rows = enrichment_monitor(str(tmp_path / "nonexistent.md"), str(tmp_path / "nonexistent.csv"))
    for r in rows:
        if r["item"] in ("enrichment_audit_report", "enriched_trades_full_year_csv"):
            assert r["status"] == "WARN"


# ── 16. coinglass fetch monitor with missing report ──

def test_coinglass_missing_report(tmp_path):
    rows = coinglass_fetch_monitor(str(tmp_path / "nonexistent.md"))
    assert any(r["item"] == "taker_4h_coverage" and r["status"] == "BLOCK" for r in rows)
    assert any(r["item"] == "calendar_availability" and r["status"] == "BLOCK" for r in rows)


# ── 17. partial_context_monitor with missing file ──

def test_partial_context_missing_file():
    rows = partial_context_monitor("/nonexistent/ctx.csv", ["session"])
    pr = [r for r in rows if r["item"] == "partial_context_ready"][0]
    assert pr["status"] == "BLOCK"


# ── 18. partial_context_monitor with all PASS ──

def test_partial_context_all_pass(tmp_path):
    ctx_csv = tmp_path / "ctx.csv"
    pd.DataFrame({
        "strategy_name": ["S1"] * 6,
        "regime": ["r1"] * 6,
        "field": ["session", "structure_state", "volatility_state", "oi_state", "funding_state", "etf_flow_state"],
        "readiness_status": ["PASS"] * 6,
    }).to_csv(ctx_csv, index=False)

    rows = partial_context_monitor(str(ctx_csv),
                                    ["session", "oi_state", "funding_state", "etf_flow_state"])
    pr = [r for r in rows if r["item"] == "partial_context_ready"][0]
    assert pr["status"] == "PASS"
    assert "ready" in str(pr["value"])


# ── 19. coinbase_premium_state NOT_AVAILABLE ──

def test_coinbase_premium_not_available(thresholds):
    df = pd.DataFrame({
        "field": ["coinbase_premium_state"],
        "unknown_ratio_after": [1.0],
        "readiness_status": ["BLOCK"],
    })
    rows = field_coverage_monitor(df, None, thresholds)
    r = [r for r in rows if r["item"] == "coinbase_premium_state"][0]
    assert r["status"] == "NOT_AVAILABLE"
