import os
import textwrap
import pandas as pd
import pytest

from strategy_enable_system.tradingview_converter import (
    TradingViewConvertOptions,
    convert_tradingview_csv,
    main as tradingview_main,
    update_config_input_path,
)
from strategy_enable_system.data_loader import _standardize
from strategy_enable_system.config import SSSConfig


def _make_fake_dmc(tmp_path):
    root = tmp_path / "fake_dmc_converter"
    package = root / "trade_engine"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "engine.py").write_text(textwrap.dedent("""
        from dataclasses import dataclass
        from enum import Enum
        import pandas as pd

        class OrderSide(Enum):
            LONG = 1
            SHORT = -1

        @dataclass
        class TradeRecord:
            entry_time: pd.Timestamp
            exit_time: pd.Timestamp = None
            side: OrderSide = None
            total_pnl: float = 0.0
            strategy_id: str = ""
            symbol: str = ""
    """), encoding="utf-8")
    (package / "trade_log.py").write_text(textwrap.dedent("""
        class SessionEnricher:
            def bulk_prepare(self, trades): pass
            def enrich(self, trade): return {"session": "London"}
        class RegimeEnricher:
            def __init__(self, symbol_4h_paths, threshold=None, snapshot_granularity="day"):
                self.snapshot_granularity = snapshot_granularity
            def bulk_prepare(self, trades): pass
            def enrich(self, trade):
                trade._regime_cache = "trend_up"
                return {"regime": "trend_up", "regime_snapshot_id": "trend_up_20260105"}
        class StructureStateEnricher:
            def bulk_prepare(self, trades): pass
            def enrich(self, trade): return {"structure_state": getattr(trade, "_regime_cache", "unknown")}
        class VolatilityEnricher:
            def __init__(self, symbol_4h_paths): pass
            def bulk_prepare(self, trades): pass
            def enrich(self, trade): return {"volatility_state": "medium"}
    """), encoding="utf-8")
    return root


def test_convert_closed_trades_with_risk_usd(tmp_path):
    input_path = tmp_path / "tv_closed.csv"
    output_path = tmp_path / "converted.csv"
    pd.DataFrame({
        "Trade #": [1, 2],
        "Direction": ["Long", "Short"],
        "Entry Time": ["2026-01-01 10:00:00", "2026-01-02 10:00:00"],
        "Exit Time": ["2026-01-01 12:00:00", "2026-01-02 12:00:00"],
        "Profit": ["$200.00", "-100.00"],
    }).to_csv(input_path, index=False)

    df = convert_tradingview_csv(TradingViewConvertOptions(
        input_path=str(input_path),
        output_path=str(output_path),
        strategy_name="TV_Strategy",
        symbol="BTCUSDT",
        regime="trend_up",
        risk_usd=100.0,
    ))

    assert output_path.exists()
    assert df["trade_id"].tolist() == ["TV_1", "TV_2"]
    assert df["direction"].tolist() == ["long", "short"]
    assert df["pnl_R"].tolist() == [2.0, -1.0]
    assert df["strategy_name"].unique().tolist() == ["TV_Strategy"]
    assert df["regime"].unique().tolist() == ["trend_up"]


def test_convert_closed_trades_with_explicit_pnl_r_column(tmp_path):
    input_path = tmp_path / "tv_closed_r.csv"
    output_path = tmp_path / "converted.csv"
    pd.DataFrame({
        "Trade #": [1],
        "Side": ["Buy"],
        "Entry Time": ["2026-01-01 10:00:00"],
        "Exit Time": ["2026-01-01 12:00:00"],
        "Profit": ["$50"],
        "R Multiple": ["1.25"],
    }).to_csv(input_path, index=False)

    df = convert_tradingview_csv(TradingViewConvertOptions(
        input_path=str(input_path),
        output_path=str(output_path),
        strategy_name="TV_Strategy",
        symbol="ETHUSDT",
        pnl_r_column="R Multiple",
    ))

    assert df.loc[0, "pnl_R"] == 1.25
    assert df.loc[0, "pnl_usd"] == 50.0


def test_convert_paired_entry_exit_rows(tmp_path):
    input_path = tmp_path / "tv_paired.csv"
    output_path = tmp_path / "converted.csv"
    pd.DataFrame({
        "Trade #": [1, 1, 2, 2],
        "Type": ["Entry Long", "Exit Long", "Entry Short", "Exit Short"],
        "Date/Time": [
            "2026-01-01 10:00:00",
            "2026-01-01 12:00:00",
            "2026-01-02 10:00:00",
            "2026-01-02 12:00:00",
        ],
        "Profit": ["", "$300", "", "($150)"],
    }).to_csv(input_path, index=False)

    df = convert_tradingview_csv(TradingViewConvertOptions(
        input_path=str(input_path),
        output_path=str(output_path),
        strategy_name="Paired",
        symbol="BTCUSDT",
        risk_usd=150.0,
    ))

    assert df["direction"].tolist() == ["long", "short"]
    assert df["pnl_usd"].tolist() == [300.0, -150.0]
    assert df["pnl_R"].tolist() == [2.0, -1.0]


def test_convert_standard_tradingview_strategy_tester_export(tmp_path):
    input_path = "data/2026-05-15/ATR_BINANCE_ETHUSDT.P_2026-05-15_82d94.csv"
    if not os.path.exists(input_path):
        pytest.skip("standard TradingView fixture not available")

    output_path = tmp_path / "converted_tv_standard.csv"
    df = convert_tradingview_csv(TradingViewConvertOptions(
        input_path=input_path,
        output_path=str(output_path),
        strategy_name="ATR_ETH_TV",
        symbol="ETHUSDT",
        regime="unknown",
        risk_usd=100.0,
    ))

    assert len(df) == 266
    assert output_path.exists()
    assert df.loc[0, "trade_id"] == "TV_1"
    assert df.loc[0, "direction"] == "long"
    assert str(df.loc[0, "entry_time"]) == "2025-01-02 15:30:00"
    assert str(df.loc[0, "exit_time"]) == "2025-01-02 16:33:00"
    assert df.loc[0, "pnl_usd"] == -81.79
    assert round(df.loc[0, "pnl_R"], 4) == -0.8179
    assert df.loc[0, "setup_type"] == "IMP_L"


def test_converter_output_is_data_loader_compatible(tmp_path):
    input_path = tmp_path / "tv_closed.csv"
    output_path = tmp_path / "converted.csv"
    pd.DataFrame({
        "Trade #": [1],
        "Direction": ["Long"],
        "Entry Time": ["2026-01-01 10:00:00"],
        "Exit Time": ["2026-01-01 12:00:00"],
        "Profit": ["$100"],
    }).to_csv(input_path, index=False)

    converted = convert_tradingview_csv(TradingViewConvertOptions(
        input_path=str(input_path),
        output_path=str(output_path),
        strategy_name="Compat",
        symbol="BTCUSDT",
        regime="range",
        risk_usd=100.0,
    ))

    config = SSSConfig()
    config.input_path = [str(output_path)]
    loaded = _standardize(converted, config)
    assert len(loaded) == 1
    assert loaded.loc[0, "pnl_R"] == 1.0


def test_requires_risk_or_pnl_r_column(tmp_path):
    input_path = tmp_path / "tv_closed.csv"
    output_path = tmp_path / "converted.csv"
    pd.DataFrame({
        "Trade #": [1],
        "Direction": ["Long"],
        "Entry Time": ["2026-01-01 10:00:00"],
        "Exit Time": ["2026-01-01 12:00:00"],
        "Profit": ["$100"],
    }).to_csv(input_path, index=False)

    with pytest.raises(ValueError, match="pnl_R requires"):
        convert_tradingview_csv(TradingViewConvertOptions(
            input_path=str(input_path),
            output_path=str(output_path),
            strategy_name="NoRisk",
            symbol="BTCUSDT",
        ))


def test_rejects_unpaired_trade(tmp_path):
    input_path = tmp_path / "tv_bad_paired.csv"
    output_path = tmp_path / "converted.csv"
    pd.DataFrame({
        "Trade #": [1],
        "Type": ["Entry Long"],
        "Date/Time": ["2026-01-01 10:00:00"],
        "Profit": [""],
    }).to_csv(input_path, index=False)

    with pytest.raises(ValueError, match="both entry and exit"):
        convert_tradingview_csv(TradingViewConvertOptions(
            input_path=str(input_path),
            output_path=str(output_path),
            strategy_name="Bad",
            symbol="BTCUSDT",
            risk_usd=100.0,
            format="paired",
        ))


def test_cli_writes_csv_and_report(tmp_path):
    input_path = tmp_path / "tv_closed.csv"
    output_path = tmp_path / "converted.csv"
    pd.DataFrame({
        "Trade #": [1],
        "Direction": ["Short"],
        "Entry Time": ["2026-01-01 10:00:00"],
        "Exit Time": ["2026-01-01 12:00:00"],
        "Profit": ["-50"],
    }).to_csv(input_path, index=False)

    rc = tradingview_main([
        "--input", str(input_path),
        "--output", str(output_path),
        "--strategy-name", "CLI",
        "--symbol", "ETHUSDT",
        "--risk-usd", "50",
    ])

    assert rc == 0
    assert output_path.exists()
    assert os.path.exists(str(output_path).replace(".csv", "_conversion_report.md"))


def test_apply_label_quality_writes_cleaned_csv(tmp_path):
    input_path = tmp_path / "tv_closed.csv"
    output_path = tmp_path / "converted.csv"
    cleaned_path = tmp_path / "converted_cleaned.csv"
    pd.DataFrame({
        "Trade #": [1],
        "Direction": ["Long"],
        "Entry Time": ["2026-01-05 10:00:00"],
        "Exit Time": ["2026-01-05 12:00:00"],
        "Profit": ["$100"],
    }).to_csv(input_path, index=False)

    convert_tradingview_csv(TradingViewConvertOptions(
        input_path=str(input_path),
        output_path=str(output_path),
        cleaned_output_path=str(cleaned_path),
        strategy_name="AutoClean",
        symbol="BTCUSDT",
        regime="range",
        risk_usd=100.0,
        apply_label_quality=True,
    ))

    cleaned = pd.read_csv(cleaned_path)
    assert cleaned_path.exists()
    assert cleaned.loc[0, "session"] != "unknown"
    assert cleaned.loc[0, "structure_state"] == "range"
    assert cleaned.loc[0, "regime_snapshot_id"] == "range_20260105"


def test_cli_apply_label_quality_writes_default_cleaned_csv(tmp_path):
    input_path = tmp_path / "tv_closed.csv"
    output_path = tmp_path / "converted.csv"
    pd.DataFrame({
        "Trade #": [1],
        "Direction": ["Short"],
        "Entry Time": ["2026-01-05 14:00:00"],
        "Exit Time": ["2026-01-05 18:00:00"],
        "Profit": ["-50"],
    }).to_csv(input_path, index=False)

    rc = tradingview_main([
        "--input", str(input_path),
        "--output", str(output_path),
        "--strategy-name", "CLI",
        "--symbol", "ETHUSDT",
        "--risk-usd", "50",
        "--apply-label-quality",
    ])

    cleaned_path = tmp_path / "converted_cleaned.csv"
    report_path = tmp_path / "converted_conversion_report.md"
    assert rc == 0
    assert cleaned_path.exists()
    assert "Label Quality Auto-Fix" in report_path.read_text(encoding="utf-8")


def test_apply_enrichment_writes_cleaned_and_enriched_csv(tmp_path):
    input_path = tmp_path / "tv_closed.csv"
    output_path = tmp_path / "converted.csv"
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    pd.DataFrame({
        "Trade #": [1],
        "Direction": ["Long"],
        "Entry Time": ["2026-01-05 10:00:00"],
        "Exit Time": ["2026-01-05 12:00:00"],
        "Profit": ["$100"],
    }).to_csv(input_path, index=False)
    pd.DataFrame({
        "datetime_utc": ["2026-01-04", "2026-01-05"],
        "close": [100.0, 104.0],
    }).to_csv(processed_dir / "BTC_oi_agg.csv", index=False)
    pd.DataFrame({
        "datetime_utc": ["2026-01-05"],
        "close": [0.0002],
    }).to_csv(processed_dir / "BTC_funding_oiw.csv", index=False)

    convert_tradingview_csv(TradingViewConvertOptions(
        input_path=str(input_path),
        output_path=str(output_path),
        strategy_name="AutoEnrich",
        symbol="BTCUSDT",
        regime="range",
        risk_usd=100.0,
        apply_enrichment=True,
        enrichment_processed_dir=str(processed_dir),
    ))

    cleaned_path = tmp_path / "converted_cleaned.csv"
    enriched_path = tmp_path / "converted_enriched.csv"
    audit_path = tmp_path / "converted_enrichment_audit_report.md"
    report_path = tmp_path / "converted_conversion_report.md"
    enriched = pd.read_csv(enriched_path)
    assert cleaned_path.exists()
    assert enriched_path.exists()
    assert audit_path.exists()
    assert enriched.loc[0, "session"] != "unknown"
    assert enriched.loc[0, "oi_state"] == "rising"
    assert enriched.loc[0, "funding_state"] == "positive"
    assert "Label Enrichment Auto-Fill" in report_path.read_text(encoding="utf-8")


def test_update_config_input_path_appends_without_duplicate(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        '# config\ninput_path:\n  - "data/existing.csv"\n\noutput_dir: "outputs"\n',
        encoding="utf-8",
    )

    changed = update_config_input_path(str(config_path), "data/new.csv")
    unchanged = update_config_input_path(str(config_path), "data/new.csv")
    text = config_path.read_text(encoding="utf-8")

    assert changed is True
    assert unchanged is False
    assert text.count('"data/new.csv"') == 1
    assert 'output_dir: "outputs"' in text


def test_cli_update_config_uses_converted_csv(tmp_path):
    input_path = tmp_path / "tv_closed.csv"
    output_path = tmp_path / "converted.csv"
    config_path = tmp_path / "config.yaml"
    config_path.write_text('input_path:\n  - "data/existing.csv"\n', encoding="utf-8")
    pd.DataFrame({
        "Trade #": [1],
        "Direction": ["Long"],
        "Entry Time": ["2026-01-05 10:00:00"],
        "Exit Time": ["2026-01-05 12:00:00"],
        "Profit": ["$100"],
    }).to_csv(input_path, index=False)

    rc = tradingview_main([
        "--input", str(input_path),
        "--output", str(output_path),
        "--strategy-name", "CLI",
        "--symbol", "BTCUSDT",
        "--risk-usd", "100",
        "--update-config-input",
        "--config", str(config_path),
    ])

    assert rc == 0
    assert str(output_path).replace("\\", "/") in config_path.read_text(encoding="utf-8")


def test_cli_update_config_uses_enriched_csv_when_enrichment_enabled(tmp_path):
    input_path = tmp_path / "tv_closed.csv"
    output_path = tmp_path / "converted.csv"
    enriched_path = tmp_path / "converted_enriched.csv"
    config_path = tmp_path / "config.yaml"
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    config_path.write_text('input_path:\n  - "data/existing.csv"\n', encoding="utf-8")
    pd.DataFrame({
        "Trade #": [1],
        "Direction": ["Long"],
        "Entry Time": ["2026-01-05 10:00:00"],
        "Exit Time": ["2026-01-05 12:00:00"],
        "Profit": ["$100"],
    }).to_csv(input_path, index=False)
    pd.DataFrame({
        "datetime_utc": ["2026-01-04", "2026-01-05"],
        "close": [100.0, 104.0],
    }).to_csv(processed_dir / "BTC_oi_agg.csv", index=False)

    rc = tradingview_main([
        "--input", str(input_path),
        "--output", str(output_path),
        "--strategy-name", "CLI",
        "--symbol", "BTCUSDT",
        "--risk-usd", "100",
        "--apply-enrichment",
        "--enrichment-processed-dir", str(processed_dir),
        "--enriched-output", str(enriched_path),
        "--update-config-input",
        "--config", str(config_path),
    ])

    text = config_path.read_text(encoding="utf-8")
    assert rc == 0
    assert str(enriched_path).replace("\\", "/") in text
    assert str(output_path).replace("\\", "/") not in text


def test_cli_apply_dmc_labels_writes_dmc_labeled_csv(tmp_path):
    dmc_root = _make_fake_dmc(tmp_path)
    input_path = tmp_path / "tv_closed.csv"
    output_path = tmp_path / "converted.csv"
    pd.DataFrame({
        "Trade #": [1],
        "Direction": ["Long"],
        "Entry Time": ["2026-01-05 10:00:00"],
        "Exit Time": ["2026-01-05 12:00:00"],
        "Profit": ["$100"],
    }).to_csv(input_path, index=False)

    rc = tradingview_main([
        "--input", str(input_path),
        "--output", str(output_path),
        "--strategy-name", "CLI",
        "--symbol", "BTCUSDT",
        "--risk-usd", "100",
        "--apply-dmc-labels",
        "--dmc-root", str(dmc_root),
    ])

    dmc_path = tmp_path / "converted_dmc_labeled.csv"
    report_path = tmp_path / "converted_conversion_report.md"
    labeled = pd.read_csv(dmc_path)
    assert rc == 0
    assert dmc_path.exists()
    assert labeled.loc[0, "regime"] == "trend_up"
    assert labeled.loc[0, "volatility_state"] == "medium"
    assert "DMC Bridge Labels" in report_path.read_text(encoding="utf-8")


def test_cli_update_config_uses_dmc_csv_when_dmc_enabled(tmp_path):
    dmc_root = _make_fake_dmc(tmp_path)
    input_path = tmp_path / "tv_closed.csv"
    output_path = tmp_path / "converted.csv"
    config_path = tmp_path / "config.yaml"
    config_path.write_text('input_path:\n  - "data/existing.csv"\n', encoding="utf-8")
    pd.DataFrame({
        "Trade #": [1],
        "Direction": ["Long"],
        "Entry Time": ["2026-01-05 10:00:00"],
        "Exit Time": ["2026-01-05 12:00:00"],
        "Profit": ["$100"],
    }).to_csv(input_path, index=False)

    rc = tradingview_main([
        "--input", str(input_path),
        "--output", str(output_path),
        "--strategy-name", "CLI",
        "--symbol", "BTCUSDT",
        "--risk-usd", "100",
        "--apply-dmc-labels",
        "--dmc-root", str(dmc_root),
        "--update-config-input",
        "--config", str(config_path),
    ])

    text = config_path.read_text(encoding="utf-8")
    assert rc == 0
    assert str(tmp_path / "converted_dmc_labeled.csv").replace("\\", "/") in text
