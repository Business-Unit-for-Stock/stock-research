from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_BAR_COLUMNS = {"date", "symbol", "open", "high", "low", "close", "volume"}
PRICE_COLUMNS = ("open", "high", "low", "close")


class DataValidationError(ValueError):
    """Raised when market data violates the repository data contract."""


def normalize_symbol(value: Any) -> str:
    """Normalize common Chinese security code forms to an explicit exchange suffix."""
    raw = str(value).strip().upper()
    if not raw:
        raise DataValidationError("证券代码不能为空")

    suffix_aliases = {
        ".SH": ".XSHG",
        ".SS": ".XSHG",
        ".XSHG": ".XSHG",
        ".SZ": ".XSHE",
        ".XSHE": ".XSHE",
        ".BJ": ".XBSE",
        ".XBSE": ".XBSE",
    }
    for suffix, normalized_suffix in suffix_aliases.items():
        if raw.endswith(suffix):
            code = raw[: -len(suffix)]
            if code.isdigit():
                return f"{code.zfill(6)}{normalized_suffix}"

    if raw.startswith(("SH", "SZ", "BJ")) and raw[2:].isdigit():
        prefix_to_suffix = {"SH": ".XSHG", "SZ": ".XSHE", "BJ": ".XBSE"}
        return f"{raw[2:].zfill(6)}{prefix_to_suffix[raw[:2]]}"

    if raw.isdigit():
        code = raw.zfill(6)
        if code.startswith(("4", "8")):
            exchange = ".XBSE"
        elif code.startswith(("5", "6", "9")):
            exchange = ".XSHG"
        else:
            exchange = ".XSHE"
        return f"{code}{exchange}"

    raise DataValidationError(f"无法识别证券代码: {value!r}")


def _coerce_bool(series: pd.Series, default: bool = False) -> pd.Series:
    if series.empty:
        return series.astype(bool)
    true_values = {"1", "true", "t", "yes", "y", "是"}
    false_values = {"0", "false", "f", "no", "n", "否", "", "nan", "none"}

    def convert(value: Any) -> bool:
        if pd.isna(value):
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        normalized = str(value).strip().lower()
        if normalized in true_values:
            return True
        if normalized in false_values:
            return False
        raise DataValidationError(f"无法识别布尔值: {value!r}")

    return series.map(convert).astype(bool)


def prepare_bars(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize and validate a daily OHLCV frame."""
    if frame is None or frame.empty:
        raise DataValidationError("行情数据不能为空")

    bars = frame.copy()
    bars.columns = [str(column).strip().lower() for column in bars.columns]
    missing = REQUIRED_BAR_COLUMNS - set(bars.columns)
    if missing:
        raise DataValidationError(f"缺少行情字段: {sorted(missing)}")

    bars["date"] = pd.to_datetime(bars["date"], errors="coerce").dt.normalize()
    bars["symbol"] = bars["symbol"].map(normalize_symbol)
    for column in (*PRICE_COLUMNS, "volume", "prev_close", "limit_up", "limit_down"):
        if column in bars.columns:
            bars[column] = pd.to_numeric(bars[column], errors="coerce")

    for column in ("suspended", "st"):
        if column not in bars.columns:
            bars[column] = False
        else:
            bars[column] = _coerce_bool(bars[column])

    bars = bars.sort_values(["symbol", "date"], kind="stable").reset_index(drop=True)
    derived_prev_close = bars.groupby("symbol", sort=False)["close"].shift(1)
    if "prev_close" not in bars.columns:
        bars["prev_close"] = derived_prev_close
    else:
        bars["prev_close"] = bars["prev_close"].fillna(derived_prev_close)
    bars["prev_close"] = bars["prev_close"].fillna(bars["close"])

    validate_bars(bars)
    return bars.sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)


def validate_bars(bars: pd.DataFrame) -> None:
    if bars["date"].isna().any():
        raise DataValidationError("存在无法解析的交易日期")
    if bars.duplicated(["date", "symbol"]).any():
        duplicates = bars.loc[bars.duplicated(["date", "symbol"], keep=False), ["date", "symbol"]]
        raise DataValidationError(f"存在重复行情主键: {duplicates.head().to_dict('records')}")
    if bars[list(PRICE_COLUMNS)].isna().any().any():
        raise DataValidationError("OHLC 价格存在空值或非数字")
    if (bars[list(PRICE_COLUMNS)] <= 0).any().any():
        raise DataValidationError("OHLC 价格必须大于 0")
    if bars["volume"].isna().any() or (bars["volume"] < 0).any():
        raise DataValidationError("成交量必须是大于等于 0 的数字")
    if bars["prev_close"].isna().any() or (bars["prev_close"] <= 0).any():
        raise DataValidationError("前收盘价必须大于 0")

    highest_body = bars[["open", "close", "low"]].max(axis=1)
    lowest_body = bars[["open", "close", "high"]].min(axis=1)
    if (bars["high"] < highest_body).any():
        raise DataValidationError("最高价小于开盘价、收盘价或最低价")
    if (bars["low"] > lowest_body).any():
        raise DataValidationError("最低价大于开盘价、收盘价或最高价")


def load_bars_csv(path: str | Path) -> pd.DataFrame:
    return prepare_bars(pd.read_csv(Path(path)))

