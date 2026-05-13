"""
Unit tests for Strategy Enable Score System v1.1 - Monte Carlo.
"""
import pytest
import pandas as pd
import numpy as np

from strategy_enable_system.monte_carlo import run_monte_carlo
from strategy_enable_system.config import SSSConfig


def _make_config(seed=42, iterations=1000, method="bootstrap"):
    config = SSSConfig()
    config.input_path = ["data/test.csv"]
    config.monte_carlo.iterations = iterations
    config.monte_carlo.method = method
    config.monte_carlo.random_seed = seed
    config.monte_carlo.drawdown_threshold_R = 10
    return config


def _make_trades(pnl_list, strategy="S1", regime="trend_up"):
    import datetime
    rows = []
    base = datetime.datetime(2026, 1, 1, 10, 0, 0)
    for i, pnl in enumerate(pnl_list):
        rows.append({
            "trade_id": f"T{i+1}",
            "strategy_name": strategy,
            "symbol": "BTCUSDT",
            "direction": "long",
            "entry_time": base + datetime.timedelta(days=i),
            "exit_time": base + datetime.timedelta(days=i, hours=4),
            "pnl_R": pnl,
            "pnl_usd": 0,
            "session": "London",
            "regime": regime,
            "regime_snapshot_id": f"snap_{regime}",
            "structure_state": "trend_up",
            "volatility_state": "medium",
            "orderflow_state": "futures_led",
            "macro_state": "neutral",
            "oi_state": "unknown",
            "cvd_state": "unknown",
            "funding_state": "unknown",
            "coinbase_premium_state": "unknown",
            "etf_flow_state": "unknown",
            "setup_type": "test",
        })
    return pd.DataFrame(rows)


class TestMonteCarlo:
    
    def test_basic_output_shape(self):
        """Test that MC produces expected columns."""
        trades = _make_trades([1.0, -0.5, 2.0, -1.0, 0.5])
        config = _make_config(iterations=100)
        
        result = run_monte_carlo(trades, config)
        
        assert len(result) == 1
        expected_cols = [
            "strategy_name", "regime", "n_trades", "iterations",
            "median_total_R", "p5_total_R", "p95_total_R",
            "median_max_drawdown_R", "p95_max_drawdown_R", "worst_max_drawdown_R",
            "median_longest_losing_streak", "p95_longest_losing_streak",
            "probability_of_negative_total_R", "probability_drawdown_exceeds_threshold",
        ]
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"
    
    def test_seed_reproducibility(self):
        """Test that fixed seed produces identical results."""
        trades = _make_trades([1.0, -0.5, 2.0, -1.0, 0.5, 1.5, -2.0])
        
        config1 = _make_config(seed=42, iterations=500)
        config2 = _make_config(seed=42, iterations=500)
        
        result1 = run_monte_carlo(trades, config1)
        result2 = run_monte_carlo(trades, config2)
        
        for col in result1.columns:
            if col in ["strategy_name", "regime"]:
                continue
            assert result1[col].iloc[0] == result2[col].iloc[0], f"Mismatch in column: {col}"
    
    def test_different_seeds_produce_different_results(self):
        """Test that different seeds produce differing results."""
        trades = _make_trades([1.0, -0.5, 2.0, -1.0, 0.5, 1.5, -2.0, 0.3, -1.2, 2.5])
        
        config1 = _make_config(seed=42, iterations=500)
        config2 = _make_config(seed=99, iterations=500)
        
        result1 = run_monte_carlo(trades, config1)
        result2 = run_monte_carlo(trades, config2)
        
        # At least one metric should differ (very unlikely they're identical)
        diff_found = False
        for col in ["median_total_R", "p95_total_R", "probability_drawdown_exceeds_threshold"]:
            if abs(result1[col].iloc[0] - result2[col].iloc[0]) > 1e-6:
                diff_found = True
                break
        assert diff_found, "Different seeds should produce different results"
    
    def test_shuffle_method(self):
        """Test that shuffle method works."""
        trades = _make_trades([1.0, -0.5, 2.0, -1.0, 0.5])
        config = _make_config(method="shuffle", iterations=100, seed=42)
        
        result = run_monte_carlo(trades, config)
        
        assert len(result) == 1
        assert result["method"].iloc[0] == "shuffle"
    
    def test_probabilities_in_range(self):
        """Test that probability values are between 0 and 1."""
        trades = _make_trades([1.0, -0.5, 2.0, -1.0, 0.5, -2.0, -3.0])
        config = _make_config(iterations=200)
        
        result = run_monte_carlo(trades, config)
        row = result.iloc[0]
        
        assert 0.0 <= row["probability_of_negative_total_R"] <= 1.0
        assert 0.0 <= row["probability_drawdown_exceeds_threshold"] <= 1.0
    
    def test_multiple_groups(self):
        """Test MC with multiple (strategy, regime) groups."""
        import datetime
        rows = []
        base = datetime.datetime(2026, 1, 1, 10, 0, 0)
        
        for i in range(16):
            rows.append({
                "trade_id": f"T{i+1}",
                "strategy_name": f"S{i // 8 + 1}",
                "symbol": "BTCUSDT",
                "direction": "long",
                "entry_time": base + datetime.timedelta(days=i),
                "exit_time": base + datetime.timedelta(days=i, hours=4),
                "pnl_R": (i % 5 - 1) * 0.5,
                "pnl_usd": 0,
                "session": "London",
                "regime": f"regime_{i % 4 // 2 + 1}",
                "regime_snapshot_id": "snap",
                "structure_state": "trend_up",
                "volatility_state": "medium",
                "orderflow_state": "futures_led",
                "macro_state": "neutral",
                "oi_state": "unknown",
                "cvd_state": "unknown",
                "funding_state": "unknown",
                "coinbase_premium_state": "unknown",
                "etf_flow_state": "unknown",
                "setup_type": "test",
            })
        trades = pd.DataFrame(rows)
        config = _make_config(iterations=50, seed=42)
        
        result = run_monte_carlo(trades, config)
        
        # 2 strategies × 2 regimes = 4 groups
        assert len(result) == 4
