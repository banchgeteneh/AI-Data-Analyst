from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from app.models.dataset import Dataset
from app.schemas.exploration import DatasetExplorationRequest, ExplorationFilter
from app.services.dataset_analysis import _read_dataframe, analyze_dataset
from app.services.exploration import build_exploration_capabilities

_NUMERIC_AGGREGATIONS = {"sum", "mean", "median", "min", "max", "std"}
_NUMERIC_FILTERS = {"gt", "gte", "lt", "lte", "between"}
_DATE_FILTERS = {"before", "after", "on_or_before", "on_or_after", "between"}
_CATEGORY_FILTERS = {"equals", "not_equals", "in", "not_in"}


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _series_for_filter(frame: pd.DataFrame, field: str, role: str) -> pd.Series:
    series = frame[field]
    if role == "numeric":
        return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if role == "date":
        return pd.to_datetime(series, errors="coerce", utc=True, format="mixed")
    return series


def _validated_filters(
    frame: pd.DataFrame,
    filters: list[ExplorationFilter],
    profiles: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    filtered = frame
    for item in filters:
        raw_values = item.value if isinstance(item.value, list) else [item.value]
        if len(raw_values) > 50 or any(isinstance(value, str) and len(value) > 240 for value in raw_values):
            raise ValueError("Filter values exceed the supported size limit.")
        if isinstance(item.value_2, str) and len(item.value_2) > 240:
            raise ValueError("Filter values exceed the supported size limit.")
        profile = profiles.get(item.field)
        if profile is None or profile.get("role") in {"IDENTIFIER", "TEXT", "UNKNOWN"}:
            raise ValueError(f"Unsupported filter field: {item.field}")
        role = str(profile.get("role", "")).lower()
        operator = item.operator
        allowed = _NUMERIC_FILTERS if role == "numeric" else _DATE_FILTERS if role == "date" else _CATEGORY_FILTERS
        if role == "boolean":
            allowed = _CATEGORY_FILTERS | {"is_true", "is_false"}
        if operator not in allowed:
            raise ValueError(f"Filter operator '{operator}' is not supported for {role} fields.")

        series = _series_for_filter(filtered, item.field, role)
        value: Any = item.value
        value_2: Any = item.value_2
        if role == "boolean" and pd.api.types.is_bool_dtype(filtered[item.field]) and isinstance(value, str):
            normalized_boolean = value.casefold()
            if normalized_boolean in {"true", "1", "yes", "y"}:
                value = True
            elif normalized_boolean in {"false", "0", "no", "n"}:
                value = False
        if role == "categorical" and pd.api.types.is_numeric_dtype(filtered[item.field]):
            raw_values = value if isinstance(value, list) else [value]
            numeric_values = [_finite_float(raw_value) for raw_value in raw_values]
            if any(numeric_value is None for numeric_value in numeric_values):
                raise ValueError("Numeric-coded categories require numeric filter values.")
            value = numeric_values if operator in {"in", "not_in"} else numeric_values[0]
        if operator in _NUMERIC_FILTERS:
            value = _finite_float(value)
            if value is None:
                raise ValueError("Numeric filters require finite numeric values.")
            if operator == "between":
                value_2 = _finite_float(value_2)
                if value_2 is None or value > value_2:
                    raise ValueError("Numeric range filters require an ordered pair of finite values.")
        elif operator in _DATE_FILTERS:
            value = pd.to_datetime(value, errors="coerce", utc=True)
            if pd.isna(value):
                raise ValueError("Date filters require valid date values.")
            if operator == "between":
                value_2 = pd.to_datetime(value_2, errors="coerce", utc=True)
                if pd.isna(value_2) or value > value_2:
                    raise ValueError("Date range filters require an ordered pair of valid dates.")
        elif operator in {"in", "not_in"}:
            value = value if isinstance(value, list) else [value]
            if not value or len(value) > 50:
                raise ValueError("Category filters accept between 1 and 50 values.")

        if operator == "equals":
            mask = series == value
        elif operator == "not_equals":
            mask = series != value
        elif operator == "in":
            mask = series.isin(value)
        elif operator == "not_in":
            mask = ~series.isin(value)
        elif operator == "gt":
            mask = series > value
        elif operator == "gte":
            mask = series >= value
        elif operator == "lt":
            mask = series < value
        elif operator == "lte":
            mask = series <= value
        elif operator == "before":
            mask = series < value
        elif operator == "after":
            mask = series > value
        elif operator == "on_or_after":
            mask = series >= value
        elif operator == "on_or_before":
            mask = series <= value
        elif operator == "between":
            if role == "date" and isinstance(item.value_2, str) and len(item.value_2) <= 10:
                mask = (series >= value) & (series < value_2 + pd.DateOffset(days=1))
            else:
                mask = series.between(value, value_2, inclusive="both")
        elif operator == "is_true":
            mask = series.astype(str).str.casefold().isin({"true", "1", "yes", "y"})
        else:
            mask = series.astype(str).str.casefold().isin({"false", "0", "no", "n"})
        filtered = filtered.loc[mask.fillna(False)]
    return filtered


def _profile_index(analysis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    profile = analysis.get("dataset_profile") or {}
    return {
        str(item.get("name")): item
        for item in profile.get("column_profiles", [])
        if isinstance(item, dict) and item.get("name") is not None
    }


def _validate_numeric_measure(name: str | None, measure_names: set[str], label: str = "measure") -> str:
    if not name or name not in measure_names:
        raise ValueError(f"Select a supported numeric {label}.")
    return name


def _grouped_points(
    frame: pd.DataFrame,
    dimension: str,
    measure: str | None,
    secondary_measure: str | None,
    aggregation: str,
    limit: int,
    sort: str | None,
    minimum_group_size: int = 2,
) -> tuple[list[dict[str, Any]], int, int]:
    selected_measures = [name for name in (measure, secondary_measure) if name]
    work = frame[[dimension, *selected_measures]].copy()
    work = work.dropna(subset=[dimension])
    if measure is None:
        grouped = work.groupby(dimension, dropna=True, sort=False).size().rename("count")
        total = int(len(grouped))
        grouped = grouped.sort_values(ascending=sort == "ascending", kind="stable")
        points = [{"label": str(label), "count": int(value)} for label, value in grouped.head(limit).items()]
        return points, total, 0

    for name in selected_measures:
        work[name] = pd.to_numeric(work[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
    work = work.dropna(subset=selected_measures)
    group_sizes = work.groupby(dimension, dropna=True, sort=False).size()
    excluded_groups = int((group_sizes < minimum_group_size).sum())
    eligible_groups = group_sizes[group_sizes >= minimum_group_size].index
    work = work.loc[work[dimension].isin(eligible_groups)]
    grouped = work.groupby(dimension, dropna=True, sort=False)[selected_measures]
    if aggregation == "count":
        values = grouped.count()
        point_key = "count"
    else:
        values = grouped.agg(aggregation)
        point_key = "value"
    values = values.dropna(subset=[measure])
    total = int(len(values))
    values = values.sort_values(by=measure, ascending=sort == "ascending", kind="stable")
    points = []
    for label, row in values.head(limit).iterrows():
        number = _finite_float(row[measure])
        if number is not None:
            point = {"label": str(label), point_key: int(number) if point_key == "count" else number}
            if secondary_measure:
                secondary_number = _finite_float(row[secondary_measure])
                point["series"] = {measure: number, secondary_measure: secondary_number}
            points.append(point)
    return points, total, excluded_groups


def _date_frequency(dates: pd.Series) -> str:
    valid = dates.dropna()
    span_seconds = (valid.max() - valid.min()).total_seconds() if not valid.empty else 0
    if valid.empty or span_seconds <= 90 * 86400:
        return "D"
    if span_seconds <= 730 * 86400:
        return "MS"
    if span_seconds <= 1825 * 86400:
        return "QS"
    return "YS"


def _trend_points(
    frame: pd.DataFrame,
    date_field: str,
    measure: str | None,
    aggregation: str,
    limit: int,
) -> tuple[list[dict[str, Any]], int, str]:
    dates = pd.to_datetime(frame[date_field], errors="coerce", utc=True, format="mixed")
    work = pd.DataFrame({"_date": dates})
    work = work.dropna(subset=["_date"])
    frequency = _date_frequency(work["_date"])
    if measure is None:
        values = work.set_index("_date").resample(frequency).size()
        key = "count"
    else:
        work["_measure"] = pd.to_numeric(frame.loc[work.index, measure], errors="coerce").replace([np.inf, -np.inf], np.nan)
        work = work.dropna(subset=["_measure"])
        grouped = work.set_index("_date").resample(frequency)["_measure"]
        values = grouped.count() if aggregation == "count" else grouped.agg(aggregation)
        key = "count" if aggregation == "count" else "value"
    values = values.dropna()
    total = int(len(values))
    points = []
    for date, value in values.tail(limit).items():
        number = _finite_float(value)
        if number is not None:
            points.append({"label": date.isoformat(), key: int(number) if key == "count" else number})
    return points, total, frequency


def _summary(title: str, description: str, points: list[dict[str, Any]], total: int, limitations: list[str]) -> dict[str, Any]:
    observation = None
    ranked = [(point, _finite_float(point.get("value", point.get("count")))) for point in points]
    ranked = [(point, value) for point, value in ranked if value is not None]
    if ranked:
        leading, value = max(ranked, key=lambda item: item[1])
        observation = f"{leading.get('label', 'The leading result')} has the highest displayed value ({value:g})."
    elif points:
        observation = f"{len(points)} paired numeric observations are shown."
    return {
        "title": title,
        "description": description,
        "result_count": len(points),
        "key_observation": observation,
        "limitations": limitations,
        "total_count": total,
    }


def execute_exploration(
    dataset: Dataset,
    request: DatasetExplorationRequest,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    analysis = analysis or analyze_dataset(dataset)
    capabilities = build_exploration_capabilities(analysis)
    profiles = _profile_index(analysis)
    dimension_names = {field.name for field in capabilities.dimensions}
    date_names = {field.name for field in capabilities.time_fields}
    measure_names = {field.name for field in capabilities.measures}
    if not any((request.exploration_type, request.dimension, request.measure, request.x_field, request.y_field, request.date_field)):
        recommendation = next(iter(capabilities.recommended_explorations), None)
        if recommendation is None:
            raise ValueError("No suitable exploration is available for this dataset.")
        request = DatasetExplorationRequest(
            exploration_type=recommendation.type,
            dimension=recommendation.dimension,
            measure=recommendation.measure,
            secondary_measure=recommendation.secondary_measure,
            date_field=recommendation.date_field,
            x_field=recommendation.dimension if recommendation.type == "numeric_relationship" else None,
            y_field=recommendation.measure if recommendation.type == "numeric_relationship" else None,
            aggregation=recommendation.aggregation,
            limit=request.limit,
            filters=request.filters,
            sort=request.sort,
        )
    limit = request.limit
    frame = _read_dataframe(dataset)

    pattern = request.exploration_type
    if request.date_field and request.date_field not in date_names:
        raise ValueError(f"Unsupported date field: {request.date_field}")
    if request.measure and request.measure not in measure_names:
        raise ValueError(f"Unsupported numeric measure: {request.measure}")
    if request.secondary_measure and request.secondary_measure not in measure_names:
        raise ValueError(f"Unsupported numeric secondary measure: {request.secondary_measure}")
    if request.secondary_measure and request.secondary_measure == request.measure:
        raise ValueError("Choose a different field for the secondary measure.")
    if request.secondary_measure and pattern != "multi_measure_comparison":
        raise ValueError("A secondary measure is only supported for multi-measure comparisons.")
    if request.dimension:
        allowed_dimensions = measure_names if pattern == "numeric_relationship" else dimension_names
        if request.dimension not in allowed_dimensions:
            raise ValueError(f"Unsupported exploration dimension: {request.dimension}")
        if pattern in {"categorical_distribution", "group_comparison", "multi_measure_comparison"} and profiles.get(request.dimension, {}).get("role") not in {"CATEGORICAL", "BOOLEAN"}:
            raise ValueError("This exploration requires a supported categorical or boolean dimension.")
    if request.x_field and request.x_field not in measure_names:
        raise ValueError(f"Unsupported numeric x field: {request.x_field}")
    if request.y_field and request.y_field not in measure_names:
        raise ValueError(f"Unsupported numeric y field: {request.y_field}")
    if pattern == "categorical_distribution" and (not request.dimension or request.measure):
        raise ValueError("A categorical distribution requires one supported dimension and no measure.")
    if pattern in {"group_comparison", "multi_measure_comparison"} and (not request.dimension or not request.measure):
        raise ValueError("A group comparison requires a supported dimension and numeric measure.")
    if pattern == "multi_measure_comparison" and not request.secondary_measure:
        raise ValueError("A multi-measure comparison requires two supported numeric measures.")
    if pattern == "multi_measure_comparison" and (not request.dimension or request.dimension not in dimension_names):
        raise ValueError("A multi-measure comparison requires a supported grouping dimension.")
    if pattern == "time_trend" and not request.date_field:
        raise ValueError("A time trend requires a supported date field.")
    if pattern == "numeric_distribution" and not request.measure:
        raise ValueError("A numeric distribution requires a supported numeric measure.")
    if pattern == "numeric_relationship" and not (request.x_field or request.dimension) or pattern == "numeric_relationship" and not (request.y_field or request.measure):
        raise ValueError("A numeric relationship requires two supported numeric fields.")
    if pattern in {"missingness_review", "duplicate_review"} and (request.dimension or request.measure or request.x_field or request.y_field):
        raise ValueError("A dataset quality review does not accept dimension or measure fields.")

    for filter_item in request.filters:
        if filter_item.field not in frame.columns:
            raise ValueError(f"Unsupported filter field: {filter_item.field}")
    frame = _validated_filters(frame, request.filters, profiles)

    if request.date_from or request.date_to:
        if not request.date_field or request.date_field not in date_names:
            raise ValueError("A supported date field is required for date-range filtering.")
        date_from = pd.to_datetime(request.date_from, errors="coerce", utc=True) if request.date_from else None
        date_to = pd.to_datetime(request.date_to, errors="coerce", utc=True) if request.date_to else None
        if request.date_from and pd.isna(date_from) or request.date_to and pd.isna(date_to):
            raise ValueError("Date-range filters require valid date values.")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("Date-range start must be on or before its end.")
        date_to_exclusive = date_to + pd.DateOffset(days=1) if request.date_to and len(request.date_to) <= 10 else date_to
        dates = pd.to_datetime(frame[request.date_field], errors="coerce", utc=True, format="mixed")
        if date_from is not None:
            frame = frame.loc[dates >= date_from]
            dates = dates.loc[frame.index]
        if date_to is not None:
            frame = frame.loc[dates < date_to_exclusive] if request.date_to and len(request.date_to) <= 10 else frame.loc[dates <= date_to]

    limitations: list[str] = []
    points: list[dict[str, Any]] = []
    total = 0
    visualization = "bar"
    aggregation = request.aggregation or "count"
    dimension = request.dimension
    measure = request.measure
    frequency = None
    relationship_correlation = None
    excluded_groups = 0

    if pattern == "duplicate_review":
        duplicate_count = int(frame.duplicated().sum())
        unique_count = max(0, int(len(frame)) - duplicate_count)
        total = 2
        points = [
            {"label": "Duplicate rows", "count": duplicate_count},
            {"label": "Distinct rows", "count": unique_count},
        ]
        visualization = "bar"
        aggregation = "count"
        title = "Duplicate and distinct rows"
        description = "A row-level duplicate check on the currently filtered records."
        dimension = None
        measure = None
    elif pattern == "missingness_review":
        counts = frame.isna().sum()
        counts = counts[counts > 0].sort_values(ascending=False, kind="stable")
        total = int(len(counts))
        points = [{"label": str(name), "count": int(count)} for name, count in counts.head(limit).items()]
        visualization = "bar"
        aggregation = "count"
        title = "Missing values by field"
        description = "Counts of missing values in the currently filtered dataset."
        dimension = None
        measure = None
    elif pattern == "numeric_distribution":
        measure = _validate_numeric_measure(measure, measure_names)
        values = pd.to_numeric(frame[measure], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        total = int(len(values))
        if total:
            bins = min(12, max(4, int(math.ceil(math.sqrt(total)))))
            counts, edges = np.histogram(values.to_numpy(dtype=float), bins=bins)
            points = [{"label": f"{edges[index]:.3g} to {edges[index + 1]:.3g}", "count": int(count)} for index, count in enumerate(counts)]
        total = len(points)
        visualization = "histogram"
        dimension = None
        aggregation = "count"
        title = f"Distribution of {measure}"
        description = f"Observed values in {measure}, grouped into equal-width numeric ranges."
    elif pattern == "numeric_relationship" or request.x_field or request.y_field:
        x_field = request.x_field or dimension
        y_field = request.y_field or measure
        x_field = _validate_numeric_measure(x_field, measure_names, "x field")
        y_field = _validate_numeric_measure(y_field, measure_names, "y field")
        if x_field == y_field:
            raise ValueError("Choose two different numeric fields for a relationship exploration.")
        paired = frame[[x_field, y_field]].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        total = int(len(paired))
        if total >= 2:
            relationship_correlation = _finite_float(paired[x_field].corr(paired[y_field]))
        if total < 5:
            limitations.append("Fewer than five paired observations are available; interpret this relationship cautiously.")
        if total > limit:
            indexes = np.linspace(0, total - 1, num=limit, dtype=int)
            paired = paired.iloc[indexes]
            limitations.append(f"Showing a deterministic sample of {limit} paired observations out of {total}.")
        points = [{"x": float(row[x_field]), "y": float(row[y_field])} for _, row in paired.iterrows()]
        visualization = "scatter"
        dimension, measure = x_field, y_field
        aggregation = "pairwise"
        title = f"Relationship between {x_field} and {y_field}"
        description = "Paired numeric observations; association does not establish causation."
    elif pattern == "time_trend" or request.date_field and (request.date_field not in dimension_names or not dimension):
        if not request.date_field or request.date_field not in date_names:
            raise ValueError("Select a supported date field for a time exploration.")
        if measure:
            measure = _validate_numeric_measure(measure, measure_names)
        if aggregation not in {"count", *_NUMERIC_AGGREGATIONS}:
            raise ValueError("Unsupported aggregation for a time exploration.")
        if measure is None:
            aggregation = "count"
        points, total, frequency = _trend_points(frame, request.date_field, measure, aggregation, limit)
        visualization = "line"
        dimension = request.date_field
        title = f"{aggregation.title()} over {request.date_field}"
        description = f"Time-bucketed {aggregation} across {request.date_field} using {frequency} intervals."
    elif dimension:
        if dimension not in dimension_names:
            raise ValueError(f"Unsupported exploration dimension: {dimension}")
        if measure:
            measure = _validate_numeric_measure(measure, measure_names)
            if aggregation not in {"count", *_NUMERIC_AGGREGATIONS}:
                raise ValueError("Unsupported numeric aggregation.")
        else:
            aggregation = "count"
        minimum_group_size = 3 if request.secondary_measure else 2
        points, total, excluded_groups = _grouped_points(frame, dimension, measure, request.secondary_measure, aggregation, limit, request.sort, minimum_group_size)
        visualization = "pie" if measure is None and len(points) <= 5 and total <= 5 else "bar"
        title = f"{aggregation.title()} of {measure or 'records'} by {dimension}"
        description = f"Values grouped by {dimension}, sorted by {'ascending' if request.sort == 'ascending' else 'descending'} result value."
    else:
        raise ValueError("Select a supported recommendation or exploration configuration.")

    showing_limited = total > len(points)
    if showing_limited and visualization == "line":
        limitations.append(f"Showing the latest {len(points)} of {total} chronological time buckets.")
    elif showing_limited and visualization == "scatter":
        pass
    elif showing_limited:
        limitations.append(f"Showing the top {len(points)} of {total} results for readability.")
    if len(frame) < 5:
        limitations.append("Fewer than five rows remain after filtering; interpret patterns cautiously.")
    if not points:
        limitations.append("No rows matched the selected fields and filters.")
    if excluded_groups:
        limitations.append(f"Excluded {excluded_groups} groups with fewer than {minimum_group_size} valid observations.")

    if not points:
        observation = "No data matched the selected filters."
        empty_message = "No data matched the selected filters."
        visualization = "empty"
    else:
        observation = _summary(title, description, points, total, limitations)["key_observation"]
        empty_message = None
    detail = _summary(title, description, points, total, limitations)
    if visualization == "scatter" and relationship_correlation is not None:
        detail["key_observation"] = f"The observed Pearson correlation is {relationship_correlation:.2f} across {total} paired observations; association does not establish causation."
        detail["correlation"] = relationship_correlation
    detail["limitations"] = limitations
    observation = detail.get("key_observation") or observation
    effective_filters = list(request.filters)
    if request.date_field and request.date_from:
        effective_filters.append(ExplorationFilter(field=request.date_field, operator="on_or_after", value=request.date_from))
    if request.date_field and request.date_to:
        effective_filters.append(ExplorationFilter(field=request.date_field, operator="on_or_before", value=request.date_to))
    return {
        "dataset_id": dataset.id,
        "exploration_type": pattern or ("time_trend" if visualization == "line" else "numeric_relationship" if visualization == "scatter" else "group_comparison" if measure else "categorical_distribution"),
        "visualization": visualization,
        "dimension": dimension,
        "measure": measure,
        "secondary_measure": request.secondary_measure,
        "aggregation": aggregation,
        "filters": effective_filters,
        "summary": f"{title}. {observation or ''}".strip(),
        "summary_detail": detail,
        "limitations": limitations,
        "empty_message": empty_message,
        "points": points,
        "capabilities": capabilities.model_dump(mode="json"),
        "total_count": total,
        "showing_limited": showing_limited,
        "chart_config": {
            "x_axis_title": dimension or measure or "Field",
            "y_axis_title": aggregation.title(),
            "series_name": measure or "Records",
            "series_names": [measure, request.secondary_measure] if request.secondary_measure else [measure or "Records"],
            "sort": request.sort or "descending",
            "limit": limit,
            "frequency": frequency,
            "date_from": request.date_from,
            "date_to": request.date_to,
        },
    }