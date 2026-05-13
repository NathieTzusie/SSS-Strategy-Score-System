"""
Unit tests for Strategy Enable Score System v1.1 - Data Loader.
"""
import pytest
import os
import tempfile
import pandas as pd
import numpy as np

from strategy_enable_system.config import load_config
from strategy_enable_system.data_loader import load_trades


def _make_config(csv_path, **overrides):
    """Helper to create a minimal config for testing."""
    import yaml
    config_data = {
        "input_path": [csv_path],
        "output_dir": "outputs",
        "min_trades": 30,
        "recent_trade_window": 20,
        "validation": {"fill_missing_state_with": "unknown"},
    }
    config_data.update(overrides)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        return f.name


def _make_csv(rows: list, temp_dir: str) -> str:
    """Write a CSV for testing."""
    if not rows:
        return ""
    df = pd.DataFrame(rows)
    path = os.path.join(temp_dir, "test_trades.csv")
    df.to_csv(path, index=False)
    return path


class TestDataLoader:
    """Tests for data loader module."""
    
    @pytest.fixture
    def tmpdir(self):
        with tempfile.TemporaryDirectory() as d:
            yield d
    
    def test_load_valid_csv(self, tmpdir):
        """Test loading a valid CSV with all core fields."""
        rows = [
            {
                "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
                "direction": "long", "entry_time": "2026-01-01 10:00:00",
                "exit_time": "2026-01-01 14:00:00", "pnl_R": 1.5,
                "pnl_usd": 300, "session": "London", "regime": "trend_up",
                "setup_type": "discount_ob",
            },
            {
                "trade_id": "T2", "strategy_name": "S1", "symbol": "BTCUSDT",
                "direction": "short", "entry_time": "2026-01-02 10:00:00",
                "exit_time": "2026-01-02 14:00:00", "pnl_R": -0.5,
                "pnl_usd": -100, "session": "NY", "regime": "trend_down",
                "setup_type": "premium_fvg",
            },
        ]
        csv_path = _make_csv(rows, tmpdir)
        config_path = _make_config(csv_path)
        
        try:
            config = load_config(config_path)
            df = load_trades(config)
            
            assert len(df) == 2
            assert list(df["trade_id"]) == ["T1", "T2"]
            assert df["pnl_R"].dtype == np.float64
            assert df["direction"].iloc[0] == "long"
            # Optional fields should be filled
            assert "regime_snapshot_id" in df.columns
            assert "structure_state" in df.columns
            assert "orderflow_state" in df.columns
        finally:
            os.unlink(config_path)
    
    def test_missing_core_field_raises_error(self, tmpdir):
        """Test that missing core fields raise ValueError."""
        rows = [
            {
                "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
                # missing direction
                "entry_time": "2026-01-01 10:00:00",
                "exit_time": "2026-01-01 14:00:00", "pnl_R": 1.5,
                "session": "London", "regime": "trend_up",
            },
        ]
        csv_path = _make_csv(rows, tmpdir)
        config_path = _make_config(csv_path)
        
        try:
            config = load_config(config_path)
            with pytest.raises(ValueError, match="Missing|direction"):
                load_trades(config)
        finally:
            os.unlink(config_path)
    
    def test_non_numeric_pnl_R_raises_error(self, tmpdir):
        """Test that non-numeric pnl_R values raise ValueError."""
        rows = [
            {
                "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
                "direction": "long", "entry_time": "2026-01-01 10:00:00",
                "exit_time": "2026-01-01 14:00:00", "pnl_R": "invalid",
                "session": "London", "regime": "trend_up",
            },
        ]
        csv_path = _make_csv(rows, tmpdir)
        config_path = _make_config(csv_path)
        
        try:
            config = load_config(config_path)
            with pytest.raises(ValueError, match="pnl_R"):
                load_trades(config)
        finally:
            os.unlink(config_path)
    
    def test_invalid_time_raises_error(self, tmpdir):
        """Test that unparseable time fields raise ValueError."""
        rows = [
            {
                "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
                "direction": "long", "entry_time": "not_a_date",
                "exit_time": "2026-01-01 14:00:00", "pnl_R": 1.5,
                "session": "London", "regime": "trend_up",
            },
        ]
        csv_path = _make_csv(rows, tmpdir)
        config_path = _make_config(csv_path)
        
        try:
            config = load_config(config_path)
            with pytest.raises(ValueError, match="entry_time"):
                load_trades(config)
        finally:
            os.unlink(config_path)
    
    def test_exit_before_entry_raises_error(self, tmpdir):
        """Test that exit_time < entry_time raises ValueError."""
        rows = [
            {
                "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
                "direction": "long", "entry_time": "2026-01-02 14:00:00",
                "exit_time": "2026-01-01 14:00:00", "pnl_R": 1.5,
                "session": "London", "regime": "trend_up",
            },
        ]
        csv_path = _make_csv(rows, tmpdir)
        config_path = _make_config(csv_path)
        
        try:
            config = load_config(config_path)
            with pytest.raises(ValueError, match="exit_time.*entry_time"):
                load_trades(config)
        finally:
            os.unlink(config_path)
    
    def test_optional_fields_filled_with_unknown(self, tmpdir):
        """Test that missing optional fields are filled with 'unknown'."""
        rows = [
            {
                "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
                "direction": "long", "entry_time": "2026-01-01 10:00:00",
                "exit_time": "2026-01-01 14:00:00", "pnl_R": 1.5,
                "session": "London", "regime": "trend_up",
                # no status fields
            },
        ]
        csv_path = _make_csv(rows, tmpdir)
        config_path = _make_config(csv_path)
        
        try:
            config = load_config(config_path)
            df = load_trades(config)
            
            assert df["volatility_state"].iloc[0] == "unknown"
            assert df["oi_state"].iloc[0] == "unknown"
            assert df["regime_snapshot_id"].iloc[0] == "unknown"
            assert df["structure_state"].iloc[0] == "unknown"
            assert df["orderflow_state"].iloc[0] == "unknown"
            assert df["macro_state"].iloc[0] == "unknown"
        finally:
            os.unlink(config_path)
    
    def test_invalid_direction_raises_error(self, tmpdir):
        """Test that invalid direction values raise ValueError."""
        rows = [
            {
                "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
                "direction": "sideways", "entry_time": "2026-01-01 10:00:00",
                "exit_time": "2026-01-01 14:00:00", "pnl_R": 1.5,
                "session": "London", "regime": "trend_up",
            },
        ]
        csv_path = _make_csv(rows, tmpdir)
        config_path = _make_config(csv_path)
        
        try:
            config = load_config(config_path)
            with pytest.raises(ValueError, match="direction"):
                load_trades(config)
        finally:
            os.unlink(config_path)
    
    def test_missing_regime_raises_error(self, tmpdir):
        """Test that missing regime values raise ValueError."""
        rows = [
            {
                "trade_id": "T1", "strategy_name": "S1", "symbol": "BTCUSDT",
                "direction": "long", "entry_time": "2026-01-01 10:00:00",
                "exit_time": "2026-01-01 14:00:00", "pnl_R": 1.5,
                "session": "London",
                # regime missing
            },
        ]
        csv_path = _make_csv(rows, tmpdir)
        config_path = _make_config(csv_path)
        
        try:
            config = load_config(config_path)
            with pytest.raises(ValueError, match="regime"):
                load_trades(config)
        finally:
            os.unlink(config_path)
