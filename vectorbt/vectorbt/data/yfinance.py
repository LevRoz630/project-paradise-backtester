# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Yahoo Finance data source."""

from vectorbt import _typing as tp
from vectorbt.data.base import Data
from vectorbt.utils.config import merge_dicts
from vectorbt.utils.datetime_ import get_local_tz, to_tzaware_datetime


class YFData(Data):
    """`Data` for data coming from `yfinance`."""

    _validate_on_download = True

    @classmethod
    def download_symbol(cls,
                        symbol: tp.Label,
                        period: str = 'max',
                        start: tp.Optional[tp.DatetimeLike] = None,
                        end: tp.Optional[tp.DatetimeLike] = None,
                        ticker_kwargs: tp.KwargsLike = None,
                        **kwargs) -> tp.Frame:
        """Download the symbol."""
        import yfinance as yf

        if start is not None:
            start = to_tzaware_datetime(start, tz=get_local_tz())
        if end is not None:
            end = to_tzaware_datetime(end, tz=get_local_tz())
        if ticker_kwargs is None:
            ticker_kwargs = {}
        return yf.Ticker(symbol, **ticker_kwargs).history(period=period, start=start, end=end, **kwargs)

    def update_symbol(self, symbol: tp.Label, **kwargs) -> tp.Frame:
        """Update the symbol using the original download kwargs."""
        download_kwargs = self.select_symbol_kwargs(symbol, self.download_kwargs)
        download_kwargs['start'] = self.data[symbol].index[-1]
        kwargs = merge_dicts(download_kwargs, kwargs)
        return self.download_symbol(symbol, **kwargs)
