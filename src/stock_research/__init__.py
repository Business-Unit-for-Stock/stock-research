"""A-share research primitives."""

from .backtest import BacktestConfig, BacktestResult, run_backtest
from .data import DataValidationError, load_bars_csv, normalize_symbol, prepare_bars
from .factors import momentum, moving_average_gap, top_n_equal_weight
from .rules import FeeSchedule, MarketRules

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "DataValidationError",
    "FeeSchedule",
    "MarketRules",
    "load_bars_csv",
    "momentum",
    "moving_average_gap",
    "normalize_symbol",
    "prepare_bars",
    "run_backtest",
    "top_n_equal_weight",
]

