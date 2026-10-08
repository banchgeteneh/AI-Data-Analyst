from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from app.services.extractors.types import StructuredDataNotFoundError


class BaseExtractor(ABC):
    @staticmethod
    def _normalize_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
        if dataframe is None:
            raise StructuredDataNotFoundError("No dataset content could be extracted from this file.")

        normalized = dataframe.copy()
        normalized.columns = [str(column).strip() if str(column).strip() else f"Column_{index + 1}" for index, column in enumerate(normalized.columns)]
        normalized = normalized.replace(r"^\s*$", pd.NA, regex=True)
        normalized = normalized.dropna(how="all")

        if normalized.empty or normalized.shape[1] == 0:
            raise StructuredDataNotFoundError("The file does not contain sufficiently structured tabular data.")

        for column_name in normalized.columns:
            series = normalized[column_name].copy()
            string_values = series.map(lambda value: value.strip() if isinstance(value, str) else value)
            normalised_series = string_values.replace({"": pd.NA})
            normalized[column_name] = normalised_series

            if normalised_series.dropna().empty:
                continue

            numeric = pd.to_numeric(normalised_series, errors="coerce")
            if numeric.notna().sum() >= max(1, int(len(normalised_series.dropna()) * 0.8)):
                normalized[column_name] = numeric
                continue

            try:
                parsed_dates = pd.to_datetime(normalised_series, errors="coerce", format="mixed")
            except (TypeError, ValueError):
                parsed_dates = pd.Series([pd.NaT] * len(normalised_series), index=normalised_series.index)

            if parsed_dates.notna().sum() >= max(1, int(len(normalised_series.dropna()) * 0.7)):
                normalized[column_name] = parsed_dates

        normalized = normalized.dropna(how="all")
        if normalized.empty:
            raise StructuredDataNotFoundError("The file does not contain sufficiently structured tabular data.")

        return normalized.reset_index(drop=True)

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")

    @abstractmethod
    def extract(self, file_path: str | Path) -> pd.DataFrame:
        raise NotImplementedError
