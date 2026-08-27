"""Optional QMT/xtquant integration with an explicit paper-trading safety gate.

The research package remains usable without QMT installed.  Importing this
module never imports xtquant; the adapter is loaded only when an order is
actually submitted on a Windows QMT host.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
from typing import Any, Iterable

import pandas as pd

from .data import normalize_symbol


class QMTConfigurationError(ValueError):
    """Raised when an execution request is not safe or complete."""


@dataclass(frozen=True)
class QMTConfig:
    account_id: str
    session_path: str
    account_type: str = "STOCK"
    mode: str = "paper"
    paper_only: bool = True
    dry_run: bool = True
    order_remark: str = "qmt-quant"
    session_id: int = 1001

    def validate(self) -> None:
        if not self.dry_run and not self.account_id.strip():
            raise QMTConfigurationError("非 dry-run 必须提供 QMT account_id")
        if not self.dry_run and not self.session_path.strip():
            raise QMTConfigurationError("非 dry-run 必须提供 QMT session_path")
        if self.session_id <= 0:
            raise QMTConfigurationError("session_id 必须是正整数")
        if self.account_type.upper() != "STOCK":
            raise QMTConfigurationError("当前仅支持 STOCK 账户")
        if self.mode.lower() not in {"paper", "live"}:
            raise QMTConfigurationError("mode 必须是 paper 或 live")
        if self.mode.lower() == "live" and self.paper_only:
            raise QMTConfigurationError("paper_only 门禁已开启，禁止 live 交易")
        if not self.order_remark.strip():
            raise QMTConfigurationError("order_remark 不能为空")


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: str
    quantity: int
    price: float | None = None
    price_type: str = "LATEST"
    signal_date: date | None = None

    def validate(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise QMTConfigurationError("订单证券代码不能为空")
        if not isinstance(self.side, str) or self.side.lower() not in {"buy", "sell"}:
            raise QMTConfigurationError("订单方向必须是 buy 或 sell")
        try:
            quantity = int(self.quantity)
        except (TypeError, ValueError, OverflowError) as exc:
            raise QMTConfigurationError("A 股订单数量必须是正数且为 100 股整数倍") from exc
        if (
            isinstance(self.quantity, bool)
            or quantity != self.quantity
            or quantity <= 0
            or quantity % 100 != 0
        ):
            raise QMTConfigurationError("A 股订单数量必须是正数且为 100 股整数倍")
        if self.price is not None:
            try:
                price = float(self.price)
            except (TypeError, ValueError, OverflowError) as exc:
                raise QMTConfigurationError("限价必须大于 0") from exc
            if not math.isfinite(price) or price <= 0:
                raise QMTConfigurationError("限价必须大于 0")
        if not isinstance(self.price_type, str) or self.price_type.upper() not in {
            "LATEST",
            "FIX",
            "LIMIT",
        }:
            raise QMTConfigurationError("price_type 必须是 LATEST、FIX 或 LIMIT")


def _load_xtquant() -> Any:
    try:
        from xtquant import xtconstant, xttrader  # type: ignore
    except ImportError as exc:  # pragma: no cover - requires QMT host
        raise QMTConfigurationError(
            "当前 Python 环境未安装 QMT xtquant，请在 QMT Windows 主机上运行"
        ) from exc
    return xtconstant, xttrader


def _parse_signal_date(value: Any) -> date | None:
    """Parse pandas/date/string values while treating CSV nulls as missing."""
    if value is None:
        return None
    try:
        missing = pd.isna(value)
        if isinstance(missing, bool) and missing:
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, datetime):
        parsed = value.date()
        return parsed if isinstance(parsed, date) else None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none", "null"}:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise QMTConfigurationError(f"signal_date 不是有效日期: {value!r}") from exc


def _normalize_qmt_symbol(value: Any) -> str:
    """Accept common forms and emit the ``.SH/.SZ/.BJ`` form used by QMT."""
    try:
        canonical = normalize_symbol(value)
    except Exception as exc:
        raise QMTConfigurationError(f"无法识别 QMT 证券代码: {value!r}") from exc
    code, exchange = canonical.split(".", 1)
    suffix = {"XSHG": "SH", "XSHE": "SZ", "XBSE": "BJ"}[exchange]
    return f"{code}.{suffix}"


class QMTExecutor:
    """Translate validated intents to xtquant orders.

    ``dry_run`` records the normalized payload and never opens a broker
    session.  Real submission is intentionally limited to paper mode.
    """

    def __init__(self, config: QMTConfig):
        config.validate()
        self.config = config

    def normalize(self, intents: Iterable[OrderIntent]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for intent in intents:
            intent.validate()
            parsed_date = _parse_signal_date(intent.signal_date)
            payload.append(
                {
                    "symbol": _normalize_qmt_symbol(intent.symbol),
                    "side": intent.side.lower(),
                    "quantity": intent.quantity,
                    "price": intent.price,
                    "price_type": intent.price_type.upper(),
                    "signal_date": parsed_date.isoformat() if parsed_date else None,
                    "remark": self.config.order_remark,
                }
            )
        return payload

    def submit(self, intents: Iterable[OrderIntent]) -> list[dict[str, Any]]:
        payload = self.normalize(intents)
        if self.config.dry_run:
            return [{**item, "status": "dry-run"} for item in payload]
        if self.config.mode.lower() != "paper" or not self.config.paper_only:
            raise QMTConfigurationError(
                "非 dry-run 仅允许 paper 模式，且必须保持 paper_only=True"
            )

        xtconstant, xttrader = _load_xtquant()
        trader = xttrader.XtQuantTrader(self.config.session_path, self.config.session_id)
        results: list[dict[str, Any]] = []
        started = False
        try:
            start_result = trader.start()
            started = True
            if start_result not in (None, 0):
                raise QMTConfigurationError(f"QMT trader.start 失败: {start_result}")
            connect_result = trader.connect()
            if connect_result not in (None, 0):
                raise QMTConfigurationError(f"QMT trader.connect 失败: {connect_result}")
            account = xttrader.StockAccount(self.config.account_id, self.config.account_type)
            subscribe = getattr(trader, "subscribe", None)
            if callable(subscribe):
                subscribe_result = subscribe(account)
                if subscribe_result not in (None, 0):
                    raise QMTConfigurationError(f"QMT subscribe 失败: {subscribe_result}")
            for item in payload:
                side = (
                    xtconstant.STOCK_BUY
                    if item["side"] == "buy"
                    else xtconstant.STOCK_SELL
                )
                order_type = xtconstant.FIX_PRICE if item["price_type"] in {"FIX", "LIMIT"} else xtconstant.LATEST_PRICE
                price = float(item["price"] or 0.0)
                order_id = trader.order_stock(
                    account,
                    item["symbol"],
                    side,
                    int(item["quantity"]),
                    order_type,
                    price,
                    self.config.order_remark,
                    self.config.order_remark,
                )
                results.append({**item, "status": "submitted", "order_id": order_id})
        finally:
            if started:
                trader.stop()
        return results


def intents_from_trade_frame(trades: Any) -> list[OrderIntent]:
    """Convert a backtest trade DataFrame into execution intents."""
    required = {"symbol", "side", "quantity", "price"}
    if trades is None or not hasattr(trades, "columns"):
        raise QMTConfigurationError("交易记录必须是包含 columns 的表格对象")
    missing = required - set(trades.columns)
    if missing:
        raise QMTConfigurationError(f"交易记录缺少字段: {sorted(missing)}")
    intents: list[OrderIntent] = []
    for row in trades.to_dict("records"):
        signal_date = _parse_signal_date(row.get("signal_date"))
        raw_quantity = row["quantity"]
        try:
            quantity_value = float(raw_quantity)
            if not math.isfinite(quantity_value) or not quantity_value.is_integer():
                raise ValueError
            quantity = int(quantity_value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise QMTConfigurationError("交易记录的 quantity 必须是有效整数") from exc
        raw_price = row["price"]
        if raw_price is None or bool(pd.isna(raw_price)):
            raise QMTConfigurationError("交易记录的 price 不能为空")
        intents.append(
            OrderIntent(
                symbol=_normalize_qmt_symbol(row["symbol"]),
                side=str(row["side"]),
                quantity=quantity,
                price=float(raw_price),
                price_type="LIMIT",
                signal_date=signal_date,
            )
        )
    return intents
