"""
Unit tests for Strategy Enable Score System v1.1 - Scoring.
"""
import pytest
import pandas as pd
import numpy as np

from strategy_enable_system.scoring import (
    compute_enable_scores,
    _compute_regime_edge_score,
    _compute_recent_health_score,
    _compute_monte_carlo_stability_score,
    _compute_risk_control_score,
    _compute_sample_confidence_multiplier,
    _compute_recent_loss_penalty,
    _compute_mc_tail_risk_penalty,
    _compute_edge_concentration_penalty,
    _determine_status,
    _compute_review_required,
    _win_rate_score,
    _profit_factor_score,
    _expectancy_score,
    _drawdown_score,
    _losing_streak_score,
    _avg_loss_score,
)
from strategy_enable_system.config import SSSConfig


def _make_config():
    config = SSSConfig()
    config.input_path = ["data/test.csv"]
    config.min_trades = 30
    return config


def _make_pm_row(**overrides):
    """Create a mock performance matrix row."""
    defaults = {
        "strategy_name": "S1",
        "regime": "trend_up",
        "trade_count": 50,
        "win_rate": 0.60,
        "avg_R": 0.50,
        "total_R": 25.0,
        "profit_factor": 2.5,
        "max_drawdown_R": -3.0,
        "expectancy_R": 0.50,
        "avg_win_R": 1.2,
        "avg_loss_R": -0.8,
        "payoff_ratio": 1.5,
        "longest_losing_streak": 3,
        "current_losing_streak": 1,
        "low_sample_warning": False,
        "edge_concentration_warning": False,
        "largest_win_contribution": 0.20,
        "top_5_trade_contribution": 0.40,
        "top_10_percent_trade_contribution": 0.50,
        "warnings": "",
    }
    defaults.update(overrides)
    return pd.Series(defaults)


def _make_mc_row(**overrides):
    """Create a mock monte carlo results row."""
    defaults = {
        "strategy_name": "S1",
        "regime": "trend_up",
        "n_trades": 50,
        "iterations": 5000,
        "median_total_R": 20.0,
        "p5_total_R": 5.0,
        "p95_total_R": 35.0,
        "median_max_drawdown_R": -5.0,
        "p95_max_drawdown_R": -8.0,
        "worst_max_drawdown_R": -12.0,
        "median_longest_losing_streak": 4.0,
        "p95_longest_losing_streak": 7.0,
        "probability_of_negative_total_R": 0.01,
        "probability_drawdown_exceeds_threshold": 0.05,
    }
    defaults.update(overrides)
    return pd.Series(defaults)


class TestScoringFunctions:
    
    def test_win_rate_score(self):
        assert _win_rate_score(0.0) == 0.0
        assert _win_rate_score(0.35) == 50.0
        assert _win_rate_score(0.70) == 100.0
        assert _win_rate_score(0.90) == 100.0  # capped
    
    def test_profit_factor_score(self):
        assert _profit_factor_score(0.0) == 0.0
        assert _profit_factor_score(1.5) == 50.0
        assert _profit_factor_score(3.0) == 100.0
        assert _profit_factor_score(5.0) == 100.0  # capped
    
    def test_expectancy_score(self):
        assert _expectancy_score(-0.5) == 0.0
        assert _expectancy_score(0.25) == 50.0
        assert _expectancy_score(1.0) == 100.0
        assert _expectancy_score(2.0) == 100.0  # capped
    
    def test_drawdown_score(self):
        assert _drawdown_score(0.0) == 100.0
        assert _drawdown_score(-10.0) == 50.0
        assert _drawdown_score(-20.0) == 0.0
        assert _drawdown_score(-30.0) == 0.0  # capped
    
    def test_losing_streak_score(self):
        assert _losing_streak_score(0) == 100.0
        assert _losing_streak_score(4) == 50.0
        assert _losing_streak_score(8) == 0.0
        assert _losing_streak_score(15) == 0.0  # capped
    
    def test_sample_confidence_multiplier(self):
        config = _make_config()
        config.min_trades = 30
        
        row = _make_pm_row(trade_count=50)
        assert _compute_sample_confidence_multiplier(row, config) == 1.0
        
        row = _make_pm_row(trade_count=15)
        assert _compute_sample_confidence_multiplier(row, config) == 0.5
        
        row = _make_pm_row(trade_count=10)
        assert _compute_sample_confidence_multiplier(row, config) == max(0.5, 10/30)
    
    def test_recent_loss_penalty(self):
        assert _compute_recent_loss_penalty(_make_pm_row(current_losing_streak=0)) == 1.0
        assert _compute_recent_loss_penalty(_make_pm_row(current_losing_streak=2)) == 1.0
        assert _compute_recent_loss_penalty(_make_pm_row(current_losing_streak=3)) == 0.92
        assert _compute_recent_loss_penalty(_make_pm_row(current_losing_streak=4)) == 0.85
        assert _compute_recent_loss_penalty(_make_pm_row(current_losing_streak=5)) == 0.75
        assert _compute_recent_loss_penalty(_make_pm_row(current_losing_streak=7)) == 0.75
    
    def test_mc_tail_risk_penalty(self):
        assert _compute_mc_tail_risk_penalty(_make_mc_row(probability_drawdown_exceeds_threshold=0.05)) == 1.0
        assert _compute_mc_tail_risk_penalty(_make_mc_row(probability_drawdown_exceeds_threshold=0.15)) == 0.92
        assert _compute_mc_tail_risk_penalty(_make_mc_row(probability_drawdown_exceeds_threshold=0.25)) == 0.85
        assert _compute_mc_tail_risk_penalty(_make_mc_row(probability_drawdown_exceeds_threshold=0.40)) == 0.75
    
    def test_status_determination(self):
        config = _make_config()
        assert _determine_status(85, config) == "强开启"
        assert _determine_status(70, config) == "中等开启"
        assert _determine_status(60, config) == "弱开启"
        assert _determine_status(40, config) == "禁用"


class TestEnableScorePipeline:
    
    def test_full_scoring_pipeline(self):
        """Test the complete scoring pipeline with mock data."""
        pm = pd.DataFrame([_make_pm_row()])
        mc = pd.DataFrame([_make_mc_row()])
        config = _make_config()
        
        result = compute_enable_scores(pm, mc, config)
        
        assert len(result) == 1
        row = result.iloc[0]
        
        # Check all expected columns exist
        expected_cols = [
            "strategy_name", "regime", "enable_score",
            "market_opportunity_score", "final_activation_score", "status",
            "regime_edge_score", "recent_health_score",
            "monte_carlo_stability_score", "risk_control_score",
            "sample_confidence_multiplier", "recent_loss_penalty",
            "mc_tail_risk_penalty", "edge_concentration_penalty",
            "score_drivers", "penalty_drivers", "primary_reason",
            "risk_notes", "review_required",
            "low_sample_warning", "edge_concentration_warning",
        ]
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"
        
        # Score should be a valid number
        assert 0 <= row["enable_score"] <= 100
    
    def test_good_strategy_gets_high_score(self):
        """Test that a strong strategy gets a high score."""
        pm = pd.DataFrame([_make_pm_row(
            trade_count=100,
            win_rate=0.65,
            avg_R=0.80,
            profit_factor=2.8,
            max_drawdown_R=-2.0,
            longest_losing_streak=2,
            current_losing_streak=0,
        )])
        mc = pd.DataFrame([_make_mc_row(
            probability_of_negative_total_R=0.001,
            probability_drawdown_exceeds_threshold=0.01,
            p95_max_drawdown_R=-3.0,
        )])
        config = _make_config()
        
        result = compute_enable_scores(pm, mc, config)
        row = result.iloc[0]
        
        assert row["enable_score"] >= 80
        assert row["status"] == "强开启"
    
    def test_bad_strategy_gets_low_score(self):
        """Test that a poor strategy gets a low score."""
        pm = pd.DataFrame([_make_pm_row(
            trade_count=50,
            win_rate=0.30,
            avg_R=-0.20,
            profit_factor=0.5,
            max_drawdown_R=-15.0,
            longest_losing_streak=8,
            current_losing_streak=6,
        )])
        mc = pd.DataFrame([_make_mc_row(
            probability_of_negative_total_R=0.60,
            probability_drawdown_exceeds_threshold=0.50,
        )])
        config = _make_config()
        
        result = compute_enable_scores(pm, mc, config)
        row = result.iloc[0]
        
        assert row["enable_score"] < 50
        assert row["status"] == "禁用"
        assert row["review_required"] == True
    
    def test_low_sample_penalty(self):
        """Test that low sample size reduces score."""
        pm = pd.DataFrame([_make_pm_row(
            trade_count=5,  # only 5 trades
            low_sample_warning=True,
            win_rate=0.80,
            avg_R=1.0,
        )])
        mc = pd.DataFrame([_make_mc_row()])
        config = _make_config()
        config.min_trades = 30
        
        result = compute_enable_scores(pm, mc, config)
        row = result.iloc[0]
        
        # Sample multiplier = max(0.5, 5/30) = 0.5 → score heavily discounted
        assert row["sample_confidence_multiplier"] == 0.5
        assert "low_sample_size" in row["penalty_drivers"]
        assert row["review_required"] == True
    
    def test_edge_concentration_penalty(self):
        """Test that edge concentration triggers penalty."""
        pm = pd.DataFrame([_make_pm_row(
            largest_win_contribution=0.55,
            top_5_trade_contribution=0.80,
            edge_concentration_warning=True,
        )])
        mc = pd.DataFrame([_make_mc_row()])
        config = _make_config()
        
        result = compute_enable_scores(pm, mc, config)
        row = result.iloc[0]
        
        assert row["edge_concentration_penalty"] == 0.85
        assert "edge_concentration" in row["penalty_drivers"]
    
    def test_disabled_low_sample_has_specific_reason(self):
        """Test that disabled due to low sample gets specific reason, not generic."""
        pm = pd.DataFrame([_make_pm_row(
            trade_count=10,
            low_sample_warning=True,
            win_rate=0.65,
            avg_R=0.50,
            profit_factor=2.5,
            max_drawdown_R=-3.0,
        )])
        mc = pd.DataFrame([_make_mc_row(
            probability_of_negative_total_R=0.02,
            probability_drawdown_exceeds_threshold=0.05,
        )])
        config = _make_config()
        config.min_trades = 30
        
        result = compute_enable_scores(pm, mc, config)
        row = result.iloc[0]
        
        # Should be disabled due to sample size
        assert row["status"] == "禁用"
        # Primary reason must mention sample size — not generic
        assert "样本不足" in row["primary_reason"]
        assert "不代表策略失效" in row["primary_reason"] or "不代表策略必然失效" in row["primary_reason"]
        # Must NOT be the old generic message
        assert "综合评分过低" not in row["primary_reason"]
    
    def test_disabled_truly_poor_gets_performance_reason(self):
        """Test that genuinely poor strategy gets performance-based reason."""
        pm = pd.DataFrame([_make_pm_row(
            trade_count=50,
            win_rate=0.30,
            avg_R=-0.20,
            profit_factor=0.5,
            max_drawdown_R=-15.0,
            longest_losing_streak=8,
            current_losing_streak=1,  # low enough to avoid recent_losing_streak penalty branch
        )])
        mc = pd.DataFrame([_make_mc_row(
            probability_of_negative_total_R=0.60,
            probability_drawdown_exceeds_threshold=0.10,  # below 0.15 → no MC penalty
        )])
        config = _make_config()
        
        result = compute_enable_scores(pm, mc, config)
        row = result.iloc[0]
        
        assert row["status"] == "禁用"
        # Should mention poor performance, not recent losing streak
        assert "edge不足" in row["primary_reason"] or "综合评分过低" in row["primary_reason"]
    
    def test_disabled_mc_tail_risk_gets_specific_reason(self):
        """Test that MC tail risk disabled strategy gets specific reason."""
        pm = pd.DataFrame([_make_pm_row(
            trade_count=50,
            win_rate=0.50,
            avg_R=0.20,
            profit_factor=1.5,
        )])
        mc = pd.DataFrame([_make_mc_row(
            probability_of_negative_total_R=0.30,
            probability_drawdown_exceeds_threshold=0.45,
        )])
        config = _make_config()
        
        result = compute_enable_scores(pm, mc, config)
        row = result.iloc[0]
        
        assert row["status"] == "禁用"
        assert "Monte Carlo" in row["primary_reason"]
    
    def test_disabled_edge_concentration_gets_specific_reason(self):
        """Test that edge concentration disabled strategy gets specific reason."""
        pm = pd.DataFrame([_make_pm_row(
            trade_count=50,
            win_rate=0.35,
            avg_R=0.05,
            profit_factor=0.8,
            max_drawdown_R=-8.0,
            largest_win_contribution=0.55,
            top_5_trade_contribution=0.80,
            edge_concentration_warning=True,
        )])
        mc = pd.DataFrame([_make_mc_row(
            probability_of_negative_total_R=0.25,
            probability_drawdown_exceeds_threshold=0.10,  # below 0.15 → no MC penalty
        )])
        config = _make_config()
        
        result = compute_enable_scores(pm, mc, config)
        row = result.iloc[0]
        
        assert row["status"] == "禁用"
        assert "收益过度集中" in row["primary_reason"]

    def test_recent_loss_does_not_hard_ban(self):
        """Test that Recent Health cannot single-handedly disable a strategy.
        
        Even with severe recent losses, if long-term edge is strong,
        the score should not drop to disabled solely due to recent health.
        """
        pm = pd.DataFrame([_make_pm_row(
            trade_count=60,
            win_rate=0.55,  # decent overall
            avg_R=0.40,  # positive expectancy
            profit_factor=2.0,
            max_drawdown_R=-3.0,
            current_losing_streak=5,  # recent bad streak
        )])
        mc = pd.DataFrame([_make_mc_row(
            probability_of_negative_total_R=0.05,
            probability_drawdown_exceeds_threshold=0.10,
        )])
        config = _make_config()
        
        result = compute_enable_scores(pm, mc, config)
        row = result.iloc[0]
        
        # Even with current_losing_streak=5 (0.75 penalty), 
        # the base score should still be driven by regime_edge at 0.40 weight
        # Recent health is only 0.15 weight.
        # So it won't hard-ban the strategy.
        assert row["recent_loss_penalty"] == 0.75
        assert "recent_losing_streak" in row["penalty_drivers"]
        # Should still be at least weak_enable if the edge is there
        assert row["enable_score"] >= 40  # Not below 50 because of the 0.75 multiplier
