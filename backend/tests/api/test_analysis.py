from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.dataset import Dataset
from app.models.user import User


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


def override_get_db() -> Generator[Session, None, None]:
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def isolated_database(tmp_path: Path) -> Generator[dict[str, Any], None, None]:
    Base.metadata.create_all(TEST_ENGINE)
    app.dependency_overrides[get_db] = override_get_db
    with TestSessionLocal() as db:
        first_user = User(name="First User", email="analysis-first@example.com", password_hash=hash_password("password123"))
        second_user = User(name="Second User", email="analysis-second@example.com", password_hash=hash_password("password123"))
        db.add_all([first_user, second_user])
        db.commit()
        db.refresh(first_user)
        db.refresh(second_user)
        context = {"first_user_id": first_user.id, "second_user_id": second_user.id, "tmp_path": tmp_path}
    yield context
    app.dependency_overrides.clear()
    Base.metadata.drop_all(TEST_ENGINE)


@asynccontextmanager
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


def auth_headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def add_dataset(user_id: int, path: Path, file_type: str) -> int:
    with TestSessionLocal() as db:
        dataset = Dataset(
            user_id=user_id,
            original_filename=path.name,
            stored_filename=f"stored-{path.name}",
            file_path=str(path),
            file_type=file_type,
            file_size=path.stat().st_size if path.exists() else 0,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return dataset.id


@pytest.fixture
def analysis_csv(isolated_database: dict[str, Any]) -> int:
    path = isolated_database["tmp_path"] / "analysis.csv"
    path.write_text("sales,profit,region\n1,2,East\n2,4,West\n2,4,West\n,8,East\n", encoding="utf-8")
    return add_dataset(int(isolated_database["first_user_id"]), path, ".csv")


@pytest.mark.anyio
async def test_unauthenticated_analysis_returns_401(analysis_csv: int) -> None:
    async with client() as test_client:
        response = await test_client.get(f"/api/v1/datasets/{analysis_csv}/analysis")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_csv_analysis_returns_json_safe_statistics(analysis_csv: int, isolated_database: dict[str, Any]) -> None:
    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{analysis_csv}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["dataset"]["rows"] == 4
    assert body["dataset"]["columns"] == 3
    assert body["summary"] == {
        "row_count": 4,
        "column_count": 3,
        "duplicate_rows": 1,
        "total_missing_values": 1,
    }
    assert body["numeric_statistics"]["sales"] == {
        "count": 3,
        "mean": 1.6666666666666667,
        "median": 2.0,
        "standard_deviation": 0.5773502691896257,
        "minimum": 1.0,
        "maximum": 2.0,
    }
    assert body["categorical_statistics"]["region"] == {
        "unique_count": 2,
        "most_common_value": "East",
        "most_common_count": 2,
    }
    assert body["correlations"]["sales"]["profit"] == 1.0
    assert body["data_quality"]["columns_with_missing_values"] == ["sales"]
    assert body["data_quality"]["columns_with_all_values_missing"] == []
    assert body["data_quality"]["duplicate_rows"] == 1
    assert body["data_quality"]["completeness_percentage"] == pytest.approx(91.666667)
    assert set(body) == {
        "dataset",
        "columns",
        "summary",
        "numeric_statistics",
        "categorical_statistics",
        "correlations",
        "data_quality",
        "chart_data",
        "dataset_profile",
        "dashboard",
    }
    assert body["dashboard"]["overview"]["row_count"] == 4
    assert body["dashboard"]["metrics"][0]["column"] == "sales"
    assert body["dashboard"]["metrics"][0]["sum"] == 5.0
    assert body["dashboard"]["distributions"][0]["column"] == "region"
    assert [item["column"] for item in body["chart_data"]["categorical_distributions"]] == ["region"]
    assert all(value is not None for value in body["numeric_statistics"]["sales"].values())
    assert isinstance(response.json(), dict)


@pytest.mark.anyio
async def test_chart_data_aggregates_dates_and_all_categories(isolated_database: dict[str, Any]) -> None:
    path = isolated_database["tmp_path"] / "chart-data.csv"
    path.write_text(
        "Date,Revenue,Product,Category,Region\n"
        "2024-02-02,10,Laptop,Hardware,East\n"
        "2024-01-01,20,Phone,Electronics,West\n"
        "2024-01-01,5,Laptop,Hardware,\n"
        ",99,Tablet,Electronics,East\n"
        "2024-02-02,,Phone,,West\n"
        "not-a-date,7,,Hardware,\n",
        encoding="utf-8",
    )
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".csv")

    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )

    assert response.status_code == 200
    chart_data = response.json()["chart_data"]
    assert chart_data["revenue_by_date"] == [
        {"date": "2024-01-01", "revenue": 25.0},
        {"date": "2024-02-02", "revenue": 10.0},
    ]
    assert {item["product"]: item["count"] for item in chart_data["product_distribution"]} == {
        "Laptop": 2,
        "Phone": 2,
        "Tablet": 1,
    }
    assert {item["category"]: item["count"] for item in chart_data["category_distribution"]} == {
        "Hardware": 3,
        "Electronics": 2,
    }
    assert {item["region"]: item["count"] for item in chart_data["region_distribution"]} == {
        "East": 2,
        "West": 2,
    }
    profile = response.json()["dataset_profile"]
    assert profile["date_columns"] == ["Date"]
    assert profile["numeric_columns"] == ["Revenue"]
    assert profile["categorical_columns"] == ["Product", "Category", "Region"]
    assert [item["column"] for item in chart_data["categorical_distributions"]] == [
        "Product",
        "Category",
        "Region",
    ]
    assert chart_data["categorical_distributions"][0]["counts"] == [
        {"value": "Laptop", "count": 2},
        {"value": "Phone", "count": 2},
        {"value": "Tablet", "count": 1},
    ]


@pytest.mark.anyio
async def test_chart_data_is_empty_when_expected_columns_are_absent(isolated_database: dict[str, Any]) -> None:
    path = isolated_database["tmp_path"] / "unrelated-columns.csv"
    path.write_text("amount,segment\n10,retail\n20,online\n", encoding="utf-8")
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".csv")

    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )

    assert response.status_code == 200
    assert response.json()["chart_data"] == {
        "revenue_by_date": [],
        "product_distribution": [],
        "category_distribution": [],
        "region_distribution": [],
        "categorical_distributions": [],
    }


@pytest.mark.anyio
async def test_xlsx_analysis_works( isolated_database: dict[str, Any]) -> None:
    path = isolated_database["tmp_path"] / "analysis.xlsx"
    pd.DataFrame(
        {
            "Date": ["2025-03-02", "2025-03-01", "2025-03-01"],
            "Revenue": [10, 20, 5],
            "Product": ["Widget", "Gadget", "Widget"],
            "Category": ["Tools", "Hardware", "Tools"],
            "Region": ["North", "South", None],
        }
    ).to_excel(path, index=False)
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".xlsx")

    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )

    assert response.status_code == 200
    assert response.json()["dataset"]["column_names"] == ["Date", "Revenue", "Product", "Category", "Region"]
    assert response.json()["chart_data"] == {
        "revenue_by_date": [
            {"date": "2025-03-01", "revenue": 25.0},
            {"date": "2025-03-02", "revenue": 10.0},
        ],
        "product_distribution": [
            {"product": "Widget", "count": 2},
            {"product": "Gadget", "count": 1},
        ],
        "category_distribution": [
            {"category": "Tools", "count": 2},
            {"category": "Hardware", "count": 1},
        ],
        "region_distribution": [
            {"region": "North", "count": 1},
            {"region": "South", "count": 1},
        ],
        "categorical_distributions": [
            {
                "column": "Product",
                "unique_count": 2,
                "total_records": 3,
                "counts": [{"value": "Widget", "count": 2}, {"value": "Gadget", "count": 1}],
            },
            {
                "column": "Category",
                "unique_count": 2,
                "total_records": 3,
                "counts": [{"value": "Tools", "count": 2}, {"value": "Hardware", "count": 1}],
            },
            {
                "column": "Region",
                "unique_count": 2,
                "total_records": 3,
                "counts": [{"value": "North", "count": 1}, {"value": "South", "count": 1}],
            },
        ],
    }


@pytest.mark.anyio
async def test_student_dataset_detects_gender_and_excludes_student_names(
    isolated_database: dict[str, Any],
) -> None:
    path = isolated_database["tmp_path"] / "students.csv"
    rows = [
        f"Student {index},{'Female' if index % 2 == 0 else 'Male'},{15 + index},2.5,90,80,82,84,83"
        for index in range(10)
    ]
    path.write_text(
        "Student,Gender,Age,Study_Hours,Attendance,Math,English,Science,Final_Grade\n" + "\n".join(rows),
        encoding="utf-8",
    )
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".csv")

    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )

    assert response.status_code == 200
    distributions = response.json()["chart_data"]["categorical_distributions"]
    assert [item["column"] for item in distributions] == ["Gender"]
    assert distributions[0]["counts"] == [
        {"value": "Female", "count": 5},
        {"value": "Male", "count": 5},
    ]


@pytest.mark.anyio
async def test_numeric_only_dataset_has_no_categorical_distributions(isolated_database: dict[str, Any]) -> None:
    path = isolated_database["tmp_path"] / "numeric-only.csv"
    path.write_text("Age,Score\n18,82\n19,91\n20,75\n", encoding="utf-8")
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".csv")

    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )

    assert response.status_code == 200
    assert response.json()["chart_data"]["categorical_distributions"] == []


@pytest.mark.anyio
async def test_multiple_categorical_columns_are_returned(isolated_database: dict[str, Any]) -> None:
    path = isolated_database["tmp_path"] / "employees.csv"
    path.write_text(
        "Department,Gender,Job_Title,Year,Employee_Name\n"
        "Sales,Female,Analyst,2023,Employee 1\n"
        "Sales,Male,Manager,2024,Employee 2\n"
        "Engineering,Female,Analyst,2023,Employee 3\n"
        "Engineering,Male,Manager,2024,Employee 4\n"
        "Support,Female,Analyst,2023,Employee 5\n"
        "Support,Male,Manager,2024,Employee 6\n"
        "Sales,Female,Analyst,2023,Employee 7\n"
        "Engineering,Male,Manager,2024,Employee 8\n"
        "Support,Female,Analyst,2023,Employee 9\n"
        "Sales,Male,Manager,2024,Employee 10\n",
        encoding="utf-8",
    )
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".csv")

    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )

    assert response.status_code == 200
    assert [item["column"] for item in response.json()["chart_data"]["categorical_distributions"]] == [
        "Department",
        "Gender",
        "Job_Title",
        "Year",
    ]


@pytest.mark.anyio
async def test_categorical_distributions_exclude_ids_free_text_and_dates_and_skip_missing(
    isolated_database: dict[str, Any],
) -> None:
    path = isolated_database["tmp_path"] / "filtered-categories.csv"
    path.write_text(
        "record_id,Student,Gender,Notes,Event_Date\n"
        "id-1,Ada,Female," + "long observation " * 10 + ",2025-01-01\n"
        "id-2,Linus,Male," + "another long comment " * 10 + ",2025-01-02\n"
        "id-3,Grace,Female," + "third long comment " * 10 + ",2025-01-03\n"
        "id-4,Alan,," + "fourth long comment " * 10 + ",2025-01-04\n"
        "id-5,Katherine,Female," + "fifth long comment " * 10 + ",2025-01-05\n"
        "id-6,Barbara,Male," + "sixth long comment " * 10 + ",2025-01-06\n"
        "id-7,Ed,Female," + "seventh long comment " * 10 + ",2025-01-07\n"
        "id-8,Donald,Male," + "eighth long comment " * 10 + ",2025-01-08\n"
        "id-9,Frances,Female," + "ninth long comment " * 10 + ",2025-01-09\n"
        "id-10,Claude,Male," + "tenth long comment " * 10 + ",2025-01-10\n",
        encoding="utf-8",
    )
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".csv")

    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )

    assert response.status_code == 200
    distributions = response.json()["chart_data"]["categorical_distributions"]
    assert [item["column"] for item in distributions] == ["Gender"]
    assert distributions[0]["total_records"] == 10
    assert sum(item["count"] for item in distributions[0]["counts"]) == 9
    profile = response.json()["dataset_profile"]
    assert profile["identifier_columns"] == ["record_id", "Student"]
    assert profile["text_columns"] == ["Notes"]
    assert profile["date_columns"] == ["Event_Date"]
    assert profile["categorical_analysis"]["Gender"]["missing_count"] == 1
    assert profile["categorical_analysis"]["Gender"]["top_values"][0]["percentage"] == pytest.approx(55.555556)


@pytest.mark.anyio
async def test_another_user_cannot_analyze_dataset(analysis_csv: int, isolated_database: dict[str, Any]) -> None:
    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{analysis_csv}/analysis",
            headers=auth_headers(int(isolated_database["second_user_id"])),
        )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_missing_dataset_returns_404(isolated_database: dict[str, Any]) -> None:
    async with client() as test_client:
        response = await test_client.get(
            "/api/v1/datasets/99999/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_missing_physical_file_returns_404(isolated_database: dict[str, Any]) -> None:
    path = isolated_database["tmp_path"] / "missing.csv"
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".csv")
    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_no_numeric_columns_is_supported(isolated_database: dict[str, Any]) -> None:
    path = isolated_database["tmp_path"] / "categorical.csv"
    path.write_text("region,segment\nEast,A\nWest,B\n", encoding="utf-8")
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".csv")
    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )
    assert response.status_code == 200
    body = response.json()
    assert body["numeric_statistics"] == {}
    assert body["correlations"] == {}
    assert set(body["categorical_statistics"]) == {"region", "segment"}
    assert body["dataset_profile"]["categorical_columns"] == ["region", "segment"]
    assert body["dataset_profile"]["numeric_analysis"] == {}


@pytest.mark.anyio
async def test_no_categorical_columns_and_constant_numeric_are_supported(isolated_database: dict[str, Any]) -> None:
    path = isolated_database["tmp_path"] / "numeric.csv"
    path.write_text("first,second\n1,5\n1,5\n", encoding="utf-8")
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".csv")
    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )
    assert response.status_code == 200
    body = response.json()
    assert body["categorical_statistics"] == {}
    assert body["correlations"]["first"]["second"] is None
    assert body["dataset_profile"]["numeric_columns"] == ["first", "second"]
    assert body["dataset_profile"]["relationships"]["correlations"]["first"]["second"] is None


@pytest.mark.anyio
async def test_empty_dataset_is_controlled(isolated_database: dict[str, Any]) -> None:
    path = isolated_database["tmp_path"] / "empty.csv"
    path.write_bytes(b"")
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".csv")
    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "The dataset file could not be read"


@pytest.mark.anyio
async def test_corrupted_xlsx_is_controlled(isolated_database: dict[str, Any]) -> None:
    path = isolated_database["tmp_path"] / "corrupt.xlsx"
    path.write_bytes(b"not an excel workbook")
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".xlsx")
    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )
    assert response.status_code == 422
    assert "could not be read" in response.json()["detail"]


@pytest.mark.anyio
async def test_unsupported_stored_type_is_controlled(isolated_database: dict[str, Any]) -> None:
    path = isolated_database["tmp_path"] / "data.txt"
    path.write_text("not supported", encoding="utf-8")
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".txt")
    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "The dataset file type is not supported"


@pytest.mark.anyio
async def test_student_profile_classifies_columns_and_calculates_safe_statistics(
    isolated_database: dict[str, Any],
) -> None:
    path = isolated_database["tmp_path"] / "student-profile.xlsx"
    pd.DataFrame(
        {
            "Student": [f"Student {index}" for index in range(10)],
            "Gender": ["Female" if index % 2 == 0 else "Male" for index in range(10)],
            "Age": list(range(15, 25)),
            "Study_Hours": [str(index) for index in range(1, 10)] + ["not reported"],
            "Attendance": [80 + index for index in range(10)],
            "Math": list(range(60, 70)),
            "English": list(range(62, 72)),
            "Science": list(range(64, 74)),
            "Final_Grade": list(range(63, 73)),
            "Event_Date": [f"2025-01-{index:02d}" for index in range(1, 10)] + ["unrecognized"],
            "Notes": [f"Student feedback item {index} " * 12 for index in range(10)],
            "record_uuid": [f"uuid-{index:08d}" for index in range(10)],
            "Passed": [index % 2 == 0 for index in range(10)],
            "Empty": [None] * 10,
        }
    ).to_excel(path, index=False)
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".xlsx")

    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )

    assert response.status_code == 200
    body = response.json()
    profile = body["dataset_profile"]
    columns = {column["name"]: column for column in profile["column_profiles"]}
    assert profile["row_count"] == 10
    assert profile["column_count"] == 14
    assert columns["Student"]["role"] == "IDENTIFIER"
    assert columns["Gender"]["role"] == "CATEGORICAL"
    assert columns["Age"]["role"] == "NUMERIC"
    assert columns["Study_Hours"]["role"] == "NUMERIC"
    assert columns["Event_Date"]["role"] == "DATE"
    assert columns["Notes"]["role"] == "TEXT"
    assert columns["record_uuid"]["role"] == "IDENTIFIER"
    assert columns["Passed"]["role"] == "BOOLEAN"
    assert columns["Empty"]["role"] == "UNKNOWN"
    assert columns["Student"]["unique_ratio"] == 1.0
    assert len(columns["Gender"]["sample_values"]) <= 5
    assert profile["numeric_analysis"]["Study_Hours"]["count"] == 9
    assert profile["numeric_analysis"]["Study_Hours"]["missing_count"] == 1
    assert profile["numeric_analysis"]["Math"]["first_quartile"] == 62.25
    assert profile["numeric_analysis"]["Math"]["third_quartile"] == 66.75
    assert profile["categorical_analysis"]["Gender"]["top_values"][0] == {
        "value": "Female",
        "count": 5,
        "percentage": 50.0,
    }
    assert body["data_quality"]["completeness_percentage"] is not None
    assert profile["relationships"]["correlations"]["Math"]["English"] == pytest.approx(1.0)


@pytest.mark.anyio
async def test_empty_columns_and_non_finite_numeric_values_are_safe(
    isolated_database: dict[str, Any],
) -> None:
    path = isolated_database["tmp_path"] / "empty-and-extreme.csv"
    pd.DataFrame({"Empty": [None, None, None], "Value": [1e308, float("inf"), float("-inf")]}).to_csv(
        path,
        index=False,
    )
    dataset_id = add_dataset(int(isolated_database["first_user_id"]), path, ".csv")

    async with client() as test_client:
        response = await test_client.get(
            f"/api/v1/datasets/{dataset_id}/analysis",
            headers=auth_headers(int(isolated_database["first_user_id"])),
        )

    assert response.status_code == 200
    profile = response.json()["dataset_profile"]
    columns = {column["name"]: column for column in profile["column_profiles"]}
    assert columns["Empty"]["role"] == "UNKNOWN"
    assert columns["Empty"]["missing_percentage"] == 100.0
    assert columns["Value"]["role"] == "NUMERIC"
    assert profile["numeric_analysis"]["Value"]["count"] == 1
    assert profile["numeric_analysis"]["Value"]["mean"] == 1e308
    assert profile["relationships"]["correlations"] == {}
