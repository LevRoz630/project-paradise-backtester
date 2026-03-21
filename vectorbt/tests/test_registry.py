import pytest
from vectorbt.registry import Registry


@pytest.fixture
def reg(tmp_path):
    return Registry(base_dir=str(tmp_path))


@pytest.fixture
def base_config():
    return {
        "data": {"source": "ccxt", "symbol": "BTC/USDT", "interval": "1h"},
        "date_range": {"start": "2024-01-01", "end": "2024-02-01"},
        "strategy": {"name": "buy_and_hold"},
        "execution": {"fees_bps": 10},
    }


# ------------------------------------------------------------------ dedup

def test_registry_dedup(reg, base_config):
    e1 = reg.create(base_config, summary={"sharpe_ratio": 1.2, "total_return": 0.15})
    e2 = reg.create(base_config, summary={"sharpe_ratio": 999})

    assert e1.run_id == e2.run_id
    assert len(reg.list()) == 1

    shown = reg.show(e1.run_id)
    assert set(shown.keys()) == {"run_id", "path", "config", "metrics", "versions"}


# ------------------------------------------------------------------ delete

def test_delete(reg, base_config):
    entry = reg.create(base_config, summary={"sharpe_ratio": 1.2, "total_return": 0.15})
    assert len(reg.list()) == 1

    reg.delete(entry.run_id)
    assert len(reg.list()) == 0


def test_delete_nonexistent(reg):
    with pytest.raises(FileNotFoundError):
        reg.delete("nonexistent_run_id")


# ------------------------------------------------------------------ compare

def test_compare(reg, base_config):
    config2 = {
        **base_config,
        "data": {**base_config["data"], "interval": "4h"},
    }
    e1 = reg.create(base_config, summary={"sharpe_ratio": 1.45, "total_return": 0.235, "max_drawdown": -0.123, "win_rate": 0.582})
    e2 = reg.create(config2, summary={"sharpe_ratio": 1.12, "total_return": 0.182, "max_drawdown": -0.151, "win_rate": 0.521})

    diff = reg.compare(e1.run_id, e2.run_id)

    assert diff["run_id_1"] == e1.run_id
    assert diff["run_id_2"] == e2.run_id
    assert "rows" in diff

    row_map = {r["field"]: r for r in diff["rows"]}
    assert row_map["Interval"]["run1"] == "1h"
    assert row_map["Interval"]["run2"] == "4h"
    assert row_map["Interval"]["diff"] == "changed"

    assert row_map["Symbol"]["diff"] == "-"

    sharpe_diff = row_map["Sharpe Ratio"]["diff"]
    assert abs(sharpe_diff - (1.12 - 1.45)) < 1e-4


# ------------------------------------------------------------------ list filtering and sorting

def test_list_filter_by_symbol(reg, base_config):
    eth_config = {
        **base_config,
        "data": {**base_config["data"], "symbol": "ETH/USDT"},
        "date_range": {"start": "2024-01-01", "end": "2024-02-01"},
        "strategy": {"name": "buy_and_hold"},
        "execution": {"fees_bps": 20},
    }
    reg.create(base_config, summary={"sharpe_ratio": 1.2, "total_return": 0.15})
    reg.create(eth_config, summary={"sharpe_ratio": 0.9, "total_return": 0.10})

    btc_runs = reg.list(filter_by="BTC")
    eth_runs = reg.list(filter_by="ETH")

    assert len(btc_runs) == 1
    assert len(eth_runs) == 1
    assert len(reg.list()) == 2


def test_list_sort_by_sharpe(reg, base_config):
    configs = [
        ({**base_config, "execution": {"fees_bps": i}}, {"sharpe_ratio": v, "total_return": 0.1})
        for i, v in enumerate([0.5, 1.8, 1.2])
    ]
    for cfg, summary in configs:
        reg.create(cfg, summary=summary)

    runs = reg.list(sort_by="sharpe")
    sharpes = [r.summary.get("sharpe_ratio") for r in runs]
    assert sharpes == sorted(sharpes, reverse=True)


def test_list_sort_by_returns(reg, base_config):
    configs = [
        ({**base_config, "execution": {"fees_bps": i}}, {"sharpe_ratio": 1.0, "total_return": v})
        for i, v in enumerate([0.05, 0.30, 0.15])
    ]
    for cfg, summary in configs:
        reg.create(cfg, summary=summary)

    runs = reg.list(sort_by="returns")
    returns = [r.summary.get("total_return") for r in runs]
    assert returns == sorted(returns, reverse=True)


# ------------------------------------------------------------------ persistence

def test_persistence(tmp_path, base_config):
    reg1 = Registry(base_dir=str(tmp_path))
    entry = reg1.create(base_config, summary={"sharpe_ratio": 1.5, "total_return": 0.20})

    reg2 = Registry(base_dir=str(tmp_path))
    runs = reg2.list()
    assert len(runs) == 1
    assert runs[0].run_id == entry.run_id

    shown = reg2.show(entry.run_id)
    assert shown["metrics"]["sharpe_ratio"] == 1.5
