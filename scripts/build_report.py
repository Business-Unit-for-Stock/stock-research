from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将回测 CSV 汇总为可发布报告")
    parser.add_argument("--input", default="outputs")
    parser.add_argument("--output", default="outputs/report.md")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.input)
    summary_path = root / "summary.json"
    equity_path = root / "equity_curve.csv"
    trades_path = root / "trades.csv"
    if not summary_path.is_file() or not equity_path.is_file() or not trades_path.is_file():
        missing = [str(path) for path in (summary_path, equity_path, trades_path) if not path.is_file()]
        raise SystemExit(f"缺少回测产物: {', '.join(missing)}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    equity = pd.read_csv(equity_path)
    trades = pd.read_csv(trades_path)
    if equity.empty or "date" not in equity.columns:
        raise SystemExit("equity_curve.csv 为空或缺少 date 字段")
    def metric(name: str, default: float = 0.0) -> float:
        try:
            return float(summary.get(name, default))
        except (TypeError, ValueError):
            return default

    trade_count = int(metric("trade_count", len(trades)))
    lines = [
        "# A 股回测报告",
        "",
        "> 研究结果仅供研究和风控验证，不构成投资建议。",
        "",
        f"- 样本区间：{equity['date'].min()} 至 {equity['date'].max()}",
        f"- 交易次数：{trade_count}",
        f"- 总收益：{metric('total_return'):.2%}",
        f"- 年化收益：{metric('annualized_return'):.2%}",
        f"- 年化波动：{metric('annualized_volatility'):.2%}",
        f"- Sharpe：{metric('sharpe'):.3f}",
        f"- 最大回撤：{metric('max_drawdown'):.2%}",
        f"- 总费用：{metric('total_fees'):.2f}",
        "",
        "## 产物",
        "",
        "- `equity_curve.csv`：每日净值、现金、持仓市值和换手",
        "- `trades.csv`：含 signal_date 的交易流水",
        "- `signals.csv`：因子信号与目标权重",
        "- `summary.json`：机器可读指标",
    ]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
