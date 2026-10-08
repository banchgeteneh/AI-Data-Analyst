from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from app.services.extractors.base import BaseExtractor
from app.services.extractors.types import MalformedFileError, StructuredDataNotFoundError


class TXTExtractor(BaseExtractor):
    def extract(self, file_path: str | Path) -> pd.DataFrame:
        path = Path(file_path)
        try:
            text = self._read_text(path)
        except OSError as error:
            raise MalformedFileError("The text file could not be read") from error

        rows: list[list[str]] = []
        for candidate_delimiter in [",", "\t", ";", "|"]:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if len(lines) < 2:
                continue
            parsed_rows: list[list[str]] = []
            for line in lines:
                parts = [part.strip() for part in line.split(candidate_delimiter)]
                if len(parts) < 2:
                    continue
                parsed_rows.append(parts)
            if len(parsed_rows) < 2:
                continue
            if all(len(row) == len(parsed_rows[0]) for row in parsed_rows):
                rows = parsed_rows
                delimiter = candidate_delimiter
                break
            delimiter = candidate_delimiter
            rows = parsed_rows
            break

        if not rows:
            raise StructuredDataNotFoundError("The text file does not contain sufficiently structured tabular data")

        try:
            dataframe = pd.DataFrame(rows[1:], columns=rows[0])
        except Exception as error:
            raise MalformedFileError("The text file is malformed and could not be turned into a table") from error

        return self._normalize_dataframe(dataframe)
