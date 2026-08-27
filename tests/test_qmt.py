import unittest
from datetime import date
import sys
import types
from unittest.mock import patch

import pandas as pd

from stock_research.qmt import (
    QMTConfig,
    QMTConfigurationError,
    QMTExecutor,
    OrderIntent,
    intents_from_trade_frame,
)


class QMTTests(unittest.TestCase):
    def test_dry_run_does_not_require_credentials(self) -> None:
        executor = QMTExecutor(QMTConfig("", "", dry_run=True))
        result = executor.submit([OrderIntent("600519", "buy", 100, 10.0)])
        self.assertEqual(result[0]["symbol"], "600519.SH")

    def test_dry_run_never_loads_xtquant(self) -> None:
        executor = QMTExecutor(QMTConfig("paper-account", "qmt-session", dry_run=True))
        result = executor.submit([OrderIntent("600519.XSHG", "buy", 100, 10.0, signal_date=date(2026, 1, 5))])
        self.assertEqual(result[0]["status"], "dry-run")
        self.assertEqual(result[0]["quantity"], 100)

    def test_live_is_blocked_by_paper_only(self) -> None:
        with self.assertRaises(QMTConfigurationError):
            QMTConfig("account", "session", mode="live", paper_only=True).validate()

    def test_trade_frame_conversion(self) -> None:
        frame = pd.DataFrame([{"symbol": "600519.XSHG", "side": "sell", "quantity": 100, "price": 12.0, "signal_date": "2026-01-05"}])
        intents = intents_from_trade_frame(frame)
        self.assertEqual(intents[0].signal_date, date(2026, 1, 5))
        self.assertEqual(intents[0].symbol, "600519.SH")

    def test_empty_trade_frame_is_valid(self) -> None:
        frame = pd.DataFrame(columns=["symbol", "side", "quantity", "price"])
        self.assertEqual(intents_from_trade_frame(frame), [])

    def test_missing_signal_date_is_none(self) -> None:
        frame = pd.DataFrame([{"symbol": "600519", "side": "buy", "quantity": 100, "price": 12.0}])
        intents = intents_from_trade_frame(frame)
        self.assertIsNone(intents[0].signal_date)

        frame["signal_date"] = pd.NaT
        intents = intents_from_trade_frame(frame)
        self.assertIsNone(intents[0].signal_date)

    def test_paper_submit_uses_xtquant_order_contract(self) -> None:
        class FakeTrader:
            instances = []

            def __init__(self, path, session_id):
                self.path = path
                self.session_id = session_id
                self.calls = []
                self.__class__.instances.append(self)

            def start(self):
                self.calls.append(("start",))
                return 0

            def connect(self):
                self.calls.append(("connect",))
                return 0

            def subscribe(self, account):
                self.calls.append(("subscribe", account))
                return 0

            def order_stock(self, *args):
                self.calls.append(("order_stock", *args))
                return 123

            def stop(self):
                self.calls.append(("stop",))

        class FakeAccount:
            def __init__(self, account_id, account_type):
                self.account_id = account_id
                self.account_type = account_type

        fake_constant = types.ModuleType("xtconstant")
        fake_constant.STOCK_BUY = "BUY"
        fake_constant.STOCK_SELL = "SELL"
        fake_constant.FIX_PRICE = "FIX"
        fake_constant.LATEST_PRICE = "LATEST"
        fake_trader = types.ModuleType("xttrader")
        fake_trader.XtQuantTrader = FakeTrader
        fake_trader.StockAccount = FakeAccount
        fake_package = types.ModuleType("xtquant")
        fake_package.xtconstant = fake_constant
        fake_package.xttrader = fake_trader
        with patch.dict(sys.modules, {"xtquant": fake_package}):
            executor = QMTExecutor(
                QMTConfig("paper-account", "C:/qmt", dry_run=False, mode="paper", paper_only=True)
            )
            result = executor.submit([OrderIntent("600519", "buy", 100, 12.0, price_type="LIMIT")])
        self.assertEqual(result[0]["status"], "submitted")
        trader = FakeTrader.instances[-1]
        order_call = next(call for call in trader.calls if call[0] == "order_stock")
        self.assertEqual(order_call[2:7], ("600519.SH", "BUY", 100, "FIX", 12.0))
        self.assertEqual(order_call[-2:], ("qmt-quant", "qmt-quant"))

    def test_submit_gate_requires_explicit_approval(self) -> None:
        from scripts.run_qmt import _check_submit_gate

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                _check_submit_gate("paper", True)


if __name__ == "__main__":
    unittest.main()
