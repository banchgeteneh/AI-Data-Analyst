from __future__ import annotations

from pathlib import Path

import pandas as pd
from docx import Document

from app.services.extractors.base import BaseExtractor
from app.services.extractors.types import MalformedFileError, StructuredDataNotFoundError


class DOCXExtractor(BaseExtractor):
    def extract(self, file_path: str | Path) -> pd.DataFrame:
        path = Path(file_path)
        try:
            document = Document(path)
        except Exception as error:
            raise MalformedFileError("The DOCX file is invalid or corrupted") from error

        tables: list[pd.DataFrame] = []
        for table in document.tables:
            rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
            if not rows or len(rows[0]) < 2:
                continue
            header = rows[0]
            data_rows = rows[1:]
            if not data_rows:
                continue
            padded_rows = []
            for row in data_rows:
                row_copy = list(row)
                while len(row_copy) < len(header):
                    row_copy.append("")
                padded_rows.append(row_copy[: len(header)])
            if not padded_rows:
                continue
            tables.append(self._normalize_dataframe(pd.DataFrame(padded_rows, columns=header)))

        if not tables:
            raise StructuredDataNotFoundError("No sufficiently structured table was found in the DOCX file")

        combined = pd.concat(tables, ignore_index=True)
        return self._normalize_dataframe(combined)
