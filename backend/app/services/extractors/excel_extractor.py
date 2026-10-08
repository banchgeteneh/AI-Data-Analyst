from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.extractors.base import BaseExtractor
from app.services.extractors.types import MalformedFileError, StructuredDataNotFoundError


class ExcelExtractor(BaseExtractor):
    def extract(self, file_path: str | Path) -> pd.DataFrame:
        path = Path(file_path)
        try:
            workbook = pd.ExcelFile(path)
        except Exception as error:
            raise MalformedFileError("The Excel file is invalid or corrupted") from error

        sheet_names = workbook.sheet_names
        if not sheet_names:
            raise StructuredDataNotFoundError("The Excel file does not contain a usable worksheet")

        for sheet_name in sheet_names:
            try:
                dataframe = pd.read_excel(path, sheet_name=sheet_name)
            except Exception as error:
                raise MalformedFileError("The Excel file could not be read") from error
            if dataframe.empty:
                continue
            return self._normalize_dataframe(dataframe)

        raise StructuredDataNotFoundError("The Excel file does not contain sufficiently structured tabular data")
