from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from docx import Document

from app.services.extractors import extract_dataset_file, detect_file_type


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "sample.csv"
    pd.DataFrame(
        {
            "Name": ["Abel", "Hana"],
            "Age": [20, 21],
            "Score": [85, 90],
            "Joined": ["2024-01-01", "2024-01-02"],
        }
    ).to_csv(path, index=False)
    return path


@pytest.fixture
def sample_excel(tmp_path: Path) -> Path:
    path = tmp_path / "sample.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"Item": ["A", "B"], "Revenue": [100.0, 200.0], "Date": ["2024-01-01", "2024-01-02"]}).to_excel(writer, index=False, sheet_name="Sheet1")
        pd.DataFrame({"Other": ["X", "Y"], "Value": [10, 20]}).to_excel(writer, index=False, sheet_name="Sheet2")
    return path


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    path = tmp_path / "sample.txt"
    path.write_text("Name;Age;Score\nAbel;20;85\nHana;21;90\n", encoding="utf-8")
    return path


@pytest.fixture
def sample_docx(tmp_path: Path) -> Path:
    path = tmp_path / "sample.docx"
    document = Document()
    table = document.add_table(rows=2, cols=3)
    table.cell(0, 0).text = "Name"
    table.cell(0, 1).text = "Age"
    table.cell(0, 2).text = "Score"
    table.cell(1, 0).text = "Abel"
    table.cell(1, 1).text = "20"
    table.cell(1, 2).text = "85"
    document.save(path)
    return path


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 153 >>
stream
BT
/F1 12 Tf
50 150 Td
(Name,Age,Score) Tj
0 -20 Td
(Abel,20,85) Tj
0 -20 Td
(Hana,21,90) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000062 00000 n 
0000000123 00000 n 
0000000245 00000 n 
0000000901 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
1090
%%EOF
"""
    path.write_bytes(content)
    return path


def test_detect_file_type_works_for_supported_formats(tmp_path: Path) -> None:
    assert detect_file_type(tmp_path / "data.csv") == ".csv"
    assert detect_file_type(tmp_path / "book.xlsx") == ".xlsx"
    assert detect_file_type(tmp_path / "notes.txt") == ".txt"
    assert detect_file_type(tmp_path / "report.docx") == ".docx"
    assert detect_file_type(tmp_path / "report.pdf") == ".pdf"


def test_csv_extractor_handles_rows_and_dates(sample_csv: Path) -> None:
    dataframe = extract_dataset_file(sample_csv)
    assert list(dataframe.columns) == ["Name", "Age", "Score", "Joined"]
    assert len(dataframe) == 2
    assert dataframe["Age"].tolist() == [20, 21]
    assert pd.api.types.is_datetime64_any_dtype(dataframe["Joined"])


def test_xlsx_extractor_uses_first_worksheet(sample_excel: Path) -> None:
    dataframe = extract_dataset_file(sample_excel)
    assert list(dataframe.columns) == ["Item", "Revenue", "Date"]
    assert dataframe["Revenue"].tolist() == [100.0, 200.0]


def test_txt_extractor_detects_delimiters(sample_txt: Path) -> None:
    dataframe = extract_dataset_file(sample_txt)
    assert dataframe.columns.tolist() == ["Name", "Age", "Score"]
    assert dataframe["Age"].tolist() == [20, 21]


def test_docx_extractor_extracts_tables(sample_docx: Path) -> None:
    dataframe = extract_dataset_file(sample_docx)
    assert dataframe.columns.tolist() == ["Name", "Age", "Score"]
    assert dataframe["Age"].tolist() == [20]


def test_pdf_extractor_extracts_simple_tables(sample_pdf: Path) -> None:
    dataframe = extract_dataset_file(sample_pdf)
    assert list(dataframe.columns) == ["Name", "Age", "Score"]


def test_unstructured_txt_returns_clear_status(tmp_path: Path) -> None:
    path = tmp_path / "unstructured.txt"
    path.write_text("This is a long narrative paragraph without a clear table structure.", encoding="utf-8")
    with pytest.raises(ValueError, match="structured tabular data"):
        extract_dataset_file(path)


def test_unsupported_extension_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("# heading", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported file type"):
        detect_file_type(path)
