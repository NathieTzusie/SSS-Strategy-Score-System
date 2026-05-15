import os
import textwrap

import pandas as pd
import pytest

from strategy_enable_system.dmc_bridge import (
    DMCBridgeOptions,
    backfill_with_dmc,
    parse_symbol_4h_paths,
)


def _make_fake_dmc(tmp_path):
    root = tmp_path / "fake_dmc"
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
            def bulk_prepare(self, trades):
                pass
            def enrich(self, trade):
                return {"session": "London"}

        class RegimeEnricher:
            def __init__(self, symbol_4h_paths, threshold=None, snapshot_granularity="week"):
                self.snapshot_granularity = snapshot_granularity
            def bulk_prepare(self, trades):
                pass
            def enrich(self, trade):
                trade._regime_cache = "trend_up"
                return {"regime": "trend_up", "regime_snapshot_id": f"trend_up_{self.snapshot_granularity}"}

        class StructureStateEnricher:
            def __init__(self, symbol_4h_paths):
                pass
            def bulk_prepare(self, trades):
                pass
            def enrich(self, trade):
                return {"structure_state": getattr(trade, "_regime_cache", "range")}

        class VolatilityEnricher:
            def __init__(self, symbol_4h_paths):
                pass
            def bulk_prepare(self, trades):
                pass
            def enrich(self, trade):
                return {"volatility_state": "high"}
    """), encoding="utf-8")
    return root


def _make_input_csv(tmp_path):
    input_path = tmp_path / "trades.csv"
    pd.DataFrame({
        "trade_id": ["T1"],
        "strategy_name": ["ATR_ETH_TV"],
        "symbol": ["ETHUSDT"],
        "direction": ["long"],
        "entry_time": ["2026-01-05 10:00:00"],
        "exit_time": ["2026-01-05 12:00:00"],
        "pnl_R": [1.0],
        "pnl_usd": [100.0],
        "session": ["unknown"],
        "regime": ["unknown"],
        "regime_snapshot_id": ["unknown"],
        "structure_state": ["unknown"],
        "volatility_state": ["unknown"],
    }).to_csv(input_path, index=False)
    return input_path


def test_dmc_bridge_backfills_supported_fields(tmp_path):
    dmc_root = _make_fake_dmc(tmp_path)
    input_path = _make_input_csv(tmp_path)
    output_path = tmp_path / "dmc_labeled.csv"

    df = backfill_with_dmc(DMCBridgeOptions(
        input_path=str(input_path),
        output_path=str(output_path),
        dmc_root=str(dmc_root),
        snapshot_granularity="day",
    ))

    assert output_path.exists()
    assert df.loc[0, "session"] == "London"
    assert df.loc[0, "regime"] == "trend_up"
    assert df.loc[0, "regime_snapshot_id"] == "trend_up_day"
    assert df.loc[0, "structure_state"] == "trend_up"
    assert df.loc[0, "volatility_state"] == "high"
    assert df.loc[0, "original_regime"] == "unknown"
    assert os.path.exists(str(output_path).replace(".csv", "_dmc_bridge_report.md"))


def test_dmc_bridge_does_not_overwrite_valid_labels_by_default(tmp_path):
    dmc_root = _make_fake_dmc(tmp_path)
    input_path = _make_input_csv(tmp_path)
    df = pd.read_csv(input_path)
    df.loc[0, "regime"] = "range"
    df.to_csv(input_path, index=False)
    output_path = tmp_path / "dmc_labeled.csv"

    result = backfill_with_dmc(DMCBridgeOptions(
        input_path=str(input_path),
        output_path=str(output_path),
        dmc_root=str(dmc_root),
    ))

    assert result.loc[0, "regime"] == "range"
    assert result.loc[0, "structure_state"] == "trend_up"


def test_dmc_bridge_overwrite_replaces_valid_labels(tmp_path):
    dmc_root = _make_fake_dmc(tmp_path)
    input_path = _make_input_csv(tmp_path)
    df = pd.read_csv(input_path)
    df.loc[0, "regime"] = "range"
    df.to_csv(input_path, index=False)
    output_path = tmp_path / "dmc_labeled.csv"

    result = backfill_with_dmc(DMCBridgeOptions(
        input_path=str(input_path),
        output_path=str(output_path),
        dmc_root=str(dmc_root),
        overwrite=True,
    ))

    assert result.loc[0, "regime"] == "trend_up"
    assert result.loc[0, "original_regime"] == "range"


def test_parse_symbol_4h_paths():
    parsed = parse_symbol_4h_paths(["btcusdt=C:/data/btc.parquet"])
    assert parsed == {"BTCUSDT": "C:/data/btc.parquet"}


def test_parse_symbol_4h_paths_rejects_invalid_value():
    with pytest.raises(ValueError, match="Invalid --symbol-4h-path"):
        parse_symbol_4h_paths(["bad-value"])
