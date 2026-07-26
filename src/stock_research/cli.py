from __future__ import annotations

import argparse
import json
from pathlib import Path

from .backtest import BacktestConfig, run_backtest
from .data import load_bars_csv
from .factors import momentum, moving_average_gap, top_n_equal_weight


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行可复现的 A 股日线研究样例")
    parser.add_argument("--bars", required=True, help="OHLCV CSV 文件")
    parser.add_argument("--factor", choices=["momentum", "ma-gap"], default="momentum")
    parser.add_argument("--lookback", type=int, default=20, help="因子回看窗口")
    parser.add_argument("--top-n", type=int, default=10, help="每日持有得分最高的 N 只股票")
    parser.add_argument("--max-weight", type=float, default=1.0, help="单只股票权重上限")
    parser.add_argument("--cash", type=float, default=1_000_000.0, help="初始现金")
    parser.add_argument("--output", default="outputs", help="结果目录")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bars = load_bars_csv(args.bars)
    if args.factor == "momentum":
        factor_values = momentum(bars, lookback=args.lookback)
    else:
        factor_values = moving_average_gap(bars, window=args.lookback)
    targets = top_n_equal_weight(
        factor_values,
        top_n=args.top_n,
        max_weight=args.max_weight,
    )
    result = run_backtest(bars, targets, config=BacktestConfig(initial_cash=args.cash))

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    result.equity_curve.to_csv(output / "equity_curve.csv", index=False)
    result.trades.to_csv(output / "trades.csv", index=False)
    targets.to_csv(output / "signals.csv", index=False)
    with (output / "summary.json").open("w", encoding="utf-8") as stream:
        json.dump(result.summary, stream, ensure_ascii=False, indent=2)

    print(json.dumps(result.summary, ensure_ascii=False, indent=2))
    print(f"结果已写入: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

