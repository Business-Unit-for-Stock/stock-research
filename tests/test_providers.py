import unittest

import pandas as pd

from stock_research.providers import baostock_code, normalize_provider_frame, read_symbols, yahoo_ticker


class ProviderTests(unittest.TestCase):
    def test_yahoo_ticker_mapping(self) -> None:
        self.assertEqual(yahoo_ticker("600519"), "600519.SS")
        self.assertEqual(yahoo_ticker("000001"), "000001.SZ")

    def test_baostock_code_mapping(self) -> None:
        self.assertEqual(baostock_code("600519"), "sh.600519")
        self.assertEqual(baostock_code("000001"), "sz.000001")

    def test_normalize_akshare_frame(self) -> None:
        frame = pd.DataFrame(
            [
                {"日期": "2026-07-24", "开盘": 10, "最高": 11, "最低": 9, "收盘": 10.5, "成交量": 100},
            ]
        )
        normalized = normalize_provider_frame(frame, "600519", "akshare", "now", "none")
        self.assertEqual(list(normalized.columns), [
            "date", "symbol", "open", "high", "low", "close", "adj_close", "volume", "amount", "provider", "fetched_at", "adjust"
        ])
        self.assertEqual(normalized.iloc[0]["symbol"], "600519.XSHG")
        self.assertEqual(normalized.iloc[0]["close"], 10.5)

    def test_read_symbols_deduplicates_and_normalizes(self) -> None:
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as directory:
            path = Path(directory) / "symbols.txt"
            path.write_text("# comment\n600519\n600519.XSHG\n000001\n", encoding="utf-8")
            self.assertEqual(read_symbols(path), ["000001.XSHE", "600519.XSHG"])


if __name__ == "__main__":
    unittest.main()
