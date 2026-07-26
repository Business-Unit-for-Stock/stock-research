import unittest

import pandas as pd

from stock_research.data import DataValidationError, normalize_symbol, prepare_bars


class DataTests(unittest.TestCase):
    def test_normalize_symbol(self) -> None:
        self.assertEqual(normalize_symbol("600519"), "600519.XSHG")
        self.assertEqual(normalize_symbol("000001.SZ"), "000001.XSHE")
        self.assertEqual(normalize_symbol("BJ430047"), "430047.XBSE")
        self.assertEqual(normalize_symbol("300750.XSHE"), "300750.XSHE")

    def test_prepare_bars_derives_previous_close(self) -> None:
        frame = pd.DataFrame(
            [
                {"date": "2026-01-05", "symbol": "600519", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100},
                {"date": "2026-01-06", "symbol": "600519", "open": 11, "high": 12, "low": 10, "close": 11, "volume": 100},
            ]
        )
        bars = prepare_bars(frame)
        self.assertEqual(bars.iloc[1]["prev_close"], 10)
        self.assertFalse(bool(bars.iloc[0]["suspended"]))

    def test_invalid_ohlc_is_rejected(self) -> None:
        frame = pd.DataFrame(
            [
                {"date": "2026-01-05", "symbol": "600519", "open": 10, "high": 9, "low": 8, "close": 10, "volume": 100},
            ]
        )
        with self.assertRaises(DataValidationError):
            prepare_bars(frame)


if __name__ == "__main__":
    unittest.main()

