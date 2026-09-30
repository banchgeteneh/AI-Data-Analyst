import { useState } from "react";
import ReactMarkdown from "react-markdown";

import { apiClient } from "../../services/api";

function reportError(requestError) {
  if (requestError.response?.status === 429) return "AI requests are temporarily limited. Please wait a moment and try again.";
  if (requestError.response?.status === 503 || requestError.response?.status === 502) return "The AI service is temporarily unavailable. Your dataset analysis is still available. Please try again shortly.";
  if (requestError.response?.status === 404) {
    return "This dataset is no longer available. Refresh your dataset list and try again.";
  }
  return "Unable to generate the report. Please try again.";
}

function formattedDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "long",
    timeStyle: "short",
  }).format(new Date(value));
}

function markdownList(items) {
  return items.map((item) => `- ${item}`).join("\n");
}

function downloadReport(report) {
  const markdown = [
    `# ${report.title}`,
    "",
    `**Dataset:** ${report.dataset_name}`,
    `**Generated:** ${formattedDate(report.generated_at)}`,
    ...(Number.isFinite(report.row_count) && Number.isFinite(report.column_count)
      ? [`**Dimensions:** ${report.row_count} rows x ${report.column_count} columns`]
      : []),
    "",
    "## Executive Summary",
    report.executive_summary,
    "",
    "## Key Findings",
    markdownList(report.key_findings),
    "",
    "## Data Quality",
    report.data_quality,
    "",
    "## Important Trends / Patterns",
    markdownList(report.trends),
    "",
    "## Business Insights",
    markdownList(report.business_insights),
    "",
    "## Recommendations",
    markdownList(report.recommendations),
    "",
    "## Conclusion",
    report.conclusion,
    "",
  ].join("\n");
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const fileBase = report.dataset_name.replace(/\.[^.]+$/, "").replace(/[^a-z0-9_-]+/gi, "-");
  link.href = url;
  link.download = `${fileBase || "dataset"}-report.md`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function MarkdownText({ children }) {
  return <ReactMarkdown skipHtml>{children}</ReactMarkdown>;
}

export default function DatasetReport({ dataset, report, loading, error, onGenerate }) {
  const [downloadMessage, setDownloadMessage] = useState("");

  return (
    <section className="dataset-report" aria-labelledby="dataset-report-heading" aria-busy={loading}>
      <header className="dataset-report-header">
        <div>
          <p className="eyebrow">AI-generated report</p>
          <h2 id="dataset-report-heading">{report?.title || `Report for ${dataset.original_filename}`}</h2>
          {report && <p className="dataset-report-meta">Generated {formattedDate(report.generated_at)}</p>}
        </div>
        {report && (
          <button type="button" className="dataset-report-download" onClick={() => { downloadReport(report); setDownloadMessage("Markdown report download started."); }}>
            Download Markdown
          </button>
        )}
      </header>

      {loading ? (
        <p className="dataset-report-status" role="status">Generating a report from the available dataset analysis...</p>
      ) : error ? (
        <div className="dataset-report-error" role="alert">
          <p>{error}</p>
          <button type="button" className="dataset-report-retry" onClick={onGenerate}>Retry report</button>
        </div>
      ) : report ? (
        <>
          {downloadMessage && <p className="form-success" role="status">{downloadMessage}</p>}
          <dl className="dataset-report-info">
            <div><dt>Dataset</dt><dd>{report.dataset_name}</dd></div>
            {Number.isFinite(report.row_count) && Number.isFinite(report.column_count) && (
              <div><dt>Dimensions</dt><dd>{report.row_count} rows, {report.column_count} columns</dd></div>
            )}
          </dl>
          <div className="dataset-report-content">
            <section><h3>Executive Summary</h3><MarkdownText>{report.executive_summary}</MarkdownText></section>
            <section><h3>Key Findings</h3><ul>{report.key_findings.map((item, index) => <li key={index}><MarkdownText>{item}</MarkdownText></li>)}</ul></section>
            <section><h3>Data Quality</h3><MarkdownText>{report.data_quality}</MarkdownText></section>
            <section><h3>Important Trends / Patterns</h3><ul>{report.trends.map((item, index) => <li key={index}><MarkdownText>{item}</MarkdownText></li>)}</ul></section>
            <section><h3>Business Insights</h3><ul>{report.business_insights.map((item, index) => <li key={index}><MarkdownText>{item}</MarkdownText></li>)}</ul></section>
            <section><h3>Recommendations</h3><ol>{report.recommendations.map((item, index) => <li key={index}><MarkdownText>{item}</MarkdownText></li>)}</ol></section>
            <section><h3>Conclusion</h3><MarkdownText>{report.conclusion}</MarkdownText></section>
          </div>
        </>
      ) : null}
    </section>
  );
}

export async function requestDatasetReport(datasetId) {
  const { data } = await apiClient.post(`/datasets/${datasetId}/ai/report`);
  return data;
}

export { reportError };