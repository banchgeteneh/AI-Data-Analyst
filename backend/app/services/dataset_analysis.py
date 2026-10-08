import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.models.dataset import Dataset
from app.services.dashboard_data import build_dashboard_data
from app.services.extractors import MalformedFileError, StructuredDataNotFoundError, UnsupportedFileTypeError, extract_dataset_file


class DatasetAnalysisError(Exception):
    """Raised when a registered dataset cannot be analyzed safely."""


class DatasetFileNotFoundError(DatasetAnalysisError):
    """Raised when a registered dataset file no longer exists."""


_MAX_CATEGORICAL_DISTRIBUTIONS = 8
_MAX_PROFILE_SAMPLES = 5
_MAX_PROFILE_CATEGORY_VALUES = 25
_NUMERIC_COERCION_THRESHOLD = 0.8


def _read_dataframe(dataset: Dataset) -> pd.DataFrame:
    path = Path(dataset.file_path).resolve()
    if not path.is_file():
        raise DatasetFileNotFoundError("Dataset file is not available")

    try:
        return extract_dataset_file(path, dataset.file_type.lower())
    except FileNotFoundError as error:
        raise DatasetFileNotFoundError("Dataset file is not available") from error
    except StructuredDataNotFoundError as error:
        raise DatasetAnalysisError("The dataset file type is not supported") from error
    except (UnsupportedFileTypeError, MalformedFileError, ValueError) as error:
        raise DatasetAnalysisError("The dataset file could not be read") from error
    except Exception as error:
        raise DatasetAnalysisError("The dataset file could not be read") from error


def _finite_number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _data_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "categorical"


def _distribution(dataframe: pd.DataFrame, column_name: str, value_key: str) -> list[dict[str, Any]]:
    if column_name not in dataframe.columns:
        return []

    counts = dataframe[column_name].dropna().value_counts()
    return [
        {value_key: _safe_value(value), "count": int(count)}
        for value, count in counts.items()
    ]


def _normalized_column_name(column_name: str) -> str:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", column_name)
    return re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").casefold()


def _is_identifier_name(column_name: str) -> bool:
    normalized = _normalized_column_name(column_name)
    return normalized in {"id", "uuid", "guid", "identifier", "key"} or normalized.endswith(
        ("_id", "_uuid", "_guid", "_identifier", "_key")
    )


def _is_date_like(values: pd.Series) -> bool:
    sample = values.dropna().head(200).astype(str).str.strip()
    if sample.empty or sample.str.fullmatch(r"\d{4}").all():
        return False
    parsed = pd.to_datetime(sample, errors="coerce", utc=True, format="mixed")
    return bool(parsed.notna().mean() >= 0.8)


def _numeric_candidate(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.replace([np.inf, -np.inf], np.nan)


def _column_role(series: pd.Series, column_name: str, row_count: int) -> tuple[str, pd.Series | None]:
    values = series.dropna()
    if values.empty or row_count == 0:
        return "UNKNOWN", None
    if _is_identifier_name(column_name):
        return "IDENTIFIER", None
    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN", None
    if pd.api.types.is_datetime64_any_dtype(series):
        return "DATE", None

    normalized_name = _normalized_column_name(column_name)
    max_unique_values = min(30, max(2, int(math.sqrt(row_count) * 2)))
    unique_count = int(values.nunique())
    unique_ratio = unique_count / row_count
    year_column = normalized_name in {"year", "fiscal_year", "school_year", "academic_year"}
    if year_column and unique_count <= max_unique_values:
        return "CATEGORICAL", None

    if pd.api.types.is_numeric_dtype(series):
        return "NUMERIC", _numeric_candidate(series)

    text_values = values.astype(str).str.strip()
    median_length = float(text_values.str.len().median())
    median_word_count = float(text_values.str.split().str.len().median())
    if median_length > 120 or median_word_count > 12:
        return "TEXT", None

    numeric = _numeric_candidate(series)
    if numeric.notna().sum() / len(values) >= _NUMERIC_COERCION_THRESHOLD:
        return "NUMERIC", numeric
    if _is_date_like(values):
        return "DATE", None

    normalized_values = {value.casefold() for value in text_values.unique()}
    boolean_values = {"true", "false", "yes", "no", "y", "n"}
    if normalized_values and normalized_values <= boolean_values:
        return "BOOLEAN", None

    # Require both a high ratio and several distinct values so tiny categorical samples remain usable.
    if unique_ratio >= 0.8 and unique_count >= 5:
        return "IDENTIFIER", None
    if unique_count > max_unique_values:
        return "TEXT", None
    return "CATEGORICAL", None


def _numeric_profile(values: pd.Series, row_count: int) -> dict[str, Any]:
    valid = values.dropna()
    result = {
        "count": int(valid.count()),
        "missing_count": int(row_count - valid.count()),
        "mean": _finite_number(valid.mean()) if not valid.empty else None,
        "median": _finite_number(valid.median()) if not valid.empty else None,
        "standard_deviation": _finite_number(valid.std()) if not valid.empty else None,
        "minimum": _finite_number(valid.min()) if not valid.empty else None,
        "maximum": _finite_number(valid.max()) if not valid.empty else None,
        "first_quartile": _finite_number(valid.quantile(0.25)) if not valid.empty else None,
        "third_quartile": _finite_number(valid.quantile(0.75)) if not valid.empty else None,
    }
    return result


def _categorical_profile(values: pd.Series, row_count: int) -> dict[str, Any]:
    non_missing = values.dropna()
    counts = non_missing.value_counts().head(_MAX_PROFILE_CATEGORY_VALUES)
    value_count = int(non_missing.count())
    return {
        "unique_count": int(non_missing.nunique()),
        "missing_count": int(row_count - value_count),
        "top_values": [
            {
                "value": _safe_value(value),
                "count": int(count),
                "percentage": round(int(count) / value_count * 100, 6) if value_count else 0.0,
            }
            for value, count in counts.items()
        ],
    }


def _dataset_profile(dataframe: pd.DataFrame, column_names: list[str]) -> dict[str, Any]:
    row_count, column_count = dataframe.shape
    column_profiles: list[dict[str, Any]] = []
    numeric_columns: list[str] = []
    categorical_columns: list[str] = []
    date_columns: list[str] = []
    text_columns: list[str] = []
    identifier_columns: list[str] = []
    boolean_columns: list[str] = []
    unknown_columns: list[str] = []
    numeric_analysis: dict[str, dict[str, Any]] = {}
    categorical_analysis: dict[str, dict[str, Any]] = {}
    numeric_values: dict[str, pd.Series] = {}

    for column_name in column_names:
        series = dataframe[column_name]
        role, numeric = _column_role(series, column_name, row_count)
        missing_count = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))
        unique_ratio = unique_count / row_count if row_count else 0.0
        column_profiles.append(
            {
                "name": column_name,
                "detected_type": {
                    "NUMERIC": "numeric",
                    "CATEGORICAL": "categorical",
                    "DATE": "datetime",
                    "TEXT": "text",
                    "IDENTIFIER": "identifier",
                    "BOOLEAN": "boolean",
                    "UNKNOWN": "unknown",
                }[role],
                "pandas_dtype": str(series.dtype),
                "role": role,
                "unique_count": unique_count,
                "unique_ratio": round(unique_ratio, 6),
                "missing_count": missing_count,
                "missing_percentage": round(missing_count / row_count * 100, 6) if row_count else 0.0,
                "sample_values": [_safe_value(value) for value in series.dropna().head(_MAX_PROFILE_SAMPLES)],
            }
        )

        if role == "NUMERIC" and numeric is not None:
            numeric_columns.append(column_name)
            numeric_values[column_name] = numeric
            numeric_analysis[column_name] = _numeric_profile(numeric, row_count)
        elif role in {"CATEGORICAL", "BOOLEAN"}:
            categorical_columns.append(column_name)
            categorical_analysis[column_name] = _categorical_profile(series, row_count)
            if role == "BOOLEAN":
                boolean_columns.append(column_name)
        elif role == "DATE":
            date_columns.append(column_name)
        elif role == "TEXT":
            text_columns.append(column_name)
        elif role == "IDENTIFIER":
            identifier_columns.append(column_name)
        else:
            unknown_columns.append(column_name)

    relationships: dict[str, dict[str, float | None]] = {}
    if len(numeric_columns) >= 2:
        correlation_frame = pd.DataFrame(numeric_values).corr(method="pearson")
        relationships = {
            column_name: {
                other_name: _finite_number(correlation_frame.loc[column_name, other_name])
                for other_name in numeric_columns
            }
            for column_name in numeric_columns
        }

    return {
        "row_count": int(row_count),
        "column_count": int(column_count),
        "column_profiles": column_profiles,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "date_columns": date_columns,
        "text_columns": text_columns,
        "identifier_columns": identifier_columns,
        "boolean_columns": boolean_columns,
        "unknown_columns": unknown_columns,
        "numeric_analysis": numeric_analysis,
        "categorical_analysis": categorical_analysis,
        "relationships": {"correlations": relationships},
    }


def _categorical_distributions(dataframe: pd.DataFrame, column_names: list[str]) -> list[dict[str, Any]]:
    row_count = len(dataframe)
    if row_count < 2:
        return []

    # The square-root cap and 80% uniqueness limit suppress ID/name-like fields, including small samples.
    max_unique_values = min(30, max(2, int(math.sqrt(row_count) * 2)))
    distributions: list[dict[str, Any]] = []
    for column_name in column_names:
        series = dataframe[column_name]
        role, _ = _column_role(series, column_name, row_count)
        if role not in {"CATEGORICAL", "BOOLEAN"}:
            continue

        values = series.dropna()
        unique_count = int(values.nunique())
        if unique_count < 2 or unique_count > max_unique_values or unique_count / row_count >= 0.8:
            continue

        counts = values.value_counts().head(max_unique_values)
        distributions.append(
            {
                "column": column_name,
                "unique_count": unique_count,
                "total_records": row_count,
                "counts": [
                    {"value": _safe_value(value), "count": int(count)}
                    for value, count in counts.items()
                ],
            }
        )
        if len(distributions) == _MAX_CATEGORICAL_DISTRIBUTIONS:
            break

    return distributions


def _revenue_by_date(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    if "Date" not in dataframe.columns or "Revenue" not in dataframe.columns:
        return []

    dates = pd.to_datetime(dataframe["Date"], errors="coerce", utc=True)
    revenues = pd.to_numeric(dataframe["Revenue"], errors="coerce").replace([np.inf, -np.inf], np.nan)
    dated_revenue = pd.DataFrame(
        {"date": dates.dt.strftime("%Y-%m-%d"), "revenue": revenues}
    ).dropna(subset=["date", "revenue"])
    daily_revenue = dated_revenue.groupby("date", as_index=False, sort=True)["revenue"].sum()

    result: list[dict[str, Any]] = []
    for date, revenue in daily_revenue.itertuples(index=False, name=None):
        finite_revenue = _finite_number(revenue)
        if finite_revenue is not None:
            result.append({"date": date, "revenue": finite_revenue})
    return result


def analyze_dataset(dataset: Dataset) -> dict[str, Any]:
    dataframe = _read_dataframe(dataset)
    row_count, column_count = dataframe.shape
    column_names = [str(name) for name in dataframe.columns]
    dataset_profile = _dataset_profile(dataframe, column_names)

    column_results: list[dict[str, Any]] = []
    numeric_statistics: dict[str, dict[str, Any]] = {}
    categorical_statistics: dict[str, dict[str, Any]] = {}
    numeric_columns: list[str] = []
    categorical_columns: list[str] = []
    columns_with_missing: list[str] = []
    columns_with_all_missing: list[str] = []

    for column_name in column_names:
        series = dataframe[column_name]
        missing_count = int(series.isna().sum())
        missing_percentage = (missing_count / row_count * 100) if row_count else 0.0
        kind = _data_type(series)
        column_results.append(
            {
                "name": column_name,
                "data_type": kind,
                "missing_count": missing_count,
                "missing_percentage": round(missing_percentage, 6),
            }
        )
        if missing_count:
            columns_with_missing.append(column_name)
        if row_count and missing_count == row_count:
            columns_with_all_missing.append(column_name)

        if kind == "numeric":
            numeric_columns.append(column_name)
            finite_series = series.replace([np.inf, -np.inf], np.nan).dropna()
            numeric_statistics[column_name] = {
                "count": int(finite_series.count()),
                "mean": _finite_number(finite_series.mean()),
                "median": _finite_number(finite_series.median()),
                "standard_deviation": _finite_number(finite_series.std()),
                "minimum": _finite_number(finite_series.min()),
                "maximum": _finite_number(finite_series.max()),
            }
        elif kind == "categorical" or kind == "boolean":
            categorical_columns.append(column_name)
            non_missing = series.dropna()
            modes = non_missing.mode()
            most_common = modes.iloc[0] if not modes.empty else None
            most_common_count = int((non_missing == most_common).sum()) if most_common is not None else 0
            categorical_statistics[column_name] = {
                "unique_count": int(non_missing.nunique()),
                "most_common_value": _safe_value(most_common),
                "most_common_count": most_common_count,
            }

    correlations: dict[str, dict[str, float | None]] = {}
    if len(numeric_columns) >= 2:
        numeric_frame = dataframe[numeric_columns].replace([np.inf, -np.inf], np.nan)
        correlation_frame = numeric_frame.corr(method="pearson")
        for column_name in numeric_columns:
            correlations[column_name] = {
                other_name: _finite_number(correlation_frame.loc[column_name, other_name])
                for other_name in numeric_columns
            }

    duplicate_rows = int(dataframe.duplicated().sum())
    total_missing_values = int(dataframe.isna().sum().sum())
    data_quality = {
        "total_cells": int(row_count * column_count),
        "missing_cells": total_missing_values,
        "duplicate_rows": duplicate_rows,
        "columns_with_missing_values": columns_with_missing,
        "columns_with_all_values_missing": columns_with_all_missing,
        "completeness_percentage": round(
            (row_count * column_count - total_missing_values) / (row_count * column_count) * 100,
            6,
        ) if row_count and column_count else None,
    }

    result = {
        "dataset": {
            "id": dataset.id,
            "filename": dataset.original_filename,
            "rows": int(row_count),
            "columns": int(column_count),
            "column_names": column_names,
        },
        "columns": column_results,
        "summary": {
            "row_count": int(row_count),
            "column_count": int(column_count),
            "duplicate_rows": duplicate_rows,
            "total_missing_values": total_missing_values,
        },
        "numeric_statistics": numeric_statistics,
        "categorical_statistics": categorical_statistics,
        "correlations": correlations,
        "data_quality": data_quality,
        "dataset_profile": dataset_profile,
        "chart_data": {
            "revenue_by_date": _revenue_by_date(dataframe),
            "product_distribution": _distribution(dataframe, "Product", "product"),
            "category_distribution": _distribution(dataframe, "Category", "category"),
            "region_distribution": _distribution(dataframe, "Region", "region"),
            "categorical_distributions": _categorical_distributions(dataframe, column_names),
        },
    }
    result["dashboard"] = build_dashboard_data(
        dataframe,
        dataset_profile,
        dataset.original_filename,
        data_quality,
    )
    return result
