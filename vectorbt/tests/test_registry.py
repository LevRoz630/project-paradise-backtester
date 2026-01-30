from vectorbt.registry import Registry

def test_registry_dedup(tmp_path):
    reg = Registry(base_dir=str(tmp_path))

    config = {
        "data": {"source": "ccxt", "symbol": "BTC/USDT", "interval": "1h"},
        "date_range": {"start": "2024-01-01", "end": "2024-02-01"},
        "strategy": {"name": "buy_and_hold"},
        "execution": {"fees_bps": 10},
    }

    e1 = reg.create(config, summary={"sharpe_ratio": 1.2, "total_return": 0.15})
    e2 = reg.create(config, summary={"sharpe_ratio": 999})

    assert e1.run_id == e2.run_id
    assert len(reg.list()) == 1

    shown = reg.show(e1.run_id)
    assert set(shown.keys()) == {"run_id", "path", "config", "metrics", "versions"}