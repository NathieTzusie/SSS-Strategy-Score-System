"""
Unit tests for Strategy Enable Score System v1.1 - Config Loader.
"""
import pytest
import os
import tempfile
import yaml

from strategy_enable_system.config import load_config, SSSConfig


def test_load_valid_config():
    """Test loading a complete valid config."""
    config_data = {
        "input_path": ["data/test.csv"],
        "output_dir": "outputs",
        "min_trades": 20,
        "recent_trade_window": 10,
        "monte_carlo": {
            "iterations": 100,
            "method": "bootstrap",
            "drawdown_threshold_R": 5.0,
            "random_seed": 123,
        },
        "score_weights": {
            "regime_edge": 0.40,
            "recent_health": 0.15,
            "monte_carlo_stability": 0.25,
            "risk_control": 0.20,
        },
        "metric_caps": {
            "max_profit_factor": 5.0,
            "max_payoff_ratio": 5.0,
        },
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name
    
    try:
        config = load_config(config_path)
        assert isinstance(config, SSSConfig)
        assert config.input_path == ["data/test.csv"]
        assert config.min_trades == 20
        assert config.monte_carlo.iterations == 100
        assert config.monte_carlo.random_seed == 123
        assert config.metric_caps.max_profit_factor == 5.0
    finally:
        os.unlink(config_path)


def test_missing_input_path():
    """Test that missing input_path raises error."""
    config_data = {
        "output_dir": "outputs",
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name
    
    try:
        with pytest.raises(ValueError, match="input_path"):
            load_config(config_path)
    finally:
        os.unlink(config_path)


def test_default_values():
    """Test that defaults are applied when fields are missing."""
    config_data = {"input_path": ["data/test.csv"]}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name
    
    try:
        config = load_config(config_path)
        assert config.min_trades == 30
        assert config.monte_carlo.iterations == 5000
        assert config.monte_carlo.method == "bootstrap"
        assert config.score_weights.regime_edge == 0.40
        assert config.metric_caps.max_profit_factor == 10.0
    finally:
        os.unlink(config_path)


def test_file_not_found():
    """Test that missing config file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent_config.yaml")
