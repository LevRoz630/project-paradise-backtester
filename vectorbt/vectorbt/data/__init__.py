# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Modules for working with data sources."""

from vectorbt.data.base import symbol_dict, Data
from vectorbt.data.synthetic import SyntheticData, GBMData
from vectorbt.data.yfinance import YFData
from vectorbt.data.binance import BinanceData
from vectorbt.data.ccxt import CCXTData
from vectorbt.data.alpaca import AlpacaData
from vectorbt.data.csv import CSVData
from vectorbt.data.alpha_vantage import AlphaVantageData
from vectorbt.data.updater import DataUpdater

__all__ = [
    'symbol_dict',
    'Data',
    'DataUpdater',
    'SyntheticData',
    'GBMData',
    'YFData',
    'BinanceData',
    'CCXTData',
    'AlpacaData',
    'CSVData',
    'AlphaVantageData'
]

__pdoc__ = {k: False for k in __all__}
