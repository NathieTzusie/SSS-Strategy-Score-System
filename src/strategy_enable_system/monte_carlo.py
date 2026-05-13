"""
Monte Carlo Risk Validation for Strategy Enable Score System v1.1.
Performs bootstrap/shuffle simulations on pnl_R sequences for each
(strategy_name, regime) combination.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List

from .config import SSSConfig
from .utils import compute_drawdown, compute_longest_losing_streak


def run_monte_carlo(
    trades: pd.DataFrame,
    config: SSSConfig,
) -> pd.DataFrame:
    """Run Monte Carlo risk validation for each strategy_name + regime.
    
    Args:
        trades: Standardized trades DataFrame.
        config: SSSConfig object.
    
    Returns:
        pd.DataFrame: One row per (strategy_name, regime) with MC metrics.
    """
    mc = config.monte_carlo
    rng = np.random.RandomState(mc.random_seed)
    
    results = []
    grouped = trades.groupby(["strategy_name", "regime"], sort=False)
    
    for (strat, regime), group in grouped:
        group = group.sort_values("entry_time").reset_index(drop=True)
        pnl_sequence = group["pnl_R"].values
        row = _simulate(pnl_sequence, strat, regime, mc, rng)
        results.append(row)
    
    df = pd.DataFrame(results)
    return df


def _simulate(
    pnl_sequence: np.ndarray,
    strategy_name: str,
    regime: str,
    mc_config,
    rng: np.random.RandomState,
) -> Dict[str, Any]:
    """Run Monte Carlo simulation for a single pnl_R sequence."""
    n = len(pnl_sequence)
    iterations = mc_config.iterations
    method = mc_config.method
    dd_threshold = mc_config.drawdown_threshold_R
    
    # Storage for simulation results
    total_Rs = np.zeros(iterations)
    max_drawdowns = np.zeros(iterations)
    longest_losing_streaks = np.zeros(iterations, dtype=int)
    
    for i in range(iterations):
        if method == "bootstrap":
            sampled = rng.choice(pnl_sequence, size=n, replace=True)
        else:  # shuffle
            sampled = rng.permutation(pnl_sequence)
        
        equity = np.cumsum(sampled)
        total_Rs[i] = equity[-1]
        max_drawdowns[i] = compute_drawdown(equity)
        longest_losing_streaks[i] = compute_longest_losing_streak(sampled)
    
    # Aggregate statistics
    prob_negative = np.mean(total_Rs < 0)
    prob_dd_exceeds = np.mean(max_drawdowns <= -dd_threshold)
    
    return {
        "strategy_name": strategy_name,
        "regime": regime,
        "n_trades": n,
        "iterations": iterations,
        "method": method,
        "median_total_R": np.median(total_Rs),
        "p5_total_R": np.percentile(total_Rs, 5),
        "p95_total_R": np.percentile(total_Rs, 95),
        "median_max_drawdown_R": np.median(max_drawdowns),
        "p95_max_drawdown_R": np.percentile(max_drawdowns, 95),
        "worst_max_drawdown_R": np.min(max_drawdowns),
        "median_longest_losing_streak": np.median(longest_losing_streaks),
        "p95_longest_losing_streak": np.percentile(longest_losing_streaks, 95),
        "probability_of_negative_total_R": prob_negative,
        "probability_drawdown_exceeds_threshold": prob_dd_exceeds,
    }
