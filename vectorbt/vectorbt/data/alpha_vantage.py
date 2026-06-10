# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Alpha Vantage data source."""

import os
import time

import pandas as pd

from vectorbt import _typing as tp
from vectorbt.data.base import Data
from vectorbt.utils.config import merge_dicts
from vectorbt.utils.datetime_ import get_utc_tz, to_tzaware_datetime

COLUMN_MAPPING = {
    '1. open': 'Open',
    '2. high': 'High',
    '3. low': 'Low',
    '4. close': 'Close',
    '5. volume': 'Volume',
}
INTRADAY_INTERVALS = {'1min', '5min', '15min', '30min', '60min'}


class AlphaVantageData(Data):
    """`Data` for data coming from the `alpha_vantage` package."""

    _validate_on_download = True

    @staticmethod
    def _to_filter_timestamp(value: tp.DatetimeLike) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is not None:
            return timestamp.tz_convert(get_utc_tz()).tz_localize(None)
        return timestamp

    @classmethod
    def _resolve_api_key(cls, api_key: tp.Optional[str]) -> str:
        from vectorbt._settings import settings

        if api_key is not None:
            return api_key
        env_api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if env_api_key:
            return env_api_key
        settings_api_key = settings['data']['alpha_vantage']['api_key']
        if settings_api_key:
            return settings_api_key
        raise ValueError("Alpha Vantage API key was not provided")

    @classmethod
    def _fetch_with_retry(cls,
                          fetcher: tp.Callable[[], tp.Tuple[pd.DataFrame, dict]],
                          rate_limit_sleep: float) -> pd.DataFrame:
        last_error = None
        for attempt in range(2):
            try:
                data, _ = fetcher()
                return data
            except Exception as exc:
                last_error = exc
                if '429' not in str(exc):
                    raise
                if attempt == 0:
                    time.sleep(rate_limit_sleep)
        raise last_error

    @classmethod
    def download_symbol(cls,
                        symbol: str,
                        api_key: tp.Optional[str] = None,
                        interval: str = 'daily',
                        start: tp.Optional[tp.DatetimeLike] = None,
                        end: tp.Optional[tp.DatetimeLike] = None,
                        outputsize: tp.Optional[str] = None,
                        rate_limit_sleep: tp.Optional[float] = None) -> tp.Frame:
        """Download the symbol from Alpha Vantage."""
        from alpha_vantage.timeseries import TimeSeries
        from vectorbt._settings import settings

        alpha_vantage_cfg = settings['data']['alpha_vantage']
        resolved_api_key = cls._resolve_api_key(api_key)
        if outputsize is None:
            outputsize = alpha_vantage_cfg['outputsize']
        if rate_limit_sleep is None:
            rate_limit_sleep = alpha_vantage_cfg['rate_limit_sleep']

        time_series = TimeSeries(key=resolved_api_key, output_format='pandas')

        if interval in INTRADAY_INTERVALS:
            fetcher = lambda: time_series.get_intraday(symbol=symbol, interval=interval, outputsize=outputsize)
        elif interval == 'daily':
            fetcher = lambda: time_series.get_daily(symbol=symbol, outputsize=outputsize)
        elif interval == 'weekly':
            fetcher = lambda: time_series.get_weekly(symbol=symbol)
        elif interval == 'monthly':
            fetcher = lambda: time_series.get_monthly(symbol=symbol)
        else:
            raise ValueError(f"Unsupported Alpha Vantage interval: {interval}")

        df = cls._fetch_with_retry(fetcher, rate_limit_sleep)
        df = df.rename(columns=COLUMN_MAPPING)
        df.index = pd.to_datetime(df.index)
        df.index.name = None
        df = df.sort_index()
        if start is not None:
            df = df[df.index >= cls._to_filter_timestamp(start)]
        if end is not None:
            df = df[df.index <= cls._to_filter_timestamp(end)]
        return df

    def update_symbol(self, symbol: str, **kwargs) -> tp.Frame:
        """Update the symbol using the original download kwargs."""
        download_kwargs = self.select_symbol_kwargs(symbol, self.download_kwargs)
        download_kwargs['start'] = self.data[symbol].index[-1]
        kwargs = merge_dicts(download_kwargs, kwargs)
        return self.download_symbol(symbol, **kwargs)
