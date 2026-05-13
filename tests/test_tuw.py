"""
Unit tests for Time Under Water / Recovery Metrics (P2-1).
"""
import pytest
import numpy as np
import pandas as pd

from strategy_enable_system.utils import (
    compute_time_under_water_ratio,
    compute_recovery_periods,
    compute_max_recovery_trades,
    compute_average_recovery_trades,
)
from strategy_enable_system.metrics import compute_performance_matrix
from strategy_enable_system.config import SSSConfig


class TestTimeUnderWaterRatio:

    def test_always_new_highs(self):
        """Continuously making new highs → 0 underwater."""
        pnl = [1.0, 2.0, 1.0, 3.0]
        assert compute_time_under_water_ratio(pnl) == 0.0

    def test_partial_underwater(self):
        """Some trades underwater, some at new highs."""
        # equity: 1, 0, 2, 1, 3 → running_max: 1,1,2,2,3
        # underwater: F, T, F, T, F → 2/5
        pnl = [1.0, -1.0, 2.0, -1.0, 2.0]
        assert compute_time_under_water_ratio(pnl) == 2 / 5

    def test_all_underwater(self):
        """First trade is peak, everything else below → almost all underwater."""
        pnl = [1.0, -0.5, -0.3, -0.1]  # equity: 1, 0.5, 0.2, 0.1
        # running_max: 1,1,1,1 → all after first are underwater
        assert compute_time_under_water_ratio(pnl) == 3 / 4

    def test_empty_sequence(self):
        """Empty sequence returns None."""
        assert compute_time_under_water_ratio([]) is None

    def test_single_trade(self):
        """Single trade — never underwater (0/1)."""
        assert compute_time_under_water_ratio([1.0]) == 0.0


class TestRecoveryPeriods:

    def test_always_new_highs(self):
        """No drawdown → no recovery periods."""
        pnl = [1.0, 2.0, 1.0, 3.0]
        assert compute_recovery_periods(pnl) == []

    def test_single_recovery(self):
        """One drawdown then recovery."""
        # equity: 1, 0, 2, 3 → peak at 1, drops below at idx 1, new high at idx 2
        # recovery = idx 2 - idx 1 = 1
        pnl = [1.0, -1.0, 2.0, 1.0]
        assert compute_recovery_periods(pnl) == [1]

    def test_multiple_recoveries(self):
        """Multiple drawdown/recovery cycles."""
        # equity: 2, 1, 3, 2, 4
        # peak: 2, 2(dd starts idx1), 3(recovery len=2-1=1), 3(dd starts idx3), 4(recovery len=4-3=1)
        pnl = [2.0, -1.0, 2.0, -1.0, 2.0]
        assert compute_recovery_periods(pnl) == [1, 1]

    def test_never_recovers(self):
        """Drawdown that never recovers → no completed recovery periods."""
        pnl = [2.0, -1.0, -1.0, -1.0]
        assert compute_recovery_periods(pnl) == []

    def test_long_recovery(self):
        """A long drawdown before recovery."""
        # equity: 5, 4, 3, 2, 1, 6
        # dd starts at idx 1, recovery at idx 5 → len = 5-1 = 4
        pnl = [5.0, -1.0, -1.0, -1.0, -1.0, 5.0]
        assert compute_recovery_periods(pnl) == [4]

    def test_recovery_with_intermittent_peaks(self):
        """Equity rises then falls without hitting new ATH → still in same drawdown."""
        # equity: 3, 2, 2.5, 1, 4
        # dd starts idx1, equity recovers to 2.5 but not >3 (ATH), still dd
        # new ATH at idx4 → recovery = 4-1 = 3
        pnl = [3.0, -1.0, 0.5, -1.5, 3.0]
        assert compute_recovery_periods(pnl) == [3]

    def test_empty_sequence(self):
        assert compute_recovery_periods([]) == []

    def test_single_trade(self):
        assert compute_recovery_periods([1.0]) == []

    def test_two_trades_no_drawdown(self):
        assert compute_recovery_periods([1.0, 2.0]) == []

    def test_two_trades_with_recovery(self):
        # equity: 2, 1, 3 → dd at idx1, recovered at idx2, len = 1
        pnl = [2.0, -1.0, 3.0]
        assert compute_recovery_periods(pnl) == [1]


class TestMaxRecovery:

    def test_no_recoveries(self):
        assert compute_max_recovery_trades([2.0, -1.0, -1.0]) is None

    def test_single_recovery(self):
        pnl = [1.0, -1.0, 3.0]  # 1-trade recovery
        assert compute_max_recovery_trades(pnl) == 1

    def test_multiple_recoveries(self):
        # equity: 2, 1, 3, 2, 2.5, 5
        # recovery 1: idx2-idx1 = 1; recovery 2: idx5-idx3 = 2
        pnl = [2.0, -1.0, 2.0, -1.0, 0.5, 2.5]
        assert compute_max_recovery_trades(pnl) == 2


class TestAverageRecovery:

    def test_no_recoveries(self):
        assert compute_average_recovery_trades([2.0, -1.0, -1.0]) is None

    def test_multiple_recoveries(self):
        # recovery lengths: 1 and 2 → avg = 1.5
        pnl = [2.0, -1.0, 2.0, -1.0, 0.5, 2.5]
        assert compute_average_recovery_trades(pnl) == 1.5


class TestMetricsIntegration:

    def test_tuw_in_performance_matrix(self):
        """Verify TUW columns appear in performance_matrix output."""
        config = SSSConfig()
        config.input_path = ["data/test.csv"]
        config.min_trades = 2

        import datetime
        rows = []
        base = datetime.datetime(2026, 1, 1, 10, 0, 0)
        for i, pnl in enumerate([1.0, -0.5, 2.0, -1.0, 0.5, 3.0]):
            rows.append({
                "trade_id": f"T{i+1}",
                "strategy_name": "S1",
                "symbol": "BTCUSDT",
                "direction": "long",
                "entry_time": base + datetime.timedelta(days=i),
                "exit_time": base + datetime.timedelta(days=i, hours=4),
                "pnl_R": pnl,
                "pnl_usd": 0,
                "session": "London",
                "regime": "trend_up",
                "regime_snapshot_id": "snap_1",
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
        pm = compute_performance_matrix(trades, config)

        assert "time_under_water_ratio" in pm.columns
        assert "max_recovery_trades" in pm.columns
        assert "average_recovery_trades" in pm.columns

        row = pm.iloc[0]
        # equity: 1, 0.5, 2.5, 1.5, 2.0, 5.0
        # underwater at idx 1 (0.5<1), idx 3 (1.5<2.5), idx 4 (2.0<2.5) → 3/6
        assert abs(row["time_under_water_ratio"] - 3/6) < 0.01
        assert row["max_recovery_trades"] is not None
        assert row["average_recovery_trades"] is not None
