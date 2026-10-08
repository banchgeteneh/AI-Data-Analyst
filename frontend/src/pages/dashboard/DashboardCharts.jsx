import * as echarts from "echarts/core";
import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import {
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import ReactEChartsCore from "echarts-for-react/esm/core";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  AriaComponent,
  BarChart,
  CanvasRenderer,
  DataZoomComponent,
  GridComponent,
  HeatmapChart,
  LegendComponent,
  LineChart,
  PieChart,
  ScatterChart,
  TooltipComponent,
  VisualMapComponent,
]);

const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

function formatNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? numberFormat.format(number) : "";
}

function colorsFor(theme) {
  return theme === "dark"
    ? { text: "#e9f0ed", muted: "#a4b6b0", grid: "#354640", surface: "#17221f", primary: "#77c9b1", secondary: "#e7b665", negative: "#e58e83" }
    : { text: "#203c34", muted: "#667a72", grid: "#dce6e1", surface: "#ffffff", primary: "#217e69", secondary: "#c88635", negative: "#bd5b50" };
}

function getDistribution(recommendation, dashboard) {
  return dashboard.distributions?.find((item) => item.column === recommendation.x_column);
}

function getComparison(recommendation, dashboard) {
  return dashboard.comparisons?.find((item) => item.dimension === recommendation.x_column && item.measure === recommendation.y_column);
}

function getTrend(recommendation, dashboard) {
  return dashboard.trends?.find((item) => item.date_column === recommendation.x_column && item.measure_column === recommendation.y_column);
}

function isNumeric(value) {
  return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
}

export function canRenderRecommendation(recommendation, dashboard) {
  if (!recommendation || !dashboard) return false;
  if (recommendation.type === "heatmap") {
    return Object.keys(dashboard.relationships?.matrix || {}).length > 1;
  }
  if (recommendation.type === "scatter") {
    return Array.isArray(recommendation.points) && recommendation.points.length > 1;
  }
  if (recommendation.type === "line") {
    return (getTrend(recommendation, dashboard)?.values?.length || 0) > 1;
  }
  if (recommendation.type === "histogram") {
    return Boolean(getDistribution(recommendation, dashboard)?.histogram?.length);
  }
  if (recommendation.type === "bar" && recommendation.y_column) {
    return (getComparison(recommendation, dashboard)?.groups?.length || 0) > 1;
  }
  if (recommendation.type === "bar" || recommendation.type === "donut") {
    return (getDistribution(recommendation, dashboard)?.categories?.length || 0) > 0;
  }
  return false;
}

function makeOption(recommendation, dashboard, theme) {
  const colors = colorsFor(theme);
  const shared = {
    aria: { enabled: true, description: recommendation.reason || recommendation.title },
    textStyle: { color: colors.text },
    tooltip: { backgroundColor: colors.surface, borderColor: colors.grid, textStyle: { color: colors.text } },
  };

  if (recommendation.type === "donut") {
    const categories = getDistribution(recommendation, dashboard)?.categories || [];
    return {
      ...shared,
      tooltip: { ...shared.tooltip, trigger: "item", formatter: ({ name, value, percent }) => `${name}: ${formatNumber(value)} (${percent}%)` },
      legend: { bottom: 0, type: "scroll", textStyle: { color: colors.muted } },
      series: [{
        type: "pie",
        radius: ["47%", "72%"],
        center: ["50%", "45%"],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: colors.surface, borderWidth: 3 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 13, fontWeight: 700, formatter: "{b}\n{d}%" } },
        data: categories.map((item) => ({ name: String(item.value), value: Number(item.count) || 0 })),
        color: [colors.primary, colors.secondary, "#6e9cc2", "#db8475", "#8b83bf", "#78a77a"],
      }],
    };
  }

  if (recommendation.type === "line") {
    const trend = getTrend(recommendation, dashboard);
    const values = trend?.values || [];
    return {
      ...shared,
      tooltip: { ...shared.tooltip, trigger: "axis", valueFormatter: formatNumber },
      grid: { left: 46, right: 20, top: 20, bottom: values.length > 10 ? 68 : 38, containLabel: true },
      xAxis: { type: "category", data: values.map((item) => item.date), boundaryGap: false, axisLabel: { color: colors.muted, hideOverlap: true }, axisLine: { lineStyle: { color: colors.grid } } },
      yAxis: { type: "value", axisLabel: { color: colors.muted, formatter: formatNumber }, splitLine: { lineStyle: { color: colors.grid } } },
      dataZoom: values.length > 18 ? [{ type: "inside" }, { type: "slider", height: 16, bottom: 4 }] : [],
      series: [{
        name: recommendation.y_column,
        type: "line",
        data: values.map((item) => Number(item.value)),
        smooth: 0.2,
        showSymbol: values.length <= 36,
        symbolSize: 6,
        lineStyle: { width: 3, color: colors.primary },
        itemStyle: { color: colors.primary, borderColor: colors.surface, borderWidth: 2 },
        areaStyle: { color: theme === "dark" ? "rgba(119, 201, 177, 0.12)" : "rgba(33, 126, 105, 0.09)" },
      }],
    };
  }

  if (recommendation.type === "histogram") {
    const bins = getDistribution(recommendation, dashboard)?.histogram || [];
    const labels = bins.map((bin) => `${formatNumber(bin.start)}–${formatNumber(bin.end)}`);
    return {
      ...shared,
      tooltip: { ...shared.tooltip, trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 42, right: 18, top: 18, bottom: 46, containLabel: true },
      xAxis: { type: "category", data: labels, axisLabel: { color: colors.muted, rotate: labels.length > 5 ? 30 : 0, hideOverlap: true }, axisLine: { lineStyle: { color: colors.grid } } },
      yAxis: { type: "value", minInterval: 1, axisLabel: { color: colors.muted }, splitLine: { lineStyle: { color: colors.grid } } },
      series: [{ type: "bar", data: bins.map((bin) => bin.count), barMaxWidth: 34, itemStyle: { color: colors.primary, borderRadius: [3, 3, 0, 0] } }],
    };
  }

  if (recommendation.type === "heatmap") {
    const matrix = dashboard.relationships?.matrix || {};
    const names = Object.keys(matrix);
    const values = [];
    names.forEach((rowName, rowIndex) => {
      names.forEach((columnName, columnIndex) => {
        const value = matrix[rowName]?.[columnName];
        if (isNumeric(value)) values.push([columnIndex, rowIndex, Number(value)]);
      });
    });
    return {
      ...shared,
      tooltip: { ...shared.tooltip, position: "top", formatter: ({ value }) => `${names[value[1]]} × ${names[value[0]]}: ${Number(value[2]).toFixed(3)}` },
      grid: { left: 12, right: 26, top: 16, bottom: 50, containLabel: true },
      xAxis: { type: "category", data: names, axisLabel: { color: colors.muted, rotate: names.length > 5 ? 35 : 0, hideOverlap: true }, axisLine: { lineStyle: { color: colors.grid } } },
      yAxis: { type: "category", data: names, axisLabel: { color: colors.text, width: 130, overflow: "truncate" }, axisLine: { lineStyle: { color: colors.grid } } },
      visualMap: { min: -1, max: 1, calculable: false, orient: "horizontal", left: "center", bottom: 0, itemWidth: 150, itemHeight: 9, text: ["Positive", "Negative"], textStyle: { color: colors.muted }, inRange: { color: [colors.negative, colors.surface, colors.primary] } },
      series: [{ type: "heatmap", data: values, label: { show: names.length <= 8, formatter: ({ value }) => Number(value[2]).toFixed(2), color: colors.text, fontSize: 10 }, itemStyle: { borderColor: colors.surface, borderWidth: 2 }, emphasis: { itemStyle: { shadowBlur: 6, shadowColor: "rgba(0, 0, 0, 0.18)" } } }],
    };
  }

  if (recommendation.type === "scatter") {
    const points = recommendation.points.filter((point) => Array.isArray(point) && isNumeric(point[0]) && isNumeric(point[1]));
    return {
      ...shared,
      tooltip: { ...shared.tooltip, trigger: "item", formatter: ({ value }) => `${recommendation.x_column}: ${formatNumber(value[0])}<br/>${recommendation.y_column}: ${formatNumber(value[1])}` },
      grid: { left: 46, right: 18, top: 18, bottom: 40, containLabel: true },
      xAxis: { type: "value", name: recommendation.x_column, nameLocation: "middle", nameGap: 28, axisLabel: { color: colors.muted }, splitLine: { lineStyle: { color: colors.grid } } },
      yAxis: { type: "value", name: recommendation.y_column, nameTextStyle: { color: colors.muted }, axisLabel: { color: colors.muted }, splitLine: { lineStyle: { color: colors.grid } } },
      series: [{ type: "scatter", data: points, symbolSize: 8, itemStyle: { color: colors.primary, opacity: 0.8 } }],
    };
  }

  const comparison = recommendation.y_column ? getComparison(recommendation, dashboard) : null;
  const entries = comparison
    ? comparison.groups.map((group) => ({ label: String(group.value), value: group.mean }))
    : (getDistribution(recommendation, dashboard)?.categories || []).map((category) => ({ label: String(category.value), value: category.count }));
  return {
    ...shared,
    tooltip: { ...shared.tooltip, trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: formatNumber },
    grid: { left: 16, right: entries.length > 12 ? 36 : 20, top: 14, bottom: 14, containLabel: true },
    xAxis: { type: "value", axisLabel: { color: colors.muted, formatter: formatNumber }, splitLine: { lineStyle: { color: colors.grid } } },
    yAxis: { type: "category", data: entries.map((item) => item.label), inverse: true, axisLabel: { color: colors.text, width: 140, overflow: "truncate" }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: "bar", data: entries.map((item) => item.value), barMaxWidth: 26, itemStyle: { color: comparison ? colors.secondary : colors.primary, borderRadius: [0, 3, 3, 0] }, emphasis: { focus: "self" } }],
  };
}

export default function DashboardVisualization({ recommendation, dashboard, theme }) {
  if (!canRenderRecommendation(recommendation, dashboard)) return null;
  const option = makeOption(recommendation, dashboard, theme);
  const chartType = recommendation.type === "donut" ? "pie" : recommendation.type;
  return (
    <ReactEChartsCore
      echarts={echarts}
      option={option}
      notMerge
      lazyUpdate
      className={`universal-chart universal-chart-${chartType}`}
      aria-label={recommendation.reason || recommendation.title}
    />
  );
}

export function ExplorationVisualization({ result, theme }) {
  const points = result?.points || [];
  const type = result?.visualization;
  if (!points.length || !["bar", "line", "scatter", "pie", "histogram"].includes(type)) return null;
  const colors = colorsFor(theme);
  const shared = {
    aria: { enabled: true, description: result.summary || "Interactive dataset exploration" },
    textStyle: { color: colors.text },
    tooltip: { backgroundColor: colors.surface, borderColor: colors.grid, textStyle: { color: colors.text } },
  };

  if (type === "scatter") {
    return <ReactEChartsCore echarts={echarts} notMerge lazyUpdate className="universal-chart" aria-label={result.summary} option={{ ...shared, tooltip: { ...shared.tooltip, trigger: "item" }, grid: { left: 48, right: 16, top: 18, bottom: 42, containLabel: true }, xAxis: { type: "value", name: result.chart_config?.x_axis_title, axisLabel: { color: colors.muted }, splitLine: { lineStyle: { color: colors.grid } } }, yAxis: { type: "value", name: result.chart_config?.y_axis_title, axisLabel: { color: colors.muted }, splitLine: { lineStyle: { color: colors.grid } } }, series: [{ type: "scatter", data: points.map((point) => [Number(point.x), Number(point.y)]), symbolSize: 8, itemStyle: { color: colors.primary, opacity: 0.78 } }] }} />;
  }

  if (type === "pie") {
    return <ReactEChartsCore echarts={echarts} notMerge lazyUpdate className="universal-chart" aria-label={result.summary} option={{ ...shared, tooltip: { ...shared.tooltip, trigger: "item" }, legend: { bottom: 0, type: "scroll", textStyle: { color: colors.muted } }, series: [{ type: "pie", radius: ["42%", "70%"], avoidLabelOverlap: true, label: { show: false }, emphasis: { label: { show: true, formatter: "{b}: {d}%" } }, data: points.map((point) => ({ name: point.label, value: Number(point.count ?? point.value) || 0 })), color: [colors.primary, colors.secondary, "#6e9cc2", "#db8475", "#78a77a"] }] }} />;
  }

  const isLine = type === "line";
  const entries = points.map((point) => ({ label: point.label, value: Number(point.value ?? point.count) || 0 }));
  const seriesNames = Object.keys(points.find((point) => point.series)?.series || {});
  const palette = [colors.primary, colors.secondary, "#6e9cc2", "#db8475"];
  const option = {
    ...shared,
    tooltip: { ...shared.tooltip, trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: formatNumber },
    grid: { left: 18, right: 18, top: 18, bottom: entries.length > 10 ? 66 : 40, containLabel: true },
    xAxis: { type: "category", data: entries.map((point) => point.label), boundaryGap: !isLine, axisLabel: { color: colors.muted, hideOverlap: true, rotate: entries.length > 8 ? 25 : 0 }, axisLine: { lineStyle: { color: colors.grid } } },
    yAxis: { type: "value", name: result.chart_config?.y_axis_title, axisLabel: { color: colors.muted, formatter: formatNumber }, splitLine: { lineStyle: { color: colors.grid } } },
    dataZoom: entries.length > 18 ? [{ type: "inside" }, { type: "slider", height: 14, bottom: 4 }] : [],
    ...(seriesNames.length > 1 ? { legend: { top: 0, type: "scroll", textStyle: { color: colors.muted } } } : {}),
    series: seriesNames.length > 1
      ? seriesNames.map((name, index) => ({ name, type: "bar", data: points.map((point) => point.series?.[name] ?? null), barMaxWidth: 32, itemStyle: { color: palette[index % palette.length], borderRadius: [3, 3, 0, 0] } }))
      : [{ name: result.chart_config?.series_name || "Value", type: isLine ? "line" : "bar", data: entries.map((point) => point.value), smooth: isLine ? 0.2 : false, showSymbol: isLine && entries.length <= 36, barMaxWidth: 34, lineStyle: { width: 3, color: colors.primary }, itemStyle: { color: colors.primary, borderRadius: isLine ? 0 : [3, 3, 0, 0] } }],
  };
  return <ReactEChartsCore echarts={echarts} option={option} notMerge lazyUpdate className={`universal-chart universal-chart-${isLine ? "line" : "bar"}`} aria-label={result.summary} />;
}