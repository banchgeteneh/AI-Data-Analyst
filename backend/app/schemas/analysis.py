from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalysisDatasetInfo(BaseModel):
    id: int
    filename: str
    rows: int
    columns: int
    column_names: list[str]


class ColumnAnalysis(BaseModel):
    name: str
    data_type: str
    missing_count: int
    missing_percentage: float


class ColumnProfile(BaseModel):
    name: str
    detected_type: Literal["numeric", "categorical", "datetime", "text", "identifier", "boolean", "unknown"]
    pandas_dtype: str
    role: Literal["NUMERIC", "CATEGORICAL", "DATE", "TEXT", "IDENTIFIER", "BOOLEAN", "UNKNOWN"]
    unique_count: int
    unique_ratio: float
    missing_count: int
    missing_percentage: float
    sample_values: list[Any]


class AnalysisSummary(BaseModel):
    row_count: int
    column_count: int
    duplicate_rows: int
    total_missing_values: int


class NumericStatistics(BaseModel):
    count: int
    mean: float | None
    median: float | None
    standard_deviation: float | None
    minimum: float | None
    maximum: float | None


class NumericProfileStatistics(NumericStatistics):
    missing_count: int
    first_quartile: float | None
    third_quartile: float | None


class CategoricalFrequency(BaseModel):
    value: Any
    count: int
    percentage: float


class CategoricalProfileStatistics(BaseModel):
    unique_count: int
    missing_count: int
    top_values: list[CategoricalFrequency]


class NumericRelationships(BaseModel):
    correlations: dict[str, dict[str, float | None]]


class DatasetProfile(BaseModel):
    row_count: int
    column_count: int
    column_profiles: list[ColumnProfile]
    numeric_columns: list[str]
    categorical_columns: list[str]
    date_columns: list[str]
    text_columns: list[str]
    identifier_columns: list[str]
    boolean_columns: list[str]
    unknown_columns: list[str]
    numeric_analysis: dict[str, NumericProfileStatistics]
    categorical_analysis: dict[str, CategoricalProfileStatistics]
    relationships: NumericRelationships


class CategoricalStatistics(BaseModel):
    unique_count: int
    most_common_value: Any | None
    most_common_count: int


class DataQualitySummary(BaseModel):
    total_cells: int
    missing_cells: int
    duplicate_rows: int
    columns_with_missing_values: list[str]
    columns_with_all_values_missing: list[str]
    completeness_percentage: float | None


class RevenueByDatePoint(BaseModel):
    date: str
    revenue: float


class ProductDistributionItem(BaseModel):
    product: Any
    count: int


class CategoryDistributionItem(BaseModel):
    category: Any
    count: int


class RegionDistributionItem(BaseModel):
    region: Any
    count: int


class CategoricalDistributionCount(BaseModel):
    value: Any
    count: int


class CategoricalDistribution(BaseModel):
    column: str
    unique_count: int
    total_records: int
    counts: list[CategoricalDistributionCount]


class ChartData(BaseModel):
    revenue_by_date: list[RevenueByDatePoint]
    product_distribution: list[ProductDistributionItem]
    category_distribution: list[CategoryDistributionItem]
    region_distribution: list[RegionDistributionItem]
    categorical_distributions: list[CategoricalDistribution]


class DashboardOverview(BaseModel):
    dataset_name: str
    row_count: int
    column_count: int
    numeric_column_count: int
    categorical_column_count: int
    date_column_count: int
    text_column_count: int
    identifier_column_count: int
    missing_value_count: int
    duplicate_row_count: int
    completeness_percentage: float | None


class DashboardMetric(BaseModel):
    column: str
    label: str
    type: Literal["numeric"]
    count: int
    mean: float | None
    median: float | None
    min: float | None
    max: float | None
    sum: float | None
    recommended_statistics: list[str]


class DashboardHistogramBin(BaseModel):
    start: float | None
    end: float | None
    count: int
    percentage: float


class DashboardBoxPlot(BaseModel):
    minimum: float | None
    first_quartile: float | None
    median: float | None
    third_quartile: float | None
    maximum: float | None


class DashboardDistribution(BaseModel):
    column: str
    label: str
    type: Literal["categorical", "numeric"]
    total_records: int
    categories: list[CategoricalFrequency]
    histogram: list[DashboardHistogramBin]
    box_plot: DashboardBoxPlot | None


class DashboardRelationshipPair(BaseModel):
    column_a: str
    column_b: str
    correlation: float
    sample_size: int
    strength: Literal["weak", "moderate", "strong"]


class DashboardRelationships(BaseModel):
    matrix: dict[str, dict[str, float | None]]
    pairs: list[DashboardRelationshipPair]
    strongest: list[DashboardRelationshipPair]


class DashboardTrendPoint(BaseModel):
    date: str
    value: float | None


class DashboardTrend(BaseModel):
    date_column: str
    measure_column: str
    aggregation: Literal["sum", "mean"]
    period: str
    values: list[DashboardTrendPoint]


class DashboardComparisonGroup(BaseModel):
    value: Any
    count: int
    mean: float | None
    median: float | None


class DashboardComparison(BaseModel):
    dimension: str
    measure: str
    aggregation: Literal["mean"]
    groups: list[DashboardComparisonGroup]


class DashboardIncompleteColumn(BaseModel):
    column: str
    missing_count: int
    missing_percentage: float


class DashboardDataQuality(BaseModel):
    total_cells: int
    missing_cells: int
    duplicate_rows: int
    columns_with_missing_values: list[str]
    columns_with_all_values_missing: list[str]
    completeness_percentage: float | None
    incomplete_columns: list[DashboardIncompleteColumn]
    high_cardinality_columns: list[str]
    invalid_or_unclear_values: list[str]
    observations: list[str]


class DashboardVisualizationRecommendation(BaseModel):
    type: Literal["bar", "donut", "histogram", "scatter", "line", "heatmap"]
    title: str
    x_column: str | None
    y_column: str | None
    reason: str


class AutomaticInsight(BaseModel):
    type: Literal["quality", "relationship", "trend", "category", "comparison"]
    title: str
    summary: str
    impact: Literal["low", "medium", "high"]
    confidence: int
    sample_size: int | None = None
    recommended_action: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    exploration: dict[str, Any] | None = None


class DashboardInsightsContext(BaseModel):
    metrics: list[DashboardMetric]
    strongest_relationships: list[DashboardRelationshipPair]
    distributions: list[DashboardDistribution]
    trends: list[DashboardTrend]
    comparisons: list[DashboardComparison]
    data_quality: DashboardDataQuality
    automatic_insights: list[AutomaticInsight] = Field(default_factory=list)


class Dashboard(BaseModel):
    overview: DashboardOverview
    metrics: list[DashboardMetric]
    distributions: list[DashboardDistribution]
    relationships: DashboardRelationships
    trends: list[DashboardTrend]
    comparisons: list[DashboardComparison]
    data_quality: DashboardDataQuality
    recommended_visualizations: list[DashboardVisualizationRecommendation]
    insights_context: DashboardInsightsContext
    automatic_insights: list[AutomaticInsight] = Field(default_factory=list)


class DatasetAnalysisResponse(BaseModel):
    dataset: AnalysisDatasetInfo
    columns: list[ColumnAnalysis]
    summary: AnalysisSummary
    numeric_statistics: dict[str, NumericStatistics]
    categorical_statistics: dict[str, CategoricalStatistics]
    correlations: dict[str, dict[str, float | None]]
    data_quality: DataQualitySummary
    chart_data: ChartData
    dataset_profile: DatasetProfile
    dashboard: Dashboard
