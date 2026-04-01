# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Local CSV and Parquet data source."""

from pathlib import Path

import pandas as pd

from vectorbt import _typing as tp
from vectorbt.data.base import Data
from vectorbt.utils.config import merge_dicts

OHLCV_COLUMNS = ('Open', 'High', 'Low', 'Close', 'Volume')
CSVDataT = tp.TypeVar("CSVDataT", bound="CSVData")


class CSVData(Data):
    """`Data` for local CSV and Parquet files."""

    _validate_on_download = True

    @staticmethod
    def _find_column(columns: pd.Index, name: str) -> tp.Optional[str]:
        for column in columns:
            if str(column).lower() == str(name).lower():
                return column
        return None

    @classmethod
    def _rename_columns(cls, df: pd.DataFrame, column_mapping: tp.Optional[dict]) -> pd.DataFrame:
        rename_map = {}
        if column_mapping is not None:
            rename_map.update(column_mapping)
        for canonical in OHLCV_COLUMNS:
            match = cls._find_column(df.columns, canonical)
            if match is not None and match != canonical:
                rename_map.setdefault(match, canonical)
        if rename_map:
            df = df.rename(columns=rename_map)
        return df

    @classmethod
    def download(cls: tp.Type[CSVDataT],
                 symbols: tp.Union[tp.Label, tp.Labels],
                 freq: tp.Optional[tp.FrequencyLike] = None,
                 **kwargs) -> CSVDataT:
        """Download local files and persist the expected gap frequency on the instance."""
        data = super().download(symbols, **kwargs)
        data._expected_freq = freq
        return data

    @classmethod
    def download_symbol(cls,
                        symbol: tp.Label,
                        path: tp.Union[str, Path],
                        column_mapping: tp.Optional[dict] = None,
                        timestamp_column: tp.Optional[str] = None) -> tp.Frame:
        """Read a local CSV or Parquet file for a symbol."""
        suffix = Path(path).suffix.lower()
        if suffix == '.csv':
            df = pd.read_csv(path)
        elif suffix == '.parquet':
            df = pd.read_parquet(path)
        else:
            raise ValueError(f"Unsupported file extension: {suffix}")

        df = cls._rename_columns(df, column_mapping)
        if timestamp_column is not None:
            resolved_timestamp_column = cls._find_column(df.columns, timestamp_column)
            if resolved_timestamp_column is None:
                raise ValueError(f"Timestamp column '{timestamp_column}' not found")
            df.index = pd.to_datetime(df[resolved_timestamp_column])
            df.index.name = None
            df = df.drop(columns=[resolved_timestamp_column])
        return df

    def update(self, freq: tp.Optional[tp.FrequencyLike] = None, **kwargs):
        """Update using the current file paths while preserving the expected frequency."""
        if freq is None:
            freq = self._expected_freq
        previous_freq = self._expected_freq
        self._expected_freq = freq
        try:
            data = super().update(**kwargs)
        finally:
            self._expected_freq = previous_freq
        data._expected_freq = freq
        return data

    def update_symbol(self, symbol: tp.Label, **kwargs) -> tp.Frame:
        """Re-read the symbol using the original download kwargs."""
        download_kwargs = self.select_symbol_kwargs(symbol, self.download_kwargs)
        kwargs = merge_dicts(download_kwargs, kwargs)
        return self.download_symbol(symbol, **kwargs)
