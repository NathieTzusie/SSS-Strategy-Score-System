"""
Unit tests for Label Quality Tool (P2-2).
"""
import pytest
import os
import tempfile
import pandas as pd
import numpy as np
from datetime import datetime

from strategy_enable_system.label_quality import (
    is_missing,
    classify_session,
    normalize_snapshot,
    ensure_label_columns,
    normalize_duplicate_trade_ids,
    fix_labels,
    build_quality_report,
    validate_required_columns,
)
from strategy_enable_system.config import LabelQualityConfig, SessionBackfillConfig, StructureStateBackfillConfig, RegimeSnapshotNormalizationConfig


def _make_config(**overrides):
    """Create a LabelQualityConfig for testing."""
    c = LabelQualityConfig()
    c.enabled = True
    for k, v in overrides.items():
        setattr(c, k, v)
    return c


def _make_df(rows: list) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TestIsMissing:
    def test_none_is_missing(self):
        assert is_missing(None)

    def test_nan_is_missing(self):
        assert is_missing(float('nan'))

    def test_unknown_is_missing(self):
        assert is_missing("unknown")
        assert is_missing("Unknown")
        assert is_missing("UNKNOWN")

    def test_empty_string_is_missing(self):
        assert is_missing("")

    def test_valid_value_not_missing(self):
        assert not is_missing("Asia")
        assert not is_missing("trend_up")
        assert not is_missing(42)


class TestClassifySession:
    def test_asia(self):
        # UTC 05:00 (Monday) → Asia
        dt = datetime(2026, 1, 5, 5, 0)  # Monday
        rules = {"Asia": [0, 9], "London": [7, 16], "NY": [12, 21], "overlap": [12, 16]}
        assert classify_session(dt, rules) == "Asia"

    def test_london(self):
        # UTC 10:00 (Monday) → London (not in overlap 12-16)
        dt = datetime(2026, 1, 5, 10, 0)  # Monday
        rules = {"Asia": [0, 9], "London": [7, 16], "NY": [12, 21], "overlap": [12, 16]}
        assert classify_session(dt, rules) == "London"

    def test_overlap(self):
        # UTC 14:00 (Monday) → overlap
        dt = datetime(2026, 1, 5, 14, 0)  # Monday
        rules = {"Asia": [0, 9], "London": [7, 16], "NY": [12, 21], "overlap": [12, 16]}
        assert classify_session(dt, rules) == "overlap"

    def test_ny(self):
        # UTC 18:00 (Monday) → NY (after overlap ends at 16:00)
        dt = datetime(2026, 1, 5, 18, 0)  # Monday
        rules = {"Asia": [0, 9], "London": [7, 16], "NY": [12, 21], "overlap": [12, 16]}
        assert classify_session(dt, rules) == "NY"

    def test_off_hours(self):
        # UTC 22:00 (Monday) → Off (after NY ends at 21:00)
        dt = datetime(2026, 1, 5, 22, 0)  # Monday
        rules = {"Asia": [0, 9], "London": [7, 16], "NY": [12, 21], "overlap": [12, 16]}
        assert classify_session(dt, rules) == "Off"

    def test_weekend_saturday(self):
        dt = datetime(2026, 1, 10, 10, 0)  # Saturday
        rules = {"Asia": [0, 9], "London": [7, 16], "NY": [12, 21], "overlap": [12, 16]}
        assert classify_session(dt, rules) == "weekend"

    def test_weekend_friday_night(self):
        # Friday 21:00 UTC → weekend
        dt = datetime(2026, 1, 9, 21, 0)  # Friday 21:00
        rules = {"Asia": [0, 9], "London": [7, 16], "NY": [12, 21], "overlap": [12, 16]}
        assert classify_session(dt, rules) == "weekend"

    def test_weekend_sunday_morning(self):
        # Sunday 10:00 UTC → weekend (before 22:00)
        dt = datetime(2026, 1, 11, 10, 0)  # Sunday
        rules = {"Asia": [0, 9], "London": [7, 16], "NY": [12, 21], "overlap": [12, 16]}
        assert classify_session(dt, rules) == "weekend"

    def test_sunday_evening_not_weekend(self):
        # Sunday 22:00 UTC → not weekend, falls to Off
        dt = datetime(2026, 1, 11, 22, 0)  # Sunday 22:00
        rules = {"Asia": [0, 9], "London": [7, 16], "NY": [12, 21], "overlap": [12, 16]}
        assert classify_session(dt, rules) == "Off"


class TestNormalizeSnapshot:
    def test_basic(self):
        dt = datetime(2026, 5, 13, 14, 30)
        result = normalize_snapshot("trend_up", dt, "{regime}_{YYYYMMDD}")
        assert result == "trend_up_20260513"

    def test_range_regime(self):
        dt = datetime(2025, 1, 1, 0, 0)
        result = normalize_snapshot("range", dt, "{regime}_{YYYYMMDD}")
        assert result == "range_20250101"


class TestFixLabels:
    def test_duplicate_trade_ids_are_namespaced(self):
        df = _make_df([
            {"trade_id": "TV_1", "strategy_name": "ATR_ETH", "regime": "trend_up",
             "entry_time": "2026-01-05 10:00:00"},
            {"trade_id": "TV_1", "strategy_name": "BAW_ETH", "regime": "trend_up",
             "entry_time": "2026-01-05 11:00:00"},
        ])
        fixed = normalize_duplicate_trade_ids(df)
        assert fixed == 2
        assert df["trade_id"].tolist() == ["ATR_ETH_TV_1", "BAW_ETH_TV_1"]
        assert df["original_trade_id"].tolist() == ["TV_1", "TV_1"]

    def test_unique_trade_ids_are_not_changed(self):
        df = _make_df([
            {"trade_id": "TV_1", "strategy_name": "ATR_ETH"},
            {"trade_id": "TV_2", "strategy_name": "ATR_ETH"},
        ])
        fixed = normalize_duplicate_trade_ids(df)
        assert fixed == 0
        assert df["trade_id"].tolist() == ["TV_1", "TV_2"]
        assert "original_trade_id" not in df.columns

    def test_missing_label_columns_are_created(self):
        df = _make_df([
            {"trade_id": "T1", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-01-05 10:00:00"},
        ])
        ensure_label_columns(df)
        for col in ["session", "structure_state", "regime_snapshot_id",
                    "volatility_state", "orderflow_state", "macro_state"]:
            assert col in df.columns
            assert df.at[0, col] == "unknown"

    def test_fix_labels_accepts_minimal_core_csv(self):
        df = _make_df([
            {"trade_id": "T1", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-01-05 10:00:00", "pnl_R": 1.0},
        ])
        config = _make_config()
        fixes = fix_labels(df, config)
        assert fixes["session_fixed"] == 1
        assert df.at[0, "session"] == "London"
        assert df.at[0, "structure_state"] == "trend_up"
        assert df.at[0, "regime_snapshot_id"] == "trend_up_20260105"
        assert df.at[0, "pnl_R"] == 1.0

    def test_session_backfill_from_unknown(self):
        df = _make_df([
            {"trade_id": "T1", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-01-05 05:00:00", "session": "unknown",
             "structure_state": "unknown", "regime_snapshot_id": "old_1"},
            {"trade_id": "T2", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-01-05 10:00:00", "session": "unknown",
             "structure_state": "unknown", "regime_snapshot_id": "old_2"},
            {"trade_id": "T3", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-01-05 14:00:00", "session": "unknown",
             "structure_state": "unknown", "regime_snapshot_id": "old_3"},
        ])
        config = _make_config()
        fixes = fix_labels(df, config)
        assert fixes["session_fixed"] == 3
        assert df.at[0, "session"] == "Asia"    # 05:00 UTC
        assert df.at[1, "session"] == "London"   # 10:00 UTC
        assert df.at[2, "session"] == "overlap"   # 14:00 UTC

    def test_session_does_not_overwrite_valid(self):
        df = _make_df([
            {"trade_id": "T1", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-01-05 05:00:00", "session": "NY",  # valid, would be Asia
             "structure_state": "unknown", "regime_snapshot_id": "old_1"},
        ])
        config = _make_config()
        # overwrite_existing defaults to False
        fixes = fix_labels(df, config)
        assert fixes["session_skipped"] == 1
        assert df.at[0, "session"] == "NY"  # unchanged

    def test_structure_state_backfill_from_regime(self):
        df = _make_df([
            {"trade_id": "T1", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-01-05 03:00:00", "session": "Asia",
             "structure_state": "unknown", "regime_snapshot_id": "old_1"},
        ])
        config = _make_config()
        fixes = fix_labels(df, config)
        assert fixes["structure_state_fixed"] == 1
        assert df.at[0, "structure_state"] == "trend_up"

    def test_structure_state_does_not_overwrite_valid(self):
        df = _make_df([
            {"trade_id": "T1", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-01-05 03:00:00", "session": "Asia",
             "structure_state": "range",  # valid value, not trend_up
             "regime_snapshot_id": "old_1"},
        ])
        config = _make_config()
        fixes = fix_labels(df, config)
        assert fixes["structure_state_skipped"] == 1
        assert df.at[0, "structure_state"] == "range"  # unchanged

    def test_snapshot_normalized(self):
        df = _make_df([
            {"trade_id": "T1", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-05-13 14:30:00", "session": "Asia",
             "structure_state": "unknown", "regime_snapshot_id": "trend_up_uu_2026051314"},
        ])
        config = _make_config()
        fixes = fix_labels(df, config)
        assert fixes["snapshot_normalized"] == 1
        assert df.at[0, "regime_snapshot_id"] == "trend_up_20260513"

    def test_original_snapshot_preserved(self):
        df = _make_df([
            {"trade_id": "T1", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-05-13 14:30:00", "session": "Asia",
             "structure_state": "unknown", "regime_snapshot_id": "trend_up_uu_2026051314"},
        ])
        config = _make_config()
        config.regime_snapshot_normalization.preserve_original_column = "original_regime_snapshot_id"
        fix_labels(df, config)
        assert "original_regime_snapshot_id" in df.columns
        assert df.at[0, "original_regime_snapshot_id"] == "trend_up_uu_2026051314"

    def test_pnl_and_core_fields_unchanged(self):
        df = _make_df([
            {"trade_id": "T99", "strategy_name": "Mystrat", "regime": "range",
             "entry_time": "2026-03-15 10:00:00", "session": "unknown",
             "structure_state": "unknown", "regime_snapshot_id": "old_x",
             "pnl_R": 3.14, "pnl_usd": 628.0, "direction": "long"},
        ])
        original = df.copy()
        config = _make_config()
        fix_labels(df, config)
        
        assert df.at[0, "trade_id"] == original.at[0, "trade_id"]
        assert df.at[0, "strategy_name"] == original.at[0, "strategy_name"]
        assert df.at[0, "regime"] == original.at[0, "regime"]
        assert df.at[0, "pnl_R"] == original.at[0, "pnl_R"]
        assert df.at[0, "pnl_usd"] == original.at[0, "pnl_usd"]
        assert df.at[0, "direction"] == original.at[0, "direction"]


class TestQualityReport:
    def test_report_generated(self):
        original = _make_df([
            {"trade_id": "T1", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-01-05 03:00:00", "session": "unknown",
             "structure_state": "unknown", "regime_snapshot_id": "old_1"},
        ])
        fixed = original.copy()
        config = _make_config()
        fixes = fix_labels(fixed, config)
        
        report = build_quality_report(original, fixed, fixes, config)
        assert "Label Quality Report" in report
        assert "session" in report.lower()
        assert "structure_state" in report.lower()
        assert "regime_snapshot_id" in report.lower() or "regime_snapshot" in report.lower()


class TestValidateColumns:
    def test_missing_columns_raises_error(self):
        df = _make_df([{"trade_id": "T1"}])
        with pytest.raises(ValueError, match="Missing"):
            validate_required_columns(df, ["trade_id", "strategy_name"])

    def test_all_columns_present_passes(self):
        df = _make_df([{"trade_id": "T1", "strategy_name": "S1", "regime": "R1", "entry_time": "2026-01-01 00:00:00"}])
        validate_required_columns(df, ["trade_id", "strategy_name", "regime", "entry_time"])


# ============================================================
# P2-5: Quality Score / Readiness Tests
# ============================================================

from strategy_enable_system.label_quality import (
    compute_field_quality,
    classify_readiness,
    compute_all_field_qualities,
    compute_snapshot_granularity,
    compute_readiness,
    build_quality_report,
    build_quality_summary_csv,
)
from strategy_enable_system.config import ReadinessConfig


def _make_lq_config():
    c = LabelQualityConfig()
    c.enabled = True
    c.readiness = ReadinessConfig()
    return c


class TestQualityScore:
    def test_perfect_score(self):
        df = _make_df([{"session": "Asia"}, {"session": "London"}])
        q = compute_field_quality(df, "session", {})
        assert q["unknown_after"] == 0
        assert q["unknown_ratio_after"] == 0.0
        assert q["quality_score_after"] == 100.0

    def test_half_unknown(self):
        df = _make_df([{"session": "Asia"}, {"session": "unknown"}])
        q = compute_field_quality(df, "session", {})
        assert q["unknown_after"] == 1
        assert q["unknown_ratio_after"] == 0.5
        assert q["quality_score_after"] == 50.0

    def test_all_unknown_empty_string(self):
        df = _make_df([{"session": ""}, {"session": ""}])
        q = compute_field_quality(df, "session", {})
        assert q["unknown_ratio_after"] == 1.0
        assert q["quality_score_after"] == 0.0

    def test_nan_values(self):
        df = _make_df([{"session": float('nan')}, {"session": "Asia"}])
        q = compute_field_quality(df, "session", {})
        assert q["unknown_ratio_after"] == 0.5


class TestReadinessStatus:
    def test_pass(self):
        assert classify_readiness(0.05, ReadinessConfig()) == "PASS"
        assert classify_readiness(0.20, ReadinessConfig()) == "PASS"

    def test_warn(self):
        assert classify_readiness(0.25, ReadinessConfig()) == "WARN"
        assert classify_readiness(0.50, ReadinessConfig()) == "WARN"

    def test_block(self):
        assert classify_readiness(0.55, ReadinessConfig()) == "BLOCK"
        assert classify_readiness(1.0, ReadinessConfig()) == "BLOCK"


class TestSnapshotGranularity:
    def test_too_fragmented_warns(self):
        # 10 trades, 9 unique snapshots → ratio=0.9 > 0.7
        original = _make_df([
            {"regime_snapshot_id": f"snap_{i}"} for i in range(10)
        ])
        original["entry_time"] = "2026-01-01"
        original["regime"] = "trend_up"
        fixed = original.copy()
        config = _make_lq_config()
        diag = compute_snapshot_granularity(original, fixed, config)
        assert diag["diagnosis"] == "WARN"
        assert any("碎片化" in r for r in diag["reasons"])

    def test_low_avg_trades_warns(self):
        # 5 trades, 5 unique → avg = 1.0 < 2.0
        original = _make_df([
            {"regime_snapshot_id": f"snap_{i}"} for i in range(5)
        ])
        original["entry_time"] = "2026-01-01"
        original["regime"] = "trend_up"
        fixed = original.copy()
        config = _make_lq_config()
        diag = compute_snapshot_granularity(original, fixed, config)
        assert diag["average_trades_per_snapshot_after"] < 2.0


class TestOverallReadiness:
    def test_classifier_blocked_when_fields_block(self):
        fq = {
            "structure_state": {"readiness_status": "PASS"},
            "volatility_state": {"readiness_status": "BLOCK"},
            "orderflow_state": {"readiness_status": "BLOCK"},
            "macro_state": {"readiness_status": "BLOCK"},
        }
        snap = {"diagnosis": "PASS", "reasons": []}
        config = _make_lq_config()
        r = compute_readiness(fq, snap, config)
        assert r["automatic_regime_classifier"]["readiness"] == "BLOCK"
        assert r["market_opportunity_score"]["readiness"] == "BLOCK"

    def test_market_opportunity_warn(self):
        fq = {
            "volatility_state": {"readiness_status": "WARN"},
            "orderflow_state": {"readiness_status": "BLOCK"},
            "macro_state": {"readiness_status": "PASS"},
        }
        snap = {"diagnosis": "PASS", "reasons": []}
        config = _make_lq_config()
        r = compute_readiness(fq, snap, config)
        assert r["market_opportunity_score"]["readiness"] == "BLOCK"  # BLOCK trumps WARN

    def test_layered_warn_when_snapshot_warns(self):
        fq = {
            "structure_state": {"readiness_status": "PASS"},
            "volatility_state": {"readiness_status": "PASS"},
            "orderflow_state": {"readiness_status": "PASS"},
            "macro_state": {"readiness_status": "PASS"},
        }
        snap = {"diagnosis": "WARN", "reasons": ["碎片化"]}
        config = _make_lq_config()
        r = compute_readiness(fq, snap, config)
        assert r["layered_regime_analysis"]["readiness"] == "WARN"


class TestReportEnhancement:
    def test_summary_csv_has_new_columns(self):
        original = _make_df([
            {"trade_id": "T1", "session": "Asia", "structure_state": "trend_up",
             "volatility_state": "low", "orderflow_state": "unknown",
             "macro_state": "unknown", "regime_snapshot_id": "snap_1",
             "entry_time": "2026-01-05 10:00:00", "regime": "trend_up"}
        ])
        fixed = original.copy()
        config = _make_lq_config()
        fixes = fix_labels(fixed, config)
        fq = compute_all_field_qualities(original, fixed, fixes, config)
        summary = build_quality_summary_csv(original, fixed, fixes, fq)
        
        expected_cols = ["field", "total_rows", "unknown_before", "unknown_after",
                         "unknown_ratio_before", "unknown_ratio_after",
                         "quality_score_before", "quality_score_after",
                         "fixed_count", "readiness_status", "notes"]
        for col in expected_cols:
            assert col in summary.columns, f"Missing column: {col}"

    def test_report_has_new_sections(self):
        original = _make_df([
            {"trade_id": "T1", "session": "Asia", "structure_state": "trend_up",
             "volatility_state": "low", "orderflow_state": "unknown",
             "macro_state": "unknown", "regime_snapshot_id": "old_1",
             "entry_time": "2026-01-05 10:00:00", "regime": "trend_up"}
        ])
        fixed = original.copy()
        config = _make_lq_config()
        fixes = fix_labels(fixed, config)
        fq = compute_all_field_qualities(original, fixed, fixes, config)
        snap = compute_snapshot_granularity(original, fixed, config)
        r = compute_readiness(fq, snap, config)
        report = build_quality_report(original, fixed, fixes, config, fq, snap, r)
        
        assert "Field Quality Scores" in report
        assert "Regime Snapshot Granularity" in report
        assert "P2 Readiness" in report
        assert "Automatic Regime Classifier" in report
        assert "Market Opportunity Score" in report
        assert "Layered Regime Analysis" in report
        assert "PASS" in report or "WARN" in report or "BLOCK" in report

    def test_label_quality_does_not_change_core_fields(self):
        df = _make_df([
            {"trade_id": "T99", "strategy_name": "Mystrat", "regime": "range",
             "entry_time": "2026-03-15 10:00:00", "session": "unknown",
             "structure_state": "unknown", "regime_snapshot_id": "old_x",
             "pnl_R": 99.99, "pnl_usd": 19998.0, "direction": "long"},
        ])
        original = df.copy()
        config = _make_lq_config()
        fix_labels(df, config)
        
        for col in ["trade_id", "strategy_name", "regime", "pnl_R", "pnl_usd", "direction"]:
            assert df.at[0, col] == original.at[0, col], f"{col} changed"


# ============================================================
# P2-9: CLI Override Tests (--input / --output-dir)
# ============================================================

class TestLabelQualityCLIOverrides:
    """Tests for --input and --output-dir CLI parameter overrides added in P2-9."""

    def _make_minimal_csv(self, path: str):
        """Write a minimal valid trades CSV to path."""
        import csv
        rows = [
            {"trade_id": "T1", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-01-05 10:00:00", "exit_time": "2026-01-05 12:00:00",
             "pnl_R": 1.5, "session": "London", "structure_state": "trend_up",
             "regime_snapshot_id": "trend_up_20260105", "volatility_state": "low",
             "orderflow_state": "unknown", "macro_state": "unknown"},
            {"trade_id": "T2", "strategy_name": "S1", "regime": "trend_up",
             "entry_time": "2026-01-06 14:00:00", "exit_time": "2026-01-06 16:00:00",
             "pnl_R": -0.5, "session": "overlap", "structure_state": "trend_up",
             "regime_snapshot_id": "trend_up_20260106", "volatility_state": "low",
             "orderflow_state": "unknown", "macro_state": "unknown"},
        ]
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    def test_input_override_reads_custom_csv(self):
        """--input override: run() should read from the overridden path, not config.input_path."""
        import yaml
        from strategy_enable_system.label_quality import run

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a test CSV to a non-default location
            custom_csv = os.path.join(tmpdir, "custom_input.csv")
            self._make_minimal_csv(custom_csv)

            # Create a minimal config that points to a DIFFERENT (non-existent) path
            config_data = {
                "input_path": [os.path.join(tmpdir, "nonexistent.csv")],  # would fail without override
                "output_dir": tmpdir,
                "min_trades": 1,
                "recent_trade_window": 5,
                "monte_carlo": {"iterations": 100, "method": "bootstrap",
                                "drawdown_threshold_R": 10, "random_seed": 42},
                "market_opportunity": {"enabled": False, "default_score": 1.0},
                "edge_concentration": {"enabled": False},
                "score_weights": {"regime_edge": 0.40, "recent_health": 0.15,
                                  "monte_carlo_stability": 0.25, "risk_control": 0.20},
                "score_thresholds": {"strong_enable": 80, "medium_enable": 65, "weak_enable": 50},
                "metric_caps": {"max_profit_factor": 10.0, "max_payoff_ratio": 10.0},
                "review_rules": {"losing_streak_review_threshold": 4,
                                 "mc_drawdown_probability_review_threshold": 0.25,
                                 "low_sample_requires_review": True,
                                 "edge_concentration_requires_review": True},
                "filters": {"symbol": [], "strategy_name": [], "date_start": None, "date_end": None},
                "validation": {"duplicate_trade_id": "warning",
                               "require_exit_after_entry": True,
                               "fill_missing_state_with": "unknown"},
                "label_quality": {
                    "enabled": True,
                    "output_dir": tmpdir,
                    "cleaned_csv_name": "cleaned_out.csv",
                    "preserve_original_regime_snapshot_id": True,
                    "session_backfill": {"enabled": True, "overwrite_existing": False,
                                        "timezone": "UTC",
                                        "rules": {"Asia": [0, 9], "London": [7, 16],
                                                  "NY": [12, 21], "overlap": [12, 16]}},
                    "structure_state_backfill": {"enabled": True, "overwrite_existing": False,
                                                "source_field": "regime"},
                    "regime_snapshot_normalization": {"enabled": False, "overwrite_existing": False,
                                                     "preserve_original_column": "original_regime_snapshot_id",
                                                     "format": "{regime}_{YYYYMMDD}"},
                    "readiness": {"unknown_warning_threshold": 0.20,
                                  "unknown_blocking_threshold": 0.50,
                                  "snapshot_unique_ratio_too_high": 0.70,
                                  "snapshot_unique_ratio_too_low": 0.05,
                                  "snapshot_min_avg_trades_per_snapshot": 2},
                },
            }
            config_path = os.path.join(tmpdir, "test_config.yaml")
            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            # Should succeed because --input override points to the real CSV
            run(config_path, input_override=custom_csv)

            # Verify output was created
            cleaned_out = os.path.join(tmpdir, "cleaned_out.csv")
            assert os.path.exists(cleaned_out), "Cleaned CSV not created"
            df_out = pd.read_csv(cleaned_out)
            assert len(df_out) == 2, f"Expected 2 rows, got {len(df_out)}"

    def test_output_dir_override_writes_to_custom_dir(self):
        """--output-dir override: run() should write outputs to the overridden directory."""
        import yaml
        from strategy_enable_system.label_quality import run

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a test CSV to the default location
            default_csv = os.path.join(tmpdir, "default_input.csv")
            self._make_minimal_csv(default_csv)

            # Custom output directory (different from config)
            custom_out_dir = os.path.join(tmpdir, "custom_output")

            config_data = {
                "input_path": [default_csv],
                "output_dir": tmpdir,
                "min_trades": 1,
                "recent_trade_window": 5,
                "monte_carlo": {"iterations": 100, "method": "bootstrap",
                                "drawdown_threshold_R": 10, "random_seed": 42},
                "market_opportunity": {"enabled": False, "default_score": 1.0},
                "edge_concentration": {"enabled": False},
                "score_weights": {"regime_edge": 0.40, "recent_health": 0.15,
                                  "monte_carlo_stability": 0.25, "risk_control": 0.20},
                "score_thresholds": {"strong_enable": 80, "medium_enable": 65, "weak_enable": 50},
                "metric_caps": {"max_profit_factor": 10.0, "max_payoff_ratio": 10.0},
                "review_rules": {"losing_streak_review_threshold": 4,
                                 "mc_drawdown_probability_review_threshold": 0.25,
                                 "low_sample_requires_review": True,
                                 "edge_concentration_requires_review": True},
                "filters": {"symbol": [], "strategy_name": [], "date_start": None, "date_end": None},
                "validation": {"duplicate_trade_id": "warning",
                               "require_exit_after_entry": True,
                               "fill_missing_state_with": "unknown"},
                "label_quality": {
                    "enabled": True,
                    "output_dir": os.path.join(tmpdir, "default_output"),  # config output (should NOT be used)
                    "cleaned_csv_name": "cleaned_out.csv",
                    "preserve_original_regime_snapshot_id": True,
                    "session_backfill": {"enabled": True, "overwrite_existing": False,
                                        "timezone": "UTC",
                                        "rules": {"Asia": [0, 9], "London": [7, 16],
                                                  "NY": [12, 21], "overlap": [12, 16]}},
                    "structure_state_backfill": {"enabled": True, "overwrite_existing": False,
                                                "source_field": "regime"},
                    "regime_snapshot_normalization": {"enabled": False, "overwrite_existing": False,
                                                     "preserve_original_column": "original_regime_snapshot_id",
                                                     "format": "{regime}_{YYYYMMDD}"},
                    "readiness": {"unknown_warning_threshold": 0.20,
                                  "unknown_blocking_threshold": 0.50,
                                  "snapshot_unique_ratio_too_high": 0.70,
                                  "snapshot_unique_ratio_too_low": 0.05,
                                  "snapshot_min_avg_trades_per_snapshot": 2},
                },
            }
            config_path = os.path.join(tmpdir, "test_config.yaml")
            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            # Run with custom output dir override
            run(config_path, output_dir_override=custom_out_dir)

            # Output should be in custom_out_dir, NOT in default_output
            custom_cleaned = os.path.join(custom_out_dir, "cleaned_out.csv")
            custom_report = os.path.join(custom_out_dir, "label_quality_report.md")
            custom_summary = os.path.join(custom_out_dir, "label_quality_summary.csv")

            assert os.path.exists(custom_cleaned), "Cleaned CSV not in custom_out_dir"
            assert os.path.exists(custom_report), "Report not in custom_out_dir"
            assert os.path.exists(custom_summary), "Summary not in custom_out_dir"

            # Default output dir should NOT have been created
            default_out = os.path.join(tmpdir, "default_output")
            assert not os.path.exists(default_out), "Default output_dir should NOT have been created"

    def test_no_override_uses_config_defaults(self):
        """When no override is provided, run() behaves exactly as before P2-9 changes."""
        import yaml
        from strategy_enable_system.label_quality import run

        with tempfile.TemporaryDirectory() as tmpdir:
            default_csv = os.path.join(tmpdir, "default_input.csv")
            self._make_minimal_csv(default_csv)
            default_out = os.path.join(tmpdir, "default_output")

            config_data = {
                "input_path": [default_csv],
                "output_dir": tmpdir,
                "min_trades": 1,
                "recent_trade_window": 5,
                "monte_carlo": {"iterations": 100, "method": "bootstrap",
                                "drawdown_threshold_R": 10, "random_seed": 42},
                "market_opportunity": {"enabled": False, "default_score": 1.0},
                "edge_concentration": {"enabled": False},
                "score_weights": {"regime_edge": 0.40, "recent_health": 0.15,
                                  "monte_carlo_stability": 0.25, "risk_control": 0.20},
                "score_thresholds": {"strong_enable": 80, "medium_enable": 65, "weak_enable": 50},
                "metric_caps": {"max_profit_factor": 10.0, "max_payoff_ratio": 10.0},
                "review_rules": {"losing_streak_review_threshold": 4,
                                 "mc_drawdown_probability_review_threshold": 0.25,
                                 "low_sample_requires_review": True,
                                 "edge_concentration_requires_review": True},
                "filters": {"symbol": [], "strategy_name": [], "date_start": None, "date_end": None},
                "validation": {"duplicate_trade_id": "warning",
                               "require_exit_after_entry": True,
                               "fill_missing_state_with": "unknown"},
                "label_quality": {
                    "enabled": True,
                    "output_dir": default_out,  # config output — should be used when no override
                    "cleaned_csv_name": "cleaned_out.csv",
                    "preserve_original_regime_snapshot_id": True,
                    "session_backfill": {"enabled": True, "overwrite_existing": False,
                                        "timezone": "UTC",
                                        "rules": {"Asia": [0, 9], "London": [7, 16],
                                                  "NY": [12, 21], "overlap": [12, 16]}},
                    "structure_state_backfill": {"enabled": True, "overwrite_existing": False,
                                                "source_field": "regime"},
                    "regime_snapshot_normalization": {"enabled": False, "overwrite_existing": False,
                                                     "preserve_original_column": "original_regime_snapshot_id",
                                                     "format": "{regime}_{YYYYMMDD}"},
                    "readiness": {"unknown_warning_threshold": 0.20,
                                  "unknown_blocking_threshold": 0.50,
                                  "snapshot_unique_ratio_too_high": 0.70,
                                  "snapshot_unique_ratio_too_low": 0.05,
                                  "snapshot_min_avg_trades_per_snapshot": 2},
                },
            }
            config_path = os.path.join(tmpdir, "test_config.yaml")
            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            # No overrides → should use config defaults
            run(config_path)

            # Output should be in default_out (from config)
            assert os.path.exists(os.path.join(default_out, "cleaned_out.csv")), \
                "Cleaned CSV not in config default output_dir"
            assert os.path.exists(os.path.join(default_out, "label_quality_report.md")), \
                "Report not in config default output_dir"
