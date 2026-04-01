# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Synthetic data sources."""

import numpy as np
import pandas as pd

from vectorbt import _typing as tp
from vectorbt.data.base import Data
from vectorbt.utils.config import merge_dicts
from vectorbt.utils.datetime_ import get_utc_tz, to_tzaware_datetime


class SyntheticData(Data):
    """`Data` for synthetically generated data."""

    @classmethod
    def generate_symbol(cls, symbol: tp.Label, index: tp.Index, **kwargs) -> tp.SeriesFrame:
        """Abstract method to generate a symbol."""
        raise NotImplementedError

    @classmethod
    def download_symbol(cls,
                        symbol: tp.Label,
                        start: tp.DatetimeLike = 0,
                        end: tp.DatetimeLike = 'now',
                        freq: tp.Union[None, str, pd.DateOffset] = None,
                        date_range_kwargs: tp.KwargsLike = None,
                        **kwargs) -> tp.SeriesFrame:
        """Generate a datetime index and delegate symbol creation."""
        if date_range_kwargs is None:
            date_range_kwargs = {}
        index = pd.date_range(
            start=to_tzaware_datetime(start, tz=get_utc_tz()),
            end=to_tzaware_datetime(end, tz=get_utc_tz()),
            freq=freq,
            **date_range_kwargs
        )
        if len(index) == 0:
            raise ValueError("Date range is empty")
        return cls.generate_symbol(symbol, index, **kwargs)

    def update_symbol(self, symbol: tp.Label, **kwargs) -> tp.SeriesFrame:
        """Update the symbol using the original download kwargs."""
        download_kwargs = self.select_symbol_kwargs(symbol, self.download_kwargs)
        download_kwargs['start'] = self.data[symbol].index[-1]
        kwargs = merge_dicts(download_kwargs, kwargs)
        return self.download_symbol(symbol, **kwargs)


def generate_gbm_paths(S0: float, mu: float, sigma: float, T: int, M: int, I: int,
                       seed: tp.Optional[int] = None) -> tp.Array2d:
    """Generate Geometric Brownian Motion paths."""
    if seed is not None:
        np.random.seed(seed)

    dt = float(T) / M
    paths = np.zeros((M + 1, I), np.float64)
    paths[0] = S0
    for t in range(1, M + 1):
        rand = np.random.standard_normal(I)
        paths[t] = paths[t - 1] * np.exp((mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * rand)
    return paths


class GBMData(SyntheticData):
    """`SyntheticData` for data generated using Geometric Brownian Motion."""

    @classmethod
    def generate_symbol(cls,
                        symbol: tp.Label,
                        index: tp.Index,
                        S0: float = 100.,
                        mu: float = 0.,
                        sigma: float = 0.05,
                        T: tp.Optional[int] = None,
                        I: int = 1,
                        seed: tp.Optional[int] = None) -> tp.SeriesFrame:
        """Generate the symbol using `generate_gbm_paths`."""
        if T is None:
            T = len(index)
        out = generate_gbm_paths(S0, mu, sigma, T, len(index), I, seed=seed)[1:]
        if out.shape[1] == 1:
            return pd.Series(out[:, 0], index=index)
        columns = pd.RangeIndex(stop=out.shape[1], name='path')
        return pd.DataFrame(out, index=index, columns=columns)

    def update_symbol(self, symbol: tp.Label, **kwargs) -> tp.SeriesFrame:
        """Update the symbol using the prior path endpoint as `S0`."""
        download_kwargs = self.select_symbol_kwargs(symbol, self.download_kwargs)
        download_kwargs['start'] = self.data[symbol].index[-1]
        _ = download_kwargs.pop('S0', None)
        S0 = self.data[symbol].iloc[-2]
        _ = download_kwargs.pop('T', None)
        download_kwargs['seed'] = None
        kwargs = merge_dicts(download_kwargs, kwargs)
        return self.download_symbol(symbol, S0=S0, **kwargs)
