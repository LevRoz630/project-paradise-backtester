# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Binance data source."""

import time

import pandas as pd
from tqdm.auto import tqdm

from vectorbt import _typing as tp
from vectorbt.data.base import Data
from vectorbt.utils.config import merge_dicts, get_func_kwargs
from vectorbt.utils.datetime_ import datetime_to_ms, get_utc_tz, to_tzaware_datetime

try:
    from binance.client import Client as ClientT
except ImportError:
    ClientT = tp.Any


BinanceDataT = tp.TypeVar("BinanceDataT", bound="BinanceData")


class BinanceData(Data):
    """`Data` for data coming from `python-binance`."""

    _validate_on_download = True

    @classmethod
    def download(cls: tp.Type[BinanceDataT],
                 symbols: tp.Labels,
                 client: tp.Optional["ClientT"] = None,
                 **kwargs) -> BinanceDataT:
        """Instantiate a Binance client before delegating to `Data.download`."""
        from binance.client import Client
        from vectorbt._settings import settings

        binance_cfg = settings['data']['binance']
        client_kwargs = {}
        for k in get_func_kwargs(Client):
            if k in kwargs:
                client_kwargs[k] = kwargs.pop(k)
        client_kwargs = merge_dicts(binance_cfg, client_kwargs)
        if client is None:
            client = Client(**client_kwargs)
        return super(BinanceData, cls).download(symbols, client=client, **kwargs)

    @classmethod
    def download_symbol(cls,
                        symbol: str,
                        client: tp.Optional["ClientT"] = None,
                        interval: str = '1d',
                        start: tp.DatetimeLike = 0,
                        end: tp.DatetimeLike = 'now UTC',
                        delay: tp.Optional[float] = 500,
                        limit: int = 500,
                        show_progress: bool = True,
                        tqdm_kwargs: tp.KwargsLike = None) -> tp.Frame:
        """Download the symbol."""
        if client is None:
            raise ValueError("client must be provided")
        if tqdm_kwargs is None:
            tqdm_kwargs = {}

        start_ts = datetime_to_ms(to_tzaware_datetime(start, tz=get_utc_tz()))
        try:
            first_data = client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=1,
                startTime=0,
                endTime=None
            )
            first_valid_ts = first_data[0][0]
            next_start_ts = start_ts = max(start_ts, first_valid_ts)
        except Exception:
            next_start_ts = start_ts
        end_ts = datetime_to_ms(to_tzaware_datetime(end, tz=get_utc_tz()))

        def _ts_to_str(ts: tp.DatetimeLike) -> str:
            return str(pd.Timestamp(to_tzaware_datetime(ts, tz=get_utc_tz())))

        data: tp.List[list] = []
        with tqdm(disable=not show_progress, **tqdm_kwargs) as pbar:
            pbar.set_description(_ts_to_str(start_ts))
            while True:
                next_data = client.get_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                    startTime=next_start_ts,
                    endTime=end_ts
                )
                if len(data) > 0:
                    next_data = list(filter(lambda d: next_start_ts < d[0] < end_ts, next_data))
                else:
                    next_data = list(filter(lambda d: d[0] < end_ts, next_data))
                if not len(next_data):
                    break
                data += next_data
                pbar.set_description("{} - {}".format(
                    _ts_to_str(start_ts),
                    _ts_to_str(next_data[-1][0])
                ))
                pbar.update(1)
                next_start_ts = next_data[-1][0]
                if delay is not None:
                    time.sleep(delay / 1000)

        df = pd.DataFrame(data, columns=[
            'Open time',
            'Open',
            'High',
            'Low',
            'Close',
            'Volume',
            'Close time',
            'Quote volume',
            'Number of trades',
            'Taker base volume',
            'Taker quote volume',
            'Ignore'
        ])
        df.index = pd.to_datetime(df['Open time'], unit='ms', utc=True)
        del df['Open time']
        df['Open'] = df['Open'].astype(float)
        df['High'] = df['High'].astype(float)
        df['Low'] = df['Low'].astype(float)
        df['Close'] = df['Close'].astype(float)
        df['Volume'] = df['Volume'].astype(float)
        df['Close time'] = pd.to_datetime(df['Close time'], unit='ms', utc=True)
        df['Quote volume'] = df['Quote volume'].astype(float)
        df['Number of trades'] = df['Number of trades'].astype(int)
        df['Taker base volume'] = df['Taker base volume'].astype(float)
        df['Taker quote volume'] = df['Taker quote volume'].astype(float)
        del df['Ignore']
        return df

    def update_symbol(self, symbol: str, **kwargs) -> tp.Frame:
        """Update the symbol using the original download kwargs."""
        download_kwargs = self.select_symbol_kwargs(symbol, self.download_kwargs)
        download_kwargs['start'] = self.data[symbol].index[-1]
        download_kwargs['show_progress'] = False
        kwargs = merge_dicts(download_kwargs, kwargs)
        return self.download_symbol(symbol, **kwargs)
