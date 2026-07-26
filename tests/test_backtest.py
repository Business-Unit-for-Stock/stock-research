import unittest

import pandas as pd

from stock_research.backtest import BacktestConfig, run_backtest


def make_bars(day_two_open: float = 10.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": "2026-01-05", "symbol": "600519", "open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0, "prev_close": 10.0, "volume": 1000},
            {"date": "2026-01-06", "symbol": "600519", "open": day_two_open, "high": max(day_two_open, 11.0), "low": min(day_two_open, 10.0), "close": 11.0, "prev_close": 10.0, "volume": 1000},
            {"date": "2026-01-07", "symbol": "600519", "open": 11.0, "high": 11.0, "low": 11.0, "close": 11.0, "prev_close": 11.0, "volume": 1000},
        ]
    )


class BacktestTests(unittest.TestCase):
    def test_signal_executes_next_session_and_t1_sell_is_next_day(self) -> None:
        targets = pd.DataFrame(
            [
                {"date": "2026-01-05", "symbol": "600519", "target_weight": 1.0},
                {"date": "2026-01-06", "symbol": "600519", "target_weight": 0.0},
            ]
        )
        result = run_backtest(make_bars(), targets, BacktestConfig(initial_cash=10_000))
        self.assertEqual(list(result.trades["side"]), ["buy", "sell"])
        self.assertEqual(result.trades.iloc[0]["date"], pd.Timestamp("2026-01-06"))
        self.assertEqual(result.trades.iloc[1]["date"], pd.Timestamp("2026-01-07"))
        self.assertEqual(result.trades.iloc[0]["quantity"] % 100, 0)

    def test_limit_up_blocks_buy(self) -> None:
        targets = pd.DataFrame(
            [{"date": "2026-01-05", "symbol": "600519", "target_weight": 1.0}]
        )
        result = run_backtest(make_bars(day_two_open=11.0), targets, BacktestConfig(initial_cash=10_000))
        self.assertTrue(result.trades.empty)


if __name__ == "__main__":
    unittest.main()

