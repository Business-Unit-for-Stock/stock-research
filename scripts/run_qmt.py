from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from stock_research.qmt import QMTConfig, QMTExecutor, intents_from_trade_frame


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="在 QMT Windows 主机上执行已审核订单意图")
    parser.add_argument("--trades", required=True, help="回测或人工审核后的 trades.csv")
    parser.add_argument("--output", default="outputs/qmt-orders.json")
    parser.add_argument("--mode", choices=["paper", "live"], default=os.getenv("QMT_MODE", "paper"))
    parser.add_argument("--submit", action="store_true", help="提交到 QMT；默认只做 dry-run")
    parser.add_argument(
        "--max-orders",
        type=int,
        default=int(os.getenv("QMT_MAX_ORDERS", "50")),
        help="单次最多允许的订单数，默认 50",
    )
    return parser


def _is_true(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _check_submit_gate(mode: str, paper_only: bool) -> None:
    """Require explicit local/runner approvals before any broker call."""
    if mode != "paper" or not paper_only:
        raise RuntimeError("QMT 提交仅允许 mode=paper 且 PAPER_ONLY=true")
    if _is_true("GITHUB_ACTIONS") and os.getenv("RUNNER_ENVIRONMENT", "") != "self-hosted":
        raise RuntimeError("禁止在 GitHub-hosted Runner 提交 QMT 订单")
    if not _is_true("QMT_RUNNER_CONFIRMED"):
        raise RuntimeError("缺少 QMT_RUNNER_CONFIRMED=true 安全确认")
    if not _is_true("QMT_APPROVED"):
        raise RuntimeError("缺少 QMT_APPROVED=true 人工审批确认")


def main() -> int:
    args = build_parser().parse_args()
    account_id = os.getenv("QMT_ACCOUNT_ID", "")
    session_path = os.getenv("QMT_SESSION_PATH", "")
    paper_only = _is_true("PAPER_ONLY", default=True)
    if args.max_orders <= 0:
        raise SystemExit("--max-orders 必须大于 0")
    if args.submit:
        _check_submit_gate(args.mode, paper_only)
    trades_path = Path(args.trades)
    if not trades_path.is_file():
        raise SystemExit(f"交易记录不存在或不是文件: {trades_path}")
    session_id_text = os.getenv("QMT_SESSION_ID", "").strip() or "1001"
    try:
        session_id = int(session_id_text)
    except ValueError as exc:
        raise SystemExit("QMT_SESSION_ID 必须是正整数") from exc
    config = QMTConfig(
        account_id=account_id,
        session_path=session_path,
        mode=args.mode,
        paper_only=paper_only,
        dry_run=not args.submit,
        session_id=session_id,
    )
    try:
        trades = pd.read_csv(trades_path)
    except (pd.errors.EmptyDataError, OSError) as exc:
        raise SystemExit(f"无法读取交易记录: {trades_path}: {exc}") from exc
    if len(trades) > args.max_orders:
        raise SystemExit(f"订单数 {len(trades)} 超过单次上限 {args.max_orders}")
    executor = QMTExecutor(config)
    result = executor.submit(intents_from_trade_frame(trades))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"orders": len(result), "output": str(output), "dry_run": config.dry_run}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
