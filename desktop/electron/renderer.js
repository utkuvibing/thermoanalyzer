let activeProjectId = null;
let activeProjectDefaultName = "thermoanalyzer_project.thermozip";
let selectedDatasetKey = null;
let selectedResultId = null;
let currentDatasets = [];
let exportableResults = [];

function setText(id, text) {
  const node = document.getElementById(id);
  if (node) node.textContent = text;
}

function setHtml(id, html) {
  const node = document.getElementById(id);
  if (node) node.innerHTML = html;
}

function appendLog(message) {
  const node = document.getElementById("log");
  const now = new Date().toLocaleTimeString();
  node.textContent = `${node.textContent}\n[${now}] ${message}`.trim();
}

function setWorkflowEnabled(enabled) {
  document.getElementById("saveProjectBtn").disabled = !enabled;
  document.getElementById("importDatasetBtn").disabled = !enabled;
  document.getElementById("runAnalysisBtn").disabled = !enabled || !selectedDatasetKey;
  document.getElementById("refreshCompareBtn").disabled = !enabled;
  document.getElementById("saveCompareBtn").disabled = !enabled;
  document.getElementById("refreshExportPrepBtn").disabled = !enabled;
  document.getElementById("exportCsvBtn").disabled = !enabled;
  document.getElementById("exportDocxBtn").disabled = !enabled;
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

function renderCompareDatasetChecks(selectedDatasets) {
  const container = document.getElementById("compareDatasetChecks");
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
    setText(
      "datasetDetailInfo",
      `Dataset ${detail.dataset.key} | Type ${detail.dataset.data_type} | Validation ${detail.validation.status}`
    );
    const payload = {
      validation: detail.validation,
      metadata: detail.metadata,
      units: detail.units,
      original_columns: detail.original_columns,
      data_preview: detail.data_preview,
      compare_selected: detail.compare_selected,
    };
    setText("datasetDetail", safeJson(payload));
  } catch (error) {
    setText("datasetDetailInfo", `Dataset detail failed: ${error}`);
    setText("datasetDetail", "");
  }
}

async function loadResultDetail(resultId) {
  if (!activeProjectId || !resultId) return;
  try {
    const detail = await window.taDesktop.getResultDetail(activeProjectId, resultId);
    setText(
      "resultDetailInfo",
      `Result ${detail.result.id} | ${detail.result.analysis_type} | status=${detail.result.status}`
    );
    const payload = {
      summary: detail.summary,
      processing: detail.processing,
      validation: detail.validation,
      provenance: detail.provenance,
      review: detail.review,
      row_count: detail.row_count,
      rows_preview: detail.rows_preview,
    };
    setText("resultDetail", safeJson(payload));
  } catch (error) {
    setText("resultDetailInfo", `Result detail failed: ${error}`);
    setText("resultDetail", "");
  }
}

function renderDatasets(datasets) {
  const body = document.getElementById("datasetsBody");
  currentDatasets = datasets;
  if (!datasets.length) {
    body.innerHTML = "<tr><td colspan='8'>No datasets loaded.</td></tr>";
    selectedDatasetKey = null;
    document.getElementById("runAnalysisBtn").disabled = true;
    setText("datasetDetailInfo", "No dataset detail selected.");
    setText("datasetDetail", "");
    renderCompareDatasetChecks([]);
    return;
  }

  if (!selectedDatasetKey || !datasets.some((item) => item.key === selectedDatasetKey)) {
    selectedDatasetKey = datasets[0].key;
  }

  body.innerHTML = datasets
    .map((item) => {
      const checked = item.key === selectedDatasetKey ? "checked" : "";
      return `
      <tr>
        <td><input type="radio" name="datasetPick" value="${escapeHtml(item.key)}" ${checked}></td>
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
      document.getElementById("runAnalysisBtn").disabled = !activeProjectId || !selectedDatasetKey;
      appendLog(`Selected dataset: ${selectedDatasetKey}`);
      await loadDatasetDetail(selectedDatasetKey);
    });
  });

  body.querySelectorAll(".inspect-dataset-btn").forEach((node) => {
    node.addEventListener("click", async () => {
      const key = node.getAttribute("data-dataset-key");
      selectedDatasetKey = key;
      const radio = Array.from(body.querySelectorAll("input[name='datasetPick']")).find((item) => item.value === key);
      if (radio) radio.checked = true;
      await loadDatasetDetail(key);
    });
  });
}

function renderResults(results) {
  const body = document.getElementById("resultsBody");
  if (!results.length) {
    body.innerHTML = "<tr><td colspan='9'>No results saved.</td></tr>";
    selectedResultId = null;
    setText("resultDetailInfo", "No result detail selected.");
    setText("resultDetail", "");
    return;
  }

  if (!selectedResultId || !results.some((item) => item.id === selectedResultId)) {
    selectedResultId = results[0].id;
  }

  body.innerHTML = results
    .map(
      (item) => `
      <tr>
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
      await loadResultDetail(resultId);
    });
  });
}

function renderExportableResults(results) {
  const body = document.getElementById("exportResultsBody");
  exportableResults = results || [];
  if (!exportableResults.length) {
    body.innerHTML = "<tr><td colspan='6'>No exportable saved results.</td></tr>";
    document.getElementById("exportCsvBtn").disabled = true;
    document.getElementById("exportDocxBtn").disabled = true;
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
  document.getElementById("exportCsvBtn").disabled = false;
  document.getElementById("exportDocxBtn").disabled = false;
}

async function refreshCompareWorkspace() {
  if (!activeProjectId) {
    setText("compareSummary", "");
    return;
  }
  try {
    const compare = await window.taDesktop.getCompareWorkspace(activeProjectId);
    document.getElementById("compareTypeSelect").value = compare.compare_workspace.analysis_type || "DSC";
    document.getElementById("compareNotes").value = compare.compare_workspace.notes || "";
    renderCompareDatasetChecks(compare.compare_workspace.selected_datasets || []);
    setText("compareSummary", safeJson(compare.compare_workspace));
  } catch (error) {
    setText("compareSummary", `Compare workspace read failed: ${error}`);
  }
}

async function refreshExportPreparation() {
  if (!activeProjectId) {
    setText("exportPrepInfo", "No export preparation data loaded.");
    setText("exportPrepSummary", "");
    setText("exportActionSummary", "");
    renderExportableResults([]);
    return;
  }

  try {
    const prep = await window.taDesktop.getExportPreparation(activeProjectId);
    renderExportableResults(prep.exportable_results || []);
    setText(
      "exportPrepInfo",
      `Exportable saved results: ${(prep.exportable_results || []).length} | Skipped invalid records: ${(prep.skipped_record_issues || []).length}`
    );
    const prepSummary = {
      supported_outputs: prep.supported_outputs,
      summary: prep.summary,
      branding: prep.branding,
      compare_workspace: prep.compare_workspace,
      skipped_record_issues: prep.skipped_record_issues,
    };
    setText("exportPrepSummary", safeJson(prepSummary));
  } catch (error) {
    setText("exportPrepInfo", `Export preparation failed: ${error}`);
    setText("exportPrepSummary", "");
    renderExportableResults([]);
  }
}

async function refreshStatus() {
  const bootstrap = window.taDesktop.getBackendBootstrap();
  setHtml(
    "bootstrap",
    `Backend URL: <code>${bootstrap.backendUrl || "N/A"}</code> | Token: <strong>${bootstrap.hasToken ? "present" : "missing"}</strong>`
  );

  try {
    const health = await window.taDesktop.checkHealth();
    setHtml("health", `Health: <span class="ok">${health.status}</span> (API ${health.api_version})`);
  } catch (error) {
    setHtml("health", `Health: <span class="fail">failed</span> (${error})`);
  }

  try {
    const version = await window.taDesktop.getVersion();
    setHtml(
      "version",
      `ThermoAnalyzer app version: <strong>${version.app_version}</strong> | Project extension: <code>${version.project_extension}</code>`
    );
  } catch (error) {
    setHtml("version", `Version call failed: <span class="fail">${error}</span>`);
  }
}

async function refreshWorkspaceViews() {
  if (!activeProjectId) {
    setText("projectInfo", "No workspace active.");
    setText("projectSummary", "");
    renderDatasets([]);
    renderResults([]);
    setText("compareSummary", "");
    setText("exportPrepInfo", "No export preparation data loaded.");
    setText("exportPrepSummary", "");
    setText("exportActionSummary", "");
    renderExportableResults([]);
    setWorkflowEnabled(false);
    return;
  }

  const summary = await window.taDesktop.getWorkspaceSummary(activeProjectId);
  const datasets = await window.taDesktop.listDatasets(activeProjectId);
  const results = await window.taDesktop.listResults(activeProjectId);
  setText("projectInfo", `Workspace: ${activeProjectId}`);
  setText("projectSummary", JSON.stringify(summary.summary, null, 2));
  renderDatasets(datasets.datasets || []);
  renderResults(results.results || []);
  setWorkflowEnabled(true);

  if (selectedDatasetKey) {
    await loadDatasetDetail(selectedDatasetKey);
  }
  if (selectedResultId) {
    await loadResultDetail(selectedResultId);
  }
  await refreshCompareWorkspace();
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
    const dataType = document.getElementById("datasetTypeSelect").value;
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

async function onRunAnalysis() {
  if (!activeProjectId || !selectedDatasetKey) {
    appendLog("Run analysis skipped: select a dataset first.");
    return;
  }
  try {
    const analysisType = document.getElementById("analysisTypeSelect").value;
    const run = await window.taDesktop.runAnalysis(activeProjectId, selectedDatasetKey, analysisType);
    setText(
      "analysisInfo",
      `Analysis ${analysisType} on ${selectedDatasetKey}: ${run.execution_status}${run.result_id ? ` (${run.result_id})` : ""}`
    );
    setText("analysisSummary", JSON.stringify(run, null, 2));
    if (run.result_id) selectedResultId = run.result_id;
    await refreshWorkspaceViews();
    appendLog(
      `Analysis ${analysisType} on ${selectedDatasetKey}: ${run.execution_status}${run.failure_reason ? ` - ${run.failure_reason}` : ""}`
    );
  } catch (error) {
    appendLog(`Run analysis failed: ${error}`);
  }
}

async function onSaveCompareSelection() {
  if (!activeProjectId) return;
  try {
    const payload = {
      analysis_type: document.getElementById("compareTypeSelect").value,
      selected_datasets: collectCompareSelectedDatasets(),
      notes: document.getElementById("compareNotes").value,
    };
    const response = await window.taDesktop.updateCompareWorkspace(activeProjectId, payload);
    setText("compareSummary", safeJson(response.compare_workspace));
    appendLog(`Saved compare workspace (${response.compare_workspace.analysis_type}) with ${response.compare_workspace.selected_datasets.length} dataset(s).`);
  } catch (error) {
    appendLog(`Save compare workspace failed: ${error}`);
  }
}

async function onExportResultsCsv() {
  if (!activeProjectId) return;
  try {
    const selectedResultIds = collectSelectedExportResultIds();
    const artifact = await window.taDesktop.generateResultsCsv(activeProjectId, selectedResultIds);
    const saved = await window.taDesktop.persistGeneratedFile(artifact.file_name, artifact.artifact_base64);
    setText("exportActionSummary", safeJson(artifact));
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
    setText("exportActionSummary", safeJson(artifact));
    if (!saved || saved.canceled) {
      appendLog("DOCX report save canceled.");
      return;
    }
    appendLog(`DOCX report saved to ${saved.filePath} (${artifact.included_result_ids.length} result(s)).`);
  } catch (error) {
    appendLog(`DOCX report generation failed: ${error}`);
  }
}

document.getElementById("newWorkspaceBtn").addEventListener("click", onNewWorkspace);
document.getElementById("openProjectBtn").addEventListener("click", onOpenProject);
document.getElementById("saveProjectBtn").addEventListener("click", onSaveProject);
document.getElementById("importDatasetBtn").addEventListener("click", onImportDataset);
document.getElementById("runAnalysisBtn").addEventListener("click", onRunAnalysis);
document.getElementById("refreshCompareBtn").addEventListener("click", refreshCompareWorkspace);
document.getElementById("saveCompareBtn").addEventListener("click", onSaveCompareSelection);
document.getElementById("refreshExportPrepBtn").addEventListener("click", refreshExportPreparation);
document.getElementById("exportCsvBtn").addEventListener("click", onExportResultsCsv);
document.getElementById("exportDocxBtn").addEventListener("click", onGenerateDocxReport);

setWorkflowEnabled(false);
refreshStatus();
