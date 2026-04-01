# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Backwards-compatible shim for deprecated `vectorbt.data.custom` imports."""

import warnings

warnings.warn(
    "Importing from vectorbt.data.custom is deprecated; import from vectorbt.data instead.",
    DeprecationWarning,
    stacklevel=2
)

from vectorbt.data.synthetic import SyntheticData, GBMData
from vectorbt.data.yfinance import YFData
from vectorbt.data.binance import BinanceData
from vectorbt.data.ccxt import CCXTData
from vectorbt.data.alpaca import AlpacaData

__all__ = [
    'SyntheticData',
    'GBMData',
    'YFData',
    'BinanceData',
    'CCXTData',
    'AlpacaData'
]
