# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""CCXT data source."""

import time
import warnings
from functools import wraps

import pandas as pd
from tqdm.auto import tqdm

from vectorbt import _typing as tp
from vectorbt.data.base import Data
from vectorbt.utils.config import merge_dicts
from vectorbt.utils.datetime_ import datetime_to_ms, get_utc_tz, to_tzaware_datetime

try:
    from ccxt.base.exchange import Exchange as ExchangeT
except ImportError:
    ExchangeT = tp.Any


class CCXTData(Data):
    """`Data` for data coming from `ccxt`."""

    _validate_on_download = True

    @classmethod
    def download_symbol(cls,
                        symbol: str,
                        exchange: tp.Union[str, "ExchangeT"] = 'binance',
                        config: tp.Optional[dict] = None,
                        timeframe: str = '1d',
                        start: tp.DatetimeLike = 0,
                        end: tp.DatetimeLike = 'now UTC',
                        delay: tp.Optional[float] = None,
                        limit: tp.Optional[int] = 500,
                        retries: int = 3,
                        show_progress: bool = True,
                        params: tp.Optional[dict] = None,
                        tqdm_kwargs: tp.KwargsLike = None) -> tp.Frame:
        """Download the symbol."""
        import ccxt
        from vectorbt._settings import settings

        ccxt_cfg = settings['data']['ccxt']
        if config is None:
            config = {}
        if tqdm_kwargs is None:
            tqdm_kwargs = {}
        if params is None:
            params = {}
        if isinstance(exchange, str):
            if not hasattr(ccxt, exchange):
                raise ValueError(f"Exchange {exchange} not found")
            default_config = {}
            for k, v in ccxt_cfg.items():
                if k in ccxt.exchanges:
                    continue
                default_config[k] = v
            if exchange in ccxt_cfg:
                default_config = merge_dicts(default_config, ccxt_cfg[exchange])
            config = merge_dicts(default_config, config)
            exchange = getattr(ccxt, exchange)(config)
        else:
            if len(config) > 0:
                raise ValueError("Cannot apply config after instantiation of the exchange")
        if not exchange.has['fetchOHLCV']:
            raise ValueError(f"Exchange {exchange} does not support OHLCV")
        if timeframe not in exchange.timeframes:
            raise ValueError(f"Exchange {exchange} does not support {timeframe} timeframe")
        if exchange.has['fetchOHLCV'] == 'emulated':
            warnings.warn("Using emulated OHLCV candles", stacklevel=2)

        def _retry(method):
            @wraps(method)
            def retry_method(*args, **kwargs):
                for i in range(retries):
                    try:
                        return method(*args, **kwargs)
                    except (ccxt.NetworkError, ccxt.ExchangeError) as e:
                        if i == retries - 1:
                            raise e
                    if delay is not None:
                        time.sleep(delay / 1000)
            return retry_method

        @_retry
        def _fetch(_since, _limit):
            return exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=_since,
                limit=_limit,
                params=params
            )

        start_ts = datetime_to_ms(to_tzaware_datetime(start, tz=get_utc_tz()))
        try:
            first_data = _fetch(0, 1)
            first_valid_ts = first_data[0][0]
            next_start_ts = start_ts = max(start_ts, first_valid_ts)
        except Exception:
            next_start_ts = start_ts
        end_ts = datetime_to_ms(to_tzaware_datetime(end, tz=get_utc_tz()))

        def _ts_to_str(ts):
            return str(pd.Timestamp(to_tzaware_datetime(ts, tz=get_utc_tz())))

        data: tp.List[list] = []
        with tqdm(disable=not show_progress, **tqdm_kwargs) as pbar:
            pbar.set_description(_ts_to_str(start_ts))
            while True:
                next_data = _fetch(next_start_ts, limit)
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

        df = pd.DataFrame(data, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df.index = pd.to_datetime(df['Open time'], unit='ms', utc=True)
        del df['Open time']
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
