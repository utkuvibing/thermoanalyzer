let activeProjectId = null;
let activeProjectDefaultName = "thermoanalyzer_project.thermozip";
let selectedDatasetKey = null;
let selectedResultId = null;
let currentDatasets = [];
let currentResults = [];
let exportableResults = [];
let currentActiveDatasetKey = null;
let compareSelectedDatasetKeys = new Set();

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
  setText(
    "projectViewInfo",
    `Workspace ${activeProjectId} | figures=${context.summary.figure_count} | history=${context.summary.analysis_history_count}`
  );
  setText("homeActiveDatasetValue", currentActiveDatasetKey || "none");
  setText("homeLatestResultValue", latestResultText);
  setText("homeCompareCountValue", String(compareCount));
  setText("homeWorkspaceSavedAtValue", valueOr(compareWorkspace.saved_at, "N/A"));
  setText(
    "compareMeta",
    `Selected datasets: ${compareCount} | Saved at: ${valueOr(compareWorkspace.saved_at, "N/A")}`
  );
  setHtml(
    "compareSummaryPanel",
    `
    ${keyGrid([
      { label: "Analysis Type", value: valueOr(compareWorkspace.analysis_type, "DSC") },
      { label: "Selected Count", value: String(compareCount) },
      { label: "Saved At", value: valueOr(compareWorkspace.saved_at, "N/A") },
      { label: "Batch Run ID", value: valueOr(compareWorkspace.batch_run_id, "none") },
      { label: "Batch Template", value: valueOr(compareWorkspace.batch_template_id, "none") },
      { label: "Notes", value: valueOr(compareWorkspace.notes, "(empty)") },
    ])}
    `
  );
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
    container.innerHTML = "No datasets available.";
    return;
  }

  const selected = new Set(selectedDatasets || []);
  container.innerHTML = currentDatasets
    .map((dataset) => {
      const checked = selected.has(dataset.key) ? "checked" : "";
      return `<label style="display:block;"><input type="checkbox" class="compare-dataset-check" value="${escapeHtml(dataset.key)}" ${checked}> ${escapeHtml(dataset.key)} (${escapeHtml(dataset.data_type)})</label>`;
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
    const validation = detail.validation || {};
    setText(
      "datasetDetailInfo",
      `Dataset ${detail.dataset.key} | Type ${detail.dataset.data_type} | Validation ${validation.status || "unknown"}`
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
  } catch (error) {
    setText("datasetDetailInfo", `Dataset detail failed: ${error}`);
    setHtml("datasetDetailPanel", "<p class='fail'>Dataset detail unavailable.</p>");
    setDiagnostic("dataset", { error: String(error) });
  }
}

async function loadResultDetail(resultId) {
  if (!activeProjectId || !resultId) return;
  try {
    const detail = await window.taDesktop.getResultDetail(activeProjectId, resultId);
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
  } catch (error) {
    setText("resultDetailInfo", `Result detail failed: ${error}`);
    setHtml("resultDetailPanel", "<p class='fail'>Result detail unavailable.</p>");
    setDiagnostic("result", { error: String(error) });
  }
}

function renderDatasets(datasets) {
  const body = el("datasetsBody");
  currentDatasets = datasets;
  if (!datasets.length) {
    body.innerHTML = "<tr><td colspan='10'>No datasets loaded.</td></tr>";
    selectedDatasetKey = null;
    updateAnalysisActionState();
    setText("datasetDetailInfo", "No dataset detail selected.");
    setHtml("datasetDetailPanel", "Select a dataset to inspect metadata, validation, and preview rows.");
    setDiagnostic("dataset", {});
    renderCompareDatasetChecks([]);
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
}

function renderResults(results) {
  const body = el("resultsBody");
  currentResults = results;
  if (!results.length) {
    body.innerHTML = "<tr><td colspan='10'>No results saved.</td></tr>";
    selectedResultId = null;
    setText("resultDetailInfo", "No result detail selected.");
    setHtml("resultDetailPanel", "Select a saved result to inspect processing, provenance, and validation.");
    setDiagnostic("result", {});
    return;
  }

  if (!selectedResultId || !results.some((item) => item.id === selectedResultId)) {
    selectedResultId = results[0].id;
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
    });
  });
}

function renderExportableResults(results) {
  const body = el("exportResultsBody");
  exportableResults = results || [];
  if (!exportableResults.length) {
    body.innerHTML = "<tr><td colspan='6'>No exportable saved results.</td></tr>";
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
    setHtml(
      "compareSummaryPanel",
      keyGrid([
        { label: "Analysis Type", value: valueOr(compare.compare_workspace.analysis_type, "DSC") },
        { label: "Selected Count", value: String((compare.compare_workspace.selected_datasets || []).length) },
        { label: "Saved At", value: valueOr(compare.compare_workspace.saved_at, "N/A") },
        { label: "Batch Run ID", value: valueOr(compare.compare_workspace.batch_run_id, "none") },
      ])
    );
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
    setHtml(
      "compareSummaryPanel",
      keyGrid([
        { label: "Analysis Type", value: valueOr(context.compare_workspace.analysis_type, "DSC") },
        { label: "Selected Count", value: String((context.compare_workspace.selected_datasets || []).length) },
        { label: "Saved At", value: valueOr(context.compare_workspace.saved_at, "N/A") },
        { label: "Batch Run ID", value: valueOr(context.compare_workspace.batch_run_id, "none") },
      ])
    );
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
  setHtml(
    "compareSummaryPanel",
    keyGrid([
      { label: "Analysis Type", value: valueOr(response.compare_workspace.analysis_type, "DSC") },
      { label: "Selected Count", value: String((response.compare_workspace.selected_datasets || []).length) },
      { label: "Saved At", value: valueOr(response.compare_workspace.saved_at, "N/A") },
      { label: "Batch Run ID", value: valueOr(response.compare_workspace.batch_run_id, "none") },
    ])
  );
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
    setText("exportPrepInfo", "No export preparation data loaded.");
    setHtml("exportPrepPanel", "Export summary metadata will appear here.");
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
      `Exportable saved results: ${(prep.exportable_results || []).length} | Skipped invalid records: ${(prep.skipped_record_issues || []).length}`
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
    currentResults = [];
    selectedDatasetKey = null;
    selectedResultId = null;
    setText("homeProjectInfo", "No workspace active.");
    setText("homeActiveDatasetValue", "none");
    setText("homeLatestResultValue", "none");
    setText("homeCompareCountValue", "0");
    setText("homeWorkspaceSavedAtValue", "N/A");
    setText("projectViewInfo", "No workspace active.");
    renderDatasets([]);
    renderResults([]);
    setText("compareMeta", "No compare metadata loaded.");
    setHtml("compareSummaryPanel", "Compare workspace summary will appear here.");
    setText("batchInfo", "No batch run executed.");
    renderBatchSummaryRows([]);
    setText("exportPrepInfo", "No export preparation data loaded.");
    setHtml("exportPrepPanel", "Export summary metadata will appear here.");
    setHtml("exportActionPanel", "");
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
  setHtml(
    "compareSummaryPanel",
    keyGrid([
      { label: "Analysis Type", value: valueOr(context.compare_workspace.analysis_type, "DSC") },
      { label: "Selected Count", value: String((context.compare_workspace.selected_datasets || []).length) },
      { label: "Saved At", value: valueOr(context.compare_workspace.saved_at, "N/A") },
      { label: "Batch Run ID", value: valueOr(context.compare_workspace.batch_run_id, "none") },
    ])
  );
  setDiagnostic("compare", context.compare_workspace);
  renderBatchWorkspaceState(context.compare_workspace);
  updateAnalysisActionState();
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
    selectedDatasetKey = imported.dataset.key;
    await refreshWorkspaceViews();
    appendLog(
      `Imported dataset ${imported.dataset.key} (${imported.dataset.data_type}) from ${picked.filePath}. Validation=${imported.validation.status}`
    );
  } catch (error) {
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
    setText(infoId, `${analysisType} failed: ${error}`);
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
    setHtml(
      "compareSummaryPanel",
      keyGrid([
        { label: "Analysis Type", value: valueOr(response.compare_workspace.analysis_type, "DSC") },
        { label: "Selected Count", value: String((response.compare_workspace.selected_datasets || []).length) },
        { label: "Saved At", value: valueOr(response.compare_workspace.saved_at, "N/A") },
        { label: "Batch Run ID", value: valueOr(response.compare_workspace.batch_run_id, "none") },
      ])
    );
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
    const artifact = await window.taDesktop.generateResultsCsv(activeProjectId, selectedResultIds);
    const saved = await window.taDesktop.persistGeneratedFile(artifact.file_name, artifact.artifact_base64);
    setHtml(
      "exportActionPanel",
      keyGrid([
        { label: "Last Artifact", value: artifact.file_name },
        { label: "Included Results", value: String((artifact.included_result_ids || []).length) },
      ])
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
    const artifact = await window.taDesktop.generateDocxReport(activeProjectId, selectedResultIds);
    const saved = await window.taDesktop.persistGeneratedFile(artifact.file_name, artifact.artifact_base64);
    setHtml(
      "exportActionPanel",
      keyGrid([
        { label: "Last Artifact", value: artifact.file_name },
        { label: "Included Results", value: String((artifact.included_result_ids || []).length) },
      ])
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
