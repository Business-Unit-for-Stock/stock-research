import unittest

import pandas as pd

from stock_research.factors import momentum, top_n_equal_weight


class FactorTests(unittest.TestCase):
    def test_momentum_ranking_selects_strongest_symbol(self) -> None:
        rows = []
        for date, first, second in [
            ("2026-01-05", 10.0, 10.0),
            ("2026-01-06", 11.0, 10.1),
            ("2026-01-07", 12.0, 10.2),
        ]:
            for symbol, close in [("600001", first), ("000001", second)]:
                rows.append(
                    {
                        "date": date,
                        "symbol": symbol,
                        "open": close,
                        "high": close,
                        "low": close,
                        "close": close,
                        "volume": 1000,
                    }
                )
        scores = momentum(pd.DataFrame(rows), lookback=2)
        targets = top_n_equal_weight(scores, top_n=1)
        final = targets.loc[targets["date"] == pd.Timestamp("2026-01-07")]
        self.assertEqual(final.iloc[0]["symbol"], "600001.XSHG")
        self.assertEqual(final.iloc[0]["target_weight"], 1.0)


if __name__ == "__main__":
    unittest.main()

