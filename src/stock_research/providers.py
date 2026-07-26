from __future__ import annotations

import json
import multiprocessing as mp
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from .data import normalize_symbol


CANONICAL_COLUMNS = [
    "date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "amount",
    "provider",
    "fetched_at",
    "adjust",
]


@dataclass
class ProviderResult:
    provider: str
    rows: int = 0
    symbols: int = 0
    files: list[str] | None = None
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        self.files = self.files or []
        self.errors = self.errors or []


def default_start_date() -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=30)).strftime("%Y%m%d")


def default_end_date() -> str:
    return datetime.now(timezone.utc).date().strftime("%Y%m%d")


def read_symbols(path: str | Path) -> list[str]:
    symbols: list[str] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        value = raw_line.split("#", 1)[0].strip()
        if not value:
            continue
        symbols.append(normalize_symbol(value))
    return sorted(set(symbols))


def exchange_code(symbol: str) -> str:
    """Return the six-digit code accepted by most mainland data endpoints."""
    return normalize_symbol(symbol).split(".", 1)[0]


def yahoo_ticker(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split(".", 1)
    suffix = {"XSHG": "SS", "XSHE": "SZ", "XBSE": "BJ"}[exchange]
    return f"{code}.{suffix}"


def baostock_code(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split(".", 1)
    prefix = {"XSHG": "sh", "XSHE": "sz", "XBSE": "bj"}[exchange]
    return f"{prefix}.{code}"


def akshare_sina_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split(".", 1)
    if exchange == "XBSE":
        raise ValueError("AKShare 新浪接口暂不支持北交所代码")
    prefix = "sh" if exchange == "XSHG" else "sz"
    return f"{prefix}{code}"


def _column_lookup(frame: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    columns = {str(column).strip().lower(): column for column in frame.columns}
    for candidate in candidates:
        if candidate.lower() in columns:
            return columns[candidate.lower()]
    return None


def normalize_provider_frame(
    frame: pd.DataFrame,
    symbol: str,
    provider: str,
    fetched_at: str,
    adjust: str,
) -> pd.DataFrame:
    """Normalize AKShare/yfinance-like frames without coupling the backtester to either."""
    if frame is None or frame.empty:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    data = frame.copy()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = ["_".join(str(part) for part in column if str(part) != "") for column in data.columns]
    if isinstance(data.index, pd.DatetimeIndex) and "date" not in data.columns and "Date" not in data.columns:
        data = data.reset_index()

    mappings = {
        "date": ("date", "Date", "日期"),
        "open": ("open", "Open", "开盘"),
        "high": ("high", "High", "最高"),
        "low": ("low", "Low", "最低"),
        "close": ("close", "Close", "收盘"),
        "adj_close": ("adj_close", "Adj Close", "Adj_Close", "收盘"),
        "volume": ("volume", "Volume", "成交量"),
        "amount": ("amount", "成交额"),
    }
    result = pd.DataFrame(index=data.index)
    for canonical, candidates in mappings.items():
        source = _column_lookup(data, candidates)
        if source is not None:
            result[canonical] = data[source]

    if "date" not in result.columns:
        result["date"] = data.index
    if "adj_close" not in result.columns:
        result["adj_close"] = result.get("close")
    if "amount" not in result.columns:
        result["amount"] = pd.NA

    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in result.columns]
    if missing:
        raise ValueError(f"{provider} 返回数据缺少字段: {missing}")

    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    for column in ["open", "high", "low", "close", "adj_close", "volume", "amount"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["symbol"] = normalize_symbol(symbol)
    result["provider"] = provider
    result["fetched_at"] = fetched_at
    result["adjust"] = adjust
    result = result[CANONICAL_COLUMNS].dropna(subset=["date", "close"])
    return result.sort_values("date").reset_index(drop=True)


def _akshare_symbol_worker(
    normalized_symbol: str,
    code: str,
    start_date: str,
    end_date: str,
    adjust: str,
    raw_path: str,
    status_path: str,
) -> None:
    """Run one external AKShare request in a killable child process."""
    try:
        import akshare as ak

        endpoint = "eastmoney"
        try:
            frame = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        except Exception as eastmoney_error:
            endpoint = "sina"
            try:
                frame = ak.stock_zh_a_daily(
                    symbol=akshare_sina_symbol(normalized_symbol),
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust,
                )
            except Exception as sina_error:
                raise RuntimeError(
                    f"eastmoney={type(eastmoney_error).__name__}: {eastmoney_error}; "
                    f"sina={type(sina_error).__name__}: {sina_error}"
                ) from sina_error
        frame.to_csv(raw_path, index=False)
        Path(status_path).write_text(
            json.dumps({"ok": True, "rows": len(frame), "endpoint": endpoint}),
            encoding="utf-8",
        )
    except BaseException as exc:  # child must report library/network failures to the parent
        Path(status_path).write_text(
            json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False),
            encoding="utf-8",
        )


def fetch_akshare(
    symbols: list[str],
    start_date: str,
    end_date: str,
    output_dir: str | Path,
    adjust: str = "",
    timeout_seconds: int = 45,
) -> ProviderResult:
    """Fetch daily bars from the public AKShare interface."""
    try:
        import akshare as ak
    except ImportError as exc:  # pragma: no cover - exercised in CI environment
        raise RuntimeError("未安装 AKShare，请先 pip install akshare") from exc

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).isoformat()
    result = ProviderResult(provider="akshare")
    frames: list[pd.DataFrame] = []
    temporary = output / ".tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    context = mp.get_context("spawn")
    for symbol in symbols:
        code = exchange_code(symbol)
        raw_path = temporary / f"akshare_{code}.csv"
        status_path = temporary / f"akshare_{code}.json"
        try:
            process = context.Process(
                target=_akshare_symbol_worker,
                args=(symbol, code, start_date, end_date, adjust, str(raw_path), str(status_path)),
            )
            process.start()
            process.join(timeout_seconds)
            if process.is_alive():
                process.terminate()
                process.join(5)
                if process.is_alive():
                    process.kill()
                    process.join()
                raise TimeoutError(f"超过 {timeout_seconds} 秒")
            if not status_path.exists():
                raise RuntimeError(f"子进程退出且未生成状态，exitcode={process.exitcode}")
            status = json.loads(status_path.read_text(encoding="utf-8"))
            if not status.get("ok"):
                raise RuntimeError(status.get("error", "未知 AKShare 错误"))
            frame = pd.read_csv(raw_path)
            normalized = normalize_provider_frame(frame, symbol, "akshare", fetched_at, adjust or "none")
            if not normalized.empty:
                frames.append(normalized)
                result.symbols += 1
                result.rows += len(normalized)
        except Exception as exc:  # keep a single bad symbol from losing the snapshot
            result.errors.append(f"{symbol}: {type(exc).__name__}: {exc}")
        finally:
            raw_path.unlink(missing_ok=True)
            status_path.unlink(missing_ok=True)

    destination = output / "akshare_daily.csv"
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CANONICAL_COLUMNS)
    combined.to_csv(destination, index=False)
    result.files.append(str(destination))
    return result


def _baostock_symbol_worker(
    normalized_symbol: str,
    start_date: str,
    end_date: str,
    adjust: str,
    raw_path: str,
    status_path: str,
) -> None:
    try:
        import baostock as bs

        login = bs.login()
        if login.error_code != "0":
            raise RuntimeError(f"login {login.error_code}: {login.error_msg}")
        try:
            adjust_flag = {"": "3", "qfq": "2", "hfq": "1"}[adjust]
            query = bs.query_history_k_data_plus(
                baostock_code(normalized_symbol),
                "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,pctChg,isST",
                start_date=datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d"),
                end_date=datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d"),
                frequency="d",
                adjustflag=adjust_flag,
            )
            if query.error_code != "0":
                raise RuntimeError(f"query {query.error_code}: {query.error_msg}")
            rows: list[list[str]] = []
            while query.next():
                rows.append(query.get_row_data())
            frame = pd.DataFrame(rows, columns=query.fields)
            frame.to_csv(raw_path, index=False)
            Path(status_path).write_text(
                json.dumps({"ok": True, "rows": len(frame)}),
                encoding="utf-8",
            )
        finally:
            bs.logout()
    except BaseException as exc:
        Path(status_path).write_text(
            json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False),
            encoding="utf-8",
        )


def fetch_baostock(
    symbols: list[str],
    start_date: str,
    end_date: str,
    output_dir: str | Path,
    adjust: str = "",
    timeout_seconds: int = 45,
) -> ProviderResult:
    """Fetch daily bars from Baostock's free public service."""
    try:
        import baostock  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised in CI environment
        raise RuntimeError("未安装 Baostock，请先 pip install baostock") from exc

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).isoformat()
    result = ProviderResult(provider="baostock")
    frames: list[pd.DataFrame] = []
    temporary = output / ".tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    context = mp.get_context("spawn")
    for symbol in symbols:
        code = exchange_code(symbol)
        raw_path = temporary / f"baostock_{code}.csv"
        status_path = temporary / f"baostock_{code}.json"
        try:
            process = context.Process(
                target=_baostock_symbol_worker,
                args=(symbol, start_date, end_date, adjust, str(raw_path), str(status_path)),
            )
            process.start()
            process.join(timeout_seconds)
            if process.is_alive():
                process.terminate()
                process.join(5)
                if process.is_alive():
                    process.kill()
                    process.join()
                raise TimeoutError(f"超过 {timeout_seconds} 秒")
            if not status_path.exists():
                raise RuntimeError(f"子进程退出且未生成状态，exitcode={process.exitcode}")
            status = json.loads(status_path.read_text(encoding="utf-8"))
            if not status.get("ok"):
                raise RuntimeError(status.get("error", "未知 Baostock 错误"))
            frame = pd.read_csv(raw_path)
            normalized = normalize_provider_frame(frame, symbol, "baostock", fetched_at, adjust or "none")
            if not normalized.empty:
                frames.append(normalized)
                result.symbols += 1
                result.rows += len(normalized)
        except Exception as exc:
            result.errors.append(f"{symbol}: {type(exc).__name__}: {exc}")
        finally:
            raw_path.unlink(missing_ok=True)
            status_path.unlink(missing_ok=True)

    destination = output / "baostock_daily.csv"
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CANONICAL_COLUMNS)
    combined.to_csv(destination, index=False)
    result.files.append(str(destination))
    return result


def fetch_yfinance(
    symbols: list[str],
    start_date: str,
    end_date: str,
    output_dir: str | Path,
) -> ProviderResult:
    """Fetch public Yahoo Finance daily bars as an optional cross-market fallback."""
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - exercised in CI environment
        raise RuntimeError("未安装 yfinance，请先 pip install yfinance") from exc

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).isoformat()
    result = ProviderResult(provider="yfinance")
    frames: list[pd.DataFrame] = []
    # Yahoo's end date is exclusive, so add one day.
    end_exclusive = (datetime.strptime(end_date, "%Y%m%d").date() + timedelta(days=1)).strftime("%Y-%m-%d")
    for symbol in symbols:
        ticker = yahoo_ticker(symbol)
        try:
            frame = yf.download(
                ticker,
                start=datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d"),
                end=end_exclusive,
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if isinstance(frame.columns, pd.MultiIndex):
                # yfinance may return either (field, ticker) or (ticker, field).
                if ticker in frame.columns.get_level_values(-1):
                    frame = frame.xs(ticker, axis=1, level=-1)
                elif ticker in frame.columns.get_level_values(0):
                    frame = frame.xs(ticker, axis=1, level=0)
            normalized = normalize_provider_frame(frame, symbol, "yfinance", fetched_at, "none")
            if not normalized.empty:
                frames.append(normalized)
                result.symbols += 1
                result.rows += len(normalized)
        except Exception as exc:
            result.errors.append(f"{symbol} ({ticker}): {type(exc).__name__}: {exc}")

    destination = output / "yfinance_daily.csv"
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CANONICAL_COLUMNS)
    combined.to_csv(destination, index=False)
    result.files.append(str(destination))
    return result


def write_manifest(
    output_dir: str | Path,
    *,
    start_date: str,
    end_date: str,
    symbols: list[str],
    providers: list[ProviderResult],
) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_date": start_date,
        "end_date": end_date,
        "symbols_requested": symbols,
        "providers": [asdict(provider) for provider in providers],
        "license_note": "Data is obtained from third-party public endpoints; verify each provider's terms before redistribution or commercial use.",
    }
    destination = output / "manifest.json"
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination
