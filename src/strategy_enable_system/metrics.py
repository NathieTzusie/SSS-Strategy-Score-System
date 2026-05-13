"""
Metrics Engine for Strategy Enable Score System v1.1.
Computes Regime Performance Matrix and Edge Concentration Metrics.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from .config import SSSConfig
from .utils import (
    gini_coefficient,
    compute_drawdown,
    compute_longest_losing_streak,
    compute_current_losing_streak,
    safe_divide,
    compute_time_under_water_ratio,
    compute_max_recovery_trades,
    compute_average_recovery_trades,
)


def compute_performance_matrix(
    trades: pd.DataFrame,
    config: SSSConfig,
) -> pd.DataFrame:
    """Compute Regime Performance Matrix grouped by strategy_name + regime.
    
    Args:
        trades: Standardized trades DataFrame.
        config: SSSConfig object.
    
    Returns:
        pd.DataFrame: One row per (strategy_name, regime) with all performance metrics.
    """
    results = []
    
    # Sort trades by entry_time for chronological processing
    grouped = trades.groupby(["strategy_name", "regime"], sort=False)
    
    for (strat, regime), group in grouped:
        # Sort by entry time for equity curve
        group = group.sort_values("entry_time").reset_index(drop=True)
        pnl_r = group["pnl_R"].values
        n = len(pnl_r)
        
        row: Dict[str, Any] = {
            "strategy_name": strat,
            "regime": regime,
            "trade_count": n,
        }
        
        # Basic stats
        wins = pnl_r[pnl_r > 0]
        losses = pnl_r[pnl_r <= 0]
        n_wins = len(wins)
        
        row["win_rate"] = safe_divide(n_wins, n)
        row["avg_R"] = np.mean(pnl_r) if n > 0 else 0.0
        row["median_R"] = np.median(pnl_r) if n > 0 else 0.0
        row["total_R"] = np.sum(pnl_r) if n > 0 else 0.0
        row["std_R"] = np.std(pnl_r, ddof=0) if n > 0 else 0.0
        
        # Profit factor (capped)
        gross_profit = np.sum(wins) if n_wins > 0 else 0.0
        gross_loss = abs(np.sum(losses)) if len(losses) > 0 else 0.0
        raw_pf = safe_divide(gross_profit, gross_loss, default=np.nan)
        max_pf = config.metric_caps.max_profit_factor
        pf_capped = False
        if not np.isnan(raw_pf) and raw_pf > max_pf:
            pf_capped = True
            row["profit_factor"] = max_pf
        else:
            row["profit_factor"] = raw_pf
        
        # Max drawdown (chronological equity curve in R units)
        cumulative_r = np.cumsum(pnl_r)
        row["max_drawdown_R"] = compute_drawdown(cumulative_r)
        
        # Expectancy
        row["expectancy_R"] = row["avg_R"]
        
        # Avg win / avg loss
        row["avg_win_R"] = np.mean(wins) if n_wins > 0 else np.nan
        row["avg_loss_R"] = np.mean(losses) if len(losses) > 0 else np.nan
        
        # Payoff ratio (capped)
        avg_win = row["avg_win_R"] if not np.isnan(row.get("avg_win_R", np.nan)) else 0
        avg_loss = abs(row["avg_loss_R"]) if not np.isnan(row.get("avg_loss_R", np.nan)) else 0
        raw_payoff = safe_divide(avg_win, avg_loss, default=np.nan)
        max_payoff = config.metric_caps.max_payoff_ratio
        payoff_capped = False
        if not np.isnan(raw_payoff) and raw_payoff > max_payoff:
            payoff_capped = True
            row["payoff_ratio"] = max_payoff
        else:
            row["payoff_ratio"] = raw_payoff
        
        # Longest losing streak
        row["longest_losing_streak"] = compute_longest_losing_streak(pnl_r)
        
        # Current losing streak (most recent trades)
        row["current_losing_streak"] = compute_current_losing_streak(pnl_r)
        
        # Session distribution
        session_counts = group["session"].value_counts(normalize=True)
        row["session_distribution"] = session_counts.to_dict()
        
        # Low sample warning
        row["low_sample_warning"] = n < config.min_trades
        
        # Warnings
        warnings_list = []
        if row["low_sample_warning"]:
            warnings_list.append("low_sample")
        if pf_capped:
            warnings_list.append("profit_factor_capped")
        if payoff_capped:
            warnings_list.append("payoff_ratio_capped")
        
        # --- Edge Concentration Metrics ---
        _compute_edge_concentration(row, pnl_r, config)
        if row.get("edge_concentration_warning"):
            warnings_list.append("edge_concentration")
        
        # --- Time Under Water / Recovery Metrics (P2-1) ---
        row["time_under_water_ratio"] = compute_time_under_water_ratio(pnl_r)
        row["max_recovery_trades"] = compute_max_recovery_trades(pnl_r)
        row["average_recovery_trades"] = compute_average_recovery_trades(pnl_r)
        
        row["warnings"] = ";".join(warnings_list) if warnings_list else ""
        
        results.append(row)
    
    df = pd.DataFrame(results)
    
    # Ensure all expected columns exist
    expected_cols = [
        "strategy_name", "regime", "trade_count", "win_rate",
        "avg_R", "median_R", "total_R", "std_R",
        "profit_factor", "max_drawdown_R", "expectancy_R",
        "avg_win_R", "avg_loss_R", "payoff_ratio",
        "longest_losing_streak", "current_losing_streak",
        "session_distribution", "low_sample_warning",
        "top_5_trade_contribution", "top_10_percent_trade_contribution",
        "largest_win_contribution", "gini_pnl_R",
        "edge_concentration_warning", "warnings",
        "time_under_water_ratio", "max_recovery_trades", "average_recovery_trades",
    ]
    
    for col in expected_cols:
        if col not in df.columns:
            df[col] = None
    
    return df


def _compute_edge_concentration(row: dict, pnl_r: np.ndarray, config: SSSConfig):
    """Compute edge concentration metrics and set warnings."""
    ec = config.edge_concentration
    
    # Positive trades only
    positive = pnl_r[pnl_r > 0]
    total_positive = np.sum(positive)
    
    if total_positive <= 0 or len(positive) == 0:
        row["top_5_trade_contribution"] = None
        row["top_10_percent_trade_contribution"] = None
        row["largest_win_contribution"] = None
        row["gini_pnl_R"] = None
        row["edge_concentration_warning"] = True
        return
    
    # Largest win contribution
    sorted_wins = np.sort(positive)[::-1]
    row["largest_win_contribution"] = safe_divide(sorted_wins[0], total_positive)
    
    # Top 5 contribution
    top_5_sum = np.sum(sorted_wins[:5])
    row["top_5_trade_contribution"] = safe_divide(top_5_sum, total_positive)
    
    # Top 10% contribution
    n_top_10pct = max(1, int(np.ceil(len(sorted_wins) * 0.10)))
    top_10pct_sum = np.sum(sorted_wins[:n_top_10pct])
    row["top_10_percent_trade_contribution"] = safe_divide(top_10pct_sum, total_positive)
    
    # Gini on positive contributions
    row["gini_pnl_R"] = gini_coefficient(positive)
    
    # Warning check
    warning_triggered = False
    if ec.enabled:
        lw = row["largest_win_contribution"]
        t5 = row["top_5_trade_contribution"]
        t10 = row["top_10_percent_trade_contribution"]
        
        if lw is not None and lw > ec.largest_win_warning_threshold:
            warning_triggered = True
        if t5 is not None and t5 > ec.top_5_warning_threshold:
            warning_triggered = True
        if t10 is not None and t10 > ec.top_10_percent_warning_threshold:
            warning_triggered = True
    
    row["edge_concentration_warning"] = warning_triggered and ec.enabled


