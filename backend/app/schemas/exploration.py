from typing import Any, Literal

from pydantic import BaseModel, Field


class ExplorationFilter(BaseModel):
    field: str = Field(..., min_length=1, max_length=200)
    operator: Literal[
        "equals",
        "not_equals",
        "in",
        "not_in",
        "gt",
        "gte",
        "lt",
        "lte",
        "between",
        "before",
        "after",
        "on_or_before",
        "on_or_after",
        "is_true",
        "is_false",
    ]
    value: Any | None = None
    value_2: Any | None = None


class ExplorationField(BaseModel):
    name: str
    label: str
    role: Literal["numeric", "categorical", "boolean", "date", "text", "identifier"]
    cardinality: int | None = None
    supports_grouping: bool = True
    supports_filtering: bool = True
    supports_aggregation: bool = False


class ExplorationRecommendation(BaseModel):
    id: str = ""
    title: str
    description: str = ""
    type: str = ""
    reason: str
    dimension: str | None = None
    measure: str | None = None
    secondary_measure: str | None = None
    date_field: str | None = None
    aggregation: str | None = None
    visualization: str | None = None
    relevance: int = Field(default=50, ge=0, le=100)
    confidence: int = Field(default=50, ge=0, le=100)
    required_capabilities: list[str] = Field(default_factory=list)


class DatasetExplorationCapabilities(BaseModel):
    dimensions: list[ExplorationField]
    measures: list[ExplorationField]
    time_fields: list[ExplorationField]
    filter_fields: list[ExplorationField]
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    recommended_explorations: list[ExplorationRecommendation] = Field(default_factory=list)


class DatasetExplorationRequest(BaseModel):
    exploration_type: Literal[
        "categorical_distribution",
        "group_comparison",
        "multi_measure_comparison",
        "time_trend",
        "numeric_relationship",
        "numeric_distribution",
        "missingness_review",
        "duplicate_review",
    ] | None = None
    dimension: str | None = Field(default=None, max_length=200)
    measure: str | None = Field(default=None, max_length=200)
    secondary_measure: str | None = Field(default=None, max_length=200)
    aggregation: Literal["count", "sum", "mean", "median", "min", "max", "std"] | None = None
    x_field: str | None = Field(default=None, max_length=200)
    y_field: str | None = Field(default=None, max_length=200)
    date_field: str | None = Field(default=None, max_length=200)
    date_from: str | None = Field(default=None, max_length=100)
    date_to: str | None = Field(default=None, max_length=100)
    filters: list[ExplorationFilter] = Field(default_factory=list)
    sort: Literal["ascending", "descending"] | None = None
    limit: int = Field(default=25, ge=1, le=200)
    visualization: Literal["bar", "line", "scatter", "pie", "histogram", "empty"] | None = None


class ExplorationPoint(BaseModel):
    label: str | None = None
    value: float | None = None
    count: int | None = None
    x: Any | None = None
    y: Any | None = None
    series: dict[str, float | None] | None = None


class DatasetExplorationResponse(BaseModel):
    dataset_id: int
    exploration_type: str
    visualization: str
    dimension: str | None = None
    measure: str | None = None
    secondary_measure: str | None = None
    aggregation: str | None = None
    filters: list[ExplorationFilter] = Field(default_factory=list)
    summary: str
    summary_detail: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    empty_message: str | None = None
    points: list[ExplorationPoint] = Field(default_factory=list)
    capabilities: DatasetExplorationCapabilities
    total_count: int | None = None
    showing_limited: bool = False
    chart_config: dict[str, Any] = Field(default_factory=dict)
