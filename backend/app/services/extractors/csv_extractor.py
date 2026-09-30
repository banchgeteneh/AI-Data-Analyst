from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from app.services.extractors.base import BaseExtractor
from app.services.extractors.types import MalformedFileError, StructuredDataNotFoundError


class CSVExtractor(BaseExtractor):
    def extract(self, file_path: str | Path) -> pd.DataFrame:
        path = Path(file_path)
        try:
            sample = path.read_bytes()[:4096]
        except OSError as error:
            raise MalformedFileError("The CSV file could not be read") from error

        if not sample or b"\x00" in sample:
            raise MalformedFileError("The CSV file is empty or corrupted")

        try:
            text = sample.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = sample.decode("latin-1")
            except UnicodeDecodeError as error:
                raise MalformedFileError("The CSV file is not valid UTF-8 or Latin-1 text") from error

        try:
            dialect = csv.Sniffer().sniff(text, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","

        try:
            dataframe = pd.read_csv(path, sep=delimiter, dtype=str, keep_default_na=True)
        except Exception as error:
            raise MalformedFileError("The CSV file is malformed and could not be parsed") from error

        if dataframe.empty or dataframe.shape[1] < 2 and dataframe.shape[0] == 0:
            raise StructuredDataNotFoundError("The CSV file does not contain enough structured data to analyze")

        return self._normalize_dataframe(dataframe)
