import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.models.dataset import Dataset
from app.schemas.exploration import (
    DatasetExplorationCapabilities,
    DatasetExplorationRequest,
    ExplorationField,
    ExplorationFilter,
    ExplorationRecommendation,
    ExplorationPoint,
)
from app.services.dataset_analysis import _read_dataframe, analyze_dataset
from app.services.exploration_recommendations import generate_exploration_recommendations

VALID_AGGREGATIONS = {
    "count": {"count"},
    "sum": {"sum", "count"},
    "mean": {"mean", "count"},
    "median": {"median", "count"},
    "min": {"min", "count"},
    "max": {"max", "count"},
    "std": {"std", "count"},
}


def _titleize(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip() or value


def _field_lookup(column_profiles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(profile.get("name")): profile for profile in column_profiles if isinstance(profile, dict) and profile.get("name") is not None}


def _normalized_column_name(column_name: str) -> str:
    if not isinstance(column_name, str):
        return ""
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in column_name).strip("_")


def _is_high_cardinality(profile: dict[str, Any], row_count: int) -> bool:
    unique_count = int(profile.get("unique_count") or 0)
    unique_ratio = float(profile.get("unique_ratio") or 0.0)
    if row_count <= 0:
        return False
    if unique_count <= 1:
        return True
    if unique_ratio >= 0.9:
        return True
    return unique_count > max(25, min(80, int(math.sqrt(row_count) * 4)))


def _build_field(profile: dict[str, Any], row_count: int) -> ExplorationField:
    name = str(profile.get("name"))
    role = str(profile.get("role", "UNKNOWN")).lower()
    normalized_role = {
        "numeric": "numeric",
        "categorical": "categorical",
        "boolean": "boolean",
        "date": "date",
        "text": "text",
        "identifier": "identifier",
    }.get(role, "text")
    field = ExplorationField(
        name=name,
        label=_titleize(name),
        role=normalized_role,
        cardinality=int(profile.get("unique_count") or 0),
        supports_grouping=normalized_role in {"numeric", "categorical", "boolean", "date"},
        supports_filtering=normalized_role in {"numeric", "categorical", "boolean", "date"},
        supports_aggregation=normalized_role == "numeric",
    )
    if role == "NUMERIC":
        field.supports_aggregation = True
    if normalized_role == "date":
        field.supports_grouping = True
    if _is_high_cardinality(profile, row_count):
        field.supports_grouping = False
    if int(profile.get("unique_count") or 0) <= 1:
        field.supports_aggregation = False
    return field


def build_exploration_capabilities(analysis: dict[str, Any]) -> DatasetExplorationCapabilities:
    profile = analysis.get("dataset_profile") if isinstance(analysis.get("dataset_profile"), dict) else {}
    columns = profile.get("column_profiles", []) if isinstance(profile.get("column_profiles", []), list) else []
    row_count = int(profile.get("row_count") or analysis.get("summary", {}).get("row_count") or 0)
    dimensions: list[ExplorationField] = []
    measures: list[ExplorationField] = []
    time_fields: list[ExplorationField] = []
    filter_fields: list[ExplorationField] = []
    relationships: list[dict[str, Any]] = []

    for column_profile in columns:
        if not isinstance(column_profile, dict):
            continue
        role = str(column_profile.get("role", "UNKNOWN")).upper()
        field = _build_field(column_profile, row_count)

        if role == "NUMERIC":
            statistics = (analysis.get("numeric_statistics") or {}).get(field.name) or {}
            minimum = statistics.get("minimum")
            maximum = statistics.get("maximum")
            if field.cardinality > 1 and statistics.get("count", 0) >= 3 and minimum is not None and maximum is not None and float(minimum) != float(maximum):
                measures.append(field)
            filter_fields.append(field)
        elif role in {"CATEGORICAL", "BOOLEAN"}:
            filter_fields.append(field)
            if not _is_high_cardinality(column_profile, row_count):
                dimensions.append(field)
        elif role == "DATE":
            time_fields.append(field)
            dimensions.append(field)
            filter_fields.append(field)

    relationships = [
        {
            "x_field": pair["column_a"],
            "y_field": pair["column_b"],
            "correlation": pair["correlation"],
            "sample_size": pair["sample_size"],
            "strength": pair["strength"],
        }
        for pair in ((analysis.get("dashboard") or {}).get("relationships") or {}).get("strongest", [])[:6]
    ]
    recommended = [
        ExplorationRecommendation.model_validate(item)
        for item in generate_exploration_recommendations(analysis)
    ]

    return DatasetExplorationCapabilities(
        dimensions=dimensions,
        measures=measures,
        time_fields=time_fields,
        filter_fields=filter_fields,
        relationships=relationships,
        recommended_explorations=recommended,
    )


def _apply_filter(frame: pd.DataFrame, filter_item: ExplorationFilter) -> pd.DataFrame:
    field = filter_item.field
    if field not in frame.columns:
        raise ValueError(f"Unsupported filter field: {field}")
    series = frame[field]
    operator = filter_item.operator
    value = filter_item.value
    value_2 = filter_item.value_2

    if operator == "equals":
        return frame[series == value]
    if operator == "not_equals":
        return frame[series != value]
    if operator == "in":
        values = value if isinstance(value, list) else [value]
        return frame[series.isin(values)]
    if operator == "not_in":
        values = value if isinstance(value, list) else [value]
        return frame[~series.isin(values)]
    if operator == "gt":
        return frame[series > value]
    if operator == "gte":
        return frame[series >= value]
    if operator == "lt":
        return frame[series < value]
    if operator == "lte":
        return frame[series <= value]
    if operator == "before":
        return frame[pd.to_datetime(series, errors="coerce") < pd.to_datetime(value, errors="coerce")]
    if operator == "after":
        return frame[pd.to_datetime(series, errors="coerce") > pd.to_datetime(value, errors="coerce")]
    if operator == "between":
        if value is None or value_2 is None:
            raise ValueError("Date or numeric range filters require two values.")
        if pd.api.types.is_numeric_dtype(series):
            return frame[(series >= value) & (series <= value_2)]
        return frame[(pd.to_datetime(series, errors="coerce") >= pd.to_datetime(value, errors="coerce")) & (pd.to_datetime(series, errors="coerce") <= pd.to_datetime(value_2, errors="coerce"))]
    if operator == "is_true":
        return frame[series.astype(str).str.lower().isin({"true", "1", "yes", "y"}) | series.fillna(False).astype(bool)]
    if operator == "is_false":
        return frame[~series.astype(str).str.lower().isin({"true", "1", "yes", "y"}) & series.fillna(False).astype(bool)]
    raise ValueError(f"Unsupported filter operator: {operator}")


def _infer_date_frequency(frame: pd.DataFrame, date_field: str) -> str:
    dates = pd.to_datetime(frame[date_field], errors="coerce").dropna()
    if dates.empty:
        return "M"
    span = (dates.max() - dates.min()).total_seconds() / 86400 if len(dates) > 1 else 1
    if span <= 365:
        return "M"
    if span <= 365 * 5:
        return "Q"
    return "Y"


def _numeric_aggregate(series: pd.Series, aggregation: str) -> float | None:
    if aggregation == "count":
        return float(series.count())
    if aggregation == "sum":
        return float(series.sum())
    if aggregation == "mean":
        return float(series.mean())
    if aggregation == "median":
        return float(series.median())
    if aggregation == "min":
        return float(series.min())
    if aggregation == "max":
        return float(series.max())
    if aggregation == "std":
        sample = series.std()
        return float(sample) if pd.notna(sample) else None
    return None


def _build_points_from_grouped(frame: pd.DataFrame, dimension: str, measure: str | None, aggregation: str, limit: int) -> tuple[list[dict[str, Any]], str]:
    if measure is None:
        counts = frame[dimension].dropna().value_counts().head(limit)
        points = [{"label": str(label), "count": int(count)} for label, count in counts.items()]
        return points, "Dimension-to-count"

    if aggregation not in VALID_AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation: {aggregation}")
    grouped = frame.groupby(dimension, dropna=False)[measure]
    if aggregation == "count":
        values = grouped.count()
        points = [{"label": str(label), "count": int(value)} for label, value in values.items()]
    else:
        values = grouped.agg(lambda series: _numeric_aggregate(series, aggregation))
        points = [{"label": str(label), "value": float(value)} for label, value in values.items() if pd.notna(value)]
    return points[:limit], "Dimension-to-measure"


def _build_date_points(frame: pd.DataFrame, date_field: str, measure: str | None, aggregation: str, limit: int) -> tuple[list[dict[str, Any]], str]:
    date_series = pd.to_datetime(frame[date_field], errors="coerce").dropna()
    if date_series.empty:
        raise ValueError("No valid date values were found in the selected date field.")
    if measure is None:
        freq = _infer_date_frequency(frame, date_field)
        counts = frame.set_index(pd.to_datetime(frame[date_field], errors="coerce")).resample(freq).size().head(limit)
        points = [{"label": str(label), "count": int(value)} for label, value in counts.items()]
        return points, "Date-to-count"

    if aggregation not in VALID_AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation: {aggregation}")
    grouped = frame.set_index(pd.to_datetime(frame[date_field], errors="coerce")).groupby(pd.Grouper(freq=_infer_date_frequency(frame, date_field)))[measure]
    if aggregation == "count":
        values = grouped.count()
        points = [{"label": str(label), "count": int(value)} for label, value in values.items()]
    else:
        values = grouped.agg(lambda series: _numeric_aggregate(series, aggregation))
        points = [{"label": str(label), "value": float(value)} for label, value in values.items() if pd.notna(value)]
    return points[:limit], "Date-to-measure"


def _build_scatter_points(frame: pd.DataFrame, x_field: str, y_field: str, limit: int) -> list[dict[str, Any]]:
    cleaned = frame[[x_field, y_field]].dropna().copy()
    cleaned = cleaned[pd.to_numeric(cleaned[x_field], errors="coerce").notna()]
    cleaned = cleaned[pd.to_numeric(cleaned[y_field], errors="coerce").notna()]
    points = [{"x": float(row[x_field]), "y": float(row[y_field])} for _, row in cleaned.head(limit).iterrows()]
    return points


def explore_dataset(dataset: Dataset, request: dict[str, Any] | DatasetExplorationRequest) -> dict[str, Any]:
    if isinstance(request, DatasetExplorationRequest):
        payload = request.model_dump()
    else:
        payload = DatasetExplorationRequest.model_validate(request).model_dump()

    analysis = analyze_dataset(dataset)
    capabilities = build_exploration_capabilities(analysis)
    dataframe = _read_dataframe(dataset)
    filtered = dataframe.copy()

    for filter_item in payload.get("filters") or []:
        if isinstance(filter_item, dict):
            filter_item = ExplorationFilter.model_validate(filter_item)
        filtered = _apply_filter(filtered, filter_item)

    if payload.get("date_from") or payload.get("date_to"):
        if payload.get("date_field"):
            date_series = pd.to_datetime(filtered[payload["date_field"]], errors="coerce")
            if payload.get("date_from"):
                filtered = filtered[date_series >= pd.to_datetime(payload["date_from"], errors="coerce")]
            if payload.get("date_to"):
                filtered = filtered[date_series <= pd.to_datetime(payload["date_to"], errors="coerce")]

    if payload.get("dimension") and payload.get("measure"):
        dimension = payload["dimension"]
        measure = payload["measure"]
        aggregation = payload.get("aggregation") or "mean"
        if dimension not in dataframe.columns:
            raise ValueError(f"Unsupported exploration dimension: {dimension}")
        if measure not in dataframe.columns:
            raise ValueError(f"Unsupported exploration measure: {measure}")
        if aggregation not in {"count", "sum", "mean", "median", "min", "max", "std"}:
            raise ValueError(f"Unsupported aggregation: {aggregation}")
        points, exploration_type = _build_points_from_grouped(filtered, dimension, measure, aggregation, int(payload.get("limit") or 25))
        visualization = "line" if dimension in {field.name for field in capabilities.time_fields} else "bar"
        summary = f"Showing {len(points)} groups for {aggregation} of {measure} by {dimension}."
        return {
            "dataset_id": dataset.id,
            "exploration_type": exploration_type,
            "visualization": visualization,
            "dimension": dimension,
            "measure": measure,
            "aggregation": aggregation,
            "filters": payload.get("filters") or [],
            "summary": summary,
            "empty_message": None if points else "No data is available for this combination after filtering.",
            "points": [{"label": point.get("label"), "value": point.get("value"), "count": point.get("count")} for point in points],
            "capabilities": capabilities.model_dump(mode="json"),
        }

    if payload.get("dimension") and not payload.get("measure"):
        dimension = payload["dimension"]
        if dimension not in dataframe.columns:
            raise ValueError(f"Unsupported exploration dimension: {dimension}")
        points, exploration_type = _build_points_from_grouped(filtered, dimension, None, "count", int(payload.get("limit") or 25))
        summary = f"Showing the distribution of {dimension} across {len(points)} categories."
        return {
            "dataset_id": dataset.id,
            "exploration_type": exploration_type,
            "visualization": "bar",
            "dimension": dimension,
            "measure": None,
            "aggregation": "count",
            "filters": payload.get("filters") or [],
            "summary": summary,
            "empty_message": None if points else "No data is available for this dimension after filtering.",
            "points": [{"label": point.get("label"), "count": point.get("count")} for point in points],
            "capabilities": capabilities.model_dump(mode="json"),
        }

    if payload.get("date_field") and payload.get("measure"):
        date_field = payload["date_field"]
        measure = payload["measure"]
        aggregation = payload.get("aggregation") or "sum"
        if date_field not in dataframe.columns:
            raise ValueError(f"Unsupported date field: {date_field}")
        if measure not in dataframe.columns:
            raise ValueError(f"Unsupported exploration measure: {measure}")
        points, exploration_type = _build_date_points(filtered, date_field, measure, aggregation, int(payload.get("limit") or 25))
        summary = f"Showing {aggregation} of {measure} over time for {date_field}."
        return {
            "dataset_id": dataset.id,
            "exploration_type": exploration_type,
            "visualization": "line",
            "dimension": date_field,
            "measure": measure,
            "aggregation": aggregation,
            "filters": payload.get("filters") or [],
            "summary": summary,
            "empty_message": None if points else "No date values are available for this trend analysis.",
            "points": [{"label": point.get("label"), "value": point.get("value"), "count": point.get("count")} for point in points],
            "capabilities": capabilities.model_dump(mode="json"),
        }

    if payload.get("date_field") and not payload.get("measure"):
        date_field = payload["date_field"]
        if date_field not in dataframe.columns:
            raise ValueError(f"Unsupported date field: {date_field}")
        points, exploration_type = _build_date_points(filtered, date_field, None, "count", int(payload.get("limit") or 25))
        return {
            "dataset_id": dataset.id,
            "exploration_type": exploration_type,
            "visualization": "line",
            "dimension": date_field,
            "measure": None,
            "aggregation": "count",
            "filters": payload.get("filters") or [],
            "summary": f"Showing observation counts over time for {date_field}.",
            "empty_message": None if points else "No valid observations were found in the selected date field.",
            "points": [{"label": point.get("label"), "count": point.get("count")} for point in points],
            "capabilities": capabilities.model_dump(mode="json"),
        }

    if payload.get("x_field") and payload.get("y_field"):
        x_field = payload["x_field"]
        y_field = payload["y_field"]
        if x_field not in dataframe.columns or y_field not in dataframe.columns:
            raise ValueError("The selected relationship fields are not available in this dataset.")
        points = _build_scatter_points(filtered, x_field, y_field, int(payload.get("limit") or 25))
        return {
            "dataset_id": dataset.id,
            "exploration_type": "numeric_numeric",
            "visualization": "scatter",
            "dimension": x_field,
            "measure": y_field,
            "aggregation": "pairwise",
            "filters": payload.get("filters") or [],
            "summary": f"Showing {len(points)} paired values for {x_field} and {y_field}.",
            "empty_message": None if points else "No valid paired values were found for this relationship.",
            "points": [{"x": point.get("x"), "y": point.get("y")} for point in points],
            "capabilities": capabilities.model_dump(mode="json"),
        }

    default_dimension = (capabilities.dimensions[0].name if capabilities.dimensions else (capabilities.time_fields[0].name if capabilities.time_fields else None))
    default_measure = capabilities.measures[0].name if capabilities.measures else None
    if default_dimension is None and default_measure is None:
        raise ValueError("This dataset does not contain a supported exploration combination.")
    if default_measure is None:
        result = {
            "dataset_id": dataset.id,
            "exploration_type": "dimension_count",
            "visualization": "bar",
            "dimension": default_dimension,
            "measure": None,
            "aggregation": "count",
            "filters": [],
            "summary": f"Showing the distribution of {default_dimension}.",
            "empty_message": None,
            "points": [],
            "capabilities": capabilities.model_dump(mode="json"),
        }
        return result

    result = {
        "dataset_id": dataset.id,
        "exploration_type": "dimension_measure",
        "visualization": "bar",
        "dimension": default_dimension,
        "measure": default_measure,
        "aggregation": "mean",
        "filters": [],
        "summary": f"Showing the mean of {default_measure} by {default_dimension}.",
        "empty_message": None,
        "points": [],
        "capabilities": capabilities.model_dump(mode="json"),
    }
    if default_dimension in {field.name for field in capabilities.time_fields}:
        result["visualization"] = "line"
    return result
