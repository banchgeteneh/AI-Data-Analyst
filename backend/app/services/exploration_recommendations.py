from __future__ import annotations

import math
from typing import Any


def _valid_measure(profile: dict[str, Any], statistics: dict[str, Any], row_count: int) -> bool:
    count = int(statistics.get("count") or 0)
    minimum = statistics.get("minimum")
    maximum = statistics.get("maximum")
    deviation = statistics.get("standard_deviation")
    if count < 3 or row_count < 3 or minimum is None or maximum is None:
        return False
    try:
        if float(minimum) == float(maximum):
            return False
        if deviation is not None and (not math.isfinite(float(deviation)) or float(deviation) <= 0):
            return False
    except (TypeError, ValueError):
        return False
    return profile.get("role") == "NUMERIC"


def _recommendation(
    *,
    pattern: str,
    title: str,
    description: str,
    reason: str,
    relevance: int,
    visualization: str,
    dimension: str | None = None,
    measure: str | None = None,
    secondary_measure: str | None = None,
    date_field: str | None = None,
    aggregation: str | None = None,
    required_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    fields = [field for field in (dimension, measure, secondary_measure, date_field) if field]
    return {
        "id": ":".join((pattern, *(str(field) for field in fields))),
        "title": title,
        "description": description,
        "type": pattern,
        "dimension": dimension,
        "measure": measure,
        "secondary_measure": secondary_measure,
        "date_field": date_field,
        "aggregation": aggregation,
        "visualization": visualization,
        "reason": reason,
        "relevance": relevance,
        "confidence": min(98, max(50, relevance)),
        "required_capabilities": required_capabilities or [],
    }


def generate_exploration_recommendations(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Recommend only explorations supported by detected roles and observed data."""
    profile = analysis.get("dataset_profile") or {}
    row_count = int(profile.get("row_count") or 0)
    column_profiles = [item for item in profile.get("column_profiles", []) if isinstance(item, dict)]
    by_name = {str(item.get("name")): item for item in column_profiles if item.get("name") is not None}
    numeric_stats = analysis.get("numeric_statistics") or {}
    profile_numeric_stats = profile.get("numeric_analysis") or {}
    dimensions: list[str] = []
    measures: list[str] = []
    dates: list[str] = []

    for name, item in by_name.items():
        role = item.get("role")
        unique_count = int(item.get("unique_count") or 0)
        unique_ratio = float(item.get("unique_ratio") or 0.0)
        if role in {"CATEGORICAL", "BOOLEAN"} and 2 <= unique_count <= 30 and unique_ratio < 0.8:
            dimensions.append(name)
        elif role == "DATE" and unique_count >= 2:
            dates.append(name)
        elif role == "NUMERIC":
            stats = numeric_stats.get(name) or profile_numeric_stats.get(name) or {}
            if _valid_measure(item, stats, row_count):
                measures.append(name)

    recommendations: list[dict[str, Any]] = []
    categorical_stats = profile.get("categorical_analysis") or {}
    for dimension in dimensions:
        stats = categorical_stats.get(dimension) or {}
        unique_count = int(stats.get("unique_count") or by_name[dimension].get("unique_count") or 0)
        top_values = stats.get("top_values") or []
        top_share = float(top_values[0].get("percentage") or 0) if top_values else 0
        cardinality_score = 20 if unique_count <= 8 else 12 if unique_count <= 20 else 5
        concentration_score = 12 if top_share >= 60 else 6 if top_share >= 40 else 0
        relevance = min(95, 55 + cardinality_score + concentration_score + (10 if row_count >= 20 else 0))
        recommendations.append(_recommendation(
            pattern="categorical_distribution",
            title=f"Distribution of {dimension}",
            description=f"Compare the frequency of values in {dimension}.",
            reason=(f"The field has {unique_count} observed values" + (f", with the most common representing {top_share:.1f}% of non-missing values." if top_values else ".")),
            relevance=relevance,
            visualization="pie" if unique_count <= 5 and row_count >= 10 else "bar",
            dimension=dimension,
            aggregation="count",
            required_capabilities=["dimension", "count"],
        ))

        for measure in measures[:4]:
            comparison = next((item for item in (analysis.get("dashboard") or {}).get("comparisons", [])
                               if item.get("dimension") == dimension and item.get("measure") == measure), None)
            groups = comparison.get("groups", []) if comparison else []
            if len(groups) < 2 or min(int(group.get("count") or 0) for group in groups) < 2:
                continue
            means = [float(group["mean"]) for group in groups if group.get("mean") is not None]
            if len(means) < 2:
                continue
            spread = max(means) - min(means)
            scale = max(abs(value) for value in means)
            variation = spread / scale if scale else 0
            relevance = min(97, 55 + (20 if variation >= 0.5 else 12 if variation >= 0.2 else 5) + (10 if row_count >= 30 else 0))
            recommendations.append(_recommendation(
                pattern="group_comparison",
                title=f"Compare {measure} across {dimension}",
                description=f"Compare the average {measure} for observed groups of {dimension}.",
                reason=f"At least two groups have two or more usable observations; displayed group averages span {spread:.3g}.",
                relevance=relevance,
                visualization="bar",
                dimension=dimension,
                measure=measure,
                aggregation="mean",
                required_capabilities=["dimension", "numeric_measure", "minimum_group_size"],
            ))

        if row_count >= 10 and unique_count <= 8 and len(measures) > 1:
            for measure_index, primary in enumerate(measures[:3]):
                secondary_candidates = measures[measure_index + 1:4]
                for secondary in secondary_candidates:
                    comparisons = (analysis.get("dashboard") or {}).get("comparisons", [])
                    primary_groups = next((item.get("groups", []) for item in comparisons if item.get("dimension") == dimension and item.get("measure") == primary), [])
                    secondary_groups = next((item.get("groups", []) for item in comparisons if item.get("dimension") == dimension and item.get("measure") == secondary), [])
                    if len(primary_groups) < 2 or len(secondary_groups) < 2:
                        continue
                    primary_by_group = {str(group.get("value")): float(group["mean"]) for group in primary_groups if group.get("mean") is not None and int(group.get("count") or 0) >= 3}
                    secondary_by_group = {str(group.get("value")): float(group["mean"]) for group in secondary_groups if group.get("mean") is not None and int(group.get("count") or 0) >= 3}
                    common_groups = primary_by_group.keys() & secondary_by_group.keys()
                    if len(common_groups) < 2:
                        continue
                    primary_values = [primary_by_group[group] for group in common_groups]
                    secondary_values = [secondary_by_group[group] for group in common_groups]
                    primary_scale = max(abs(value) for value in primary_values)
                    secondary_scale = max(abs(value) for value in secondary_values)
                    if min(primary_scale, secondary_scale) == 0 or max(primary_scale, secondary_scale) / min(primary_scale, secondary_scale) > 10:
                        continue
                    recommendations.append(_recommendation(
                        pattern="multi_measure_comparison",
                        title=f"Compare {primary} and {secondary} across {dimension}",
                        description="Compare group averages for two numeric measures with similar observed scales.",
                        reason=f"Both measures have at least two groups with three or more observations, and their displayed scales are comparable.",
                        relevance=76,
                        visualization="bar",
                        dimension=dimension,
                        measure=primary,
                        secondary_measure=secondary,
                        aggregation="mean",
                        required_capabilities=["dimension", "two_numeric_measures", "minimum_group_size", "comparable_scale"],
                    ))
                    break
                if any(item["type"] == "multi_measure_comparison" and item.get("dimension") == dimension for item in recommendations):
                    break

    for measure in measures:
        stats = numeric_stats.get(measure) or profile_numeric_stats.get(measure) or {}
        deviation = float(stats.get("standard_deviation") or 0)
        mean = abs(float(stats.get("mean") or 0))
        relative_spread = deviation / mean if mean else deviation
        relevance = min(90, 60 + (15 if relative_spread >= 1 else 8 if relative_spread >= 0.25 else 0) + (8 if row_count >= 20 else 0))
        recommendations.append(_recommendation(
            pattern="numeric_distribution",
            title=f"Distribution of {measure}",
            description=f"Inspect the range and shape of values in {measure}.",
            reason=f"{measure} varies from {stats.get('minimum')} to {stats.get('maximum')} across {int(stats.get('count') or 0)} valid observations.",
            relevance=relevance,
            visualization="histogram",
            measure=measure,
            required_capabilities=["numeric_measure", "multiple_observations"],
        ))

    dashboard = analysis.get("dashboard") or {}
    trends = dashboard.get("trends") or []
    for date_field in dates:
        matching = [item for item in trends if item.get("date_column") == date_field and len(item.get("values") or []) >= 2]
        for trend in matching[:2]:
            measure = str(trend.get("measure_column"))
            recommendations.append(_recommendation(
                pattern="time_trend",
                title=f"Track {measure} over time",
                description=f"Follow the {trend.get('aggregation', 'mean')} of {measure} across {date_field}.",
                reason=f"{date_field} contains repeated observations across {len(trend.get('values') or [])} time points.",
                relevance=min(96, 65 + min(20, len(trend.get("values") or []))),
                visualization="line",
                dimension=date_field,
                measure=measure,
                date_field=date_field,
                aggregation=trend.get("aggregation") or "mean",
                required_capabilities=["date_field", "numeric_measure", "repeated_time_points"],
            ))

    for pair in ((dashboard.get("relationships") or {}).get("strongest") or [])[:5]:
        correlation = pair.get("correlation")
        sample_size = int(pair.get("sample_size") or 0)
        if pair.get("column_a") not in measures or pair.get("column_b") not in measures:
            continue
        if correlation is None or sample_size < 5 or abs(float(correlation)) < 0.4:
            continue
        relevance = min(98, int(58 + abs(float(correlation)) * 30 + min(sample_size, 50) / 5))
        recommendations.append(_recommendation(
            pattern="numeric_relationship",
            title=f"Explore {pair['column_a']} and {pair['column_b']}",
            description="Inspect paired numeric values and their observed association.",
            reason=f"The numeric fields have a correlation of {float(correlation):.2f} across {sample_size} matched observations; association does not establish causation.",
            relevance=relevance,
            visualization="scatter",
            dimension=pair["column_a"],
            measure=pair["column_b"],
            required_capabilities=["two_numeric_measures", "minimum_pair_count"],
        ))

    missing_columns = [item for item in column_profiles if int(item.get("missing_count") or 0) > 0]
    if missing_columns:
        missing_columns.sort(key=lambda item: int(item.get("missing_count") or 0), reverse=True)
        highest = missing_columns[0]
        recommendations.append(_recommendation(
            pattern="missingness_review",
            title="Review missing values",
            description="Compare missing-value counts across fields.",
            reason=f"{len(missing_columns)} fields contain missing values; {highest.get('name')} has the most ({highest.get('missing_count')}).",
            relevance=min(96, 60 + int(float(highest.get("missing_percentage") or 0) / 2)),
            visualization="bar",
            required_capabilities=["column_missingness"],
        ))

    duplicate_rows = int((analysis.get("summary") or {}).get("duplicate_rows") or 0)
    if duplicate_rows > 0:
        recommendations.append(_recommendation(
            pattern="duplicate_review",
            title="Review duplicate records",
            description="Compare duplicate and distinct row counts in the current dataset.",
            reason=f"The deterministic profile found {duplicate_rows} duplicate rows out of {row_count} total rows.",
            relevance=min(96, 60 + int(duplicate_rows / max(row_count, 1) * 100)),
            visualization="bar",
            required_capabilities=["row_duplicate_profile"],
        ))

    recommendations.sort(key=lambda item: (-item["relevance"], item["type"], item["id"]))
    return recommendations[:12]