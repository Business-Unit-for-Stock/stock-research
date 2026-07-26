from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping, Any

import pandas as pd


def round_tick(price: float, tick_size: str = "0.01") -> float:
    return float(Decimal(str(price)).quantize(Decimal(tick_size), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class FeeSchedule:
    commission_rate: float = 0.0003
    minimum_commission: float = 5.0
    transfer_fee_rate: float = 0.00001
    stamp_duty_rate: float = 0.0005

    def calculate(self, side: str, gross_amount: float) -> float:
        if gross_amount <= 0:
            return 0.0
        normalized_side = side.lower()
        if normalized_side not in {"buy", "sell"}:
            raise ValueError(f"未知交易方向: {side}")
        commission = max(self.minimum_commission, gross_amount * self.commission_rate)
        transfer_fee = gross_amount * self.transfer_fee_rate
        stamp_duty = gross_amount * self.stamp_duty_rate if normalized_side == "sell" else 0.0
        return commission + transfer_fee + stamp_duty


@dataclass(frozen=True)
class MarketRules:
    lot_size: int = 100
    main_board_limit: float = 0.10
    growth_board_limit: float = 0.20
    beijing_limit: float = 0.30
    st_limit: float = 0.05
    price_epsilon: float = 1e-8

    def round_lot(self, quantity: float) -> int:
        if quantity <= 0:
            return 0
        return int(quantity // self.lot_size) * self.lot_size

    def infer_limit_ratio(self, symbol: str, is_st: bool = False) -> float:
        if is_st:
            return self.st_limit
        code, _, exchange = symbol.partition(".")
        if exchange == "XBSE":
            return self.beijing_limit
        if exchange == "XSHG" and code.startswith(("688", "689")):
            return self.growth_board_limit
        if exchange == "XSHE" and code.startswith(("300", "301")):
            return self.growth_board_limit
        return self.main_board_limit

    def price_limits(self, symbol: str, prev_close: float, is_st: bool = False) -> tuple[float, float]:
        ratio = self.infer_limit_ratio(symbol, is_st=is_st)
        return round_tick(prev_close * (1 + ratio)), round_tick(prev_close * (1 - ratio))

    def resolve_price_limits(self, bar: Mapping[str, Any]) -> tuple[float, float]:
        supplied_up = bar.get("limit_up")
        supplied_down = bar.get("limit_down")
        if supplied_up is not None and supplied_down is not None:
            if not pd.isna(supplied_up) and not pd.isna(supplied_down):
                return float(supplied_up), float(supplied_down)
        return self.price_limits(
            str(bar["symbol"]),
            float(bar["prev_close"]),
            is_st=bool(bar.get("st", False)),
        )

    @staticmethod
    def is_suspended(bar: Mapping[str, Any]) -> bool:
        return bool(bar.get("suspended", False)) or float(bar.get("volume", 0.0)) <= 0

    def can_buy(self, bar: Mapping[str, Any], price: float) -> bool:
        if self.is_suspended(bar):
            return False
        limit_up, _ = self.resolve_price_limits(bar)
        return price < limit_up - self.price_epsilon

    def can_sell(self, bar: Mapping[str, Any], price: float) -> bool:
        if self.is_suspended(bar):
            return False
        _, limit_down = self.resolve_price_limits(bar)
        return price > limit_down + self.price_epsilon

