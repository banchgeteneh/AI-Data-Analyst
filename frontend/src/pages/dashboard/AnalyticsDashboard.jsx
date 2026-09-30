import { useEffect, useState } from "react";
import DashboardVisualization, { canRenderRecommendation, ExplorationVisualization } from "./DashboardCharts";
import { useTheme } from "../../context/ThemeContext";
import { exploreDataset, getDatasetExplorationCapabilities } from "../../services/api";
import "./dashboard.css";

const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

function hasNumber(value) {
  return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
}

function formatNumber(value) {
  return hasNumber(value) ? numberFormat.format(Number(value)) : "Not available";
}

function formatPercent(value) {
  return hasNumber(value) ? `${numberFormat.format(Number(value))}%` : "Not available";
}

function titleCase(value) {
  return String(value || "").replace(/[_-]+/g, " ").replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function hasRelationshipMatrix(matrix = {}) {
  return Object.entries(matrix).some(([rowName, row]) =>
    Object.entries(row || {}).some(([columnName, value]) => rowName !== columnName && hasNumber(value))
  );
}

function DashboardSection({ id, eyebrow, title, description, children, className = "" }) {
  return (
    <section id={id} className={`dashboard-section ${className}`}>
      <header className="dashboard-section-heading">
        <div>
          {eyebrow && <p className="dashboard-eyebrow">{eyebrow}</p>}
          <h3>{title}</h3>
          {description && <p>{description}</p>}
        </div>
      </header>
      {children}
    </section>
  );
}

function DashboardMetric({ metric }) {
  const totalIsRecommended = metric.recommended_statistics?.includes("total") && hasNumber(metric.sum);
  const statistic = totalIsRecommended ? "sum" : ["mean", "median", "max", "min"].find((key) => hasNumber(metric[key]));
  if (!statistic) return null;

  const label = statistic === "sum" ? `Total ${metric.label}` : statistic === "mean" ? `Average ${metric.label}` : `${titleCase(statistic)} ${metric.label}`;
  const detail = statistic === "sum" && hasNumber(metric.mean)
    ? `Average ${formatNumber(metric.mean)}`
    : `${formatNumber(metric.count)} values`;

  return (
    <article className="dashboard-metric" aria-label={`${label}: ${formatNumber(metric[statistic])}`}>
      <span className="dashboard-metric-label">{label}</span>
      <strong>{formatNumber(metric[statistic])}</strong>
      <span className="dashboard-metric-detail">{detail} · {metric.column}</span>
    </article>
  );
}

function OverviewStat({ label, value, detail }) {
  return (
    <div className="dashboard-overview-stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}

function VisualizationCard({ recommendation, dashboard, theme }) {
  if (!canRenderRecommendation(recommendation, dashboard)) return null;
  const subtitle = recommendation.type === "bar" && recommendation.y_column
    ? `Average ${titleCase(recommendation.y_column)} across ${titleCase(recommendation.x_column)} groups`
    : recommendation.reason;
  return (
    <article className="dashboard-visual-card">
      <header><h4>{recommendation.title}</h4><p>{subtitle}</p></header>
      <DashboardVisualization recommendation={recommendation} dashboard={dashboard} theme={theme} />
    </article>
  );
}

function RelationshipList({ relationships }) {
  const pairs = relationships?.strongest || [];
  if (!pairs.length) return <p className="dashboard-empty">Not enough numeric data to calculate relationships.</p>;
  return (
    <ul className="relationship-list">
      {pairs.slice(0, 5).map((pair) => {
        const direction = Number(pair.correlation) < 0 ? "negative" : "positive";
        return (
          <li key={`${pair.column_a}-${pair.column_b}`}>
            <span className={`relationship-mark relationship-${direction}`} aria-hidden="true">{direction === "positive" ? "+" : "−"}</span>
            <span className="relationship-copy"><strong>{titleCase(pair.column_a)} <span aria-hidden="true">↔</span> {titleCase(pair.column_b)}</strong><small>{titleCase(pair.strength || "")} {direction} relationship · correlation does not imply causation</small></span>
            <strong className="relationship-value">{Number(pair.correlation).toFixed(2)}</strong>
          </li>
        );
      })}
    </ul>
  );
}

function buildFindings(dashboard) {
  const findings = [];
  const strongest = dashboard.insights_context?.strongest_relationships?.[0] || dashboard.relationships?.strongest?.[0];
  if (strongest) {
    const direction = Number(strongest.correlation) < 0 ? "negative" : "positive";
    findings.push(`${titleCase(strongest.column_a)} and ${titleCase(strongest.column_b)} have a ${strongest.strength} ${direction} relationship in this dataset.`);
  }

  const comparison = dashboard.insights_context?.comparisons?.[0] || dashboard.comparisons?.[0];
  if (comparison?.groups?.length > 1) {
    const ranked = comparison.groups.filter((group) => hasNumber(group.mean)).sort((left, right) => Number(right.mean) - Number(left.mean));
    if (ranked.length > 1 && Number(ranked[0].mean) !== Number(ranked[ranked.length - 1].mean)) {
      findings.push(`${String(ranked[0].value)} has the highest average ${titleCase(comparison.measure)} among the ${titleCase(comparison.dimension)} groups shown.`);
    }
  }

  const trend = dashboard.insights_context?.trends?.[0] || dashboard.trends?.[0];
  if (trend?.values?.length > 1) {
    const start = trend.values[0];
    const end = trend.values[trend.values.length - 1];
    if (hasNumber(start.value) && hasNumber(end.value) && Number(start.value) !== Number(end.value)) {
      findings.push(`${titleCase(trend.measure_column)} ${Number(end.value) > Number(start.value) ? "increased" : "decreased"} from ${start.date} to ${end.date}.`);
    }
  }
  return findings.slice(0, 3);
}

function AutomaticInsights({ insights = [], onExplore }) {
  if (!insights.length) return null;

  return (
    <DashboardSection eyebrow="AUTOMATIC INSIGHTS" title="Prioritized findings" description="These are the strongest signals detected from the dataset profile and metrics.">
      <ul className="dashboard-findings-list">
        {insights.map((insight, index) => (
          <li key={`${insight.type}-${index}`}>
            <strong>{insight.title}</strong>
            <span>{insight.summary}</span>
            <small>{insight.impact} priority · {insight.confidence}% confidence{insight.sample_size ? ` · sample size ${insight.sample_size}` : ""}</small>
            {insight.recommended_action && <em>{insight.recommended_action}</em>}
            {insight.exploration?.available && <button type="button" className="dashboard-insight-explore" onClick={() => onExplore?.(insight.exploration)}>Explore this finding</button>}
          </li>
        ))}
      </ul>
    </DashboardSection>
  );
}

function DataQuality({ quality, overview }) {
  const completeness = overview.completeness_percentage;
  const qualityLabel = hasNumber(completeness)
    ? Number(completeness) >= 95 ? "High completeness" : Number(completeness) >= 80 ? "Some values need attention" : "Review data completeness"
    : "Quality summary";
  const incompleteColumns = quality.incomplete_columns || [];
  const fieldsToReview = [...new Set([
    ...incompleteColumns.map((column) => column.column),
    ...(quality.high_cardinality_columns || []),
  ])];
  const fields = fieldsToReview.slice(0, 8);

  return (
    <DashboardSection eyebrow="RELIABILITY" title="Data quality" description="A quick view of completeness and fields that may need a closer look." className="dashboard-quality-section">
      <div className="dashboard-quality-summary">
        <span className="quality-status-mark" aria-hidden="true">{hasNumber(completeness) && Number(completeness) >= 95 ? "✓" : "!"}</span>
        <div><strong>{qualityLabel}</strong><span>{formatPercent(completeness)} of cells are complete</span></div>
      </div>
      <div className="dashboard-quality-stats">
        <div><strong>{formatNumber(overview.missing_value_count)}</strong><span>Missing values</span></div>
        <div><strong>{formatNumber(overview.duplicate_row_count)}</strong><span>Duplicate records</span></div>
        <div><strong>{formatNumber(fieldsToReview.length)}</strong><span>Fields to review</span></div>
      </div>
      {fields.length > 0 && <div className="dashboard-quality-fields"><h4>Fields to review</h4><ul>{fields.map((field) => <li key={field}>{field}</li>)}</ul></div>}
      {quality.invalid_or_unclear_values?.length > 0 && <div className="dashboard-quality-fields"><h4>Other checks</h4><ul>{quality.invalid_or_unclear_values.map((item) => <li key={item}>{item}</li>)}</ul></div>}
    </DashboardSection>
  );
}

function recommendationConfig(recommendation) {
  return {
    exploration_type: recommendation.type,
    dimension: recommendation.dimension || "",
    measure: recommendation.measure || "",
    secondary_measure: recommendation.secondary_measure || "",
    date_field: recommendation.date_field || (recommendation.type === "time_trend" ? recommendation.dimension : ""),
    x_field: recommendation.type === "numeric_relationship" ? recommendation.dimension || "" : "",
    y_field: recommendation.type === "numeric_relationship" ? recommendation.measure || "" : "",
    aggregation: recommendation.aggregation || "mean",
  };
}

function DataExploration({ dataset, onAskAI, initialRequest }) {
  const { theme } = useTheme();
  const [capabilities, setCapabilities] = useState(null);
  const [result, setResult] = useState(null);
  const [capabilityLoading, setCapabilityLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [configuration, setConfiguration] = useState(null);
  const [selectedRecommendation, setSelectedRecommendation] = useState("");
  const [limit, setLimit] = useState(10);
  const [sort, setSort] = useState("descending");
  const [filterField, setFilterField] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [filterValueTo, setFilterValueTo] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    let active = true;
    setCapabilityLoading(true);
    setCapabilities(null);
    setResult(null);
    setConfiguration(null);
    setError(null);

    async function loadCapabilities() {
      if (!dataset?.id) return;
      try {
        const data = await getDatasetExplorationCapabilities(dataset.id);
        if (!active) return;
        setCapabilities(data);
        const recommendation = data?.recommended_explorations?.[0];
        if (recommendation) {
          setConfiguration(recommendationConfig(recommendation));
          setSelectedRecommendation(recommendation.id);
        } else {
          setConfiguration({
            exploration_type: data?.dimensions?.length ? "categorical_distribution" : data?.measures?.length ? "numeric_distribution" : "",
            dimension: data?.dimensions?.[0]?.name || "",
            measure: data?.measures?.[0]?.name || "",
            date_field: data?.time_fields?.[0]?.name || "",
            x_field: "",
            y_field: "",
            aggregation: "mean",
          });
        }
      } catch (loadError) {
        if (!active) return;
        setError(loadError?.response?.data?.detail || "Unable to load exploration options for this dataset.");
      } finally {
        if (active) setCapabilityLoading(false);
      }
    }

    loadCapabilities();

    return () => {
      active = false;
    };
  }, [dataset?.id]);

  const recommendations = capabilities?.recommended_explorations || [];
  const dimensions = capabilities?.dimensions || [];
  const groupDimensions = dimensions.filter((field) => field.role !== "date");
  const measures = capabilities?.measures || [];
  const timeFields = capabilities?.time_fields || [];
  const filterFields = capabilities?.filter_fields || [];
  const selectedFilter = filterFields.find((field) => field.name === filterField);

  useEffect(() => {
    if (!initialRequest || !configuration) return;
    const mapped = {
      ...configuration,
      exploration_type: initialRequest.type || "",
      dimension: initialRequest.dimension || "",
      measure: initialRequest.measure || "",
      date_field: initialRequest.date_field || "",
      x_field: initialRequest.x_field || "",
      y_field: initialRequest.y_field || "",
      aggregation: initialRequest.aggregation || "mean",
    };
    setConfiguration(mapped);
    setSelectedRecommendation("");
    setResult(null);
    document.getElementById("dataset-exploration")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [initialRequest, capabilityLoading]);

  function updateConfiguration(key, value) {
    setConfiguration((current) => ({ ...current, [key]: value }));
    setSelectedRecommendation("");
    setResult(null);
  }

  function selectRecommendation(recommendation) {
    setConfiguration(recommendationConfig(recommendation));
    setSelectedRecommendation(recommendation.id);
    setResult(null);
    setError(null);
  }

  async function runExploration(event) {
    event.preventDefault();
    if (!dataset?.id || !configuration) return;
    setLoading(true);
    setError(null);
    try {
      const filters = [];
      if (filterField && selectedFilter?.role === "numeric") {
        if (filterValue !== "" && filterValueTo !== "") filters.push({ field: filterField, operator: "between", value: Number(filterValue), value_2: Number(filterValueTo) });
        else if (filterValue !== "") filters.push({ field: filterField, operator: "gte", value: Number(filterValue) });
        else if (filterValueTo !== "") filters.push({ field: filterField, operator: "lte", value: Number(filterValueTo) });
      } else if (filterField && selectedFilter?.role !== "date" && filterValue !== "") {
        filters.push({ field: filterField, operator: "equals", value: filterValue });
      }
      const payload = {
        exploration_type: configuration.exploration_type || undefined,
        dimension: configuration.dimension || undefined,
        measure: configuration.measure || undefined,
        secondary_measure: configuration.secondary_measure || undefined,
        date_field: configuration.date_field || undefined,
        x_field: configuration.x_field || undefined,
        y_field: configuration.y_field || undefined,
        aggregation: configuration.aggregation || "mean",
        limit: Number(limit),
        sort,
        filters,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      };
      const data = await exploreDataset(dataset.id, payload);
      setResult(data);
    } catch (queryError) {
      setResult(null);
      setError(queryError?.response?.data?.detail || "This exploration could not be generated for the current dataset.");
    } finally {
      setLoading(false);
    }
  }

  function resetExploration() {
    const first = recommendations[0];
    if (first) {
      setConfiguration(recommendationConfig(first));
      setSelectedRecommendation(first.id);
    }
    setLimit(10);
    setSort("descending");
    setFilterField("");
    setFilterValue("");
    setFilterValueTo("");
    setDateFrom("");
    setDateTo("");
    setResult(null);
    setError(null);
  }

  const usesDimension = configuration && ["categorical_distribution", "group_comparison", "multi_measure_comparison", ""].includes(configuration.exploration_type);
  const usesMeasure = configuration && ["group_comparison", "multi_measure_comparison", "time_trend", ""].includes(configuration.exploration_type);

  if (capabilityLoading) {
    return <DashboardSection id="dataset-exploration" eyebrow="EXPLORE" title="Interactive exploration" description="Analyzing the fields and useful patterns in this dataset."><p className="dashboard-empty" role="status">Analyzing…</p></DashboardSection>;
  }

  return (
    <DashboardSection id="dataset-exploration" eyebrow="EXPLORE" title="Interactive exploration" description="Recommended views are based on this dataset's detected fields, distributions, and observed relationships." className="dashboard-visual-section">
      {error && <p className="dashboard-exploration-error" role="alert">{error}</p>}
      {!recommendations.length && <p className="dashboard-empty">No suitable exploration is available for this dataset.</p>}
      {recommendations.length > 0 && (
        <div className="exploration-recommendations" role="group" aria-label="Recommended explorations">
          {recommendations.map((recommendation) => (
            <button type="button" key={recommendation.id} className="exploration-recommendation" aria-pressed={selectedRecommendation === recommendation.id} onClick={() => selectRecommendation(recommendation)}>
              <strong>{recommendation.title}</strong>
              <span>{recommendation.reason}</span>
              <small>{recommendation.relevance}% relevance</small>
            </button>
          ))}
        </div>
      )}

      {configuration && recommendations.length > 0 && (
        <form className="exploration-builder" onSubmit={runExploration}>
          {usesDimension && groupDimensions.length > 0 && <label><span>Dimension</span><select value={configuration.dimension} onChange={(event) => updateConfiguration("dimension", event.target.value)}>{groupDimensions.map((field) => <option key={field.name} value={field.name}>{field.label}</option>)}</select></label>}
          {usesMeasure && measures.length > 0 && (measures.length > 1 ? <label><span>Measure</span><select value={configuration.measure} onChange={(event) => updateConfiguration("measure", event.target.value)}>{measures.map((field) => <option key={field.name} value={field.name}>{field.label}</option>)}</select></label> : <div className="exploration-fixed-field"><span>Measure</span><strong>{measures[0].label}</strong></div>)}
          {configuration.exploration_type === "numeric_distribution" && measures.length > 0 && <label><span>Numeric field</span><select value={configuration.measure} onChange={(event) => updateConfiguration("measure", event.target.value)}>{measures.map((field) => <option key={field.name} value={field.name}>{field.label}</option>)}</select></label>}
          {configuration.exploration_type === "numeric_relationship" && measures.length > 1 && <div className="exploration-pair-fields"><label><span>Horizontal numeric field</span><select value={configuration.x_field} onChange={(event) => updateConfiguration("x_field", event.target.value)}>{measures.map((field) => <option key={field.name} value={field.name}>{field.label}</option>)}</select></label><label><span>Vertical numeric field</span><select value={configuration.y_field} onChange={(event) => updateConfiguration("y_field", event.target.value)}>{measures.filter((field) => field.name !== configuration.x_field).map((field) => <option key={field.name} value={field.name}>{field.label}</option>)}</select></label></div>}
          {configuration.exploration_type === "multi_measure_comparison" && measures.length > 1 && <label><span>Compare with</span><select value={configuration.secondary_measure || ""} onChange={(event) => { setConfiguration((current) => ({ ...current, secondary_measure: event.target.value, exploration_type: event.target.value ? "multi_measure_comparison" : "group_comparison" })); setSelectedRecommendation(""); setResult(null); }}><option value="">No second measure</option>{measures.filter((field) => field.name !== configuration.measure).map((field) => <option key={field.name} value={field.name}>{field.label}</option>)}</select></label>}
          {timeFields.length > 0 && ["time_trend", ""].includes(configuration.exploration_type) && <label><span>Date field</span><select value={configuration.date_field || timeFields[0].name} onChange={(event) => updateConfiguration("date_field", event.target.value)}>{timeFields.map((field) => <option key={field.name} value={field.name}>{field.label}</option>)}</select></label>}
          {usesMeasure && <label><span>Aggregation</span><select value={configuration.aggregation || "mean"} onChange={(event) => updateConfiguration("aggregation", event.target.value)}>{["mean", "sum", "median", "min", "max", "count"].map((item) => <option key={item} value={item}>{titleCase(item)}</option>)}</select></label>}
          {filterFields.length > 0 && <div className="exploration-filter-fields"><label><span>Filter field</span><select value={filterField} onChange={(event) => { setFilterField(event.target.value); setFilterValue(""); setFilterValueTo(""); if (filterFields.find((field) => field.name === event.target.value)?.role === "date") setConfiguration((current) => ({ ...current, date_field: event.target.value })); }}><option value="">No filter</option>{filterFields.map((field) => <option key={field.name} value={field.name}>{field.label} ({field.role})</option>)}</select></label>{selectedFilter?.role === "numeric" && <><label><span>Minimum value</span><input type="number" value={filterValue} onChange={(event) => setFilterValue(event.target.value)} /></label><label><span>Maximum value</span><input type="number" value={filterValueTo} onChange={(event) => setFilterValueTo(event.target.value)} /></label></>}{selectedFilter?.role === "boolean" && <label><span>Matching value</span><select value={filterValue} onChange={(event) => setFilterValue(event.target.value)}><option value="">Select</option><option value="true">True</option><option value="false">False</option></select></label>}{selectedFilter?.role === "categorical" && <label><span>Matching value</span><input type="text" value={filterValue} onChange={(event) => setFilterValue(event.target.value)} /></label>}</div>}
          {timeFields.length > 0 && configuration.date_field && <div className="exploration-date-range"><label><span>From</span><input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label><label><span>To</span><input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label></div>}
          <label><span>Top results</span><input type="number" min="1" max="200" value={limit} onChange={(event) => setLimit(Math.max(1, Math.min(200, Number(event.target.value) || 1)))} /></label>
          <label><span>Sort</span><select value={sort} onChange={(event) => setSort(event.target.value)}><option value="descending">Highest first</option><option value="ascending">Lowest first</option></select></label>
          <div className="exploration-builder-actions"><button type="submit" className="dashboard-button dashboard-button-primary" disabled={loading}>{loading ? "Analyzing…" : "Run exploration"}</button><button type="button" className="dashboard-button dashboard-button-quiet" onClick={resetExploration} disabled={loading}>Reset</button></div>
        </form>
      )}

      {loading && <p className="dashboard-empty" role="status">Analyzing…</p>}
      {result && <article className="dashboard-visual-card exploration-result" aria-live="polite"><header><h4>{result.summary_detail?.title || "Exploration result"}</h4><p>{result.summary_detail?.description || result.summary}</p></header><p className="exploration-observation">{result.summary_detail?.key_observation || result.empty_message}</p>{result.points?.length ? <ExplorationVisualization result={result} theme={theme} /> : <p className="dashboard-empty">{result.empty_message || "No data matched the selected filters."}</p>}{result.limitations?.length > 0 && <ul className="exploration-limitations">{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul>}<button type="button" className="dashboard-button dashboard-button-secondary" onClick={() => onAskAI?.(result)}>Ask AI about this exploration</button></article>}
    </DashboardSection>
  );
}

function AnalysisDetails({ analysis }) {
  const columns = Array.isArray(analysis.columns) ? analysis.columns : [];
  const numericRows = Object.entries(analysis.numeric_statistics || {});
  const categoricalRows = Object.entries(analysis.categorical_statistics || {});
  if (!columns.length && !numericRows.length && !categoricalRows.length) return null;

  return (
    <details className="dashboard-details">
      <summary>Detailed column statistics</summary>
      <div className="dashboard-details-content">
        {columns.length > 0 && <div className="dashboard-table-wrap"><table><thead><tr><th>Field</th><th>Type</th><th>Missing</th><th>Missing rate</th></tr></thead><tbody>{columns.map((column) => <tr key={column.name}><td>{column.name}</td><td>{column.data_type}</td><td>{formatNumber(column.missing_count)}</td><td>{formatPercent(column.missing_percentage)}</td></tr>)}</tbody></table></div>}
        {numericRows.length > 0 && <div className="dashboard-table-wrap"><table><thead><tr><th>Numeric field</th><th>Count</th><th>Mean</th><th>Median</th><th>Minimum</th><th>Maximum</th></tr></thead><tbody>{numericRows.map(([name, stats]) => <tr key={name}><td>{name}</td><td>{formatNumber(stats.count)}</td><td>{formatNumber(stats.mean)}</td><td>{formatNumber(stats.median)}</td><td>{formatNumber(stats.minimum)}</td><td>{formatNumber(stats.maximum)}</td></tr>)}</tbody></table></div>}
        {categoricalRows.length > 0 && <div className="dashboard-table-wrap"><table><thead><tr><th>Category field</th><th>Values</th><th>Most common</th><th>Count</th></tr></thead><tbody>{categoricalRows.map(([name, stats]) => <tr key={name}><td>{name}</td><td>{formatNumber(stats.unique_count)}</td><td>{stats.most_common_value ?? "Not available"}</td><td>{formatNumber(stats.most_common_count)}</td></tr>)}</tbody></table></div>}
      </div>
    </details>
  );
}

function LoadingDashboard({ dataset }) {
  return (
    <section className="analytics-dashboard universal-dashboard" aria-label="Loading dataset analysis" aria-busy="true">
      <header className="universal-dashboard-header"><div><p className="dashboard-eyebrow">DATASET ANALYSIS</p><h2>{dataset?.original_filename || "Preparing your data"}</h2><p>Building an overview of this dataset.</p></div></header>
      <div className="dashboard-skeleton-metrics">{[0, 1, 2, 3].map((key) => <div className="dashboard-skeleton" key={key}><i /><i /><i /></div>)}</div>
      <div className="dashboard-skeleton-charts"><div className="dashboard-skeleton" /><div className="dashboard-skeleton" /></div>
      <p className="dashboard-loading-label" role="status">Profiling columns and preparing visual summaries…</p>
    </section>
  );
}

function ErrorDashboard({ onRetry }) {
  return (
    <section className="universal-dashboard dashboard-error" role="alert">
      <div><p className="dashboard-eyebrow">ANALYSIS</p><h2>We couldn't load the dashboard analysis.</h2><p>Try again, or check that the dataset contains readable tabular data.</p></div>
      <button type="button" className="dashboard-button dashboard-button-primary" onClick={onRetry}>Try again</button>
    </section>
  );
}

export default function AnalyticsDashboard({ analysis, dashboard: dashboardProp, dataset, loading, error, onRetry, onOpenAssistant, onOpenReport, reportLoading = false }) {
  const { theme } = useTheme();
  const [explorationSeed, setExplorationSeed] = useState(null);
  if (loading) return <LoadingDashboard dataset={dataset} />;
  if (error || !analysis) return <ErrorDashboard onRetry={onRetry} />;

  const dashboard = dashboardProp || analysis.dashboard;
  if (!dashboard?.overview) {
    return <section className="universal-dashboard dashboard-error" role="status"><div><p className="dashboard-eyebrow">ANALYSIS</p><h2>This dashboard model is not available.</h2><p>Refresh the analysis to load dataset-aware summaries.</p></div><button type="button" className="dashboard-button dashboard-button-primary" onClick={onRetry}>Refresh analysis</button></section>;
  }

  const { overview, metrics = [], distributions = [], relationships = {}, trends = [], comparisons = [], data_quality: quality = {}, recommended_visualizations: recommendations = [] } = dashboard;
  const filename = overview.dataset_name || analysis.dataset?.filename || dataset?.original_filename || "Dataset";
  const numericMetrics = metrics.filter((metric) => hasNumber(metric.mean) || hasNumber(metric.sum));
  const displayedMetrics = [...numericMetrics.filter((metric) => metric.recommended_statistics?.includes("total") && hasNumber(metric.sum)), ...numericMetrics.filter((metric) => !metric.recommended_statistics?.includes("total") || !hasNumber(metric.sum))].slice(0, 8);
  const recommendedDistributions = recommendations.filter((item) => ["bar", "donut", "histogram"].includes(item.type) && !item.y_column);
  const distributionRecommendations = recommendedDistributions.length ? recommendedDistributions : distributions.map((item) => ({
    type: item.type === "numeric" ? "histogram" : item.categories?.length <= 5 ? "donut" : "bar",
    title: `${item.label || titleCase(item.column)} distribution`,
    x_column: item.column,
    y_column: null,
    reason: "Shows the distribution of values in this field",
  }));
  const recommendedComparisons = recommendations.filter((item) => item.type === "bar" && item.y_column);
  const comparisonRecommendations = recommendedComparisons.length ? recommendedComparisons : comparisons.slice(0, 4).map((item) => ({
    type: "bar",
    title: `${titleCase(item.measure)} by ${titleCase(item.dimension)}`,
    x_column: item.dimension,
    y_column: item.measure,
    reason: "Compares a numeric measure across detected groups",
  }));
  const recommendedTrends = recommendations.filter((item) => item.type === "line");
  const trendRecommendations = recommendedTrends.length ? recommendedTrends : trends.slice(0, 4).map((item) => ({
    type: "line",
    title: `${titleCase(item.measure_column)} over time`,
    x_column: item.date_column,
    y_column: item.measure_column,
    reason: "Shows aggregated values across the available dates",
  }));
  const heatmapRecommendation = recommendations.find((item) => item.type === "heatmap") || { type: "heatmap", title: "Correlation overview", reason: "Pairwise relationships between numeric fields" };
  const hasHeatmap = hasRelationshipMatrix(relationships.matrix || {});
  const findings = buildFindings(dashboard);
  const automaticInsights = dashboard.automatic_insights || dashboard.insights_context?.automatic_insights || [];
  const fileType = dataset?.file_type?.replace(".", "").toUpperCase() || filename.split(".").pop()?.toUpperCase() || "DATASET";

  return (
    <section className="analytics-dashboard universal-dashboard" aria-labelledby="universal-dashboard-title">
      <header className="universal-dashboard-header">
        <div className="universal-title-block">
          <p className="dashboard-eyebrow">YOUR DATA, AUTOMATICALLY UNDERSTOOD</p>
          <h2 id="universal-dashboard-title">{filename}</h2>
          <p>AI-generated overview of your data</p>
          <span className="dashboard-file-type">{fileType}</span>
        </div>
        <div className="dashboard-header-actions">
          <button type="button" className="dashboard-button dashboard-button-primary" onClick={onOpenAssistant}>Ask AI about this dataset</button>
          <button type="button" className="dashboard-button dashboard-button-secondary" onClick={onOpenReport} disabled={reportLoading}>{reportLoading ? "Generating report…" : "Generate Analysis Report"}</button>
          <button type="button" className="dashboard-button dashboard-button-quiet" onClick={onRetry} aria-label="Refresh analysis">Refresh</button>
        </div>
      </header>

      <div className="dashboard-overview-strip" aria-label="Dataset overview">
        <OverviewStat label="Records" value={formatNumber(overview.row_count)} />
        <OverviewStat label="Fields" value={formatNumber(overview.column_count)} />
        <OverviewStat label="Completeness" value={formatPercent(overview.completeness_percentage)} />
      </div>

      <DashboardSection eyebrow="AT A GLANCE" title="Dataset overview" description="The shape and mix of information in this file.">
        <div className="dashboard-overview-grid">
          <OverviewStat label="Numeric fields" value={formatNumber(overview.numeric_column_count)} />
          <OverviewStat label="Categorical fields" value={formatNumber(overview.categorical_column_count)} />
          <OverviewStat label="Date fields" value={formatNumber(overview.date_column_count)} />
          <OverviewStat label="Text fields" value={formatNumber(overview.text_column_count)} />
          <OverviewStat label="Missing values" value={formatNumber(overview.missing_value_count)} />
          <OverviewStat label="Duplicate records" value={formatNumber(overview.duplicate_row_count)} />
        </div>
      </DashboardSection>

      <DashboardSection eyebrow="SIGNAL" title="Key numbers" description="Summary statistics selected from the fields in your dataset." className="dashboard-metrics-section">
        {displayedMetrics.length ? <div className="dashboard-metric-grid">{displayedMetrics.map((metric) => <DashboardMetric key={metric.column} metric={metric} />)}</div> : <p className="dashboard-empty">No numeric fields are available for summary metrics.</p>}
      </DashboardSection>

      {distributionRecommendations.some((item) => canRenderRecommendation(item, dashboard)) && (
        <DashboardSection eyebrow="SHAPE" title="Distributions" description="See how values are spread across fields and categories." className="dashboard-visual-section">
          <div className="dashboard-visual-grid">{distributionRecommendations.filter((item) => canRenderRecommendation(item, dashboard)).map((item) => <VisualizationCard key={`${item.type}-${item.x_column}`} recommendation={item} dashboard={dashboard} theme={theme} />)}</div>
        </DashboardSection>
      )}

      {(relationships.strongest?.length > 0 || hasHeatmap) && (
        <DashboardSection eyebrow="CONNECTIONS" title="Relationships" description="These patterns describe association, not cause and effect." className="dashboard-relationship-section">
          <div className="dashboard-relationship-layout">
            <div className="dashboard-relationship-summary"><RelationshipList relationships={relationships} /></div>
            {hasHeatmap && <article className="dashboard-visual-card dashboard-heatmap-card"><header><h4>{heatmapRecommendation.title || "Correlation overview"}</h4><p>{heatmapRecommendation.reason || "Pairwise correlations across numeric fields. Correlation does not imply causation."}</p></header><DashboardVisualization recommendation={{ ...heatmapRecommendation, type: "heatmap" }} dashboard={dashboard} theme={theme} /></article>}
          </div>
        </DashboardSection>
      )}

      {comparisonRecommendations.some((item) => canRenderRecommendation(item, dashboard)) && (
        <DashboardSection eyebrow="ACROSS GROUPS" title="Group comparisons" description="Compare average values across detected categories." className="dashboard-visual-section">
          <div className="dashboard-visual-grid">{comparisonRecommendations.filter((item) => canRenderRecommendation(item, dashboard)).map((item) => <VisualizationCard key={`${item.x_column}-${item.y_column}`} recommendation={item} dashboard={dashboard} theme={theme} />)}</div>
        </DashboardSection>
      )}

      {trendRecommendations.some((item) => canRenderRecommendation(item, dashboard)) && (
        <DashboardSection eyebrow="OVER TIME" title="Trends" description="Daily values grouped from the date fields detected in this dataset." className="dashboard-visual-section">
          <div className="dashboard-visual-grid">{trendRecommendations.filter((item) => canRenderRecommendation(item, dashboard)).map((item) => <VisualizationCard key={`${item.x_column}-${item.y_column}`} recommendation={item} dashboard={dashboard} theme={theme} />)}</div>
        </DashboardSection>
      )}

      {dataset && <DataExploration dataset={dataset} initialRequest={explorationSeed} onAskAI={onOpenAssistant} />}

      <div className="dashboard-lower-grid">
        <AutomaticInsights insights={automaticInsights} onExplore={(exploration) => setExplorationSeed({ ...exploration })} />
        <DashboardSection eyebrow="WHAT STANDS OUT" title="Key findings" description="A concise read of the strongest patterns in the returned analysis." className="dashboard-findings-section">
          {findings.length ? <ul className="dashboard-findings-list">{findings.map((finding) => <li key={finding}>{finding}</li>)}</ul> : <p className="dashboard-empty">No standout pattern can be summarized from the available aggregates.</p>}
        </DashboardSection>
        <DataQuality quality={quality} overview={overview} />
      </div>

      <section className="dashboard-assistant-banner" aria-labelledby="dashboard-assistant-title">
        <div className="assistant-banner-mark" aria-hidden="true">AI</div>
        <div className="assistant-banner-copy"><p className="dashboard-eyebrow">GO DEEPER</p><h3 id="dashboard-assistant-title">Ask AI about this dataset</h3><p>Explore a pattern, compare fields, or ask for a plain-language summary.</p><div className="assistant-question-prompts"><span>What patterns stand out?</span><span>Explain the strongest relationships</span><span>What should I investigate next?</span></div></div>
        <button type="button" className="dashboard-button dashboard-button-primary" onClick={onOpenAssistant}>Open assistant</button>
      </section>

      <AnalysisDetails analysis={analysis} />
    </section>
  );
}