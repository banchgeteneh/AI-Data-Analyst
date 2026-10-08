import math
import re
from typing import Any

import numpy as np
import pandas as pd

from app.services.insights import build_automatic_insights


_MAX_DISTRIBUTIONS = 8
_MAX_DISTRIBUTION_VALUES = 25
_MAX_TRENDS = 6
_MAX_COMPARISONS = 12
_MAX_RECOMMENDATIONS = 16


def _finite_number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _label(column: str) -> str:
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", column)
    return re.sub(r"[_\W]+", " ", words).strip().title()


def _is_additive_measure(column: str) -> bool:
    tokens = set(re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", column).casefold().split("_"))
    return bool(tokens & {"amount", "cost", "count", "profit", "quantity", "revenue", "sales", "spend", "total", "units", "value", "volume"})


def _numeric_values(dataframe: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(dataframe[column], errors="coerce").replace([np.inf, -np.inf], np.nan)


def _useful_dimensions(profile: dict[str, Any]) -> list[str]:
    row_count = profile["row_count"]
    max_unique = min(30, max(2, int(math.sqrt(row_count) * 2))) if row_count else 0
    return [
        name
        for name in profile["categorical_columns"]
        if 2 <= profile["categorical_analysis"].get(name, {}).get("unique_count", 0) <= max_unique
        and profile["categorical_analysis"].get(name, {}).get("unique_count", 0) / max(row_count, 1) < 0.8
    ]


def _build_metrics(profile: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = []
    for column in profile["numeric_columns"]:
        stats = profile["numeric_analysis"].get(column, {})
        useful_statistics = ["mean", "median", "minimum", "maximum"]
        additive = _is_additive_measure(column)
        if additive:
            useful_statistics.insert(0, "total")
        metrics.append({
            "column": column,
            "label": _label(column),
            "type": "numeric",
            "count": stats.get("count", 0),
            "mean": stats.get("mean"),
            "median": stats.get("median"),
            "min": stats.get("minimum"),
            "max": stats.get("maximum"),
            "sum": _finite_number(stats["mean"] * stats["count"]) if additive and stats.get("mean") is not None else None,
            "recommended_statistics": useful_statistics,
        })
    return metrics


def _build_distributions(dataframe: pd.DataFrame, profile: dict[str, Any]) -> list[dict[str, Any]]:
    if profile["row_count"] < 2:
        return []
    results: list[dict[str, Any]] = []
    for column in _useful_dimensions(profile)[:_MAX_DISTRIBUTIONS]:
        stats = profile["categorical_analysis"].get(column, {})
        results.append({
            "column": column,
            "label": _label(column),
            "type": "categorical",
            "total_records": profile["row_count"],
            "categories": stats.get("top_values", [])[:_MAX_DISTRIBUTION_VALUES],
            "histogram": [],
            "box_plot": None,
        })

    for column in profile["numeric_columns"][:3]:
        values = _numeric_values(dataframe, column).dropna()
        if len(values) < 2:
            continue
        bin_count = min(10, max(2, int(math.ceil(math.sqrt(len(values))))))
        counts, edges = np.histogram(values.to_numpy(dtype=float), bins=bin_count)
        results.append({
            "column": column,
            "label": _label(column),
            "type": "numeric",
            "total_records": int(len(values)),
            "categories": [],
            "histogram": [
                {
                    "start": _finite_number(edges[index]),
                    "end": _finite_number(edges[index + 1]),
                    "count": int(count),
                    "percentage": round(int(count) / len(values) * 100, 6),
                }
                for index, count in enumerate(counts)
            ],
            "box_plot": {
                "minimum": _finite_number(values.min()),
                "first_quartile": _finite_number(values.quantile(0.25)),
                "median": _finite_number(values.median()),
                "third_quartile": _finite_number(values.quantile(0.75)),
                "maximum": _finite_number(values.max()),
            },
        })
    return results


def _build_relationships(dataframe: pd.DataFrame, profile: dict[str, Any]) -> dict[str, Any]:
    matrix = profile.get("relationships", {}).get("correlations", {})
    pairs = []
    columns = profile["numeric_columns"]
    for left_index, left in enumerate(columns):
        for right in columns[left_index + 1:]:
            value = matrix.get(left, {}).get(right)
            if value is None:
                continue
            left_values = _numeric_values(dataframe, left)
            right_values = _numeric_values(dataframe, right)
            sample_size = int((left_values.notna() & right_values.notna()).sum())
            if sample_size < 2:
                continue
            absolute = abs(value)
            strength = "strong" if absolute >= 0.7 else "moderate" if absolute >= 0.4 else "weak"
            pairs.append({
                "column_a": left,
                "column_b": right,
                "correlation": value,
                "sample_size": sample_size,
                "strength": strength,
            })
    strongest = sorted(pairs, key=lambda pair: (-abs(pair["correlation"]), pair["column_a"], pair["column_b"]))[:5]
    return {"matrix": matrix, "pairs": pairs, "strongest": strongest}


def _build_trends(dataframe: pd.DataFrame, profile: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for date_column in profile["date_columns"]:
        dates = pd.to_datetime(dataframe[date_column], errors="coerce", utc=True, format="mixed")
        for measure in profile["numeric_columns"]:
            values = _numeric_values(dataframe, measure)
            valid = pd.DataFrame({"date": dates.dt.strftime("%Y-%m-%d"), "value": values}).dropna()
            if len(valid) < 2:
                continue
            aggregation = "sum" if _is_additive_measure(measure) else "mean"
            grouped = valid.groupby("date", as_index=False, sort=True)["value"]
            aggregated = getattr(grouped, aggregation)()
            results.append({
                "date_column": date_column,
                "measure_column": measure,
                "aggregation": aggregation,
                "period": "day",
                "values": [
                    {"date": date, "value": _finite_number(value)}
                    for date, value in aggregated.itertuples(index=False, name=None)
                ],
            })
            if len(results) >= _MAX_TRENDS:
                return results
    return results


def _build_comparisons(dataframe: pd.DataFrame, profile: dict[str, Any]) -> list[dict[str, Any]]:
    if profile["row_count"] < 3:
        return []
    comparisons = []
    dimensions = _useful_dimensions(profile)
    for dimension in dimensions:
        groups = dataframe[dimension]
        ordered_values = sorted(groups.dropna().unique(), key=lambda value: (-int((groups == value).sum()), str(value)))
        ordered_values = ordered_values[:_MAX_DISTRIBUTION_VALUES]
        for measure in profile["numeric_columns"]:
            values = _numeric_values(dataframe, measure)
            group_results = []
            for category in ordered_values:
                selected = values[groups == category].dropna()
                if selected.empty:
                    continue
                group_results.append({
                    "value": category.item() if isinstance(category, np.generic) else category,
                    "count": int(len(selected)),
                    "mean": _finite_number(selected.mean()),
                    "median": _finite_number(selected.median()),
                })
            if len(group_results) >= 2:
                comparisons.append({
                    "dimension": dimension,
                    "measure": measure,
                    "aggregation": "mean",
                    "groups": group_results,
                })
            if len(comparisons) >= _MAX_COMPARISONS:
                return comparisons
    return comparisons


def _build_quality(profile: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    incomplete = [
        {"column": column["name"], "missing_count": column["missing_count"], "missing_percentage": column["missing_percentage"]}
        for column in profile["column_profiles"]
        if column["missing_count"] > 0
    ]
    high_cardinality = [
        column["name"]
        for column in profile["column_profiles"]
        if column["role"] in {"IDENTIFIER", "TEXT"}
    ]
    observations = []
    missing = source["missing_cells"]
    if missing:
        observations.append(f"{missing} values are missing")
    duplicates = source["duplicate_rows"]
    if duplicates:
        observations.append(f"{duplicates} duplicate rows were found")
    if source["completeness_percentage"] is not None:
        observations.append(f"Dataset completeness is {source['completeness_percentage']}%")
    return {
        **source,
        "incomplete_columns": incomplete,
        "high_cardinality_columns": high_cardinality,
        "invalid_or_unclear_values": [],
        "observations": observations,
    }


def _recommendations(
    distributions: list[dict[str, Any]],
    relationships: dict[str, Any],
    trends: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    numeric_columns: list[str],
) -> list[dict[str, Any]]:
    recommended = []
    for distribution in distributions:
        if distribution["type"] == "categorical":
            chart_type = "donut" if len(distribution["categories"]) <= 5 else "bar"
            recommended.append({
                "type": chart_type,
                "title": f"{distribution['label']} distribution",
                "x_column": distribution["column"],
                "y_column": None,
                "reason": "Shows how records are distributed across detected categories",
            })
        elif distribution["histogram"]:
            recommended.append({
                "type": "histogram",
                "title": f"{distribution['label']} distribution",
                "x_column": distribution["column"],
                "y_column": None,
                "reason": "Shows the shape and spread of a numeric field",
            })
    for pair in relationships["strongest"][:3]:
        recommended.append({
            "type": "scatter",
            "title": f"{_label(pair['column_a'])} vs {_label(pair['column_b'])}",
            "x_column": pair["column_a"],
            "y_column": pair["column_b"],
            "reason": "Shows association between two numeric fields; correlation does not imply causation",
        })
    for trend in trends[:4]:
        recommended.append({
            "type": "line",
            "title": f"{_label(trend['measure_column'])} over time",
            "x_column": trend["date_column"],
            "y_column": trend["measure_column"],
            "reason": f"Shows daily {trend['aggregation']} values over time",
        })
    for comparison in comparisons[:4]:
        recommended.append({
            "type": "bar",
            "title": f"{_label(comparison['measure'])} by {_label(comparison['dimension'])}",
            "x_column": comparison["dimension"],
            "y_column": comparison["measure"],
            "reason": "Compares a numeric measure across detected groups",
        })
    if len(numeric_columns) >= 2 and relationships["pairs"]:
        recommended.append({
            "type": "heatmap",
            "title": "Numeric correlation matrix",
            "x_column": None,
            "y_column": None,
            "reason": "Summarizes pairwise relationships between numeric fields",
        })
    return recommended[:_MAX_RECOMMENDATIONS]


def build_dashboard_data(
    dataframe: pd.DataFrame,
    profile: dict[str, Any],
    dataset_name: str,
    data_quality: dict[str, Any],
) -> dict[str, Any]:
    """Build a generic dashboard contract from Phase 1 profiling output."""
    metrics = _build_metrics(profile)
    distributions = _build_distributions(dataframe, profile)
    relationships = _build_relationships(dataframe, profile)
    trends = _build_trends(dataframe, profile)
    comparisons = _build_comparisons(dataframe, profile)
    quality = _build_quality(profile, data_quality)
    overview = {
        "dataset_name": dataset_name,
        "row_count": profile["row_count"],
        "column_count": profile["column_count"],
        "numeric_column_count": len(profile["numeric_columns"]),
        "categorical_column_count": len(profile["categorical_columns"]),
        "date_column_count": len(profile["date_columns"]),
        "text_column_count": len(profile["text_columns"]),
        "identifier_column_count": len(profile["identifier_columns"]),
        "missing_value_count": data_quality["missing_cells"],
        "duplicate_row_count": data_quality["duplicate_rows"],
        "completeness_percentage": data_quality["completeness_percentage"],
    }
    recommendations = _recommendations(distributions, relationships, trends, comparisons, profile["numeric_columns"])
    result = {
        "overview": overview,
        "metrics": metrics,
        "distributions": distributions,
        "relationships": relationships,
        "trends": trends,
        "comparisons": comparisons,
        "data_quality": quality,
        "recommended_visualizations": recommendations,
        "insights_context": {
            "metrics": metrics,
            "strongest_relationships": relationships["strongest"],
            "distributions": distributions,
            "trends": trends,
            "comparisons": comparisons,
            "data_quality": quality,
        },
    }
    result["automatic_insights"] = build_automatic_insights(result)
    result["insights_context"]["automatic_insights"] = result["automatic_insights"]
    return result