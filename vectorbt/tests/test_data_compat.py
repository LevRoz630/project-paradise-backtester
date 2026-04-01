import importlib
import sys
import warnings

import pandas as pd

import vectorbt as vbt


class PublicData(vbt.Data):
    @classmethod
    def download_symbol(cls, symbol, **kwargs):
        return pd.Series([1.0, 2.0, 3.0])


def test_import_from_custom_shim():
    sys.modules.pop("vectorbt.data.custom", None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        custom = importlib.import_module("vectorbt.data.custom")

    assert custom.YFData is vbt.YFData
    assert custom.BinanceData is vbt.BinanceData
    assert custom.CCXTData is vbt.CCXTData
    assert custom.AlpacaData is vbt.AlpacaData


def test_custom_shim_deprecation_warning():
    sys.modules.pop("vectorbt.data.custom", None)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        importlib.import_module("vectorbt.data.custom")

    assert any(item.category is DeprecationWarning for item in caught)


def test_from_data_public_api():
    data = PublicData.from_data({"TEST": pd.Series([1.0, 2.0, 3.0])})

    pd.testing.assert_series_equal(data.data["TEST"], pd.Series([1.0, 2.0, 3.0]))
