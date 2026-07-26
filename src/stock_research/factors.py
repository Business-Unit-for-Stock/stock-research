from __future__ import annotations

import pandas as pd

from .data import prepare_bars


def momentum(bars: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """Close-to-close momentum observed at each session close."""
    if lookback < 1:
        raise ValueError("lookback 必须大于等于 1")
    clean = prepare_bars(bars)
    result = clean[["date", "symbol", "close"]].copy()
    result["score"] = result.groupby("symbol", sort=False)["close"].pct_change(lookback)
    return result[["date", "symbol", "score"]]


def moving_average_gap(bars: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Percentage distance between close and trailing moving average."""
    if window < 2:
        raise ValueError("window 必须大于等于 2")
    clean = prepare_bars(bars)
    result = clean[["date", "symbol", "close"]].copy()
    moving_average = result.groupby("symbol", sort=False)["close"].transform(
        lambda values: values.rolling(window=window, min_periods=window).mean()
    )
    result["score"] = result["close"] / moving_average - 1.0
    return result[["date", "symbol", "score"]]


def top_n_equal_weight(
    factors: pd.DataFrame,
    top_n: int = 10,
    max_weight: float = 1.0,
) -> pd.DataFrame:
    """Convert close-time factor observations into long-only target weights."""
    required = {"date", "symbol", "score"}
    missing = required - set(factors.columns)
    if missing:
        raise ValueError(f"因子数据缺少字段: {sorted(missing)}")
    if top_n < 1:
        raise ValueError("top_n 必须大于等于 1")
    if not 0 < max_weight <= 1:
        raise ValueError("max_weight 必须位于 (0, 1]")

    clean = factors.copy()
    clean["date"] = pd.to_datetime(clean["date"]).dt.normalize()
    selected_frames: list[pd.DataFrame] = []
    for _, group in clean.dropna(subset=["score"]).groupby("date", sort=True):
        selected = group.sort_values(["score", "symbol"], ascending=[False, True]).head(top_n).copy()
        if selected.empty:
            continue
        selected["target_weight"] = min(1.0 / len(selected), max_weight)
        selected_frames.append(selected[["date", "symbol", "score", "target_weight"]])

    if not selected_frames:
        return pd.DataFrame(columns=["date", "symbol", "score", "target_weight"])
    return pd.concat(selected_frames, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)

