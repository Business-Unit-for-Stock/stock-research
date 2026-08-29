"""A-share research primitives."""

from .backtest import BacktestConfig, BacktestResult, run_backtest
from .data import DataValidationError, load_bars_csv, normalize_symbol, prepare_bars
from .factors import momentum, moving_average_gap, top_n_equal_weight
from .industry import IndustryKBError, IndustrySnapshot, parse_industry_kb, write_industry_snapshot
from .qmt import QMTConfig, QMTConfigurationError, QMTExecutor, OrderIntent
from .rules import FeeSchedule, MarketRules

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "DataValidationError",
    "FeeSchedule",
    "MarketRules",
    "IndustryKBError",
    "IndustrySnapshot",
    "OrderIntent",
    "QMTConfig",
    "QMTConfigurationError",
    "QMTExecutor",
    "load_bars_csv",
    "momentum",
    "moving_average_gap",
    "normalize_symbol",
    "prepare_bars",
    "run_backtest",
    "parse_industry_kb",
    "top_n_equal_weight",
    "write_industry_snapshot",
]
