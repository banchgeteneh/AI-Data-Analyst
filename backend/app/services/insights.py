from __future__ import annotations

import json
import math
from typing import Any

from groq import APIStatusError, Groq

from app.config import get_settings


def explain_insights_with_ai(insights: list[dict[str, Any]], dataset_name: str = "Dataset") -> str | None:
    settings = get_settings()
    api_key = settings.groq_api_key.strip()
    if not api_key:
        return None

    payload = json.dumps({"dataset_name": dataset_name, "insights": insights[:5]}, ensure_ascii=False)
    try:
        client = Groq(api_key=api_key, timeout=20.0, max_retries=0)
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {
                    "role": "system",
                    "content": "You translate deterministic data insights into concise, plain-English guidance. Use only the supplied facts and avoid guessing. Keep the answer brief and specific.",
                },
                {"role": "user", "content": f"Dataset: {dataset_name}\nInsights JSON:\n{payload}"},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        content = getattr(response.choices[0].message, "content", None) if getattr(response, "choices", None) else None
        return str(content).strip() if content else None
    except (APIStatusError, Exception):
        return None


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, str) and value.strip() == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _to_title(value: Any) -> str:
    if value is None:
        return "Value"
    text = str(value)
    return text.replace("_", " ").strip() or "Value"


def _insight_score(priority: str, confidence: int, sample_size: int | None) -> tuple[int, int]:
    weight = {"low": 1, "medium": 2, "high": 3}.get(priority, 1)
    sample_bonus = 5 if sample_size and sample_size >= 10 else 0
    return weight * 100 + confidence + sample_bonus, confidence


def detect_quality_insight(data_quality: dict[str, Any], overview: dict[str, Any]) -> dict[str, Any] | None:
    missing = int(data_quality.get("missing_cells") or 0)
    duplicates = int(data_quality.get("duplicate_rows") or 0)
    completeness = data_quality.get("completeness_percentage")
    row_count = int(overview.get("row_count") or 0)
    if missing == 0 and duplicates == 0 and (completeness is None or completeness >= 95):
        if row_count < 3:
            return None
        return {
            "type": "quality",
            "title": "Data quality is in good shape",
            "summary": "The dataset is complete, with no missing values or duplicated records, so the numerical patterns are likely stable.",
            "impact": "low",
            "confidence": 84,
            "sample_size": row_count,
            "recommended_action": "Keep an eye on data entry quality as the dataset grows, but the current profile is solid for analysis.",
            "evidence": {
                "missing_cells": missing,
                "duplicate_rows": duplicates,
                "completeness_percentage": completeness,
            },
        }

    issues = []
    if missing:
        issues.append(f"{missing} missing values")
    if duplicates:
        issues.append(f"{duplicates} duplicate rows")
    if completeness is not None and completeness < 95:
        issues.append(f"{completeness:.1f}% completeness")

    summary = "; ".join(issues)
    return {
        "type": "quality",
        "title": "Data quality needs a quick review",
        "summary": f"The dataset shows {summary}.",
        "impact": "high" if completeness is not None and completeness < 80 or missing > 0 or duplicates > 0 else "medium",
        "confidence": 72,
        "sample_size": row_count,
        "recommended_action": "Review the missing or duplicated values before drawing conclusions from the dataset.",
        "evidence": {
            "missing_cells": missing,
            "duplicate_rows": duplicates,
            "completeness_percentage": completeness,
        },
    }


def detect_relationship_insight(relationships: dict[str, Any]) -> dict[str, Any] | None:
    strongest = relationships.get("strongest") or []
    for pair in strongest:
        sample_size = int(pair.get("sample_size") or 0)
        if sample_size < 3:
            continue
        correlation = _finite_number(pair.get("correlation"))
        if correlation is None:
            continue
        magnitude = abs(correlation)
        if magnitude < 0.4:
            continue
        direction = "positive" if correlation >= 0 else "negative"
        return {
            "type": "relationship",
            "title": f"{_to_title(pair.get('column_a'))} and {_to_title(pair.get('column_b'))} are meaningfully connected",
            "summary": (
                f"The {direction} relationship between {_to_title(pair.get('column_a'))} and {_to_title(pair.get('column_b'))} "
                f"has a correlation of {correlation:.2f} across {sample_size} matched records."
            ),
            "impact": "high" if magnitude >= 0.7 else "medium",
            "confidence": min(96, max(60, int(abs(correlation) * 100))),
            "sample_size": sample_size,
            "recommended_action": "Validate whether this relationship reflects a business rule or a data artifact before acting on it.",
            "evidence": {
                "column_a": pair.get("column_a"),
                "column_b": pair.get("column_b"),
                "correlation": round(correlation, 4),
                "strength": pair.get("strength"),
            },
        }
    return None


def detect_trend_insight(trends: list[dict[str, Any]]) -> dict[str, Any] | None:
    for trend in trends or []:
        values = trend.get("values") or []
        if len(values) < 2:
            continue
        valid_values = [item.get("value") for item in values if _finite_number(item.get("value")) is not None]
        if len(valid_values) < 2:
            continue
        start = _finite_number(valid_values[0])
        end = _finite_number(valid_values[-1])
        if start is None or end is None or start == end:
            continue
        delta = end - start
        percent_change = (delta / abs(start)) * 100 if start != 0 else 0.0
        direction = "increased" if delta >= 0 else "decreased"
        return {
            "type": "trend",
            "title": f"{_to_title(trend.get('measure_column'))} has been trending {direction}",
            "summary": (
                f"{_to_title(trend.get('measure_column'))} moved from {start:.2f} to {end:.2f} across {len(values)} time points, "
                f"which is a change of {percent_change:.1f}%"
            ),
            "impact": "high" if abs(percent_change) >= 20 else "medium",
            "confidence": min(95, max(55, int(abs(percent_change) * 1.5 + (len(values) * 5))),),
            "sample_size": len(values),
            "recommended_action": "Keep monitoring the trend and compare it to any known seasonal or operational context.",
            "evidence": {
                "date_column": trend.get("date_column"),
                "measure_column": trend.get("measure_column"),
                "start_value": round(start, 4),
                "end_value": round(end, 4),
                "percent_change": round(percent_change, 4),
            },
        }
    return None


def detect_category_insight(distributions: list[dict[str, Any]], row_count: int) -> dict[str, Any] | None:
    for distribution in distributions or []:
        if distribution.get("type") != "categorical":
            continue
        categories = distribution.get("categories") or []
        if not categories:
            continue
        top = categories[0]
        if not isinstance(top, dict):
            continue
        count = int(top.get("count") or 0)
        if row_count <= 0 or count <= 0:
            continue
        share = count / row_count
        if share < 0.4:
            continue
        return {
            "type": "category",
            "title": f"{_to_title(top.get('value'))} dominates {_to_title(distribution.get('column'))}",
            "summary": (
                f"{_to_title(top.get('value'))} makes up {share * 100:.1f}% of the records in {_to_title(distribution.get('column'))}."
            ),
            "impact": "high" if share >= 0.6 else "medium",
            "confidence": min(97, max(60, int(share * 100 + 20))),
            "sample_size": row_count,
            "recommended_action": "Check whether this concentration reflects the expected segment mix or a biased sample.",
            "evidence": {
                "column": distribution.get("column"),
                "top_value": top.get("value"),
                "share": round(share, 4),
            },
        }
    return None


def detect_comparison_insight(comparisons: list[dict[str, Any]]) -> dict[str, Any] | None:
    for comparison in comparisons or []:
        groups = comparison.get("groups") or []
        if len(groups) < 2:
            continue
        valid = [group for group in groups if _finite_number(group.get("mean")) is not None]
        if len(valid) < 2:
            continue
        highest = max(valid, key=lambda item: _finite_number(item.get("mean")) or 0.0)
        lowest = min(valid, key=lambda item: _finite_number(item.get("mean")) or float("inf"))
        highest_value = _finite_number(highest.get("mean"))
        lowest_value = _finite_number(lowest.get("mean"))
        if highest_value is None or lowest_value is None:
            continue
        gap = highest_value - lowest_value
        if abs(gap) < 1e-9:
            continue
        return {
            "type": "comparison",
            "title": f"{_to_title(highest.get('value'))} stands out on {_to_title(comparison.get('measure'))}",
            "summary": (
                f"The {_to_title(comparison.get('dimension'))} group {_to_title(highest.get('value'))} averages {highest_value:.2f} for "
                f"{_to_title(comparison.get('measure'))}, compared with {lowest_value:.2f} for {_to_title(lowest.get('value'))}."
            ),
            "impact": "high" if gap >= max(2.0, abs(lowest_value) * 0.25) else "medium",
            "confidence": min(95, max(60, int(abs(gap) * 10 + 40))),
            "sample_size": sum(int(group.get("count") or 0) for group in valid),
            "recommended_action": "Investigate the drivers behind the highest and lowest group performance to inform the next decision.",
            "evidence": {
                "dimension": comparison.get("dimension"),
                "measure": comparison.get("measure"),
                "highest_group": highest.get("value"),
                "highest_mean": round(highest_value, 4),
                "lowest_group": lowest.get("value"),
                "lowest_mean": round(lowest_value, 4),
            },
        }
    return None


def build_automatic_insights(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    overview = dashboard.get("overview") or {}
    row_count = int(overview.get("row_count") or 0)
    data_quality = dashboard.get("data_quality") or {}
    distributions = dashboard.get("distributions") or []
    relationships = dashboard.get("relationships") or {}
    trends = dashboard.get("trends") or []
    comparisons = dashboard.get("comparisons") or []

    candidates = [
        detect_quality_insight(data_quality, overview),
        detect_relationship_insight(relationships),
        detect_trend_insight(trends),
        detect_category_insight(distributions, row_count),
        detect_comparison_insight(comparisons),
    ]

    insights = [insight for insight in candidates if insight is not None]
    insights.sort(key=lambda insight: _insight_score(insight["impact"], insight["confidence"], insight.get("sample_size"))[0], reverse=True)
    for insight in insights[:5]:
        evidence = insight.get("evidence") or {}
        link: dict[str, Any] | None = None
        if insight.get("type") == "relationship" and evidence.get("column_a") and evidence.get("column_b"):
            link = {"type": "numeric_relationship", "x_field": evidence["column_a"], "y_field": evidence["column_b"], "visualization": "scatter"}
        elif insight.get("type") == "trend" and evidence.get("date_column") and evidence.get("measure_column"):
            matched_trend = next((trend for trend in trends if trend.get("date_column") == evidence["date_column"] and trend.get("measure_column") == evidence["measure_column"]), {})
            link = {"type": "time_trend", "date_field": evidence["date_column"], "measure": evidence["measure_column"], "aggregation": matched_trend.get("aggregation") or "mean", "visualization": "line"}
        elif insight.get("type") == "comparison" and evidence.get("dimension") and evidence.get("measure"):
            link = {"type": "group_comparison", "dimension": evidence["dimension"], "measure": evidence["measure"], "aggregation": "mean", "visualization": "bar"}
        elif insight.get("type") == "category" and evidence.get("column"):
            link = {"type": "categorical_distribution", "dimension": evidence["column"], "aggregation": "count", "visualization": "bar"}
        elif insight.get("type") == "quality" and evidence.get("missing_cells", 0) > 0:
            link = {"type": "missingness_review", "visualization": "bar"}
        elif insight.get("type") == "quality" and evidence.get("duplicate_rows", 0) > 0:
            link = {"type": "duplicate_review", "visualization": "bar"}
        if link is not None:
            insight["exploration"] = {"available": True, **link}
    return insights[:5]
