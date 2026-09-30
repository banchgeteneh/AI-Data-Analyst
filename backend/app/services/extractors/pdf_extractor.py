from __future__ import annotations

import csv
import io
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from app.services.extractors.base import BaseExtractor
from app.services.extractors.types import MalformedFileError, StructuredDataNotFoundError


class PDFExtractor(BaseExtractor):
    def extract(self, file_path: str | Path) -> pd.DataFrame:
        path = Path(file_path)
        try:
            reader = PdfReader(str(path))
        except Exception as error:
            raise MalformedFileError("The PDF file is invalid or corrupted") from error

        rows: list[list[str]] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if not text:
                continue
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                for delimiter in [",", "\t", ";", "|"]:
                    if stripped.count(delimiter) >= 1:
                        record = [cell.strip() for cell in stripped.split(delimiter)]
                        if len(record) >= 2:
                            rows.append(record)
                            break

        if len(rows) < 2:
            raise StructuredDataNotFoundError("The PDF file does not contain a usable table")

        try:
            dataframe = pd.DataFrame(rows[1:], columns=rows[0])
        except Exception as error:
            raise MalformedFileError("The PDF file could not be converted into a table") from error

        return self._normalize_dataframe(dataframe)
