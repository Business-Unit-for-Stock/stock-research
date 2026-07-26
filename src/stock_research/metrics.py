from __future__ import annotations

import math

import pandas as pd


def performance_summary(equity: pd.Series, annual_sessions: int = 252) -> dict[str, float]:
    values = pd.Series(equity, dtype="float64").dropna()
    if values.empty:
        return {
            "total_return": 0.0,
            "annualized_return": 0.0,
            "annualized_volatility": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
        }

    returns = values.pct_change().dropna()
    total_return = values.iloc[-1] / values.iloc[0] - 1.0 if values.iloc[0] else 0.0
    session_count = max(len(values) - 1, 1)
    annualized_return = (1.0 + total_return) ** (annual_sessions / session_count) - 1.0
    annualized_volatility = returns.std(ddof=1) * math.sqrt(annual_sessions) if len(returns) > 1 else 0.0
    sharpe = (
        returns.mean() / returns.std(ddof=1) * math.sqrt(annual_sessions)
        if len(returns) > 1 and returns.std(ddof=1) > 0
        else 0.0
    )
    drawdown = values / values.cummax() - 1.0
    return {
        "total_return": float(total_return),
        "annualized_return": float(annualized_return),
        "annualized_volatility": float(annualized_volatility),
        "sharpe": float(sharpe),
        "max_drawdown": float(drawdown.min()),
    }

