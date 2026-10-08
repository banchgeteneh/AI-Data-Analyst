import { useEffect, useRef, useState } from "react";

import ThemeToggle from "../../components/common/ThemeToggle";
import { useAuth } from "../../context/AuthContext";
import DatasetManager from "./DatasetManager";

export default function WorkspacePage() {
  const { user, logout } = useAuth();
  const [datasetCount, setDatasetCount] = useState(null);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [selectedDatasetActions, setSelectedDatasetActions] = useState(null);
  const [workflow, setWorkflow] = useState({ analytics: false, analyzing: false, assistant: false, report: false, reportLoading: false, analysisSummary: null });
  const [activeSection, setActiveSection] = useState("workspace-overview");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const menuButtonRef = useRef(null);

  useEffect(() => {
    if (!mobileMenuOpen) return undefined;
    function handleEscape(event) {
      if (event.key === "Escape") {
        setMobileMenuOpen(false);
        menuButtonRef.current?.focus();
      }
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [mobileMenuOpen]);

  const navigationGroups = [
    { title: "WORKSPACE", items: [
      { label: "Overview", id: "workspace-overview", icon: "◫", visible: true },
      { label: "Datasets", id: "dataset-heading", icon: "▦", visible: true },
      { label: "Analytics", id: "analytics-heading", icon: "⌁", visible: workflow.analytics },
    ] },
    { title: "INTELLIGENCE", items: [
      { label: "AI Assistant", id: "assistant-heading", icon: "✦", visible: workflow.assistant },
      { label: "Reports", id: "dataset-report-heading", icon: "▤", visible: workflow.report },
    ] },
  ];

  return (
    <div className="app-shell">
      <aside className={`app-sidebar${mobileMenuOpen ? " is-open" : ""}`} aria-label="Workspace navigation">
        <div className="sidebar-brand-row">
          <a className="brand-lockup app-brand" href="#workspace-overview"><span className="brand-mark" aria-hidden="true">A</span><span>Data Analyst<small>DECISION WORKSPACE</small></span></a>
          <button className="app-sidebar-close" type="button" aria-label="Close workspace navigation" onClick={() => setMobileMenuOpen(false)}>×</button>
        </div>
        <nav className="app-navigation" aria-label="Workspace sections">
          {navigationGroups.map((group) => {
            const items = group.items.filter((item) => item.visible);
            return items.length ? <div className="sidebar-nav-group" key={group.title}><p className="sidebar-label">{group.title}</p>{items.map((item) => <a className={activeSection === item.id ? "sidebar-link is-current" : "sidebar-link"} key={item.id} href={`#${item.id}`} aria-current={activeSection === item.id ? "location" : undefined} onClick={() => { setActiveSection(item.id); setMobileMenuOpen(false); }}><span className="sidebar-link-icon" aria-hidden="true">{item.icon}</span>{item.label}</a>)}</div> : null;
          })}
        </nav>
        <div className="sidebar-account"><span className="account-avatar" aria-hidden="true">{user.name?.slice(0, 1).toUpperCase() || "U"}</span><div><strong>{user.name}</strong><span>{user.email}</span></div></div>
      </aside>
      {mobileMenuOpen && <button className="sidebar-backdrop" type="button" aria-label="Close workspace navigation" onClick={() => setMobileMenuOpen(false)} />}
      <div className="app-main">
        <header className="app-topbar">
          <button ref={menuButtonRef} className="mobile-menu-toggle app-menu-toggle" type="button" aria-label={mobileMenuOpen ? "Close workspace navigation" : "Open workspace navigation"} aria-expanded={mobileMenuOpen} onClick={() => setMobileMenuOpen((open) => !open)}><span /><span /><span /></button>
          <div className="topbar-context"><span className="online-dot" />{selectedDataset ? <><span>Selected dataset</span><strong title={selectedDataset.original_filename}>{selectedDataset.original_filename}</strong></> : <span>Private workspace</span>}</div>
          <div className="topbar-actions"><ThemeToggle /><button type="button" className="logout-button" onClick={logout}>Log out</button></div>
        </header>
        <main className="workspace-content">
          <section className="workspace-overview" id="workspace-overview">
            <div><p className="eyebrow">WORKSPACE</p><h1>Overview</h1><p>{selectedDataset ? `AI-powered analysis of ${selectedDataset.original_filename}` : "AI-powered analysis of your datasets."}</p></div>
            <div className="overview-stat"><span>YOUR DATASETS</span><strong>{datasetCount === null ? "..." : datasetCount}</strong><small>{datasetCount === 1 ? "dataset in your workspace" : "datasets in your workspace"}</small></div>
          </section>
          <section className="selected-dataset-summary" aria-label="Selected dataset status">
            <div className="selected-dataset-details">
              <span className="dataset-file-mark" aria-hidden="true">{selectedDataset?.file_type?.replace(".", "").toUpperCase() || "DATA"}</span>
              <div><span className="selected-dataset-label">SELECTED DATASET</span><strong>{selectedDataset?.original_filename || "No dataset selected"}</strong><span>{selectedDataset ? `${selectedDataset.file_type.toUpperCase()}${workflow.analysisSummary ? ` · ${workflow.analysisSummary.row_count} rows · ${workflow.analysisSummary.column_count} columns` : ` · ${workflow.analyzing ? "Analysis in progress" : "Ready to analyze"}`}${selectedDataset.created_at ? ` · Uploaded ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(selectedDataset.created_at))}` : ""}` : "Choose a dataset below to see its analysis and available actions."}</span></div>
            </div>
            {selectedDataset && selectedDatasetActions && <div className="selected-dataset-actions" role="group" aria-label="Selected dataset actions">
              <button type="button" onClick={() => selectedDatasetActions.analyze(selectedDataset)} disabled={workflow.analyzing}>{workflow.analyzing ? "Analyzing..." : "Analyze"}</button>
              <button type="button" onClick={() => selectedDatasetActions.askAI(selectedDataset)}>Ask AI</button>
              <button type="button" onClick={() => selectedDatasetActions.generateReport(selectedDataset)} disabled={workflow.reportLoading}>{workflow.reportLoading ? "Generating..." : "Generate Report"}</button>
            </div>}
            {!selectedDataset && <a href="#dataset-heading">Go to datasets <span aria-hidden="true">-&gt;</span></a>}
          </section>
          <DatasetManager onDatasetsLoaded={setDatasetCount} onWorkflowChange={setWorkflow} onSelectedDataset={setSelectedDataset} onSelectedActions={setSelectedDatasetActions} onSectionChange={setActiveSection} />
        </main>
      </div>
    </div>
  );
}
