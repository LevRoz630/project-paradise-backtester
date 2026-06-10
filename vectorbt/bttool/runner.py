"""Data fetching and strategy execution for bt run."""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


def _hash_dataframe(df: pd.DataFrame) -> str:
    """Compute a stable SHA256 hash of a DataFrame's bytes."""
    raw = pd.util.hash_pandas_object(df, index=True).values.tobytes()
    return hashlib.sha256(raw).hexdigest()


def fetch_data(
    source: str,
    symbol: str,
    interval: str,
    start: str,
    end: str,
    exchange: Optional[str] = None,
    file: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch OHLCV data from the specified source.

    Returns a DataFrame with columns: Open, High, Low, Close, Volume.
    """
    if source == "csv":
        if not file:
            raise ValueError("--file is required for source=csv")
        df = pd.read_csv(file, index_col=0, parse_dates=True)
        return df

    if source == "yfinance":
        from vectorbt.data import YFData
        data = YFData.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
        )
        return data.get()

    if source == "ccxt":
        if not exchange:
            raise ValueError("--exchange is required for source=ccxt")
        from vectorbt.data import CCXTData
        data = CCXTData.download(
            symbol,
            exchange=exchange,
            start=start,
            end=end,
            timeframe=interval,
        )
        return data.get()

    raise ValueError(f"Unknown source: {source!r}. Use ccxt, yfinance, or csv.")


def load_strategy(strategy_path: str):
    """Import a strategy file and return its run() function.

    The strategy file must define:
        def run(data: pd.DataFrame) -> vbt.Portfolio: ...
    """
    path = Path(strategy_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Strategy file not found: {path}")

    spec = importlib.util.spec_from_file_location("_bt_strategy", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_bt_strategy"] = module
    spec.loader.exec_module(module)

    if not hasattr(module, "run"):
        raise AttributeError(
            f"Strategy file {path} must define a top-level run(data) function."
        )
    return module.run


def extract_metrics(portfolio) -> Dict[str, Any]:
    """Extract key performance metrics from a vectorbt Portfolio object."""
    try:
        total_return = float(portfolio.total_return())
    except Exception:
        total_return = None

    try:
        sharpe = float(portfolio.sharpe_ratio())
    except Exception:
        sharpe = None

    try:
        max_dd = float(portfolio.max_drawdown())
    except Exception:
        max_dd = None

    try:
        trades = portfolio.trades
        total_trades = int(len(trades.records))
        win_rate = float(trades.win_rate()) if total_trades > 0 else None
    except Exception:
        total_trades = None
        win_rate = None

    return {
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
        "total_trades": total_trades,
    }
