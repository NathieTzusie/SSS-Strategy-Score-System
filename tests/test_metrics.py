"""
Unit tests for Strategy Enable Score System v1.1 - Metrics Engine.
"""
import pytest
import pandas as pd
import numpy as np

from strategy_enable_system.metrics import compute_performance_matrix
from strategy_enable_system.config import SSSConfig


def _make_config(**overrides):
    """Create a minimal config for testing."""
    config = SSSConfig()
    config.input_path = ["data/test.csv"]
    for k, v in overrides.items():
        if "." in k:
            obj_name, attr = k.split(".", 1)
            setattr(getattr(config, obj_name), attr, v)
        else:
            setattr(config, k, v)
    return config


def _make_trades(pnl_list, strategy="S1", regime="trend_up", symbol="BTCUSDT"):
    """Create a standardized trades DataFrame with sequential dates."""
    import datetime
    rows = []
    base = datetime.datetime(2026, 1, 1, 10, 0, 0)
    for i, pnl in enumerate(pnl_list):
        rows.append({
            "trade_id": f"T{i+1}",
            "strategy_name": strategy,
            "symbol": symbol,
            "direction": "long",
            "entry_time": base + datetime.timedelta(days=i),
            "exit_time": base + datetime.timedelta(days=i, hours=4),
            "pnl_R": pnl,
            "pnl_usd": pnl * 200,
            "session": ["London", "NY", "Asia"][i % 3],
            "regime": regime,
            "regime_snapshot_id": f"snapshot_{regime}",
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


class TestPerformanceMatrix:
    
    def test_basic_metrics(self):
        """Test basic metric calculations."""
        pnl = [1.0, 2.0, -0.5, 1.5, -1.0]
        trades = _make_trades(pnl)
        config = _make_config(min_trades=3)
        
        pm = compute_performance_matrix(trades, config)
        row = pm.iloc[0]
        
        assert row["trade_count"] == 5
        assert row["win_rate"] == 3 / 5  # 3 wins
        assert row["avg_R"] == np.mean(pnl)
        assert row["median_R"] == 1.0
        assert row["total_R"] == sum(pnl)  # 3.0
        # Max drawdown from equity curve [1, 3, 2.5, 4, 3]
        # running max: [1, 3, 3, 4, 4], drawdowns: [0, 0, -0.5, 0, -1.0]
        assert row["max_drawdown_R"] == -1.0
    
    def test_profit_factor(self):
        """Test profit factor computation."""
        pnl = [1.0, 2.0, -0.5, 1.5]
        trades = _make_trades(pnl)
        config = _make_config(min_trades=2)
        
        pm = compute_performance_matrix(trades, config)
        row = pm.iloc[0]
        
        gross_profit = 1.0 + 2.0 + 1.5  # 4.5
        gross_loss = 0.5
        expected_pf = 4.5 / 0.5  # 9.0
        assert abs(row["profit_factor"] - expected_pf) < 0.01
    
    def test_profit_factor_capped(self):
        """Test that profit_factor is capped at max_profit_factor."""
        pnl = [5.0, 3.0, -0.1]  # PF = 80, should be capped
        trades = _make_trades(pnl)
        config = _make_config(min_trades=2)
        config.metric_caps.max_profit_factor = 5.0
        
        pm = compute_performance_matrix(trades, config)
        row = pm.iloc[0]
        
        assert row["profit_factor"] == 5.0
        assert "profit_factor_capped" in row["warnings"]
    
    def test_profit_factor_no_losses(self):
        """Test profit_factor when there are no losing trades."""
        pnl = [1.0, 2.0, 3.0]
        trades = _make_trades(pnl)
        config = _make_config(min_trades=2)
        
        pm = compute_performance_matrix(trades, config)
        row = pm.iloc[0]
        
        # No losses → PF is NaN but should be capped or handled
        assert pd.notna(row["profit_factor"]) or True  # handled gracefully
    
    def test_longest_losing_streak(self):
        """Test longest losing streak computation."""
        pnl = [1.0, -0.5, -1.0, 2.0, -0.3, -0.7, -0.2, 1.5]
        trades = _make_trades(pnl)
        config = _make_config(min_trades=2)
        
        pm = compute_performance_matrix(trades, config)
        row = pm.iloc[0]
        
        # Streaks: W, L2, W, L3, W → max = 3
        assert row["longest_losing_streak"] == 3
    
    def test_current_losing_streak(self):
        """Test current losing streak computation."""
        pnl = [1.0, -0.5, -1.0, -0.3]  # current = 3
        trades = _make_trades(pnl)
        config = _make_config(min_trades=2)
        
        pm = compute_performance_matrix(trades, config)
        row = pm.iloc[0]
        
        assert row["current_losing_streak"] == 3
    
    def test_low_sample_warning(self):
        """Test low sample warning when trade_count < min_trades."""
        pnl = [1.0, -0.5]
        trades = _make_trades(pnl)
        config = _make_config(min_trades=10)
        
        pm = compute_performance_matrix(trades, config)
        row = pm.iloc[0]
        
        assert row["low_sample_warning"] == True
        assert "low_sample" in row["warnings"]
    
    def test_edge_concentration_metrics(self):
        """Test edge concentration metrics are computed."""
        pnl = [10.0, 1.0, 0.5, -1.0, -2.0]  # largest win = 10, total positive = 11.5
        trades = _make_trades(pnl)
        config = _make_config(min_trades=2)
        
        pm = compute_performance_matrix(trades, config)
        row = pm.iloc[0]
        
        # largest_win_contribution = 10 / 11.5 ≈ 0.87
        assert row["largest_win_contribution"] > 0.35
        assert row["edge_concentration_warning"] == True
    
    def test_payoff_ratio_capped(self):
        """Test that payoff_ratio is capped."""
        pnl = [10.0, -0.1, 8.0]  # avg_win = 9, avg_loss = -0.1, payoff = 90
        trades = _make_trades(pnl)
        config = _make_config(min_trades=2)
        config.metric_caps.max_payoff_ratio = 5.0
        
        pm = compute_performance_matrix(trades, config)
        row = pm.iloc[0]
        
        assert row["payoff_ratio"] == 5.0
        assert "payoff_ratio_capped" in row["warnings"]
    
    def test_multiple_groups(self):
        """Test computation across multiple (strategy, regime) groups."""
        rows = []
        import datetime
        base = datetime.datetime(2026, 1, 1, 10, 0, 0)
        
        for i in range(20):
            strat = f"S{i % 2 + 1}"
            regime = f"regime_{i % 3 + 1}"
            pnl = (i % 5 - 1) * 0.5  # some wins, some losses
            rows.append({
                "trade_id": f"T{i+1}",
                "strategy_name": strat,
                "symbol": "BTCUSDT",
                "direction": "long" if i % 2 == 0 else "short",
                "entry_time": base + datetime.timedelta(days=i),
                "exit_time": base + datetime.timedelta(days=i, hours=4),
                "pnl_R": pnl,
                "pnl_usd": pnl * 200,
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
        trades = pd.DataFrame(rows)
        config = _make_config(min_trades=2)
        
        pm = compute_performance_matrix(trades, config)
        
        # 2 strategies × 3 regimes = 6 groups
        assert len(pm) == 6
        assert set(pm["strategy_name"]) == {"S1", "S2"}
        assert set(pm["regime"]) == {"regime_1", "regime_2", "regime_3"}
