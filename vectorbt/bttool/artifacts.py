"""Artifact extraction, saving, and validation for backtest runs."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# ------------------------------------------------------------------ extraction

def extract_returns(portfolio) -> pd.DataFrame:
    """Extract returns time series from a vectorbt Portfolio."""
    returns = portfolio.returns()
    if isinstance(returns, pd.DataFrame):
        returns = returns.iloc[:, 0]
    cumulative = (1 + returns).cumprod() - 1
    df = pd.DataFrame({
        "returns": returns,
        "cumulative_returns": cumulative,
    })
    df.index.name = "timestamp"
    return df


def extract_equity(portfolio) -> pd.DataFrame:
    """Extract equity curve and drawdown from a vectorbt Portfolio."""
    equity = portfolio.value()
    if isinstance(equity, pd.DataFrame):
        equity = equity.iloc[:, 0]
    drawdown = portfolio.drawdown()
    if isinstance(drawdown, pd.DataFrame):
        drawdown = drawdown.iloc[:, 0]
    df = pd.DataFrame({
        "equity": equity,
        "drawdown": drawdown,
    })
    df.index.name = "timestamp"
    return df


def extract_trades(portfolio) -> pd.DataFrame:
    """Extract trade log from a vectorbt Portfolio."""
    try:
        records = portfolio.trades.records_readable
    except Exception:
        return pd.DataFrame(columns=[
            "entry_time", "exit_time", "direction", "size",
            "entry_price", "exit_price", "pnl", "return", "fees",
        ])

    col_map = {
        "Entry Timestamp": "entry_time",
        "Exit Timestamp": "exit_time",
        "Direction": "direction",
        "Size": "size",
        "Avg Entry Price": "entry_price",
        "Avg Exit Price": "exit_price",
        "PnL": "pnl",
        "Return": "return",
        "Entry Fees": "fees",
    }

    df = records.rename(columns={k: v for k, v in col_map.items() if k in records.columns})

    required = ["entry_time", "exit_time", "direction", "size",
                "entry_price", "exit_price", "pnl", "return", "fees"]
    for col in required:
        if col not in df.columns:
            df[col] = None

    return df[required].reset_index(drop=True)


def extract_full_metrics(portfolio) -> Dict[str, Any]:
    """Extract the full metrics.json schema from a vectorbt Portfolio."""
    def _safe(fn):
        try:
            v = fn()
            return float(v) if v is not None else None
        except Exception:
            return None

    trades = portfolio.trades
    total_trades = int(len(trades.records)) if hasattr(trades, "records") else None

    try:
        winning = trades.winning
        losing = trades.losing
        avg_win = float(winning.returns.mean()) if len(winning.records) > 0 else None
        avg_loss = float(losing.returns.mean()) if len(losing.records) > 0 else None
        avg_trade_return = float(trades.returns.mean()) if total_trades else None
        profit_factor = (
            float(winning.pnl.sum() / abs(losing.pnl.sum()))
            if len(losing.records) > 0 and losing.pnl.sum() != 0
            else None
        )
    except Exception:
        avg_win = avg_loss = avg_trade_return = profit_factor = None

    return {
        "total_return":      _safe(portfolio.total_return),
        "annualized_return": _safe(portfolio.annualized_return),
        "sharpe_ratio":      _safe(portfolio.sharpe_ratio),
        "sortino_ratio":     _safe(portfolio.sortino_ratio),
        "max_drawdown":      _safe(portfolio.max_drawdown),
        "win_rate":          _safe(lambda: trades.win_rate()) if total_trades else None,
        "profit_factor":     profit_factor,
        "total_trades":      total_trades,
        "avg_trade_return":  avg_trade_return,
        "avg_win":           avg_win,
        "avg_loss":          avg_loss,
    }


# ------------------------------------------------------------------ validation

RETURNS_SCHEMA = {
    "returns":            float,
    "cumulative_returns": float,
}

EQUITY_SCHEMA = {
    "equity":   float,
    "drawdown": float,
}

TRADES_SCHEMA = {
    "entry_time":  None,
    "exit_time":   None,
    "direction":   None,
    "size":        float,
    "entry_price": float,
    "exit_price":  float,
    "pnl":         float,
    "return":      float,
}


def validate(name: str, df: pd.DataFrame, schema: Dict[str, Any]) -> List[str]:
    """Validate a DataFrame against a column schema. Returns list of error strings."""
    errors = []
    for col, dtype in schema.items():
        if col not in df.columns:
            errors.append(f"Missing required column '{col}'")
            continue
        if dtype is not None:
            if not pd.api.types.is_float_dtype(df[col]) and df[col].notna().any():
                try:
                    df[col].astype(float)
                except Exception:
                    errors.append(f"Column '{col}' cannot be cast to float")
        if df[col].isna().all() and len(df) > 0:
            errors.append(f"Column '{col}' is entirely NaN")
    return errors


# ------------------------------------------------------------------ save

def save_artifacts(run_dir: Path, portfolio) -> Tuple[Dict[str, str], List[str]]:
    """Extract, validate, and save all artifacts. Returns (paths_dict, errors)."""
    all_errors: List[str] = []
    saved: Dict[str, str] = {}

    # returns.parquet
    try:
        returns_df = extract_returns(portfolio)
        errs = validate("returns.parquet", returns_df, RETURNS_SCHEMA)
        if errs:
            all_errors += [f"returns.parquet: {e}" for e in errs]
        path = run_dir / "returns.parquet"
        returns_df.to_parquet(path)
        saved["returns"] = str(path)
    except Exception as e:
        all_errors.append(f"returns.parquet: {e}")

    # equity.parquet
    try:
        equity_df = extract_equity(portfolio)
        errs = validate("equity.parquet", equity_df, EQUITY_SCHEMA)
        if errs:
            all_errors += [f"equity.parquet: {e}" for e in errs]
        path = run_dir / "equity.parquet"
        equity_df.to_parquet(path)
        saved["equity"] = str(path)
    except Exception as e:
        all_errors.append(f"equity.parquet: {e}")

    # trades.csv
    try:
        trades_df = extract_trades(portfolio)
        errs = validate("trades.csv", trades_df, TRADES_SCHEMA)
        if errs:
            all_errors += [f"trades.csv: {e}" for e in errs]
        path = run_dir / "trades.csv"
        trades_df.to_csv(path, index=False)
        saved["trades"] = str(path)
    except Exception as e:
        all_errors.append(f"trades.csv: {e}")

    return saved, all_errors
