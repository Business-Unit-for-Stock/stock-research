from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from stock_research.providers import (  # noqa: E402
    default_end_date,
    default_start_date,
    fetch_akshare,
    fetch_baostock,
    fetch_yfinance,
    read_symbols,
    write_manifest,
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="获取免费公开接口的 A 股日线数据快照")
    command.add_argument("--symbols", default="config/symbols.txt")
    command.add_argument("--start-date", default=None, help="YYYYMMDD，默认最近 30 天")
    command.add_argument("--end-date", default=None, help="YYYYMMDD，默认今天")
    command.add_argument(
        "--providers",
        default="akshare,baostock,yfinance",
        help="逗号分隔：akshare,baostock,yfinance",
    )
    command.add_argument("--adjust", default="none", choices=["none", "qfq", "hfq"])
    command.add_argument("--output-dir", default="data/snapshot")
    command.add_argument("--per-symbol-timeout", type=int, default=45)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    symbols = read_symbols(args.symbols)
    if not symbols:
        raise SystemExit("symbols 文件没有有效证券代码")
    start_date = args.start_date or default_start_date()
    end_date = args.end_date or default_end_date()
    if start_date > end_date:
        raise SystemExit("start-date 不能晚于 end-date")

    results = []
    providers = [name.strip().lower() for name in args.providers.split(",") if name.strip()]
    for provider in providers:
        if provider == "akshare":
            adjust = "" if args.adjust == "none" else args.adjust
            result = fetch_akshare(
                symbols,
                start_date,
                end_date,
                args.output_dir,
                adjust=adjust,
                timeout_seconds=args.per_symbol_timeout,
            )
        elif provider == "baostock":
            adjust = "" if args.adjust == "none" else args.adjust
            result = fetch_baostock(
                symbols,
                start_date,
                end_date,
                args.output_dir,
                adjust=adjust,
                timeout_seconds=args.per_symbol_timeout,
            )
        elif provider == "yfinance":
            result = fetch_yfinance(symbols, start_date, end_date, args.output_dir)
        else:
            raise SystemExit(f"不支持的数据源: {provider}")
        results.append(result)
        print(f"{provider}: rows={result.rows}, symbols={result.symbols}, errors={len(result.errors)}")
        for error in result.errors[:10]:
            print(f"  {error}")

    write_manifest(
        args.output_dir,
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
        providers=results,
    )
    if not any(result.rows for result in results):
        raise SystemExit("所有数据源均未返回数据")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
