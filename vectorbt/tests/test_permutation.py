import numpy as np
import pandas as pd
import pytest

from bttool.permutation import (
    _permute_prices,
    _shuffle_signals,
    compute_stats,
    significance_stars,
)


@pytest.fixture
def ohlcv():
    rng = np.random.default_rng(0)
    n = 100
    close = 100 * np.cumprod(1 + rng.normal(0.001, 0.02, n))
    return pd.DataFrame(
        {
            "Open": close * 0.99,
            "High": close * 1.01,
            "Low": close * 0.98,
            "Close": close,
            "Volume": rng.integers(1000, 5000, n),
        },
        index=pd.date_range("2024-01-01", periods=n, freq="D"),
    )


# ------------------------------------------------------------------ price permutation

def test_permute_prices_preserves_endpoints(ohlcv):
    rng = np.random.default_rng(42)
    permuted = _permute_prices(ohlcv, rng)

    # Permuting log returns preserves the first and last close exactly
    assert permuted["Close"].iloc[0] == pytest.approx(ohlcv["Close"].iloc[0])
    assert permuted["Close"].iloc[-1] == pytest.approx(ohlcv["Close"].iloc[-1])


def test_permute_prices_preserves_return_distribution(ohlcv):
    rng = np.random.default_rng(42)
    permuted = _permute_prices(ohlcv, rng)

    orig_returns = np.sort(np.diff(np.log(ohlcv["Close"].to_numpy())))
    perm_returns = np.sort(np.diff(np.log(permuted["Close"].to_numpy())))
    np.testing.assert_allclose(orig_returns, perm_returns)


def test_permute_prices_changes_path(ohlcv):
    rng = np.random.default_rng(42)
    permuted = _permute_prices(ohlcv, rng)
    assert not np.allclose(permuted["Close"].to_numpy(), ohlcv["Close"].to_numpy())


def test_permute_prices_keeps_intrabar_ratios(ohlcv):
    rng = np.random.default_rng(42)
    permuted = _permute_prices(ohlcv, rng)
    np.testing.assert_allclose(
        (permuted["High"] / permuted["Close"]).to_numpy(),
        (ohlcv["High"] / ohlcv["Close"]).to_numpy(),
    )


def test_permute_prices_without_close_falls_back_to_row_shuffle(ohlcv):
    rng = np.random.default_rng(42)
    no_close = ohlcv.drop(columns=["Close"])
    permuted = _permute_prices(no_close, rng)
    assert sorted(permuted["Open"].tolist()) == sorted(no_close["Open"].tolist())
    assert list(permuted.index) == list(no_close.index)


# ------------------------------------------------------------------ signal shuffle

def test_shuffle_signals_preserves_values_and_index():
    rng = np.random.default_rng(0)
    sig = pd.Series([1, 0, -1, 0, 1], index=pd.date_range("2024-01-01", periods=5))
    shuffled = _shuffle_signals(sig, rng)
    assert sorted(shuffled.tolist()) == sorted(sig.tolist())
    assert list(shuffled.index) == list(sig.index)


# ------------------------------------------------------------------ stats

def _results(observed, null):
    return {
        "observed": observed,
        "null": null,
        "n_permutations": max(len(v) for v in null.values()),
        "seed": 42,
    }


def test_compute_stats_p_value():
    # Observed 2.0 beats 90 of 100 null values -> p = 0.10
    null = list(np.linspace(-1, 1.9, 90)) + list(np.linspace(2.1, 3.0, 10))
    results = _results({"sharpe_ratio": 2.0}, {"sharpe_ratio": null})
    stats = compute_stats(results, correction="none")
    assert stats["sharpe_ratio"]["p_value"] == pytest.approx(0.10)
    assert stats["sharpe_ratio"]["percentile"] == pytest.approx(90.0)


def test_compute_stats_bonferroni():
    null = {"sharpe_ratio": [0.0] * 80 + [1.0] * 20, "total_return": [0.0] * 95 + [1.0] * 5}
    results = _results({"sharpe_ratio": 0.5, "total_return": 0.5}, null)
    stats = compute_stats(results, correction="bonferroni")
    # raw p: 0.20 and 0.05; bonferroni multiplies by 2
    assert stats["sharpe_ratio"]["p_value_adjusted"] == pytest.approx(0.40)
    assert stats["total_return"]["p_value_adjusted"] == pytest.approx(0.10)


def test_compute_stats_holm():
    null = {"sharpe_ratio": [0.0] * 80 + [1.0] * 20, "total_return": [0.0] * 95 + [1.0] * 5}
    results = _results({"sharpe_ratio": 0.5, "total_return": 0.5}, null)
    stats = compute_stats(results, correction="holm")
    # raw p sorted: total_return 0.05 (rank 0, x2), sharpe 0.20 (rank 1, x1)
    assert stats["total_return"]["p_value_adjusted"] == pytest.approx(0.10)
    assert stats["sharpe_ratio"]["p_value_adjusted"] == pytest.approx(0.20)


def test_compute_stats_handles_missing_metric():
    results = _results({"sharpe_ratio": None}, {"sharpe_ratio": []})
    stats = compute_stats(results, correction="none")
    assert stats["sharpe_ratio"]["p_value"] is None


def test_significance_stars():
    assert significance_stars(0.005) == "***"
    assert significance_stars(0.03) == "**"
    assert significance_stars(0.07) == "*"
    assert significance_stars(0.5) == ""
    assert significance_stars(None) == ""
