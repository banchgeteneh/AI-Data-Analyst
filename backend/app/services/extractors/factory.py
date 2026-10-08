from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.extractors.base import BaseExtractor
from app.services.extractors.csv_extractor import CSVExtractor
from app.services.extractors.docx_extractor import DOCXExtractor
from app.services.extractors.excel_extractor import ExcelExtractor
from app.services.extractors.pdf_extractor import PDFExtractor
from app.services.extractors.txt_extractor import TXTExtractor
from app.services.extractors.types import UnsupportedFileTypeError

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".txt", ".docx", ".pdf"}


def detect_file_type(file_name: str | Path) -> str:
    text = str(file_name).strip().lower()
    if text.startswith(".") and text in SUPPORTED_EXTENSIONS:
        return text
    if text and not text.startswith(".") and f".{text}" in SUPPORTED_EXTENSIONS:
        return f".{text}"

    suffix = Path(str(file_name)).suffix.lower()
    if suffix in SUPPORTED_EXTENSIONS:
        return suffix

    path = Path(file_name)
    if path.exists():
        content = path.read_bytes()[:4]
        if content.startswith(b"%PDF"):
            return ".pdf"
        if content.startswith(b"PK"):
            try:
                import zipfile

                with zipfile.ZipFile(path) as archive:
                    names = set(archive.namelist())
                    if "xl/workbook.xml" in names:
                        return ".xlsx"
                    if "word/document.xml" in names:
                        return ".docx"
            except (OSError, zipfile.BadZipFile):
                pass

    raise UnsupportedFileTypeError(f"Unsupported file type: {Path(str(file_name)).name or 'uploaded file'}")


def extract_dataset_file(file_path: str | Path, file_type: str | None = None) -> pd.DataFrame:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path.name}")

    detected_type = detect_file_type(file_type or path)
    extractors: dict[str, type[BaseExtractor]] = {
        ".csv": CSVExtractor,
        ".xlsx": ExcelExtractor,
        ".txt": TXTExtractor,
        ".docx": DOCXExtractor,
        ".pdf": PDFExtractor,
    }

    extractor = extractors.get(detected_type)
    if extractor is None:
        raise UnsupportedFileTypeError(f"Unsupported file type: {detected_type}")

    return extractor().extract(path)
