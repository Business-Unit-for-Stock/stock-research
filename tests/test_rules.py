import unittest

from stock_research.rules import FeeSchedule, MarketRules


class RuleTests(unittest.TestCase):
    def test_board_specific_price_limits(self) -> None:
        rules = MarketRules()
        self.assertEqual(rules.price_limits("600519.XSHG", 10.0), (11.0, 9.0))
        self.assertEqual(rules.price_limits("300750.XSHE", 10.0), (12.0, 8.0))
        self.assertEqual(rules.price_limits("430047.XBSE", 10.0), (13.0, 7.0))
        self.assertEqual(rules.price_limits("600519.XSHG", 10.0, is_st=True), (10.5, 9.5))

    def test_sell_fee_contains_stamp_duty(self) -> None:
        fees = FeeSchedule()
        self.assertGreater(fees.calculate("sell", 100_000), fees.calculate("buy", 100_000))


if __name__ == "__main__":
    unittest.main()

