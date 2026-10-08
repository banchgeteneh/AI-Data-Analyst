from typing import Any

from app.services.exploration_recommendations import generate_exploration_recommendations


def _column(name: str, role: str, unique_count: int, *, missing_count: int = 0, missing_percentage: float = 0) -> dict[str, Any]:
    return {
        "name": name,
        "role": role,
        "unique_count": unique_count,
        "unique_ratio": unique_count / 30,
        "missing_count": missing_count,
        "missing_percentage": missing_percentage,
    }


def _analysis(columns: list[dict[str, Any]], rows: int = 30) -> dict[str, Any]:
    return {
        "dataset_profile": {
            "row_count": rows,
            "column_profiles": columns,
            "categorical_analysis": {
                "group": {"unique_count": 3, "top_values": [{"value": "A", "count": 12, "percentage": 40.0}]},
            },
            "numeric_analysis": {},
        },
        "numeric_statistics": {
            "measure": {"count": rows, "mean": 15.5, "standard_deviation": 8.7, "minimum": 1, "maximum": 30},
            "second_measure": {"count": rows, "mean": 17, "standard_deviation": 9, "minimum": 2, "maximum": 32},
            "constant": {"count": rows, "mean": 4, "standard_deviation": 0, "minimum": 4, "maximum": 4},
        },
        "dashboard": {
            "comparisons": [{"dimension": "group", "measure": "measure", "groups": [
                {"value": "A", "count": 10, "mean": 10},
                {"value": "B", "count": 10, "mean": 20},
                {"value": "C", "count": 10, "mean": 30},
            ]}],
            "trends": [{"date_column": "when", "measure_column": "measure", "aggregation": "mean", "values": [{"date": "2025-01", "value": 3}, {"date": "2025-02", "value": 5}]}],
            "relationships": {"strongest": [{"column_a": "measure", "column_b": "second_measure", "correlation": 0.82, "sample_size": rows, "strength": "strong"}]},
        },
    }


def test_numeric_only_dataset_recommends_only_supported_numeric_distribution() -> None:
    analysis = _analysis([_column("measure", "NUMERIC", 30)])

    recommendations = generate_exploration_recommendations(analysis)

    assert [item["type"] for item in recommendations] == ["numeric_distribution"]
    assert recommendations[0]["visualization"] == "histogram"


def test_mixed_dataset_skips_constant_and_unique_identifier_fields() -> None:
    analysis = _analysis([
        _column("group", "CATEGORICAL", 3),
        _column("measure", "NUMERIC", 30),
        _column("second_measure", "NUMERIC", 30),
        _column("constant", "NUMERIC", 1),
        _column("record_key", "IDENTIFIER", 30),
        _column("when", "DATE", 8),
    ])

    recommendations = generate_exploration_recommendations(analysis)
    types = {item["type"] for item in recommendations}

    assert {"categorical_distribution", "group_comparison", "numeric_distribution", "numeric_relationship", "time_trend"} <= types
    assert all("constant" not in item["id"] and "record_key" not in item["id"] for item in recommendations)
    assert all(item["reason"] and item["relevance"] > 0 for item in recommendations)


def test_high_cardinality_and_constant_fields_do_not_get_recommended() -> None:
    analysis = _analysis([
        _column("near_unique", "CATEGORICAL", 29),
        _column("constant", "NUMERIC", 1),
    ])

    recommendations = generate_exploration_recommendations(analysis)

    assert recommendations == []


def test_missingness_review_only_appears_when_profile_has_missing_values() -> None:
    with_missing = generate_exploration_recommendations(_analysis([
        _column("group", "CATEGORICAL", 3, missing_count=4, missing_percentage=13.3),
    ]))
    complete = generate_exploration_recommendations(_analysis([_column("group", "CATEGORICAL", 3)]))

    assert any(item["type"] == "missingness_review" for item in with_missing)
    assert not any(item["type"] == "missingness_review" for item in complete)


def test_categorical_only_dataset_gets_distribution_without_numeric_measure() -> None:
    recommendations = generate_exploration_recommendations(_analysis([_column("unfamiliar segment", "CATEGORICAL", 3)]))

    assert recommendations
    assert all(item["type"] == "categorical_distribution" for item in recommendations)
    assert all(item["measure"] is None for item in recommendations)


def test_duplicate_review_is_recommended_only_from_duplicate_evidence() -> None:
    analysis = _analysis([_column("group", "CATEGORICAL", 3)])
    analysis["summary"] = {"duplicate_rows": 4}

    recommendations = generate_exploration_recommendations(analysis)

    duplicate_recommendation = next(item for item in recommendations if item["type"] == "duplicate_review")
    assert "4 duplicate rows" in duplicate_recommendation["reason"]