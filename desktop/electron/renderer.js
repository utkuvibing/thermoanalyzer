let activeProjectId = null;
let activeProjectDefaultName = "thermoanalyzer_project.thermozip";
let selectedDatasetKey = null;
let selectedResultId = null;
let currentDatasets = [];
let currentResults = [];
let exportableResults = [];
let currentActiveDatasetKey = null;
let compareSelectedDatasetKeys = new Set();
let currentDatasetDetail = null;
let currentResultDetail = null;
const lastAnalysisRuns = {
  DSC: null,
  TGA: null,
};

const viewTitles = {
  home: "Home / Import",
  compare: "Compare",
  dsc: "DSC",
  tga: "TGA",
  export: "Export",
  project: "Project",
  license: "License",
  diagnostics: "Diagnostics",
};

function el(id) {
  return document.getElementById(id);
}

function setText(id, text) {
  const node = el(id);
  if (node) node.textContent = text;
}

function setHtml(id, html) {
  const node = el(id);
  if (node) node.innerHTML = html;
}

function setDisabled(id, disabled) {
  const node = el(id);
  if (node && "disabled" in node) node.disabled = disabled;
}

function appendLog(message) {
  const node = el("log");
  if (!node) return;
  const now = new Date().toLocaleTimeString();
  node.textContent = `${node.textContent}\n[${now}] ${message}`.trim();
}

function switchView(name) {
  document.querySelectorAll(".view").forEach((node) => node.classList.remove("active"));
  document.querySelectorAll(".nav-item[data-view]").forEach((node) => node.classList.remove("active"));
  const view = el(`view-${name}`);
  if (view) view.classList.add("active");
  const nav = document.querySelector(`.nav-item[data-view="${name}"]`);
  if (nav) nav.classList.add("active");
  setText("pageTitle", viewTitles[name] || "ThermoAnalyzer Desktop");
}

function updateStatusWorkspace() {
  setText("statusWorkspace", `Workspace: ${activeProjectId || "none"}`);
}

function updateAnalysisActionState() {
  const enabled = Boolean(activeProjectId && selectedDatasetKey);
  setDisabled("runDscAnalysisBtn", !enabled);
  setDisabled("runTgaAnalysisBtn", !enabled);
  setDisabled("inspectSelectedDatasetBtn", !enabled);
  setDisabled("inspectSelectedDatasetBtn2", !enabled);
  setDisabled("addSelectedToCompareBtn", !enabled);
  setDisabled("removeSelectedFromCompareBtn", !enabled);
}

function setWorkflowEnabled(enabled) {
  setDisabled("saveProjectBtn", !enabled);
  setDisabled("saveProjectBtnProjectView", !enabled);
  setDisabled("refreshWorkspaceContextBtn", !enabled);
  setDisabled("refreshWorkspaceContextBtnProjectView", !enabled);
  setDisabled("importDatasetBtn", !enabled);
  setDisabled("refreshCompareBtn", !enabled);
  setDisabled("saveCompareBtn", !enabled);
  setDisabled("clearCompareSelectionBtn", !enabled);
  setDisabled("runBatchBtn", !enabled);
  setDisabled("refreshExportPrepBtn", !enabled);
  setDisabled("exportCsvBtn", !enabled);
  setDisabled("exportDocxBtn", !enabled);
  updateAnalysisActionState();
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function safeJson(value) {
  return JSON.stringify(value || {}, null, 2);
}

function setDiagnostic(name, value) {
  const map = {
    workspace: "diagWorkspaceContext",
    dataset: "diagDatasetDetail",
    result: "diagResultDetail",
    compare: "diagComparePayload",
    batch: "diagBatchPayload",
    export: "diagExportPayload",
  };
  const targetId = map[name];
  if (targetId) {
    setText(targetId, safeJson(value));
  }
}

function valueOr(value, fallback = "N/A") {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  return String(value);
}

function keyGrid(items) {
  return `<div class="kv-grid">${(items || [])
    .map(
      (item) => `
      <div class="kv-item">
        <div class="kv-label">${escapeHtml(item.label)}</div>
        <div class="kv-value">${escapeHtml(item.value)}</div>
      </div>`
    )
    .join("")}</div>`;
}

function renderIssueList(title, items) {
  if (!items || !items.length) {
    return `<p class="small muted">${escapeHtml(title)}: none</p>`;
  }
  return `<p class="small"><strong>${escapeHtml(title)}:</strong></p><ul class="list-box">${items
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("")}</ul>`;
}

function renderRowsPreview(rows) {
  const data = Array.isArray(rows) ? rows.slice(0, 8) : [];
  if (!data.length) return '<p class="small muted">No preview rows.</p>';
  const keys = Object.keys(data[0] || {}).slice(0, 6);
  if (!keys.length) return '<p class="small muted">No preview rows.</p>';
  return `<table><thead><tr>${keys.map((key) => `<th>${escapeHtml(key)}</th>`).join("")}</tr></thead><tbody>${data
    .map((row) => `<tr>${keys.map((key) => `<td>${escapeHtml(row[key])}</td>`).join("")}</tr>`)
    .join("")}</tbody></table>`;
}

function asArray(value) {
  if (Array.isArray(value)) return value;
  if (typeof value === "string" && value.trim()) return [value.trim()];
  return [];
}

function toneBadgeClass(statusToken) {
  const token = String(statusToken || "").toLowerCase();
  if (token === "pass" || token === "ok" || token === "saved") return "badge badge-ok";
  if (token === "warn" || token === "warning" || token === "blocked") return "badge badge-warn";
  if (token === "fail" || token === "error" || token === "failed") return "badge badge-fail";
  return "badge badge-neutral";
}

function renderCompareSelectionChips(selectedKeys) {
  const keys = selectedKeys || [];
  if (!keys.length) {
    setHtml("compareSelectedDatasetsPanel", '<span class="dataset-chip">No compare-selected datasets.</span>');
    return;
  }
  const chips = keys
    .map((key) => {
      const dataset = currentDatasets.find((item) => item.key === key);
      const suffix = dataset ? `${dataset.data_type}` : "unknown";
      return `<span class="dataset-chip">${escapeHtml(key)} (${escapeHtml(suffix)})</span>`;
    })
    .join("");
  setHtml("compareSelectedDatasetsPanel", chips);
}

function renderHomeWorkflowSteps(context) {
  const summary = (context && context.summary) || {};
  const compareWorkspace = (context && context.compare_workspace) || {};
  const datasetCount = Number(summary.dataset_count || 0);
  const resultCount = Number(summary.result_count || 0);
  const selectedCompareCount = (compareWorkspace.selected_datasets || []).length;

  setText("homeStepWorkspaceStatus", activeProjectId ? "Workspace ready" : "Create/open workspace");
  setText("homeStepImportStatus", datasetCount > 0 ? `${datasetCount} dataset(s) imported` : "Import at least one dataset");
  setText("homeStepCompareStatus", selectedCompareCount > 0 ? `${selectedCompareCount} selected for compare` : "Select compare datasets");
  setText("homeStepRunStatus", resultCount > 0 ? `${resultCount} result(s) saved` : "Run DSC/TGA analysis");

  let nextStep = "Create or open a workspace.";
  if (activeProjectId) nextStep = "Import your first dataset.";
  if (datasetCount > 0) nextStep = "Inspect validation and set compare selection.";
  if (selectedCompareCount > 0) nextStep = "Run DSC/TGA analysis or batch from Compare.";
  if (resultCount > 0) nextStep = "Save project or continue with export.";
  setText("homeNextStepValue", nextStep);
}

function renderCompareWorkspaceSummary(compareWorkspace) {
  const payload = compareWorkspace || {};
  const selectedCount = (payload.selected_datasets || []).length;
  setHtml(
    "compareSummaryPanel",
    `
    ${keyGrid([
      { label: "Analysis Type", value: valueOr(payload.analysis_type, "DSC") },
      { label: "Selected Count", value: String(selectedCount) },
      { label: "Saved At", value: valueOr(payload.saved_at, "N/A") },
      { label: "Batch Run ID", value: valueOr(payload.batch_run_id, "none") },
      { label: "Batch Template", value: valueOr(payload.batch_template_id, "none") },
      { label: "Notes", value: valueOr(payload.notes, "(empty)") },
    ])}
    <div style="margin-top:8px;">
      <span class="${toneBadgeClass(selectedCount > 0 ? "ok" : "warning")}">Selected: ${selectedCount}</span>
      <span class="${toneBadgeClass(payload.batch_run_id ? "saved" : "neutral")}">Batch: ${payload.batch_run_id ? "available" : "not run"}</span>
    </div>
    `
  );
  renderCompareSelectionChips(payload.selected_datasets || []);
}

function isDatasetEligibleForAnalysis(analysisType, datasetType) {
  const token = String(analysisType || "").toUpperCase();
  const dtype = String(datasetType || "UNKNOWN").toUpperCase();
  if (token === "DSC") return dtype === "DSC" || dtype === "DTA" || dtype === "UNKNOWN";
  if (token === "TGA") return dtype === "TGA" || dtype === "UNKNOWN";
  return false;
}

function findLatestResultByType(analysisType) {
  const token = String(analysisType || "").toUpperCase();
  const filtered = (currentResults || []).filter((item) => String(item.analysis_type || "").toUpperCase() === token);
  if (!filtered.length) return null;
  const sorted = [...filtered].sort((a, b) => {
    const aTime = Date.parse(a.saved_at_utc || "") || 0;
    const bTime = Date.parse(b.saved_at_utc || "") || 0;
    return bTime - aTime;
  });
  return sorted[0];
}

function renderAnalysisPage(analysisType) {
  const token = String(analysisType || "").toUpperCase();
  const isDsc = token === "DSC";
  const prefix = isDsc ? "dsc" : "tga";
  const defaultTemplate = isDsc ? "dsc.general" : "tga.general";
  const dataset = (currentDatasets || []).find((item) => item.key === selectedDatasetKey) || null;
  const detail = currentDatasetDetail && currentDatasetDetail.dataset && currentDatasetDetail.dataset.key === selectedDatasetKey
    ? currentDatasetDetail
    : null;
  const validation = (detail && detail.validation) || {};
  const metadata = (detail && detail.metadata) || {};
  const units = (detail && detail.units) || {};
  const importWarnings = asArray(metadata.import_warnings);
  const issues = validation.issues || [];
  const warnings = validation.warnings || [];
  const reviewRequired = Boolean(metadata.import_review_required);
  const confidence = valueOr(metadata.import_confidence || metadata.import_confidence_level, "not_recorded");
  const eligible = dataset ? isDatasetEligibleForAnalysis(token, dataset.data_type) : false;

  const latestResult = findLatestResultByType(token);
  const focusedResult = currentResultDetail && currentResultDetail.result && String(currentResultDetail.result.analysis_type || "").toUpperCase() === token
    ? currentResultDetail
    : null;
  const runInfo = lastAnalysisRuns[token];

  setHtml(
    `${prefix}ActiveDatasetContextPanel`,
    dataset
      ? `
      ${keyGrid([
        { label: "Dataset Key", value: valueOr(dataset.key) },
        { label: "Dataset Type", value: valueOr(dataset.data_type, "unknown") },
        { label: "Sample", value: valueOr(dataset.sample_name, "not named") },
        { label: "Active In Workspace", value: dataset.key === currentActiveDatasetKey ? "yes" : "no" },
      ])}
      <div style="margin-top:8px;">
        <span class="${toneBadgeClass(eligible ? "ok" : "warning")}">${token} eligibility: ${eligible ? "compatible" : "review dataset type"}</span>
      </div>
      `
      : "Select a dataset from Home / Import to begin analysis context."
  );

  setHtml(
    `${prefix}MethodContextPanel`,
    isDsc
      ? `
      ${keyGrid([
        { label: "Suggested Workflow Template", value: defaultTemplate },
        { label: "Selected Dataset Type", value: valueOr(dataset && dataset.data_type, "none") },
        { label: "Validation Status", value: valueOr(validation.status, dataset ? dataset.validation_status : "unknown") },
      ])}
      `
      : `
      ${keyGrid([
        { label: "Suggested Workflow Template", value: defaultTemplate },
        { label: "Selected Dataset Type", value: valueOr(dataset && dataset.data_type, "none") },
        { label: "Signal Unit", value: valueOr(units.signal, "n/a") },
      ])}
      `
  );

  const validationContextHtml = `
    <div>
      <span class="${toneBadgeClass(validation.status || (dataset && dataset.validation_status))}">Validation: ${escapeHtml(valueOr(validation.status || (dataset && dataset.validation_status), "unknown"))}</span>
      <span class="${toneBadgeClass(reviewRequired ? "warning" : "ok")}">Import Review Required: ${reviewRequired ? "yes" : "no"}</span>
      <span class="badge badge-neutral">Import Confidence: ${escapeHtml(confidence)}</span>
    </div>
    ${renderIssueList("Validation warnings", warnings)}
    ${renderIssueList("Validation issues", issues)}
    ${renderIssueList("Import warnings", importWarnings)}
  `;
  setHtml(`${prefix}ValidationPanel`, validationContextHtml);

  if (!isDsc) {
    setHtml(
      "tgaUnitContextPanel",
      `
      ${keyGrid([
        { label: "Temperature Unit", value: valueOr(units.temperature, "n/a") },
        { label: "Signal Unit", value: valueOr(units.signal, "n/a") },
        { label: "Inferred Signal Unit", value: valueOr(metadata.inferred_signal_unit, "n/a") },
        { label: "Import Review Required", value: reviewRequired ? "yes" : "no" },
      ])}
      `
    );
  }

  const templateFromResult = focusedResult && focusedResult.processing
    ? valueOr(focusedResult.processing.workflow_template_id, defaultTemplate)
    : defaultTemplate;
  setHtml(
    `${prefix}TemplateContextPanel`,
    `
    ${keyGrid([
      { label: "Template ID", value: templateFromResult },
      { label: "Page Analysis Type", value: token },
      { label: "Ready To Run", value: dataset && eligible ? "yes" : "select compatible dataset" },
    ])}
    <p class="small">Run will save into the same project result store and preserve validation/provenance context.</p>
    `
  );

  const resultPanelId = `${prefix}ResultSummaryPanel`;
  if (focusedResult) {
    setHtml(
      resultPanelId,
      `
      ${keyGrid([
        { label: "Focused Result ID", value: valueOr(focusedResult.result.id) },
        { label: "Status", value: valueOr(focusedResult.result.status) },
        { label: "Dataset", value: valueOr(focusedResult.result.dataset_key) },
        { label: "Template", value: valueOr(focusedResult.processing && focusedResult.processing.workflow_template_id, "n/a") },
        { label: "Saved At (UTC)", value: valueOr(focusedResult.provenance && focusedResult.provenance.saved_at_utc, "n/a") },
      ])}
      <div style="margin-top:8px;">
        <span class="${toneBadgeClass(focusedResult.validation && focusedResult.validation.status)}">Validation: ${escapeHtml(valueOr(focusedResult.validation && focusedResult.validation.status, "unknown"))}</span>
        <span class="badge badge-neutral">Calibration: ${escapeHtml(valueOr(focusedResult.provenance && focusedResult.provenance.calibration_state, "unknown"))}</span>
        <span class="badge badge-neutral">Reference: ${escapeHtml(valueOr(focusedResult.provenance && focusedResult.provenance.reference_state, "unknown"))}</span>
      </div>
      `
    );
  } else if (latestResult) {
    setHtml(
      resultPanelId,
      `
      ${keyGrid([
        { label: "Latest Saved Result", value: valueOr(latestResult.id) },
        { label: "Status", value: valueOr(latestResult.status) },
        { label: "Dataset", value: valueOr(latestResult.dataset_key) },
        { label: "Validation", value: valueOr(latestResult.validation_status, "unknown") },
        { label: "Saved At (UTC)", value: valueOr(latestResult.saved_at_utc, "n/a") },
      ])}
      <p class="small">Open this result from Project page to inspect full processing/provenance details.</p>
      `
    );
  } else {
    setHtml(resultPanelId, `No ${token} result context yet.`);
  }

  if (runInfo) {
    const infoText = `${token} on ${runInfo.dataset_key}: ${runInfo.execution_status}${runInfo.result_id ? ` (${runInfo.result_id})` : ""}${runInfo.failure_reason ? ` - ${runInfo.failure_reason}` : ""}`;
    setText(`${prefix}AnalysisInfo`, infoText);
  } else if (!dataset) {
    setText(`${prefix}AnalysisInfo`, `No ${token} analysis executed yet.`);
  }
}

function renderAnalysisPages() {
  renderAnalysisPage("DSC");
  renderAnalysisPage("TGA");
}

function applyWorkspaceContext(context) {
  currentActiveDatasetKey = context.active_dataset_key || null;
  compareSelectedDatasetKeys = new Set((context.compare_workspace && context.compare_workspace.selected_datasets) || []);
  const compareCount = context.compare_workspace && context.compare_workspace.selected_datasets
    ? context.compare_workspace.selected_datasets.length
    : 0;
  const latestResultText = context.latest_result && context.latest_result.id ? context.latest_result.id : "none";
  const compareWorkspace = context.compare_workspace || {};

  setText(
    "homeProjectInfo",
    `Workspace ${activeProjectId} | datasets=${context.summary.dataset_count} | results=${context.summary.result_count}`
  );
  setText("homeDatasetCountValue", String(context.summary.dataset_count || 0));
  setText("homeResultCountValue", String(context.summary.result_count || 0));
  setText(
    "projectViewInfo",
    `Workspace ${activeProjectId} | figures=${context.summary.figure_count} | history=${context.summary.analysis_history_count}`
  );
  setText("projectDatasetCountValue", String(context.summary.dataset_count || 0));
  setText("projectResultCountValue", String(context.summary.result_count || 0));
  setText("projectHistoryCountValue", String(context.summary.analysis_history_count || 0));
  setText("projectFigureCountValue", String(context.summary.figure_count || 0));
  const projectConfidence =
    Number(context.summary.dataset_count || 0) === 0
      ? "Import datasets to establish project archive baseline."
      : Number(context.summary.result_count || 0) === 0
      ? "Datasets imported. Run analyses to build saved result history."
      : "Workspace has saved results and is ready for archive save/export.";
  setText("projectConfidenceMessage", projectConfidence);
  setText("homeActiveDatasetValue", currentActiveDatasetKey || "none");
  setText("homeLatestResultValue", latestResultText);
  setText("homeCompareCountValue", String(compareCount));
  setText("homeWorkspaceSavedAtValue", valueOr(compareWorkspace.saved_at, "N/A"));
  setText(
    "compareMeta",
    `Selected datasets: ${compareCount} | Saved at: ${valueOr(compareWorkspace.saved_at, "N/A")}`
  );
  renderCompareWorkspaceSummary(compareWorkspace);
  renderHomeWorkflowSteps(context);
  setDiagnostic("workspace", {
    summary: context.summary,
    active_dataset: context.active_dataset,
    latest_result: context.latest_result,
    compare_workspace: compareWorkspace,
    compare_selected_datasets: context.compare_selected_datasets,
    recent_history: context.recent_history,
  });
  updateStatusWorkspace();
}

function renderCompareDatasetChecks(selectedDatasets) {
  const container = el("compareDatasetChecks");
  if (!currentDatasets.length) {
    container.innerHTML = "<div class='panel-soft small'>No datasets available.</div>";
    return;
  }

  const selected = new Set(selectedDatasets || []);
  container.innerHTML = currentDatasets
    .map((dataset) => {
      const checked = selected.has(dataset.key) ? "checked" : "";
      const cardClass = selected.has(dataset.key) ? "compare-pick selected" : "compare-pick";
      const isActive = dataset.key === currentActiveDatasetKey ? "Active workspace dataset" : "Not active";
      return `
      <label class="${cardClass}">
        <div class="small">
          <input type="checkbox" class="compare-dataset-check" value="${escapeHtml(dataset.key)}" ${checked}>
          <strong>${escapeHtml(dataset.key)}</strong> (${escapeHtml(dataset.data_type)})
        </div>
        <div class="small muted">${escapeHtml(valueOr(dataset.sample_name, "sample not named"))}</div>
        <div class="small">
          <span class="${toneBadgeClass(dataset.validation_status)}">Validation: ${escapeHtml(valueOr(dataset.validation_status, "unknown"))}</span>
          <span class="badge badge-neutral">Warnings: ${escapeHtml(valueOr(dataset.warning_count, "0"))}</span>
          <span class="badge badge-neutral">Issues: ${escapeHtml(valueOr(dataset.issue_count, "0"))}</span>
        </div>
        <div class="small muted">${escapeHtml(isActive)}</div>
      </label>`;
    })
    .join("");
}

function collectCompareSelectedDatasets() {
  return Array.from(document.querySelectorAll(".compare-dataset-check"))
    .filter((node) => node.checked)
    .map((node) => node.value);
}

function collectSelectedExportResultIds() {
  return Array.from(document.querySelectorAll(".export-result-check"))
    .filter((node) => node.checked)
    .map((node) => node.value);
}

async function loadDatasetDetail(datasetKey) {
  if (!activeProjectId || !datasetKey) return;
  try {
    const detail = await window.taDesktop.getDatasetDetail(activeProjectId, datasetKey);
    currentDatasetDetail = detail;
    const validation = detail.validation || {};
    const metadata = detail.metadata || {};
    const importWarnings = asArray(metadata.import_warnings);
    const confidence = valueOr(metadata.import_confidence || metadata.import_confidence_level || "not_recorded", "not_recorded");
    const reviewRequired = Boolean(metadata.import_review_required);
    const inferredType = valueOr(metadata.inferred_analysis_type, "n/a");
    const inferredUnit = valueOr(metadata.inferred_signal_unit, "n/a");
    const inferredVendor = valueOr(metadata.inferred_vendor, "n/a");
    setText(
      "datasetDetailInfo",
      `Dataset ${detail.dataset.key} | Type ${detail.dataset.data_type} | Validation ${validation.status || "unknown"}`
    );
    setHtml(
      "homeSelectedDatasetPanel",
      `
      ${keyGrid([
        { label: "Selected Dataset", value: detail.dataset.key },
        { label: "Type", value: detail.dataset.data_type },
        { label: "Sample", value: valueOr(detail.dataset.sample_name) },
        { label: "Validation", value: valueOr(validation.status, "unknown") },
        { label: "Warnings", value: String((validation.warnings || []).length) },
        { label: "Issues", value: String((validation.issues || []).length) },
      ])}
      `
    );
    setHtml(
      "homeImportQualityPanel",
      `
      <div>
        <span class="${toneBadgeClass(validation.status)}">Validation: ${escapeHtml(valueOr(validation.status, "unknown"))}</span>
        <span class="${toneBadgeClass(reviewRequired ? "warning" : "ok")}">Review Required: ${reviewRequired ? "yes" : "no"}</span>
        <span class="badge badge-neutral">Import Confidence: ${escapeHtml(confidence)}</span>
      </div>
      ${keyGrid([
        { label: "Inferred Type", value: inferredType },
        { label: "Inferred Signal Unit", value: inferredUnit },
        { label: "Inferred Vendor", value: inferredVendor },
      ])}
      ${renderIssueList("Import warnings", importWarnings)}
      `
    );
    setHtml(
      "datasetDetailPanel",
      `
      ${keyGrid([
        { label: "Dataset Key", value: detail.dataset.key },
        { label: "Type", value: detail.dataset.data_type },
        { label: "Sample", value: valueOr(detail.dataset.sample_name) },
        { label: "Validation", value: valueOr(validation.status, "unknown") },
        { label: "Warnings", value: String((validation.warnings || []).length) },
        { label: "Issues", value: String((validation.issues || []).length) },
      ])}
      ${renderIssueList("Warnings", validation.warnings || [])}
      ${renderIssueList("Issues", validation.issues || [])}
      <p class="small"><strong>Metadata</strong></p>
      ${keyGrid(
        Object.entries(detail.metadata || {})
          .slice(0, 8)
          .map(([key, value]) => ({ label: key, value: valueOr(value) }))
      )}
      <p class="small"><strong>Units / Columns</strong></p>
      ${keyGrid([
        { label: "Temperature Unit", value: valueOr(detail.units && detail.units.temperature) },
        { label: "Signal Unit", value: valueOr(detail.units && detail.units.signal) },
        { label: "Original Columns", value: valueOr((detail.original_columns || []).join(", "), "none") },
        { label: "Compare Selected", value: detail.compare_selected ? "yes" : "no" },
      ])}
      <p class="small"><strong>Data Preview</strong></p>
      ${renderRowsPreview(detail.data_preview || [])}
      `
    );
    setDiagnostic("dataset", detail);
    renderAnalysisPages();
  } catch (error) {
    currentDatasetDetail = null;
    setText("datasetDetailInfo", `Dataset detail failed: ${error}`);
    setHtml("datasetDetailPanel", "<p class='fail'>Dataset detail unavailable.</p>");
    setHtml("homeImportQualityPanel", "<p class='fail'>Import confidence details unavailable.</p>");
    setDiagnostic("dataset", { error: String(error) });
    renderAnalysisPages();
  }
}

async function loadResultDetail(resultId) {
  if (!activeProjectId || !resultId) return;
  try {
    const detail = await window.taDesktop.getResultDetail(activeProjectId, resultId);
    currentResultDetail = detail;
    const validation = detail.validation || {};
    const processing = detail.processing || {};
    const provenance = detail.provenance || {};
    setText(
      "resultDetailInfo",
      `Result ${detail.result.id} | ${detail.result.analysis_type} | status=${detail.result.status}`
    );
    setHtml(
      "resultDetailPanel",
      `
      ${keyGrid([
        { label: "Result ID", value: detail.result.id },
        { label: "Analysis Type", value: detail.result.analysis_type },
        { label: "Status", value: detail.result.status },
        { label: "Dataset", value: detail.result.dataset_key },
        { label: "Validation", value: valueOr(validation.status, "unknown") },
        { label: "Saved At (UTC)", value: valueOr(provenance.saved_at_utc) },
      ])}
      <p class="small"><strong>Processing / Template</strong></p>
      ${keyGrid([
        { label: "Template ID", value: valueOr(processing.workflow_template_id, "n/a") },
        { label: "Template Label", value: valueOr(processing.workflow_template_label, "n/a") },
        { label: "Schema Version", value: valueOr(processing.schema_version, "n/a") },
        { label: "Calibration", value: valueOr(provenance.calibration_state, "unknown") },
        { label: "Reference", value: valueOr(provenance.reference_state, "unknown") },
        { label: "Row Count", value: valueOr(detail.row_count, "0") },
      ])}
      ${renderIssueList("Warnings", validation.warnings || [])}
      ${renderIssueList("Issues", validation.issues || [])}
      <p class="small"><strong>Rows Preview</strong></p>
      ${renderRowsPreview(detail.rows_preview || [])}
      `
    );
    setDiagnostic("result", detail);
    renderAnalysisPages();
  } catch (error) {
    currentResultDetail = null;
    setText("resultDetailInfo", `Result detail failed: ${error}`);
    setHtml("resultDetailPanel", "<p class='fail'>Result detail unavailable.</p>");
    setDiagnostic("result", { error: String(error) });
    renderAnalysisPages();
  }
}

function renderDatasets(datasets) {
  const body = el("datasetsBody");
  currentDatasets = datasets;
  if (!datasets.length) {
    body.innerHTML = "<tr><td colspan='10'>No datasets loaded.</td></tr>";
    selectedDatasetKey = null;
    currentDatasetDetail = null;
    updateAnalysisActionState();
    setText("datasetDetailInfo", "No dataset detail selected.");
    setHtml("datasetDetailPanel", "Select a dataset to inspect metadata, validation, and preview rows.");
    setHtml("homeSelectedDatasetPanel", "No active dataset selected.");
    setHtml("homeImportQualityPanel", "Import confidence and review guidance will appear here after dataset inspection.");
    setDiagnostic("dataset", {});
    renderCompareDatasetChecks([]);
    renderAnalysisPages();
    return;
  }

  if (!selectedDatasetKey || !datasets.some((item) => item.key === selectedDatasetKey)) {
    selectedDatasetKey = datasets[0].key;
  }
  updateAnalysisActionState();

  body.innerHTML = datasets
    .map((item) => {
      const checked = item.key === selectedDatasetKey ? "checked" : "";
      const active = item.key === currentActiveDatasetKey ? "Active" : "";
      const compareSelected = compareSelectedDatasetKeys.has(item.key);
      return `
      <tr>
        <td><input type="radio" name="datasetPick" value="${escapeHtml(item.key)}" ${checked}></td>
        <td>
          <button class="set-active-btn" data-dataset-key="${escapeHtml(item.key)}">Set Active</button>
          <div class="small">${escapeHtml(active)}</div>
        </td>
        <td>
          <button class="toggle-compare-btn" data-dataset-key="${escapeHtml(item.key)}">${compareSelected ? "Remove" : "Add"}</button>
          <div class="small">${compareSelected ? "Selected" : "Not selected"}</div>
        </td>
        <td><button class="inspect-dataset-btn" data-dataset-key="${escapeHtml(item.key)}">View</button></td>
        <td>${escapeHtml(item.key)}</td>
        <td>${escapeHtml(item.data_type)}</td>
        <td>${escapeHtml(item.sample_name)}</td>
        <td>${escapeHtml(item.validation_status)}</td>
        <td>${escapeHtml(item.warning_count)}</td>
        <td>${escapeHtml(item.issue_count)}</td>
      </tr>
    `;
    })
    .join("");

  body.querySelectorAll("input[name='datasetPick']").forEach((node) => {
    node.addEventListener("change", async (event) => {
      selectedDatasetKey = event.target.value;
      updateAnalysisActionState();
      appendLog(`Selected dataset: ${selectedDatasetKey}`);
      await loadDatasetDetail(selectedDatasetKey);
    });
  });

  body.querySelectorAll(".set-active-btn").forEach((node) => {
    node.addEventListener("click", async () => {
      const key = node.getAttribute("data-dataset-key");
      await onSetActiveDataset(key);
    });
  });

  body.querySelectorAll(".toggle-compare-btn").forEach((node) => {
    node.addEventListener("click", async () => {
      const key = node.getAttribute("data-dataset-key");
      await onToggleCompareDataset(key);
    });
  });

  body.querySelectorAll(".inspect-dataset-btn").forEach((node) => {
    node.addEventListener("click", async () => {
      const key = node.getAttribute("data-dataset-key");
      selectedDatasetKey = key;
      const radio = Array.from(body.querySelectorAll("input[name='datasetPick']")).find((item) => item.value === key);
      if (radio) radio.checked = true;
      updateAnalysisActionState();
      await loadDatasetDetail(key);
    });
  });

  renderAnalysisPages();
}

function renderResults(results) {
  const body = el("resultsBody");
  currentResults = results;
  if (!results.length) {
    body.innerHTML = "<tr><td colspan='10'>No results saved.</td></tr>";
    selectedResultId = null;
    currentResultDetail = null;
    setText("resultDetailInfo", "No result detail selected.");
    setHtml("resultDetailPanel", "Select a saved result to inspect processing, provenance, and validation.");
    setDiagnostic("result", {});
    renderAnalysisPages();
    return;
  }

  if (!selectedResultId || !results.some((item) => item.id === selectedResultId)) {
    selectedResultId = results[0].id;
  }
  if (currentResultDetail && currentResultDetail.result && !results.some((item) => item.id === currentResultDetail.result.id)) {
    currentResultDetail = null;
  }

  body.innerHTML = results
    .map(
      (item) => `
      <tr>
        <td>${item.id === selectedResultId ? "Selected" : ""}</td>
        <td><button class="inspect-result-btn" data-result-id="${escapeHtml(item.id)}">View</button></td>
        <td>${escapeHtml(item.id)}</td>
        <td>${escapeHtml(item.analysis_type)}</td>
        <td>${escapeHtml(item.status)}</td>
        <td>${escapeHtml(item.dataset_key)}</td>
        <td>${escapeHtml(item.validation_status)}</td>
        <td>${escapeHtml(item.calibration_state)}</td>
        <td>${escapeHtml(item.reference_state)}</td>
        <td>${escapeHtml(item.saved_at_utc)}</td>
      </tr>
    `
    )
    .join("");

  body.querySelectorAll(".inspect-result-btn").forEach((node) => {
    node.addEventListener("click", async () => {
      const resultId = node.getAttribute("data-result-id");
      selectedResultId = resultId;
      renderResults(currentResults);
      await loadResultDetail(resultId);
      const context = await refreshWorkspaceContext();
      if (!context) {
        setText(
          "homeProjectInfo",
          `Active dataset: ${currentActiveDatasetKey || "none"} | Selected result: ${selectedResultId || "none"}`
        );
      }
      renderAnalysisPages();
    });
  });
  renderAnalysisPages();
}

function renderExportableResults(results) {
  const body = el("exportResultsBody");
  exportableResults = results || [];
  if (!exportableResults.length) {
    body.innerHTML = "<tr><td colspan='6'>No saved results are currently available for export. Run analysis and save results first.</td></tr>";
    setText("exportSelectionHint", "No exportable saved results yet. Generate at least one stable result first.");
    setDisabled("exportCsvBtn", true);
    setDisabled("exportDocxBtn", true);
    return;
  }

  body.innerHTML = exportableResults
    .map(
      (item) => `
      <tr>
        <td><input type="checkbox" class="export-result-check" value="${escapeHtml(item.id)}" checked></td>
        <td>${escapeHtml(item.id)}</td>
        <td>${escapeHtml(item.analysis_type)}</td>
        <td>${escapeHtml(item.status)}</td>
        <td>${escapeHtml(item.validation_status)}</td>
        <td>${escapeHtml(item.saved_at_utc)}</td>
      </tr>
    `
    )
    .join("");
  setText(
    "exportSelectionHint",
    `Select the saved results to include. ${exportableResults.length} result(s) currently eligible for export/report generation.`
  );
  setDisabled("exportCsvBtn", false);
  setDisabled("exportDocxBtn", false);
}

function renderBatchSummaryRows(rows) {
  const body = el("batchSummaryBody");
  const items = rows || [];
  if (!items.length) {
    body.innerHTML = "<tr><td colspan='5'>No batch summary rows.</td></tr>";
    return;
  }
  body.innerHTML = items
    .map((row) => {
      return `
      <tr>
        <td>${escapeHtml(row.dataset_key)}</td>
        <td>${escapeHtml(row.execution_status)}</td>
        <td>${escapeHtml(row.validation_status)}</td>
        <td>${escapeHtml(row.result_id)}</td>
        <td>${escapeHtml(row.failure_reason)}</td>
      </tr>
    `;
    })
    .join("");
}

function renderBatchWorkspaceState(compareWorkspace) {
  const payload = compareWorkspace || {};
  const feedback = payload.batch_last_feedback || {};
  const selectedCount = (payload.selected_datasets || []).length;
  const canRun = Boolean(activeProjectId) && selectedCount > 0;
  setDisabled("runBatchBtn", !canRun);
  if (!selectedCount) {
    setText("batchInfo", "No compare-selected datasets available for batch.");
  } else if (payload.batch_run_id) {
    setText(
      "batchInfo",
      `Last batch ${payload.batch_run_id}: saved=${feedback.saved || 0}, blocked=${feedback.blocked || 0}, failed=${feedback.failed || 0}`
    );
  } else {
    setText("batchInfo", `Ready for batch run on ${selectedCount} compare-selected dataset(s).`);
  }
  setHtml(
    "compareBatchStatsPanel",
    `
    <div>
      <span class="badge badge-neutral">Selected datasets: ${selectedCount}</span>
      <span class="badge badge-ok">Saved: ${feedback.saved || 0}</span>
      <span class="badge badge-warn">Blocked: ${feedback.blocked || 0}</span>
      <span class="badge badge-fail">Failed: ${feedback.failed || 0}</span>
      <span class="badge badge-neutral">Template: ${escapeHtml(valueOr(payload.batch_template_id, "n/a"))}</span>
      <span class="badge badge-neutral">Run ID: ${escapeHtml(valueOr(payload.batch_run_id, "not run"))}</span>
    </div>
    `
  );
  renderBatchSummaryRows(payload.batch_summary || []);
  setDiagnostic("batch", {
    batch_run_id: payload.batch_run_id,
    batch_template_id: payload.batch_template_id,
    batch_template_label: payload.batch_template_label,
    batch_completed_at: payload.batch_completed_at,
    batch_last_feedback: feedback,
    batch_result_ids: payload.batch_result_ids || [],
    batch_summary: payload.batch_summary || [],
  });
}

async function refreshCompareWorkspace() {
  if (!activeProjectId) {
    setText("compareMeta", "No compare metadata loaded.");
    setHtml("compareSummaryPanel", "Compare workspace summary will appear here.");
    setHtml("compareBatchStatsPanel", "");
    renderCompareSelectionChips([]);
    setDiagnostic("compare", {});
    return;
  }
  try {
    const compare = await window.taDesktop.getCompareWorkspace(activeProjectId);
    compareSelectedDatasetKeys = new Set(compare.compare_workspace.selected_datasets || []);
    el("compareTypeSelect").value = compare.compare_workspace.analysis_type || "DSC";
    el("batchAnalysisTypeSelect").value = compare.compare_workspace.analysis_type || "DSC";
    el("compareNotes").value = compare.compare_workspace.notes || "";
    renderCompareDatasetChecks(compare.compare_workspace.selected_datasets || []);
    renderCompareWorkspaceSummary(compare.compare_workspace);
    setText(
      "compareMeta",
      `Selected datasets: ${(compare.compare_workspace.selected_datasets || []).length} | Saved at: ${valueOr(compare.compare_workspace.saved_at, "N/A")}`
    );
    if (currentDatasets.length) {
      renderDatasets(currentDatasets);
    }
    renderBatchWorkspaceState(compare.compare_workspace);
    setDiagnostic("compare", compare.compare_workspace);
  } catch (error) {
    setText("compareMeta", "Compare metadata unavailable.");
    setHtml("compareSummaryPanel", `<p class='fail'>Compare workspace read failed: ${escapeHtml(String(error))}</p>`);
    setHtml("compareBatchStatsPanel", "");
    renderCompareSelectionChips([]);
    setText("batchInfo", "Batch summary unavailable.");
    renderBatchSummaryRows([]);
    setDiagnostic("compare", { error: String(error) });
  }
}

async function refreshWorkspaceContext() {
  if (!activeProjectId) {
    setText("homeProjectInfo", "No workspace context loaded.");
    setDiagnostic("workspace", {});
    return null;
  }
  try {
    const context = await window.taDesktop.getWorkspaceContext(activeProjectId);
    applyWorkspaceContext(context);
    el("compareTypeSelect").value = context.compare_workspace.analysis_type || "DSC";
    el("batchAnalysisTypeSelect").value = context.compare_workspace.analysis_type || "DSC";
    el("compareNotes").value = context.compare_workspace.notes || "";
    renderCompareDatasetChecks(context.compare_workspace.selected_datasets || []);
    setText(
      "compareMeta",
      `Selected datasets: ${(context.compare_workspace.selected_datasets || []).length} | Saved at: ${valueOr(context.compare_workspace.saved_at, "N/A")}`
    );
    renderCompareWorkspaceSummary(context.compare_workspace);
    renderBatchWorkspaceState(context.compare_workspace);
    setDiagnostic("compare", context.compare_workspace);
    if (currentDatasets.length) {
      renderDatasets(currentDatasets);
    }
    return context;
  } catch (error) {
    setText("homeProjectInfo", `Workspace context failed: ${error}`);
    setDiagnostic("workspace", { error: String(error) });
    return null;
  }
}

async function onSetActiveDataset(datasetKey) {
  if (!activeProjectId || !datasetKey) return;
  try {
    const response = await window.taDesktop.setActiveDataset(activeProjectId, datasetKey);
    currentActiveDatasetKey = response.active_dataset_key;
    appendLog(`Active dataset set to ${response.active_dataset_key}.`);
    await refreshWorkspaceViews();
  } catch (error) {
    appendLog(`Set active dataset failed: ${error}`);
  }
}

async function updateCompareSelection(operation, datasetKeys) {
  if (!activeProjectId) return;
  const response = await window.taDesktop.updateCompareSelection(activeProjectId, operation, datasetKeys);
  compareSelectedDatasetKeys = new Set(response.compare_workspace.selected_datasets || []);
  el("compareTypeSelect").value = response.compare_workspace.analysis_type || "DSC";
  el("compareNotes").value = response.compare_workspace.notes || "";
  renderCompareDatasetChecks(response.compare_workspace.selected_datasets || []);
  setText(
    "compareMeta",
    `Selected datasets: ${(response.compare_workspace.selected_datasets || []).length} | Saved at: ${valueOr(response.compare_workspace.saved_at, "N/A")}`
  );
  renderCompareWorkspaceSummary(response.compare_workspace);
  setDiagnostic("compare", response.compare_workspace);
  renderBatchWorkspaceState(response.compare_workspace);
  renderDatasets(currentDatasets);
  await refreshWorkspaceContext();
}

async function onToggleCompareDataset(datasetKey) {
  if (!datasetKey) return;
  const operation = compareSelectedDatasetKeys.has(datasetKey) ? "remove" : "add";
  try {
    await updateCompareSelection(operation, [datasetKey]);
    appendLog(`Compare selection ${operation}: ${datasetKey}`);
  } catch (error) {
    appendLog(`Compare selection update failed: ${error}`);
  }
}

async function refreshExportPreparation() {
  if (!activeProjectId) {
    setText("exportPrepInfo", "Open or create a workspace to prepare export context.");
    setText("exportSelectionHint", "Select the saved results to include in your export package.");
    setHtml("exportPrepPanel", "Refresh export context after loading or analyzing datasets.");
    setHtml("exportActionPanel", "");
    renderExportableResults([]);
    setDiagnostic("export", {});
    return;
  }

  try {
    const prep = await window.taDesktop.getExportPreparation(activeProjectId);
    renderExportableResults(prep.exportable_results || []);
    setText(
      "exportPrepInfo",
      `Export context ready: ${(prep.exportable_results || []).length} exportable result(s), ${(prep.skipped_record_issues || []).length} skipped invalid record issue(s).`
    );
    setHtml(
      "exportPrepPanel",
      `
      ${keyGrid([
        { label: "Supported Outputs", value: valueOr((prep.supported_outputs || []).join(", "), "none") },
        { label: "Exportable Results", value: String((prep.exportable_results || []).length) },
        { label: "Skipped Invalid Records", value: String((prep.skipped_record_issues || []).length) },
        { label: "Compare Analysis", value: valueOr(prep.compare_workspace && prep.compare_workspace.analysis_type, "N/A") },
      ])}
      ${renderIssueList("Skipped record issues", prep.skipped_record_issues || [])}
      `
    );
    setDiagnostic("export", prep);
  } catch (error) {
    setText("exportPrepInfo", `Export preparation failed: ${error}`);
    setHtml("exportPrepPanel", "<p class='fail'>Export preparation unavailable.</p>");
    renderExportableResults([]);
    setDiagnostic("export", { error: String(error) });
  }
}

async function refreshStatus() {
  const bootstrap = window.taDesktop.getBackendBootstrap();
  setHtml(
    "diagBootstrap",
    `Backend URL: <code>${escapeHtml(bootstrap.backendUrl || "N/A")}</code> | Token: <strong>${bootstrap.hasToken ? "present" : "missing"}</strong>`
  );

  try {
    const health = await window.taDesktop.checkHealth();
    setText("statusHealth", `Health: ${health.status}`);
    setHtml("diagHealth", `Health: <span class="ok">${escapeHtml(health.status)}</span> (API ${escapeHtml(health.api_version)})`);
  } catch (error) {
    setText("statusHealth", "Health: failed");
    setHtml("diagHealth", `Health: <span class="fail">failed</span> (${escapeHtml(String(error))})`);
  }

  try {
    const version = await window.taDesktop.getVersion();
    setText("statusVersion", `Version: ${version.app_version}`);
    setText("licenseVersionValue", valueOr(version.app_version, "unknown"));
    setText("licenseProjectExtValue", valueOr(version.project_extension, "unknown"));
    setHtml("diagVersion", `ThermoAnalyzer app version: <strong>${escapeHtml(version.app_version)}</strong> | Project extension: <code>${escapeHtml(version.project_extension)}</code>`);
  } catch (error) {
    setText("statusVersion", "Version: failed");
    setHtml("diagVersion", `Version call failed: <span class="fail">${escapeHtml(String(error))}</span>`);
  }
}

async function refreshWorkspaceViews() {
  if (!activeProjectId) {
    currentActiveDatasetKey = null;
    compareSelectedDatasetKeys = new Set();
    currentDatasetDetail = null;
    currentResultDetail = null;
    lastAnalysisRuns.DSC = null;
    lastAnalysisRuns.TGA = null;
    currentResults = [];
    selectedDatasetKey = null;
    selectedResultId = null;
    setText("homeProjectInfo", "No workspace active.");
    setText("homeDatasetCountValue", "0");
    setText("homeResultCountValue", "0");
    setText("homeActiveDatasetValue", "none");
    setText("homeLatestResultValue", "none");
    setText("homeCompareCountValue", "0");
    setText("homeNextStepValue", "Create or open a workspace.");
    setText("homeWorkspaceSavedAtValue", "N/A");
    setText("homeStepWorkspaceStatus", "Create/open workspace");
    setText("homeStepImportStatus", "Import at least one dataset");
    setText("homeStepCompareStatus", "Select compare datasets");
    setText("homeStepRunStatus", "Run DSC/TGA analysis");
    setText("projectViewInfo", "No workspace active.");
    setText("projectDatasetCountValue", "0");
    setText("projectResultCountValue", "0");
    setText("projectHistoryCountValue", "0");
    setText("projectFigureCountValue", "0");
    setText("projectConfidenceMessage", "Open or create a workspace to establish project archive context.");
    renderDatasets([]);
    renderResults([]);
    setText("compareMeta", "No compare metadata loaded.");
    setHtml("compareSummaryPanel", "Compare workspace summary will appear here.");
    setHtml("compareSelectedDatasetsPanel", "<span class='dataset-chip'>No compare-selected datasets.</span>");
    setHtml("compareBatchStatsPanel", "");
    setText("batchInfo", "No batch run executed.");
    renderBatchSummaryRows([]);
    setText("exportPrepInfo", "Open or create a workspace to prepare export context.");
    setText("exportSelectionHint", "Select the saved results to include in your export package.");
    setHtml("exportPrepPanel", "Refresh export context after loading or analyzing datasets.");
    setHtml("exportActionPanel", "");
    setHtml("homeImportFeedbackPanel", "No import action yet.");
    setHtml("homeImportQualityPanel", "Import confidence and review guidance will appear here after dataset inspection.");
    setHtml("homeSelectedDatasetPanel", "No active dataset selected.");
    setHtml("dscActiveDatasetContextPanel", "Select a dataset from Home / Import to begin DSC context.");
    setHtml("dscMethodContextPanel", "DSC processing context will appear here.");
    setHtml("dscValidationPanel", "Validation summary will appear after dataset inspection.");
    setHtml("dscTemplateContextPanel", "Workflow template context will appear here.");
    setHtml("dscResultSummaryPanel", "No DSC result context yet.");
    setText("dscAnalysisInfo", "No DSC analysis executed yet.");
    setHtml("tgaActiveDatasetContextPanel", "Select a dataset from Home / Import to begin TGA context.");
    setHtml("tgaUnitContextPanel", "TGA unit and import-review context will appear here.");
    setHtml("tgaValidationPanel", "Validation summary will appear after dataset inspection.");
    setHtml("tgaTemplateContextPanel", "Workflow template context will appear here.");
    setHtml("tgaResultSummaryPanel", "No TGA result context yet.");
    setText("tgaAnalysisInfo", "No TGA analysis executed yet.");
    setHtml("datasetDetailPanel", "Select a dataset to inspect metadata, validation, and preview rows.");
    setHtml("resultDetailPanel", "Select a saved result to inspect processing, provenance, and validation.");
    renderExportableResults([]);
    setDiagnostic("workspace", {});
    setDiagnostic("compare", {});
    setDiagnostic("batch", {});
    setDiagnostic("export", {});
    setDiagnostic("dataset", {});
    setDiagnostic("result", {});
    setWorkflowEnabled(false);
    updateStatusWorkspace();
    return;
  }

  const context = await window.taDesktop.getWorkspaceContext(activeProjectId);
  const datasets = await window.taDesktop.listDatasets(activeProjectId);
  const results = await window.taDesktop.listResults(activeProjectId);
  applyWorkspaceContext(context);
  compareSelectedDatasetKeys = new Set((context.compare_workspace && context.compare_workspace.selected_datasets) || []);
  renderDatasets(datasets.datasets || []);
  renderResults(results.results || []);
  setWorkflowEnabled(true);

  if (selectedDatasetKey) {
    await loadDatasetDetail(selectedDatasetKey);
  }
  if (selectedResultId) {
    await loadResultDetail(selectedResultId);
  }
  el("compareTypeSelect").value = context.compare_workspace.analysis_type || "DSC";
  el("batchAnalysisTypeSelect").value = context.compare_workspace.analysis_type || "DSC";
  el("compareNotes").value = context.compare_workspace.notes || "";
  renderCompareDatasetChecks(context.compare_workspace.selected_datasets || []);
  setText(
    "compareMeta",
    `Selected datasets: ${(context.compare_workspace.selected_datasets || []).length} | Saved at: ${valueOr(context.compare_workspace.saved_at, "N/A")}`
  );
  renderCompareWorkspaceSummary(context.compare_workspace);
  setDiagnostic("compare", context.compare_workspace);
  renderBatchWorkspaceState(context.compare_workspace);
  updateAnalysisActionState();
  renderAnalysisPages();
  await refreshExportPreparation();
}

async function onNewWorkspace() {
  try {
    const created = await window.taDesktop.createWorkspace();
    activeProjectId = created.project_id;
    selectedDatasetKey = null;
    selectedResultId = null;
    activeProjectDefaultName = "thermoanalyzer_project.thermozip";
    await refreshWorkspaceViews();
    appendLog(`Created workspace ${activeProjectId}.`);
  } catch (error) {
    appendLog(`Create workspace failed: ${error}`);
  }
}

async function onOpenProject() {
  try {
    const picked = await window.taDesktop.pickProjectArchive();
    if (!picked || picked.canceled) {
      appendLog("Open project canceled.");
      return;
    }
    const loaded = await window.taDesktop.loadProjectArchive(picked.archiveBase64);
    activeProjectId = loaded.project_id;
    selectedDatasetKey = null;
    selectedResultId = null;
    activeProjectDefaultName = `thermoanalyzer_project${loaded.project_extension}`;
    await refreshWorkspaceViews();
    appendLog(`Loaded project from ${picked.filePath}.`);
  } catch (error) {
    appendLog(`Open project failed: ${error}`);
  }
}

async function onSaveProject() {
  if (!activeProjectId) {
    appendLog("Save skipped: no workspace active.");
    return;
  }
  try {
    const archive = await window.taDesktop.saveProjectArchive(activeProjectId);
    const persisted = await window.taDesktop.persistProjectArchive(
      activeProjectDefaultName || archive.file_name,
      archive.archive_base64
    );
    if (!persisted || persisted.canceled) {
      appendLog("Save workspace canceled.");
      return;
    }
    appendLog(`Saved workspace archive to ${persisted.filePath}.`);
  } catch (error) {
    appendLog(`Save workspace failed: ${error}`);
  }
}

async function onImportDataset() {
  if (!activeProjectId) {
    appendLog("Import skipped: no workspace active.");
    return;
  }
  try {
    const picked = await window.taDesktop.pickDatasetFile();
    if (!picked || picked.canceled) {
      appendLog("Import dataset canceled.");
      return;
    }
    const dataType = el("datasetTypeSelect").value;
    const imported = await window.taDesktop.importDataset(
      activeProjectId,
      picked.fileName,
      picked.fileBase64,
      dataType
    );
    setHtml(
      "homeImportFeedbackPanel",
      `
      <div>
        <span class="${toneBadgeClass(imported.validation.status)}">Validation: ${escapeHtml(valueOr(imported.validation.status, "unknown"))}</span>
        <span class="badge badge-neutral">Warnings: ${escapeHtml(valueOr(imported.validation.warning_count, "0"))}</span>
        <span class="badge badge-neutral">Issues: ${escapeHtml(valueOr(imported.validation.issue_count, "0"))}</span>
      </div>
      <p class="small">Imported <strong>${escapeHtml(imported.dataset.key)}</strong> (${escapeHtml(imported.dataset.data_type)}) from <strong>${escapeHtml(picked.fileName)}</strong>.</p>
      `
    );
    selectedDatasetKey = imported.dataset.key;
    await refreshWorkspaceViews();
    appendLog(
      `Imported dataset ${imported.dataset.key} (${imported.dataset.data_type}) from ${picked.filePath}. Validation=${imported.validation.status}`
    );
  } catch (error) {
    setHtml(
      "homeImportFeedbackPanel",
      `<span class="badge badge-fail">Import failed</span><p class="small">${escapeHtml(String(error))}</p>`
    );
    appendLog(`Import dataset failed: ${error}`);
  }
}

async function onRunAnalysis(analysisType) {
  if (!activeProjectId || !selectedDatasetKey) {
    appendLog(`Run ${analysisType} skipped: select a dataset first.`);
    return;
  }
  const infoId = analysisType === "DSC" ? "dscAnalysisInfo" : "tgaAnalysisInfo";
  try {
    const run = await window.taDesktop.runAnalysis(activeProjectId, selectedDatasetKey, analysisType);
    lastAnalysisRuns[analysisType] = {
      ...run,
      dataset_key: selectedDatasetKey,
    };
    setText(
      infoId,
      `${analysisType} on ${selectedDatasetKey}: ${run.execution_status}${run.result_id ? ` (${run.result_id})` : ""}`
    );
    if (run.result_id) selectedResultId = run.result_id;
    await refreshWorkspaceViews();
    appendLog(
      `${analysisType} on ${selectedDatasetKey}: ${run.execution_status}${run.failure_reason ? ` - ${run.failure_reason}` : ""}`
    );
  } catch (error) {
    lastAnalysisRuns[analysisType] = {
      execution_status: "failed",
      failure_reason: String(error),
      result_id: null,
      dataset_key: selectedDatasetKey,
    };
    setText(infoId, `${analysisType} failed: ${error}`);
    renderAnalysisPages();
    appendLog(`Run ${analysisType} failed: ${error}`);
  }
}

async function onSaveCompareSelection() {
  if (!activeProjectId) return;
  try {
    const payload = {
      analysis_type: el("compareTypeSelect").value,
      selected_datasets: collectCompareSelectedDatasets(),
      notes: el("compareNotes").value,
    };
    const response = await window.taDesktop.updateCompareWorkspace(activeProjectId, payload);
    compareSelectedDatasetKeys = new Set(response.compare_workspace.selected_datasets || []);
    setText(
      "compareMeta",
      `Selected datasets: ${(response.compare_workspace.selected_datasets || []).length} | Saved at: ${valueOr(response.compare_workspace.saved_at, "N/A")}`
    );
    renderCompareWorkspaceSummary(response.compare_workspace);
    setDiagnostic("compare", response.compare_workspace);
    renderBatchWorkspaceState(response.compare_workspace);
    renderDatasets(currentDatasets);
    await refreshWorkspaceContext();
    appendLog(`Saved compare workspace (${response.compare_workspace.analysis_type}) with ${response.compare_workspace.selected_datasets.length} dataset(s).`);
  } catch (error) {
    appendLog(`Save compare workspace failed: ${error}`);
  }
}

async function onAddSelectedToCompare() {
  if (!activeProjectId || !selectedDatasetKey) {
    appendLog("Add to compare skipped: select a dataset first.");
    return;
  }
  try {
    await updateCompareSelection("add", [selectedDatasetKey]);
    appendLog(`Added to compare: ${selectedDatasetKey}`);
  } catch (error) {
    appendLog(`Add to compare failed: ${error}`);
  }
}

async function onRemoveSelectedFromCompare() {
  if (!activeProjectId || !selectedDatasetKey) {
    appendLog("Remove from compare skipped: select a dataset first.");
    return;
  }
  try {
    await updateCompareSelection("remove", [selectedDatasetKey]);
    appendLog(`Removed from compare: ${selectedDatasetKey}`);
  } catch (error) {
    appendLog(`Remove from compare failed: ${error}`);
  }
}

async function onClearCompareSelection() {
  if (!activeProjectId) return;
  try {
    await updateCompareSelection("clear", []);
    appendLog("Cleared compare selected datasets.");
  } catch (error) {
    appendLog(`Clear compare selection failed: ${error}`);
  }
}

function onBatchAnalysisTypeChanged() {
  const analysisType = el("batchAnalysisTypeSelect").value;
  const templateInput = el("batchTemplateIdInput");
  if (!templateInput.value || templateInput.value === "dsc.general" || templateInput.value === "tga.general") {
    templateInput.value = analysisType === "TGA" ? "tga.general" : "dsc.general";
  }
}

async function onRunBatch() {
  if (!activeProjectId) return;
  try {
    const analysisType = el("batchAnalysisTypeSelect").value;
    const workflowTemplateId = (el("batchTemplateIdInput").value || "").trim();
    const response = await window.taDesktop.runBatch(activeProjectId, {
      analysis_type: analysisType,
      workflow_template_id: workflowTemplateId || null,
    });
    setText(
      "batchInfo",
      `Batch ${response.batch_run_id}: saved=${response.outcomes.saved}, blocked=${response.outcomes.blocked}, failed=${response.outcomes.failed}`
    );
    setDiagnostic("batch", response);
    renderBatchSummaryRows(response.batch_summary || []);
    appendLog(
      `Batch run ${response.batch_run_id} finished (saved=${response.outcomes.saved}, blocked=${response.outcomes.blocked}, failed=${response.outcomes.failed}).`
    );
    await refreshWorkspaceViews();
  } catch (error) {
    appendLog(`Batch run failed: ${error}`);
  }
}

async function onExportResultsCsv() {
  if (!activeProjectId) return;
  try {
    const selectedResultIds = collectSelectedExportResultIds();
    if (!selectedResultIds.length) {
      setHtml(
        "exportActionPanel",
        "<span class='badge badge-warn'>No results selected</span><p class='small'>Select at least one saved result before generating CSV.</p>"
      );
      return;
    }
    const artifact = await window.taDesktop.generateResultsCsv(activeProjectId, selectedResultIds);
    const saved = await window.taDesktop.persistGeneratedFile(artifact.file_name, artifact.artifact_base64);
    setHtml(
      "exportActionPanel",
      `
      <span class="badge badge-ok">CSV artifact generated</span>
      ${keyGrid([
        { label: "Artifact", value: artifact.file_name },
        { label: "Included Results", value: String((artifact.included_result_ids || []).length) },
      ])}
      `
    );
    setDiagnostic("export", { action: "results_csv", artifact });
    if (!saved || saved.canceled) {
      appendLog("Results CSV export canceled.");
      return;
    }
    appendLog(`Results CSV exported to ${saved.filePath} (${artifact.included_result_ids.length} result(s)).`);
  } catch (error) {
    appendLog(`Results CSV export failed: ${error}`);
  }
}

async function onGenerateDocxReport() {
  if (!activeProjectId) return;
  try {
    const selectedResultIds = collectSelectedExportResultIds();
    if (!selectedResultIds.length) {
      setHtml(
        "exportActionPanel",
        "<span class='badge badge-warn'>No results selected</span><p class='small'>Select at least one saved result before generating DOCX.</p>"
      );
      return;
    }
    const artifact = await window.taDesktop.generateDocxReport(activeProjectId, selectedResultIds);
    const saved = await window.taDesktop.persistGeneratedFile(artifact.file_name, artifact.artifact_base64);
    setHtml(
      "exportActionPanel",
      `
      <span class="badge badge-ok">DOCX artifact generated</span>
      ${keyGrid([
        { label: "Artifact", value: artifact.file_name },
        { label: "Included Results", value: String((artifact.included_result_ids || []).length) },
      ])}
      `
    );
    setDiagnostic("export", { action: "report_docx", artifact });
    if (!saved || saved.canceled) {
      appendLog("DOCX report save canceled.");
      return;
    }
    appendLog(`DOCX report saved to ${saved.filePath} (${artifact.included_result_ids.length} result(s)).`);
  } catch (error) {
    appendLog(`DOCX report generation failed: ${error}`);
  }
}

document.querySelectorAll(".nav-item[data-view]").forEach((node) => {
  node.addEventListener("click", () => {
    switchView(node.getAttribute("data-view"));
  });
});

el("newWorkspaceBtn").addEventListener("click", onNewWorkspace);
el("openProjectBtn").addEventListener("click", onOpenProject);
el("saveProjectBtn").addEventListener("click", onSaveProject);
el("saveProjectBtnProjectView").addEventListener("click", onSaveProject);
el("refreshWorkspaceContextBtn").addEventListener("click", refreshWorkspaceContext);
el("refreshWorkspaceContextBtnProjectView").addEventListener("click", refreshWorkspaceContext);
el("importDatasetBtn").addEventListener("click", onImportDataset);
el("runDscAnalysisBtn").addEventListener("click", () => onRunAnalysis("DSC"));
el("runTgaAnalysisBtn").addEventListener("click", () => onRunAnalysis("TGA"));
el("inspectSelectedDatasetBtn").addEventListener("click", async () => {
  if (!selectedDatasetKey) return;
  switchView("home");
  await loadDatasetDetail(selectedDatasetKey);
});
el("inspectSelectedDatasetBtn2").addEventListener("click", async () => {
  if (!selectedDatasetKey) return;
  switchView("home");
  await loadDatasetDetail(selectedDatasetKey);
});
el("refreshCompareBtn").addEventListener("click", refreshCompareWorkspace);
el("saveCompareBtn").addEventListener("click", onSaveCompareSelection);
el("addSelectedToCompareBtn").addEventListener("click", onAddSelectedToCompare);
el("removeSelectedFromCompareBtn").addEventListener("click", onRemoveSelectedFromCompare);
el("clearCompareSelectionBtn").addEventListener("click", onClearCompareSelection);
el("batchAnalysisTypeSelect").addEventListener("change", onBatchAnalysisTypeChanged);
el("runBatchBtn").addEventListener("click", onRunBatch);
el("refreshExportPrepBtn").addEventListener("click", refreshExportPreparation);
el("exportCsvBtn").addEventListener("click", onExportResultsCsv);
el("exportDocxBtn").addEventListener("click", onGenerateDocxReport);

switchView("home");
setWorkflowEnabled(false);
updateStatusWorkspace();
refreshWorkspaceViews();
refreshStatus();
