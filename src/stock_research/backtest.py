from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .data import normalize_symbol, prepare_bars
from .metrics import performance_summary
from .rules import FeeSchedule, MarketRules


@dataclass
class PositionState:
    quantity: int = 0
    sellable: int = 0


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 1_000_000.0
    annual_sessions: int = 252
    fees: FeeSchedule = field(default_factory=FeeSchedule)
    rules: MarketRules = field(default_factory=MarketRules)


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    summary: dict[str, float]


TRADE_COLUMNS = [
    "date",
    "signal_date",
    "symbol",
    "side",
    "quantity",
    "price",
    "gross_amount",
    "fees",
    "cash_after",
]


def _prepare_targets(targets: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "symbol", "target_weight"}
    missing = required - set(targets.columns)
    if missing:
        raise ValueError(f"目标权重缺少字段: {sorted(missing)}")
    clean = targets.copy()
    clean["date"] = pd.to_datetime(clean["date"], errors="coerce").dt.normalize()
    clean["symbol"] = clean["symbol"].map(normalize_symbol)
    clean["target_weight"] = pd.to_numeric(clean["target_weight"], errors="coerce")
    if clean[["date", "symbol", "target_weight"]].isna().any().any():
        raise ValueError("目标权重存在空值或非法值")
    if clean.duplicated(["date", "symbol"]).any():
        raise ValueError("同一交易日和股票存在重复目标权重")
    if (clean["target_weight"] < 0).any() or (clean["target_weight"] > 1).any():
        raise ValueError("目标权重必须位于 [0, 1]")
    daily_sum = clean.groupby("date")["target_weight"].sum()
    if (daily_sum > 1.0000001).any():
        raise ValueError("单日目标权重之和不能超过 1")
    return clean.sort_values(["date", "symbol"]).reset_index(drop=True)


def run_backtest(
    bars: pd.DataFrame,
    targets: pd.DataFrame,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run a long-only daily backtest with close-time signals executed next open."""
    cfg = config or BacktestConfig()
    if cfg.initial_cash <= 0:
        raise ValueError("initial_cash 必须大于 0")

    market = prepare_bars(bars)
    desired = _prepare_targets(targets)
    dates = list(pd.Index(market["date"].drop_duplicates()).sort_values())
    targets_by_date = {date: group for date, group in desired.groupby("date", sort=False)}
    bars_by_date = {
        date: group.set_index("symbol", drop=False) for date, group in market.groupby("date", sort=False)
    }

    cash = float(cfg.initial_cash)
    positions: dict[str, PositionState] = {}
    last_prices: dict[str, float] = {}
    trades: list[dict[str, object]] = []
    curve: list[dict[str, object]] = []

    for index, date in enumerate(dates):
        day = bars_by_date[date]
        for position in positions.values():
            position.sellable = position.quantity

        opening_prices = {symbol: float(row["open"]) for symbol, row in day.iterrows()}
        opening_equity = cash + sum(
            position.quantity * opening_prices.get(symbol, last_prices.get(symbol, 0.0))
            for symbol, position in positions.items()
        )
        day_fees = 0.0
        day_gross = 0.0

        signal_date = dates[index - 1] if index > 0 else None
        signal_targets = targets_by_date.get(signal_date) if signal_date is not None else None
        if signal_targets is not None and not signal_targets.empty:
            target_weights = dict(zip(signal_targets["symbol"], signal_targets["target_weight"]))
            symbols_to_consider = sorted(set(positions) | set(target_weights))
            target_quantities: dict[str, int] = {}
            for symbol in symbols_to_consider:
                if symbol not in day.index:
                    continue
                price = float(day.loc[symbol, "open"])
                weight = float(target_weights.get(symbol, 0.0))
                target_quantities[symbol] = cfg.rules.round_lot(opening_equity * weight / price)

            # Sell first so proceeds can fund the new target portfolio.
            for symbol in symbols_to_consider:
                position = positions.get(symbol)
                if position is None or position.quantity <= 0 or symbol not in day.index:
                    continue
                target_quantity = target_quantities.get(symbol, position.quantity)
                requested = cfg.rules.round_lot(max(position.quantity - target_quantity, 0))
                sell_quantity = min(requested, position.sellable)
                if sell_quantity <= 0:
                    continue
                row = day.loc[symbol].to_dict()
                price = float(row["open"])
                if not cfg.rules.can_sell(row, price):
                    continue
                gross = price * sell_quantity
                fee = cfg.fees.calculate("sell", gross)
                cash += gross - fee
                position.quantity -= sell_quantity
                position.sellable -= sell_quantity
                day_fees += fee
                day_gross += gross
                trades.append(
                    {
                        "date": date,
                        "signal_date": signal_date,
                        "symbol": symbol,
                        "side": "sell",
                        "quantity": sell_quantity,
                        "price": price,
                        "gross_amount": gross,
                        "fees": fee,
                        "cash_after": cash,
                    }
                )

            for symbol in sorted(target_weights, key=lambda item: (-target_weights[item], item)):
                if symbol not in day.index:
                    continue
                position = positions.setdefault(symbol, PositionState())
                target_quantity = target_quantities.get(symbol, position.quantity)
                buy_quantity = cfg.rules.round_lot(max(target_quantity - position.quantity, 0))
                if buy_quantity <= 0:
                    continue
                row = day.loc[symbol].to_dict()
                price = float(row["open"])
                if not cfg.rules.can_buy(row, price):
                    continue

                while buy_quantity > 0:
                    gross = price * buy_quantity
                    fee = cfg.fees.calculate("buy", gross)
                    if gross + fee <= cash + 1e-9:
                        break
                    buy_quantity -= cfg.rules.lot_size
                if buy_quantity <= 0:
                    continue

                gross = price * buy_quantity
                fee = cfg.fees.calculate("buy", gross)
                cash -= gross + fee
                position.quantity += buy_quantity
                day_fees += fee
                day_gross += gross
                trades.append(
                    {
                        "date": date,
                        "signal_date": signal_date,
                        "symbol": symbol,
                        "side": "buy",
                        "quantity": buy_quantity,
                        "price": price,
                        "gross_amount": gross,
                        "fees": fee,
                        "cash_after": cash,
                    }
                )

        for symbol, row in day.iterrows():
            last_prices[symbol] = float(row["close"])
        market_value = sum(
            position.quantity * last_prices.get(symbol, 0.0)
            for symbol, position in positions.items()
            if position.quantity > 0
        )
        equity = cash + market_value
        curve.append(
            {
                "date": date,
                "cash": cash,
                "market_value": market_value,
                "equity": equity,
                "fees": day_fees,
                "turnover": day_gross / opening_equity if opening_equity > 0 else 0.0,
                "position_count": sum(position.quantity > 0 for position in positions.values()),
            }
        )

    equity_curve = pd.DataFrame(curve)
    trade_frame = pd.DataFrame(trades, columns=TRADE_COLUMNS)
    summary = performance_summary(equity_curve["equity"], annual_sessions=cfg.annual_sessions)
    summary["final_equity"] = float(equity_curve["equity"].iloc[-1])
    summary["trade_count"] = float(len(trade_frame))
    summary["total_fees"] = float(trade_frame["fees"].sum()) if not trade_frame.empty else 0.0
    return BacktestResult(equity_curve=equity_curve, trades=trade_frame, summary=summary)

