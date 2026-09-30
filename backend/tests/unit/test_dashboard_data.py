from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.models.dataset import Dataset
from app.services.dataset_analysis import analyze_dataset


def _analyze(dataframe: pd.DataFrame, tmp_path: Path, filename: str = "sample.csv") -> dict[str, Any]:
    path = tmp_path / filename
    dataframe.to_csv(path, index=False)
    dataset = Dataset(
        id=1,
        user_id=1,
        original_filename=filename,
        stored_filename=filename,
        file_path=str(path),
        file_type=".csv",
        file_size=path.stat().st_size,
    )
    return analyze_dataset(dataset)["dashboard"]


def test_student_dataset_has_domain_agnostic_analytics(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({
        "Student": [f"Student {index}" for index in range(10)],
        "Gender": ["Female", "Male"] * 5,
        "Age": range(15, 25),
        "Study_Hours": range(1, 11),
        "Attendance": range(80, 90),
        "Math": range(60, 70),
        "English": range(62, 72),
        "Science": range(64, 74),
        "Final_Grade": range(63, 73),
    }), tmp_path)

    assert dashboard["overview"]["row_count"] == 10
    assert dashboard["overview"]["column_count"] == 9
    assert dashboard["overview"]["identifier_column_count"] == 1
    assert {metric["column"] for metric in dashboard["metrics"]} >= {"Study_Hours", "Final_Grade"}
    assert any(pair["column_a"] == "Study_Hours" and pair["column_b"] == "Final_Grade" for pair in dashboard["relationships"]["pairs"])
    assert any(item["column"] == "Gender" for item in dashboard["distributions"])
    assert {item["measure"] for item in dashboard["comparisons"] if item["dimension"] == "Gender"} >= {"Final_Grade", "Attendance", "Study_Hours"}
    assert dashboard["trends"] == []


def test_sales_dataset_has_generalized_trends_and_measure_totals(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({
        "Date": ["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-02"],
        "Product": ["A", "B", "A", "B"],
        "Category": ["Tools", "Food", "Tools", "Food"],
        "Region": ["North", "South", "North", "South"],
        "Revenue": [20, 30, 25, 35],
        "Cost": [8, 10, 9, 12],
        "Profit": [12, 20, 16, 23],
    }), tmp_path)

    assert dashboard["overview"]["date_column_count"] == 1
    assert {metric["column"] for metric in dashboard["metrics"]} == {"Revenue", "Cost", "Profit"}
    assert next(metric for metric in dashboard["metrics"] if metric["column"] == "Revenue")["sum"] == 110
    assert {item["column"] for item in dashboard["distributions"] if item["type"] == "categorical"} == {"Product", "Category", "Region"}
    assert {item["measure_column"] for item in dashboard["trends"]} == {"Revenue", "Cost", "Profit"}
    assert all(item["aggregation"] == "sum" for item in dashboard["trends"])


def test_employee_dataset_compares_numeric_measures_by_dimensions(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({
        "Employee": [f"E{index}" for index in range(8)],
        "Department": ["Engineering", "Sales"] * 4,
        "Gender": ["F", "M", "M", "F"] * 2,
        "Job_Title": ["Analyst", "Manager"] * 4,
        "Salary": [70, 80, 90, 100, 75, 85, 95, 105],
        "Age": [24, 31, 38, 42, 27, 34, 40, 45],
    }), tmp_path)

    assert any(item["dimension"] == "Department" and item["measure"] == "Salary" for item in dashboard["comparisons"])
    assert any(item["dimension"] == "Gender" and item["measure"] == "Age" for item in dashboard["comparisons"])


def test_numeric_only_data_returns_histograms_and_relationships(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({"Height": [150, 160, 170, 180], "Weight": [50, 60, 70, 80]}), tmp_path)

    assert dashboard["distributions"]
    assert all(item["type"] == "numeric" and item["histogram"] for item in dashboard["distributions"])
    assert dashboard["relationships"]["pairs"]
    assert any(item["type"] == "heatmap" for item in dashboard["recommended_visualizations"])


def test_categorical_only_data_returns_distributions(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({"Status": ["Open", "Closed", "Open", "Pending"]}), tmp_path)

    assert len(dashboard["distributions"]) == 1
    assert dashboard["distributions"][0]["column"] == "Status"
    assert dashboard["metrics"] == []
    assert dashboard["relationships"]["pairs"] == []
    assert dashboard["trends"] == []
    assert dashboard["comparisons"] == []


def test_date_and_numeric_data_generates_daily_mean_trend(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({
        "Recorded_At": ["2025-03-01", "2025-03-01", "2025-03-02"],
        "Temperature": [10, 14, 20],
    }), tmp_path)

    assert dashboard["trends"][0]["date_column"] == "Recorded_At"
    assert dashboard["trends"][0]["measure_column"] == "Temperature"
    assert dashboard["trends"][0]["aggregation"] == "mean"
    assert dashboard["trends"][0]["values"][0] == {"date": "2025-03-01", "value": 12.0}


def test_high_cardinality_fields_are_excluded_from_dimension_charts(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({
        "Reference": [f"ref-{index}" for index in range(20)],
        "Amount": range(20),
    }), tmp_path)

    assert all(item["column"] != "Reference" for item in dashboard["distributions"])
    assert dashboard["data_quality"]["high_cardinality_columns"] == ["Reference"]


def test_missing_values_are_explained_in_quality_model(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({"Group": ["A", "B", None], "Score": [10, None, 30]}), tmp_path)

    assert dashboard["overview"]["missing_value_count"] == 2
    assert {item["column"] for item in dashboard["data_quality"]["incomplete_columns"]} == {"Group", "Score"}
    assert "2 values are missing" in dashboard["data_quality"]["observations"]


def test_small_dataset_has_empty_comparisons_and_no_crash(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({"Kind": ["A", "B"], "Score": [4, 8]}), tmp_path)

    assert dashboard["overview"]["row_count"] == 2
    assert dashboard["comparisons"] == []
    assert dashboard["recommended_visualizations"]


def test_constant_numeric_column_does_not_create_invalid_relationship(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({"Constant": [1, 1, 1], "Changing": [2, 3, 4]}), tmp_path)

    assert dashboard["relationships"]["pairs"] == []
    assert not any(item["type"] == "scatter" for item in dashboard["recommended_visualizations"])


def test_multiple_dimensions_and_measures_are_bounded(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({
        "Team": ["A", "B"] * 6,
        "Shift": ["Day", "Night", "Day"] * 4,
        "Zone": ["East", "West", "Central"] * 4,
        "Score": range(12),
        "Units": range(10, 22),
        "Hours": range(20, 32),
        "Quality": range(30, 42),
    }), tmp_path)

    assert 0 < len(dashboard["comparisons"]) <= 12
    assert {item["dimension"] for item in dashboard["comparisons"]} >= {"Team", "Shift"}
    assert len(dashboard["recommended_visualizations"]) <= 16


def test_empty_and_missing_heavy_data_returns_valid_empty_collections(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({"Empty": [None, None, None], "Group": [None, "A", None]}), tmp_path)

    assert dashboard["overview"]["numeric_column_count"] == 0
    assert dashboard["metrics"] == []
    assert dashboard["relationships"]["pairs"] == []
    assert dashboard["trends"] == []
    assert dashboard["comparisons"] == []
    assert dashboard["data_quality"]["incomplete_columns"]


def test_automatic_insights_are_generated_from_dashboard_results(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({
        "Date": ["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-02"],
        "Category": ["A", "B", "A", "B"],
        "Revenue": [20, 30, 25, 35],
        "Cost": [8, 10, 9, 12],
    }), tmp_path)

    insights = dashboard["automatic_insights"]
    assert isinstance(insights, list)
    assert insights
    assert {item["type"] for item in insights} >= {"trend", "relationship", "category", "quality"}
    assert all("title" in item and "summary" in item for item in insights)
    assert any(item.get("exploration", {}).get("available") for item in insights)
    relationship = next(item for item in insights if item["type"] == "relationship")
    assert relationship["exploration"]["type"] == "numeric_relationship"


def test_automatic_insights_skip_low_sample_size_patterns(tmp_path: Path) -> None:
    dashboard = _analyze(pd.DataFrame({"Group": ["A", "B"], "Score": [4, 8]}), tmp_path)

    insights = dashboard["automatic_insights"]
    assert isinstance(insights, list)
    assert not any(item["sample_size"] and item["sample_size"] < 3 for item in insights)
