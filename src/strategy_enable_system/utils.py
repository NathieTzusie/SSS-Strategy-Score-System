"""
Utility functions for Strategy Enable Score System v1.1.
"""

import numpy as np


def clamp(value, low=0.0, high=100.0):
    """Clamp value to [low, high] range."""
    return max(low, min(high, value))


def safe_divide(numerator, denominator, default=0.0):
    """Safe division returning default when denominator is 0."""
    if denominator == 0 or denominator is None:
        return default
    return numerator / denominator


def gini_coefficient(values):
    """Calculate Gini coefficient for an array of positive values.
    
    Args:
        values: Array-like of positive values.
    
    Returns:
        float: Gini coefficient in [0, 1], or None if insufficient data.
    """
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) < 2:
        return None
    values = np.sort(values)
    n = len(values)
    index = np.arange(1, n + 1)
    gini = (2 * np.sum(index * values) - (n + 1) * np.sum(values)) / (n * np.sum(values))
    return float(gini)


def compute_drawdown(equity_curve):
    """Compute maximum drawdown from an equity curve.
    
    Args:
        equity_curve: Array-like of cumulative equity values.
    
    Returns:
        float: Maximum drawdown as a negative number (or 0 if no drawdown).
    """
    equity = np.asarray(equity_curve, dtype=float)
    if len(equity) == 0:
        return 0.0
    running_max = np.maximum.accumulate(equity)
    drawdowns = equity - running_max
    return float(np.min(drawdowns))


def compute_longest_losing_streak(pnl_series):
    """Compute the longest consecutive losing streak.
    
    Args:
        pnl_series: Array-like of PnL values (negative = loss).
    
    Returns:
        int: Maximum consecutive losses.
    """
    pnl = np.asarray(pnl_series, dtype=float)
    max_streak = 0
    current_streak = 0
    for val in pnl:
        if val <= 0:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
    return max_streak


def compute_current_losing_streak(pnl_series):
    """Compute the current (most recent) consecutive losing streak.
    
    Args:
        pnl_series: Array-like of PnL values in chronological order.
    
    Returns:
        int: Current consecutive losses counting back from the end.
    """
    pnl = np.asarray(pnl_series, dtype=float)
    streak = 0
    for val in reversed(pnl):
        if val <= 0:
            streak += 1
        else:
            break
    return streak


# ============================================================
# Time Under Water / Recovery Metrics (P2-1)
# ============================================================

def compute_time_under_water_ratio(pnl_series):
    """Compute the fraction of trades spent underwater.
    
    Underwater = current cumulative equity < historical peak equity.
    
    Args:
        pnl_series: Array-like of PnL values in chronological order.
    
    Returns:
        float: Ratio in [0, 1], or None if < 1 trade.
    """
    pnl = np.asarray(pnl_series, dtype=float)
    if len(pnl) < 1:
        return None
    equity = np.cumsum(pnl)
    running_max = np.maximum.accumulate(equity)
    underwater = equity < running_max
    return float(np.mean(underwater))


def compute_recovery_periods(pnl_series):
    """Compute recovery trade counts from equity curve.
    
    A recovery period is measured from the first trade where equity
    drops below the previous all-time high, to the trade where equity
    reaches a new all-time high. Only completed (recovered) periods are
    counted.
    
    Args:
        pnl_series: Array-like of PnL values in chronological order.
    
    Returns:
        list[int]: List of recovery lengths in trades, or empty list.
    """
    pnl = np.asarray(pnl_series, dtype=float)
    if len(pnl) < 2:
        return []
    
    equity = np.cumsum(pnl)
    peak = equity[0]
    recovery_periods = []
    in_drawdown = False
    drawdown_start_idx = 0
    
    for i in range(len(equity)):
        if equity[i] > peak:
            # New all-time high
            if in_drawdown:
                # Recovery completed — count trades from drawdown start to here
                recovery_len = i - drawdown_start_idx
                recovery_periods.append(recovery_len)
                in_drawdown = False
            peak = equity[i]
        elif equity[i] < peak and not in_drawdown:
            # Just entered drawdown
            in_drawdown = True
            drawdown_start_idx = i
        # equity[i] == peak: no change in state
    
    # If still in drawdown at end, it's unrecovered — don't count
    return recovery_periods


def compute_max_recovery_trades(pnl_series):
    """Compute the maximum number of trades to recover from a drawdown.
    
    Args:
        pnl_series: Array-like of PnL values in chronological order.
    
    Returns:
        int or None: Max recovery trades, or None if no completed recoveries.
    """
    periods = compute_recovery_periods(pnl_series)
    if not periods:
        return None
    return max(periods)


def compute_average_recovery_trades(pnl_series):
    """Compute the average number of trades to recover from a drawdown.
    
    Args:
        pnl_series: Array-like of PnL values in chronological order.
    
    Returns:
        float or None: Mean recovery trades, or None if no completed recoveries.
    """
    periods = compute_recovery_periods(pnl_series)
    if not periods:
        return None
    return float(np.mean(periods))
