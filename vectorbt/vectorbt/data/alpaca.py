# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Alpaca data source."""

import pandas as pd

from vectorbt import _typing as tp
from vectorbt.data.base import Data
from vectorbt.utils.config import get_func_kwargs, merge_dicts
from vectorbt.utils.datetime_ import get_utc_tz, to_tzaware_datetime


class AlpacaData(Data):
    """`Data` for data coming from `alpaca-py`."""

    _validate_on_download = True

    @classmethod
    def download_symbol(cls,
                        symbol: str,
                        timeframe: str = '1d',
                        start: tp.DatetimeLike = 0,
                        end: tp.DatetimeLike = 'now UTC',
                        adjustment: tp.Optional[str] = 'all',
                        limit: int = 500,
                        feed: tp.Optional[str] = None,
                        **kwargs) -> tp.Frame:
        """Download the symbol."""
        from vectorbt._settings import settings
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
        from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient

        alpaca_cfg = settings['data']['alpaca']
        if "/" in symbol:
            REST = CryptoHistoricalDataClient
        else:
            REST = StockHistoricalDataClient

        client_kwargs = {}
        for k in get_func_kwargs(REST):
            if k in kwargs:
                client_kwargs[k] = kwargs.pop(k)
        client_kwargs = merge_dicts(alpaca_cfg, client_kwargs)
        client = REST(**client_kwargs)

        timeframe_units = {'d': TimeFrameUnit.Day, 'h': TimeFrameUnit.Hour, 'm': TimeFrameUnit.Minute}
        if len(timeframe) < 2:
            raise ValueError("invalid timeframe")
        amount_str = timeframe[:-1]
        unit_str = timeframe[-1]
        if not amount_str.isnumeric() or unit_str not in timeframe_units:
            raise ValueError("invalid timeframe")

        amount = int(amount_str)
        unit = timeframe_units[unit_str]
        resolved_timeframe = TimeFrame(amount, unit)
        start_ts = to_tzaware_datetime(start, tz=get_utc_tz()).isoformat()
        end_ts = to_tzaware_datetime(end, tz=get_utc_tz()).isoformat()

        if "/" in symbol:
            df = client.get_crypto_bars(CryptoBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=resolved_timeframe,
                start=start_ts,
                end=end_ts,
                limit=limit,
            )).df
        else:
            df = client.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=resolved_timeframe,
                start=start_ts,
                end=end_ts,
                adjustment=adjustment,
                limit=limit,
                feed=feed,
            )).df

        df.drop(['trade_count', 'vwap'], axis=1, errors='ignore', inplace=True)
        df.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
        }, inplace=True)
        df['Open'] = df['Open'].astype(float)
        df['High'] = df['High'].astype(float)
        df['Low'] = df['Low'].astype(float)
        df['Close'] = df['Close'].astype(float)
        df['Volume'] = df['Volume'].astype(float)
        return df

    def update_symbol(self, symbol: str, **kwargs) -> tp.Frame:
        """Update the symbol using the original download kwargs."""
        download_kwargs = self.select_symbol_kwargs(symbol, self.download_kwargs)
        download_kwargs['start'] = self.data[symbol].index[-1]
        download_kwargs['show_progress'] = False
        kwargs = merge_dicts(download_kwargs, kwargs)
        return self.download_symbol(symbol, **kwargs)
