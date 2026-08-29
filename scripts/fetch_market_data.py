from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from stock_research.data import normalize_symbol  # noqa: E402
from stock_research.qmt import QMTDataClient, QMTDataError  # noqa: E402
from stock_research.providers import (  # noqa: E402
    ProviderResult,
    fetch_akshare,
    fetch_baostock,
    fetch_yfinance,
    read_symbols,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="QMT 优先获取 A 股行情；QMT 不可用时可审计地回退到公共数据"
    )
    parser.add_argument("--symbols", default="config/symbols.txt")
    parser.add_argument("--start-date", required=True, help="YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument(
        "--source",
        choices=["qmt", "qmt-first", "public"],
        default="qmt-first",
        help="qmt=只用 QMT；qmt-first=QMT 失败后回退公共数据；public=只用公共数据",
    )
    parser.add_argument("--public-providers", default="akshare,baostock,yfinance")
    parser.add_argument("--adjust", default="none", choices=["none", "qfq", "hfq"])
    parser.add_argument("--output-dir", default="data/market")
    parser.add_argument("--per-symbol-timeout", type=int, default=45)
    return parser


def _canonical_dates(start_date: str, end_date: str) -> tuple[str, str]:
    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        raise SystemExit("日期必须是 YYYYMMDD 或 YYYY-MM-DD")
    start_text = start.strftime("%Y%m%d")
    end_text = end.strftime("%Y%m%d")
    if start_text > end_text:
        raise SystemExit("start-date 不能晚于 end-date")
    return start_text, end_text


def _write_manifest(
    output: Path,
    *,
    source_requested: str,
    source_used: str,
    symbols: list[str],
    start_date: str,
    end_date: str,
    qmt_error: str = "",
    public_results: list[ProviderResult] | None = None,
) -> None:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_requested": source_requested,
        "source_used": source_used,
        "symbols_requested": symbols,
        "start_date": start_date,
        "end_date": end_date,
        "qmt_error": qmt_error,
        "public_providers": [result.__dict__ for result in (public_results or [])],
        "data_policy": (
            "QMT is preferred; public providers are used only when explicitly selected "
            "or as qmt-first fallback"
        ),
    }
    (output / "market-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _fetch_public(
    symbols: list[str],
    start_date: str,
    end_date: str,
    output: Path,
    providers: list[str],
    adjust: str,
    timeout: int,
) -> tuple[pd.DataFrame, list[ProviderResult]]:
    public_output = output / ".public"
    public_output.mkdir(parents=True, exist_ok=True)
    results: list[ProviderResult] = []
    for provider in providers:
        if provider == "akshare":
            result = fetch_akshare(
                symbols,
                start_date,
                end_date,
                public_output,
                adjust="" if adjust == "none" else adjust,
                timeout_seconds=timeout,
            )
        elif provider == "baostock":
            result = fetch_baostock(
                symbols,
                start_date,
                end_date,
                public_output,
                adjust="" if adjust == "none" else adjust,
                timeout_seconds=timeout,
            )
        elif provider == "yfinance":
            result = fetch_yfinance(symbols, start_date, end_date, public_output)
        else:
            raise SystemExit(f"不支持的公共数据源: {provider}")
        results.append(result)
        print(
            f"{provider}: rows={result.rows}, symbols={result.symbols}, "
            f"errors={len(result.errors)}"
        )

    for result in results:
        for path in result.files:
            candidate = Path(path)
            if candidate.is_file() and candidate.stat().st_size > 0:
                frame = pd.read_csv(candidate)
                if not frame.empty:
                    return frame, results
    return pd.DataFrame(), results


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    symbols = read_symbols(args.symbols)
    if not symbols:
        raise SystemExit("symbols 文件没有有效证券代码")
    start_date, end_date = _canonical_dates(args.start_date, args.end_date)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    qmt_error = ""
    source_used = ""
    frame = pd.DataFrame()
    public_results: list[ProviderResult] = []

    if args.source in {"qmt", "qmt-first"}:
        try:
            frame = QMTDataClient().fetch_history(
                symbols, start_date, end_date, dividend_type=args.adjust
            )
            requested_symbols = {normalize_symbol(symbol) for symbol in symbols}
            returned_symbols = set(frame["symbol"].dropna().map(normalize_symbol))
            missing_symbols = sorted(requested_symbols - returned_symbols)
            if missing_symbols:
                raise QMTDataError(
                    "QMT 未覆盖请求证券: " + ", ".join(missing_symbols)
                )
            source_used = "qmt"
            print(f"qmt: rows={len(frame)}, symbols={frame['symbol'].nunique()}")
        except (QMTDataError, OSError, RuntimeError) as exc:
            qmt_error = f"{type(exc).__name__}: {exc}"
            print(f"qmt: unavailable: {qmt_error}")
            if args.source == "qmt":
                raise SystemExit(qmt_error)

    if frame.empty and args.source in {"qmt-first", "public"}:
        frame, public_results = _fetch_public(
            symbols,
            start_date,
            end_date,
            output,
            [name.strip().lower() for name in args.public_providers.split(",") if name.strip()],
            args.adjust,
            args.per_symbol_timeout,
        )
        source_used = "public-fallback" if args.source == "qmt-first" else "public"

    if frame.empty:
        raise SystemExit("QMT 和公共数据源均未返回数据")
    destination = output / "market_daily.csv"
    frame.to_csv(destination, index=False)
    _write_manifest(
        output,
        source_requested=args.source,
        source_used=source_used,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        qmt_error=qmt_error,
        public_results=public_results,
    )
    print(f"source={source_used} rows={len(frame)} output={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
