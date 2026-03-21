"""Permutation testing for backtest statistical validation."""
from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ------------------------------------------------------------------ metrics

def _get_metric(portfolio, name: str) -> Optional[float]:
    try:
        if name == "sharpe_ratio":
            return float(portfolio.sharpe_ratio())
        if name == "total_return":
            return float(portfolio.total_return())
        if name == "max_drawdown":
            return float(portfolio.max_drawdown())
        if name == "sortino_ratio":
            return float(portfolio.sortino_ratio())
    except Exception:
        pass
    return None


# ------------------------------------------------------------------ shuffle

def _shuffle_signals(signals: pd.Series, rng: np.random.Generator) -> pd.Series:
    """Randomly permute signal values, preserving index."""
    shuffled_values = rng.permutation(signals.values)
    return pd.Series(shuffled_values, index=signals.index, name=signals.name)


def _extract_signals(portfolio) -> Optional[pd.Series]:
    """Try to extract the entry/exit signal series from a portfolio."""
    try:
        # vectorbt stores signals as records; attempt to reconstruct from orders
        orders = portfolio.orders.records_readable
        if "Side" in orders.columns and "Timestamp" in orders.columns:
            signal = pd.Series(0, index=portfolio.wrapper.index)
            entries = orders[orders["Side"] == "Buy"]["Timestamp"]
            exits   = orders[orders["Side"] == "Sell"]["Timestamp"]
            signal.loc[entries] = 1
            signal.loc[exits]   = -1
            return signal
    except Exception:
        pass
    return None


# ------------------------------------------------------------------ core

def run_permutation_test(
    strategy_fn,
    data: pd.DataFrame,
    original_portfolio,
    n_permutations: int = 1000,
    seed: int = 42,
    metrics: List[str] = ("sharpe_ratio", "total_return"),
    n_jobs: int = 1,
) -> Dict[str, Any]:
    """Run permutation test and return raw results dict (without p-value correction).

    Strategy must accept (data, signals) where signals is a pd.Series,
    OR just (data) if it generates signals internally. We prefer the former.
    Falls back to calling strategy_fn(data) and shuffling portfolio returns.
    """
    rng = np.random.default_rng(seed)
    metrics = list(metrics)

    # Observed values
    observed = {m: _get_metric(original_portfolio, m) for m in metrics}

    # Try to get signals from portfolio for shuffling
    signals = _extract_signals(original_portfolio)
    use_signal_shuffle = signals is not None and hasattr(strategy_fn, "__code__") and \
                         strategy_fn.__code__.co_argcount >= 2

    # Null distribution
    null: Dict[str, List[float]] = {m: [] for m in metrics}

    for i in range(n_permutations):
        try:
            if use_signal_shuffle:
                shuffled = _shuffle_signals(signals, rng)
                pf = strategy_fn(data, shuffled)
            else:
                # Shuffle the data rows to randomise timing
                shuffled_data = data.sample(frac=1, random_state=rng.integers(0, 2**31)).reset_index(drop=True)
                shuffled_data.index = data.index
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    pf = strategy_fn(shuffled_data)
            for m in metrics:
                v = _get_metric(pf, m)
                if v is not None:
                    null[m].append(v)
        except Exception:
            continue

    return {"observed": observed, "null": null, "n_permutations": n_permutations, "seed": seed}


# ------------------------------------------------------------------ stats

def compute_stats(
    results: Dict[str, Any],
    correction: str = "bonferroni",
) -> Dict[str, Any]:
    """Compute p-values, percentiles, and apply multiple-testing correction."""
    observed = results["observed"]
    null = results["null"]
    n = results["n_permutations"]
    metrics = list(observed.keys())

    stats: Dict[str, Dict] = {}
    raw_p: Dict[str, float] = {}

    for m in metrics:
        obs = observed.get(m)
        dist = null.get(m, [])
        if obs is None or not dist:
            stats[m] = {"observed": obs, "null_mean": None, "null_std": None,
                        "p_value": None, "percentile": None}
            continue
        arr = np.array(dist)
        p = float(np.mean(arr >= obs))
        raw_p[m] = p
        stats[m] = {
            "observed":   round(obs, 6),
            "null_mean":  round(float(arr.mean()), 6),
            "null_std":   round(float(arr.std()), 6),
            "p_value":    round(p, 6),
            "percentile": round(float(np.mean(arr <= obs) * 100), 2),
        }

    # Multiple testing correction
    n_tests = len(raw_p)
    if correction == "bonferroni" and n_tests > 1:
        for m in raw_p:
            adjusted = min(1.0, raw_p[m] * n_tests)
            stats[m]["p_value_adjusted"] = round(adjusted, 6)
            stats[m]["correction"] = "bonferroni"
    elif correction == "holm" and n_tests > 1:
        sorted_metrics = sorted(raw_p, key=lambda x: raw_p[x])
        for rank, m in enumerate(sorted_metrics):
            adjusted = min(1.0, raw_p[m] * (n_tests - rank))
            stats[m]["p_value_adjusted"] = round(adjusted, 6)
            stats[m]["correction"] = "holm"

    return stats


def significance_stars(p: Optional[float]) -> str:
    if p is None:
        return ""
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


# ------------------------------------------------------------------ save

def save_permutation_results(
    run_dir: Path,
    results: Dict[str, Any],
    stats: Dict[str, Any],
) -> Path:
    null = results.get("null", {})
    output = {
        "n_permutations": results["n_permutations"],
        "seed":           results["seed"],
        "results":        stats,
        "distributions":  {m: [round(v, 6) for v in null.get(m, [])] for m in stats},
    }
    path = run_dir / "permutation.json"
    path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return path
