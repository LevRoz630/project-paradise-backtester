from datetime import datetime

import numpy as np
import pandas as pd
import pytest

import vectorbt as vbt
from vectorbt.utils.config import merge_dicts


def _make_ohlcv_df(index=None, extra_columns=None):
    if index is None:
        index = pd.date_range("2020-01-01", periods=5, freq="1D", tz="UTC")
    size = len(index)
    data = {
        "Open": [float(i) for i in range(1, size + 1)],
        "High": [float(i) for i in range(2, size + 2)],
        "Low": [float(i) + 0.5 for i in range(size)],
        "Close": [float(i) + 1.5 for i in range(size)],
        "Volume": [float(i * 10) for i in range(1, size + 1)],
    }
    if extra_columns is not None:
        data.update(extra_columns)
    return pd.DataFrame(data, index=index)


class TrackingOHLCVData(vbt.Data):
    _validate_on_download = True
    _expected_freq = "1D"
    prepare_calls = []

    @classmethod
    def _prepare_symbol(cls, df):
        cls.prepare_calls.append(df.copy())
        return super()._prepare_symbol(df)

    @classmethod
    def download_symbol(cls, symbol, index=None, extra_columns=None, **kwargs):
        return _make_ohlcv_df(index=index, extra_columns=extra_columns)

    def update_symbol(self, symbol, index=None, extra_columns=None, **kwargs):
        download_kwargs = self.select_symbol_kwargs(symbol, self.download_kwargs)
        next_index = index
        if next_index is None:
            next_index = pd.date_range(
                self.data[symbol].index[-1],
                periods=2,
                freq="1D",
                tz="UTC",
            )
        kwargs = merge_dicts(download_kwargs, kwargs)
        return self.download_symbol(symbol, index=next_index, extra_columns=extra_columns, **kwargs)


class PlainData(vbt.Data):
    _validate_on_download = False
    prepare_calls = 0

    @classmethod
    def _prepare_symbol(cls, df):
        cls.prepare_calls += 1
        return super()._prepare_symbol(df)

    @classmethod
    def download_symbol(cls, symbol, **kwargs):
        return pd.Series([1.0, 2.0, 3.0])


@pytest.fixture(autouse=True)
def reset_tracking_state():
    TrackingOHLCVData.prepare_calls = []
    PlainData.prepare_calls = 0


def test_normalize_strips_extra_columns():
    df = _make_ohlcv_df(extra_columns={"Adj Close": [1, 2, 3, 4, 5], "Trades": [9, 8, 7, 6, 5]})

    result = TrackingOHLCVData._normalize(df)

    assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert all(pd.api.types.is_float_dtype(result[column]) for column in result.columns)


def test_normalize_raises_on_missing_column():
    df = _make_ohlcv_df().drop(columns=["Close"])

    with pytest.raises(ValueError):
        TrackingOHLCVData._normalize(df)


def test_validate_schema_correct():
    df = _make_ohlcv_df()

    TrackingOHLCVData._validate_schema(df)


def test_validate_schema_wrong_dtype():
    df = _make_ohlcv_df()
    df["Close"] = df["Close"].astype(str)

    with pytest.raises(ValueError):
        TrackingOHLCVData._validate_schema(df)


def test_validate_ohlc_logic_warns(caplog):
    df = _make_ohlcv_df()
    df.loc[df.index[0], "High"] = 0.25

    with caplog.at_level("WARNING", logger="vectorbt.data.base"):
        TrackingOHLCVData._validate_ohlc_logic(df)

    assert "OHLC validation failed" in caplog.text


def test_validate_ohlc_logic_clean(caplog):
    df = _make_ohlcv_df()

    with caplog.at_level("WARNING", logger="vectorbt.data.base"):
        TrackingOHLCVData._validate_ohlc_logic(df)

    assert caplog.text == ""


def test_validate_timezone_utc(caplog):
    df = _make_ohlcv_df()

    with caplog.at_level("WARNING", logger="vectorbt.data.base"):
        TrackingOHLCVData._validate_timezone(df)

    assert caplog.text == ""


def test_validate_timezone_naive_warns(caplog):
    index = pd.date_range("2020-01-01", periods=5, freq="1D")
    df = _make_ohlcv_df(index=index)

    with caplog.at_level("WARNING", logger="vectorbt.data.base"):
        TrackingOHLCVData._validate_timezone(df)

    assert "UTC" in caplog.text


def test_validate_timezone_non_utc(caplog):
    index = pd.date_range("2020-01-01", periods=5, freq="1D")
    df = _make_ohlcv_df(index=index)

    with caplog.at_level("WARNING", logger="vectorbt.data.base"):
        TrackingOHLCVData.from_data({"TEST": df}, tz_localize="UTC", tz_convert="US/Eastern")

    assert "UTC" in caplog.text


def test_detect_gaps_none(caplog):
    df = _make_ohlcv_df()

    with caplog.at_level("WARNING", logger="vectorbt.data.base"):
        gaps = TrackingOHLCVData._detect_gaps(df, "1D")

    assert gaps == []
    assert caplog.text == ""


def test_detect_gaps_found(caplog):
    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2020-01-01", tz="UTC"),
            pd.Timestamp("2020-01-02", tz="UTC"),
            pd.Timestamp("2020-01-06", tz="UTC"),
        ]
    )
    df = _make_ohlcv_df(index=index)

    with caplog.at_level("WARNING", logger="vectorbt.data.base"):
        gaps = TrackingOHLCVData._detect_gaps(df, "1D")

    assert len(gaps) == 1
    assert gaps[0][0] == pd.Timestamp("2020-01-03", tz="UTC")
    assert gaps[0][1] == pd.Timestamp("2020-01-05", tz="UTC")
    assert "3 missing bars" in caplog.text


def test_detect_gaps_requires_explicit_freq(caplog):
    df = _make_ohlcv_df()

    with caplog.at_level("WARNING", logger="vectorbt.data.base"):
        gaps = TrackingOHLCVData._detect_gaps(df, None)

    assert gaps == []
    assert caplog.text == ""


def test_prepare_symbol_called_on_download():
    data = TrackingOHLCVData.download("TEST", extra_columns={"Adj Close": [1, 2, 3, 4, 5]})

    assert len(TrackingOHLCVData.prepare_calls) == 1
    assert list(data.data["TEST"].columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_prepare_symbol_called_on_update():
    data = TrackingOHLCVData.download("TEST")
    TrackingOHLCVData.prepare_calls = []

    updated = data.update()

    assert len(TrackingOHLCVData.prepare_calls) == 1
    assert len(updated.data["TEST"]) >= len(data.data["TEST"])


def test_prepare_symbol_skipped_when_disabled():
    data = PlainData.download("TEST")

    assert PlainData.prepare_calls == 0
    pd.testing.assert_series_equal(data.data["TEST"], pd.Series([1.0, 2.0, 3.0]))


def test_synthetic_data_unaffected():
    data = vbt.GBMData.download(
        "GBM",
        start=datetime(2020, 1, 1),
        end=datetime(2020, 1, 5),
        freq="1D",
        seed=42,
    )

    assert isinstance(data.data["GBM"], pd.Series)
    assert not data.data["GBM"].empty
