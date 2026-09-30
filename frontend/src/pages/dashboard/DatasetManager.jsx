import { lazy, Suspense, useEffect, useRef, useState } from "react";

import { apiClient, getDashboardData, getDatasetAnalysis } from "../../services/api";
import DatasetAssistant from "./DatasetAssistant";
import DatasetReport, { reportError, requestDatasetReport } from "./DatasetReport";

const AnalyticsDashboard = lazy(() => import("./AnalyticsDashboard"));

function getErrorMessage(requestError, fallback) {
  const status = requestError.response?.status;
  if (status === 401) return "Your session has expired. Sign in again to continue.";
  if (status === 413) return "This file exceeds the configured upload limit. Choose a smaller file.";
  if (status === 415 || status === 422) return "We couldn't process that dataset. Check its file type and contents.";
  if (status === 404) return "That dataset is no longer available. Refresh your workspace and try again.";
  if (status >= 500) return "We couldn't process your request right now. Please try again.";
  return fallback;
}

function formatFileSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

export default function DatasetManager({ onDatasetsLoaded, onWorkflowChange, onSelectedDataset, onSelectedActions, onSectionChange }) {
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [analyzingDatasetId, setAnalyzingDatasetId] = useState(null);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [analysisError, setAnalysisError] = useState(false);
  const [assistantDataset, setAssistantDataset] = useState(null);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantExploration, setAssistantExploration] = useState(null);
  const [report, setReport] = useState(null);
  const [reportDataset, setReportDataset] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportErrorMessage, setReportErrorMessage] = useState("");
  const [datasetToDelete, setDatasetToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const cancelDeleteRef = useRef(null);
  const confirmDeleteRef = useRef(null);
  const deleteTriggerRef = useRef(null);

  async function loadDatasets() {
    setLoading(true);
    try {
      const { data } = await apiClient.get("/datasets");
      setDatasets(data);
      onDatasetsLoaded?.(data.length);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to load your datasets."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDatasets();
  }, []);

  useEffect(() => {
    onWorkflowChange?.({
      analytics: Boolean(analysis),
      analyzing: analyzingDatasetId !== null,
      assistant: assistantOpen,
      report: Boolean(reportDataset),
      reportLoading,
      analysisSummary: analysis?.summary || null,
    });
  }, [analysis, analyzingDatasetId, assistantOpen, reportDataset, reportLoading, onWorkflowChange]);

  useEffect(() => {
    if (!datasetToDelete) return undefined;
    cancelDeleteRef.current?.focus();
    function closeOnEscape(event) {
      if (event.key === "Escape" && !deleting) closeDeleteDialog();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [datasetToDelete, deleting]);

  function selectDataset(dataset) {
    setSelectedDataset(dataset);
    onSelectedDataset?.(dataset);
  }

  function openAssistant(dataset, explorationContext = null) {
    if (!dataset || !dataset.id) {
      setError("Please select a dataset before opening the assistant.");
      return;
    }
    selectDataset(dataset);
    setAssistantDataset(dataset);
    setAssistantExploration(explorationContext);
    setAssistantOpen(true);
    onSectionChange?.("assistant-heading");
  }

  function toggleAssistant(dataset) {
    if (assistantDataset?.id !== dataset.id) {
      openAssistant(dataset);
      return;
    }
    const nextOpen = !assistantOpen;
    setAssistantOpen(nextOpen);
    onSectionChange?.(nextOpen ? "assistant-heading" : "dataset-heading");
  }

  function closeDeleteDialog() {
    setDatasetToDelete(null);
    requestAnimationFrame(() => deleteTriggerRef.current?.focus());
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0] || null;
    setError("");
    setMessage("");
    setProgress(0);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    const supportedExtensions = [".csv", ".xlsx", ".txt", ".docx", ".pdf"];
    if (!supportedExtensions.includes(extension)) {
      setSelectedFile(null);
      setError("Only CSV, XLSX, TXT, DOCX, and PDF files are supported.");
      return;
    }
    setSelectedFile(file);
  }

  async function handleUpload(event) {
    event.preventDefault();
    if (!selectedFile) {
      setError("Choose a supported dataset file first.");
      return;
    }
    setUploading(true);
    setError("");
    setMessage("");
    const formData = new FormData();
    formData.append("file", selectedFile);
    try {
      await apiClient.post("/datasets/upload", formData, {
        onUploadProgress: (event) => {
          if (event.total) setProgress(Math.round((event.loaded * 100) / event.total));
        },
      });
      setSelectedFile(null);
      setProgress(100);
      setMessage("Dataset uploaded successfully.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      await loadDatasets();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to upload the dataset."));
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete() {
    if (!datasetToDelete || deleting) return;
    const datasetId = datasetToDelete.id;
    setDeleting(true);
    setError("");
    setMessage("");
    try {
      await apiClient.delete(`/datasets/${datasetId}`);
      setDatasets((current) => current.filter((dataset) => dataset.id !== datasetId));
      onDatasetsLoaded?.(datasets.length - 1);
      if (selectedDataset?.id === datasetId) {
        setSelectedDataset(null);
        onSelectedDataset?.(null);
      }
      setAnalysis((current) => (current?.dataset.id === datasetId ? null : current));
      setSelectedDataset((current) => (current?.id === datasetId ? null : current));
      setAssistantDataset((current) => (current?.id === datasetId ? null : current));
      if (reportDataset?.id === datasetId) {
        setReport(null);
        setReportDataset(null);
        setReportErrorMessage("");
      }
      if (assistantDataset?.id === datasetId) setAssistantOpen(false);
      if (selectedDataset?.id === datasetId) {
        setAnalysisError(false);
        setAnalysis(null);
      }
      setMessage("Dataset deleted.");
      setDatasetToDelete(null);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to delete the dataset."));
    } finally {
      setDeleting(false);
    }
  }

  async function handleAnalyze(datasetId) {
    const dataset = datasets.find((item) => item.id === datasetId) || null;
    setAnalyzingDatasetId(datasetId);
    selectDataset(dataset);
    onSectionChange?.("analytics-heading");
    setAnalysis(null);
    setAnalysisError(false);
    setError("");
    setMessage("");
    try {
      const data = await getDatasetAnalysis(datasetId);
      setAnalysis(data);
    } catch {
      setAnalysisError(true);
    } finally {
      setAnalyzingDatasetId(null);
    }
  }

  async function handleGenerateReport(dataset = reportDataset) {
    if (!dataset || reportLoading) return;
    if (!dataset.id) {
      setError("Please select a dataset before generating a report.");
      return;
    }
    selectDataset(dataset);
    setReportDataset(dataset);
    onSectionChange?.("dataset-report-heading");
    setReport(null);
    setReportErrorMessage("");
    setReportLoading(true);
    try {
      setReport(await requestDatasetReport(dataset.id));
    } catch (requestError) {
      setReportErrorMessage(reportError(requestError));
    } finally {
      setReportLoading(false);
    }
  }

  const currentDataset = selectedDataset ?? (analysis?.dataset ? {
    id: analysis.dataset.id,
    original_filename: analysis.dataset.filename || "Dataset",
    file_type: analysis.dataset.filename?.split(".").pop() || "",
    file_size: analysis.dataset?.file_size || 0,
    created_at: new Date().toISOString(),
  } : null);

  const selectedActionHandlers = useRef({});
  selectedActionHandlers.current = {
    analyze: handleAnalyze,
    askAI: openAssistant,
    generateReport: handleGenerateReport,
  };

  useEffect(() => {
    onSelectedActions?.({
      analyze: (dataset) => selectedActionHandlers.current.analyze(dataset.id),
      askAI: (dataset) => selectedActionHandlers.current.askAI(dataset),
      generateReport: (dataset) => selectedActionHandlers.current.generateReport(dataset),
    });
  }, [onSelectedActions]);

  return (
    <section className="dataset-panel" aria-labelledby="dataset-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Phase 3 | Dataset management</p>
          <h2 id="dataset-heading">Your datasets</h2>
        </div>
        <span className="dataset-limit">CSV / XLSX · size checked by server</span>
      </div>
      <form className="upload-form" onSubmit={handleUpload}>
        <label className="file-picker">
          Select a dataset
          <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.txt,.docx,.pdf" onChange={handleFileChange} />
        </label>
        <span className="selected-file">{selectedFile ? `${selectedFile.name} · ${formatFileSize(selectedFile.size)}` : "No file selected"}</span>
        <button type="submit" disabled={!selectedFile || uploading}>{uploading ? `Uploading ${progress}%` : "Upload dataset"}</button>
      </form>
      {progress > 0 && uploading && <progress value={progress} max="100" aria-label="Upload progress" />}
      {error && <p className="form-error" role="alert">{error}</p>}
      {message && <p className="form-success" role="status">{message}</p>}
      {loading ? <p role="status">Loading datasets...</p> : datasets.length === 0 ? <div className="dataset-empty-state"><strong>No datasets yet</strong><p>Choose a CSV or Excel file above to start exploring your data.</p></div> : (
        <div className="dataset-table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Type</th><th>Size</th><th>Uploaded</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {datasets.map((dataset) => (
                <tr key={dataset.id} className={selectedDataset?.id === dataset.id ? "dataset-row-selected" : undefined} aria-current={selectedDataset?.id === dataset.id ? "true" : undefined}>
                  <td>{dataset.original_filename}</td>
                  <td>{dataset.file_type.toUpperCase()}</td>
                  <td>{formatFileSize(dataset.file_size)}</td>
                  <td>{formatDate(dataset.created_at)}</td>
                  <td className="dataset-actions"><button type="button" className="analyze-button" onClick={() => handleAnalyze(dataset.id)} disabled={analyzingDatasetId !== null}>{analyzingDatasetId === dataset.id ? "Analyzing dataset..." : "Analyze Dataset"}</button><button type="button" className="dataset-report-button" onClick={() => handleGenerateReport(dataset)} disabled={reportLoading}>{reportLoading && reportDataset?.id === dataset.id ? "Generating report..." : "Generate Report"}</button><button type="button" className="assistant-open-button" onClick={() => toggleAssistant(dataset)} aria-expanded={assistantDataset?.id === dataset.id && assistantOpen}>Ask AI</button><button type="button" className="delete-button" onClick={(event) => { deleteTriggerRef.current = event.currentTarget; setError(""); setDatasetToDelete(dataset); }}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {selectedDataset && !analysis && !analysisError && analyzingDatasetId === null && (
        <section className="analysis-empty-state" aria-label="Analysis not started">
          <div><p className="eyebrow">SELECTED DATASET</p><h3>Analyze your dataset to unlock insights.</h3><p>{selectedDataset.original_filename} is ready for its statistical overview and charts.</p></div>
          <button type="button" className="analyze-button" onClick={() => handleAnalyze(selectedDataset.id)}>Analyze dataset</button>
        </section>
      )}
      {assistantDataset && <div hidden={!assistantOpen}><DatasetAssistant key={assistantDataset.id} dataset={assistantDataset} explorationContext={assistantExploration} onClose={() => { setAssistantOpen(false); setAssistantExploration(null); onSectionChange?.("dataset-heading"); }} /></div>}
      {(analysis || analysisError || analyzingDatasetId !== null) && (
        <Suspense fallback={<p className="muted" role="status">Loading interactive charts...</p>}>
          <AnalyticsDashboard
            analysis={analysis}
            dashboard={getDashboardData(analysis)}
            dataset={currentDataset}
            loading={analyzingDatasetId !== null}
            error={analysisError}
            reportLoading={reportLoading && reportDataset?.id === currentDataset?.id}
            onRetry={() => currentDataset && handleAnalyze(currentDataset.id)}
            onOpenAssistant={(exploration) => currentDataset && openAssistant(currentDataset, exploration || null)}
            onOpenReport={() => currentDataset && handleGenerateReport(currentDataset)}
          />
        </Suspense>
      )}
      {reportDataset && (
        <DatasetReport
          dataset={reportDataset}
          report={report}
          loading={reportLoading}
          error={reportErrorMessage}
          onGenerate={() => handleGenerateReport(reportDataset)}
        />
      )}
      {datasetToDelete && (
        <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !deleting) closeDeleteDialog(); }}>
          <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-dialog-heading" aria-describedby="delete-dialog-description" onKeyDown={(event) => { if (event.key === "Tab") { event.preventDefault(); (event.shiftKey ? confirmDeleteRef.current : cancelDeleteRef.current)?.focus(); } }}>
            <p className="eyebrow">DATASET MANAGEMENT</p>
            <h2 id="delete-dialog-heading">Delete this dataset?</h2>
            <p id="delete-dialog-description">Deleting <strong>{datasetToDelete.original_filename}</strong> will remove it from your workspace and cannot be undone.</p>
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="confirm-dialog-actions">
              <button ref={cancelDeleteRef} type="button" className="confirm-cancel" onClick={closeDeleteDialog} disabled={deleting}>Cancel</button>
              <button ref={confirmDeleteRef} type="button" className="confirm-delete" onClick={handleDelete} disabled={deleting}>{deleting ? "Deleting..." : "Delete Dataset"}</button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
