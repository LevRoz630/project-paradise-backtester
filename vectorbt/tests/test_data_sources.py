import sys
import types
from pathlib import Path

import pandas as pd
import pytest

import vectorbt as vbt


def _make_source_df(index=None, columns=None):
    if index is None:
        index = pd.date_range("2020-01-01", periods=4, freq="1D", tz="UTC")
    data = {
        "Open": [1.0, 2.0, 3.0, 4.0],
        "High": [2.0, 3.0, 4.0, 5.0],
        "Low": [0.5, 1.5, 2.5, 3.5],
        "Close": [1.5, 2.5, 3.5, 4.5],
        "Volume": [10.0, 20.0, 30.0, 40.0],
    }
    df = pd.DataFrame(data, index=index)
    if columns is not None:
        df = df.rename(columns=columns)
    return df


def _write_csv(df, path: Path, index_name="timestamp"):
    out = df.reset_index(names=index_name)
    out.to_csv(path, index=False)
    return path


def _write_parquet(df, path: Path, index_name="timestamp"):
    out = df.reset_index(names=index_name)
    out.to_parquet(path, index=False)
    return path


def _install_fake_alpha_vantage(monkeypatch, time_series_cls):
    alpha_vantage_module = types.ModuleType("alpha_vantage")
    timeseries_module = types.ModuleType("alpha_vantage.timeseries")
    timeseries_module.TimeSeries = time_series_cls
    monkeypatch.setitem(sys.modules, "alpha_vantage", alpha_vantage_module)
    monkeypatch.setitem(sys.modules, "alpha_vantage.timeseries", timeseries_module)


def test_csv_load_csv_file(tmp_path):
    path = _write_csv(_make_source_df(), tmp_path / "btc.csv")

    data = vbt.CSVData.download("BTC", path=path, timestamp_column="timestamp")

    pd.testing.assert_frame_equal(data.data["BTC"], _make_source_df())


def test_csv_load_parquet_file(tmp_path):
    path = _write_parquet(_make_source_df(), tmp_path / "btc.parquet")

    data = vbt.CSVData.download("BTC", path=path, timestamp_column="timestamp")

    pd.testing.assert_frame_equal(data.data["BTC"], _make_source_df())


def test_csv_column_mapping(tmp_path):
    path = _write_csv(
        _make_source_df().rename(columns={
            "Open": "open_px",
            "High": "high_px",
            "Low": "low_px",
            "Close": "close_px",
            "Volume": "vol",
        }),
        tmp_path / "btc.csv",
        index_name="date",
    )

    data = vbt.CSVData.download(
        "BTC",
        path=path,
        timestamp_column="date",
        column_mapping={
            "open_px": "Open",
            "high_px": "High",
            "low_px": "Low",
            "close_px": "Close",
            "vol": "Volume",
        },
    )

    pd.testing.assert_frame_equal(data.data["BTC"], _make_source_df())


def test_csv_symbol_dict_paths(tmp_path):
    btc_path = _write_csv(_make_source_df(), tmp_path / "btc.csv")
    eth_path = _write_csv(_make_source_df() * 10, tmp_path / "eth.csv")

    data = vbt.CSVData.download(
        ["BTC", "ETH"],
        path=vbt.symbol_dict({"BTC": btc_path, "ETH": eth_path}),
        timestamp_column="timestamp",
    )

    pd.testing.assert_frame_equal(data.data["BTC"], _make_source_df())
    pd.testing.assert_frame_equal(data.data["ETH"], _make_source_df() * 10)


def test_csv_missing_ohlcv_column(tmp_path):
    path = _write_csv(_make_source_df().drop(columns=["High"]), tmp_path / "btc.csv")

    with pytest.raises(ValueError):
        vbt.CSVData.download("BTC", path=path, timestamp_column="timestamp")


def test_csv_naive_timestamps(tmp_path):
    naive_index = pd.date_range("2020-01-01", periods=4, freq="1D")
    path = _write_csv(_make_source_df(index=naive_index), tmp_path / "btc.csv")

    data = vbt.CSVData.download("BTC", path=path, timestamp_column="timestamp", tz_localize="UTC")

    assert str(data.data["BTC"].index.tz) == "UTC"


def test_alpha_vantage_download(monkeypatch):
    frame = pd.DataFrame(
        {
            "1. open": [1.0, 2.0, 3.0],
            "2. high": [2.0, 3.0, 4.0],
            "3. low": [0.5, 1.5, 2.5],
            "4. close": [1.5, 2.5, 3.5],
            "5. volume": [10.0, 20.0, 30.0],
        },
        index=pd.Index(["2020-01-01", "2020-01-02", "2020-01-03"], name="date"),
    )

    class FakeTimeSeries:
        def __init__(self, key, output_format="pandas"):
            self.key = key
            self.output_format = output_format

        def get_daily(self, symbol, outputsize="compact"):
            return frame, {"Meta Data": {}}

    _install_fake_alpha_vantage(monkeypatch, FakeTimeSeries)

    data = vbt.AlphaVantageData.download(
        "AAPL",
        api_key="test-key",
        interval="daily",
        start="2020-01-02",
        end="2020-01-03",
    )

    expected = pd.DataFrame(
        {
            "Open": [2.0, 3.0],
            "High": [3.0, 4.0],
            "Low": [1.5, 2.5],
            "Close": [2.5, 3.5],
            "Volume": [20.0, 30.0],
        },
        index=pd.to_datetime(["2020-01-02", "2020-01-03"], utc=True),
    )
    pd.testing.assert_frame_equal(data.data["AAPL"], expected)


def test_alpha_vantage_rate_limit(monkeypatch):
    frame = pd.DataFrame(
        {
            "1. open": [1.0],
            "2. high": [2.0],
            "3. low": [0.5],
            "4. close": [1.5],
            "5. volume": [10.0],
        },
        index=pd.Index(["2020-01-01"], name="date"),
    )
    calls = {"count": 0}
    sleeps = []

    class FakeTimeSeries:
        def __init__(self, key, output_format="pandas"):
            self.key = key
            self.output_format = output_format

        def get_intraday(self, symbol, interval="60min", outputsize="compact"):
            calls["count"] += 1
            if calls["count"] == 1:
                raise ValueError("429 Too Many Requests")
            return frame, {"Meta Data": {}}

    _install_fake_alpha_vantage(monkeypatch, FakeTimeSeries)
    monkeypatch.setattr("vectorbt.data.alpha_vantage.time.sleep", sleeps.append)

    data = vbt.AlphaVantageData.download("AAPL", api_key="test-key", interval="60min")

    assert calls["count"] == 2
    assert sleeps
    assert list(data.data["AAPL"].columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_alpha_vantage_api_key_from_env(monkeypatch):
    frame = pd.DataFrame(
        {
            "1. open": [1.0],
            "2. high": [2.0],
            "3. low": [0.5],
            "4. close": [1.5],
            "5. volume": [10.0],
        },
        index=pd.Index(["2020-01-01"], name="date"),
    )
    seen_keys = []

    class FakeTimeSeries:
        def __init__(self, key, output_format="pandas"):
            seen_keys.append(key)
            self.key = key
            self.output_format = output_format

        def get_daily(self, symbol, outputsize="compact"):
            return frame, {"Meta Data": {}}

    _install_fake_alpha_vantage(monkeypatch, FakeTimeSeries)
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "env-key")

    vbt.AlphaVantageData.download("AAPL", interval="daily")

    assert seen_keys == ["env-key"]


def test_yf_normalization(monkeypatch):
    raw = _make_source_df().assign(Dividends=[0, 0, 0, 0], **{"Stock Splits": [0, 0, 0, 0]})

    monkeypatch.setattr(
        vbt.YFData,
        "download_symbol",
        classmethod(lambda cls, symbol, **kwargs: raw.copy()),
    )

    data = vbt.YFData.download("AAPL")

    pd.testing.assert_frame_equal(data.data["AAPL"], _make_source_df())


def test_binance_normalization(monkeypatch):
    raw = _make_source_df().assign(
        **{
            "Close time": pd.date_range("2020-01-01", periods=4, freq="1D", tz="UTC"),
            "Quote volume": [100.0, 200.0, 300.0, 400.0],
            "Number of trades": [1, 2, 3, 4],
            "Taker base volume": [5.0, 6.0, 7.0, 8.0],
            "Taker quote volume": [9.0, 10.0, 11.0, 12.0],
        }
    )

    monkeypatch.setattr(
        vbt.BinanceData,
        "download_symbol",
        classmethod(lambda cls, symbol, **kwargs: raw.copy()),
    )
    monkeypatch.setattr(
        vbt.BinanceData,
        "download",
        classmethod(lambda cls, symbols, **kwargs: vbt.Data.download.__func__(cls, symbols, **kwargs)),
    )

    data = vbt.BinanceData.download("BTCUSDT")

    pd.testing.assert_frame_equal(data.data["BTCUSDT"], _make_source_df())
