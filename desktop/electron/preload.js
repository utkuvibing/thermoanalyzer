const { contextBridge, ipcRenderer } = require("electron");

function readArgValue(name) {
  const prefix = `--${name}=`;
  const token = process.argv.find((item) => item.startsWith(prefix));
  return token ? token.slice(prefix.length) : "";
}

const backendUrl = readArgValue("ta-backend-url");
const backendToken = readArgValue("ta-backend-token");

async function apiCall(pathname, options) {
  const headers = {
    "Content-Type": "application/json",
    "X-TA-Token": backendToken,
    ...(options && options.headers ? options.headers : {}),
  };
  const response = await fetch(`${backendUrl}${pathname}`, {
    ...(options || {}),
    headers,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload && payload.detail ? payload.detail : `${response.status}`;
    throw new Error(detail);
  }
  return payload;
}

contextBridge.exposeInMainWorld("taDesktop", {
  getBackendBootstrap() {
    return {
      backendUrl,
      hasToken: Boolean(backendToken),
    };
  },
  async checkHealth() {
    const response = await fetch(`${backendUrl}/health`);
    if (!response.ok) {
      throw new Error(`Health check failed (${response.status})`);
    }
    return response.json();
  },
  async getVersion() {
    return apiCall("/version", { method: "GET" });
  },
  async createWorkspace() {
    return apiCall("/workspace/new", { method: "POST" });
  },
  async getWorkspaceSummary(projectId) {
    return apiCall(`/workspace/${encodeURIComponent(projectId)}`, { method: "GET" });
  },
  async getWorkspaceContext(projectId) {
    return apiCall(`/workspace/${encodeURIComponent(projectId)}/context`, { method: "GET" });
  },
  async listDatasets(projectId) {
    return apiCall(`/workspace/${encodeURIComponent(projectId)}/datasets`, { method: "GET" });
  },
  async setActiveDataset(projectId, datasetKey) {
    return apiCall(`/workspace/${encodeURIComponent(projectId)}/active-dataset`, {
      method: "PUT",
      body: JSON.stringify({ dataset_key: datasetKey }),
    });
  },
  async getDatasetDetail(projectId, datasetKey) {
    return apiCall(
      `/workspace/${encodeURIComponent(projectId)}/datasets/${encodeURIComponent(datasetKey)}`,
      { method: "GET" }
    );
  },
  async listResults(projectId) {
    return apiCall(`/workspace/${encodeURIComponent(projectId)}/results`, { method: "GET" });
  },
  async getResultDetail(projectId, resultId) {
    return apiCall(
      `/workspace/${encodeURIComponent(projectId)}/results/${encodeURIComponent(resultId)}`,
      { method: "GET" }
    );
  },
  async getCompareWorkspace(projectId) {
    return apiCall(`/workspace/${encodeURIComponent(projectId)}/compare`, { method: "GET" });
  },
  async updateCompareWorkspace(projectId, payload) {
    return apiCall(`/workspace/${encodeURIComponent(projectId)}/compare`, {
      method: "PUT",
      body: JSON.stringify(payload || {}),
    });
  },
  async updateCompareSelection(projectId, operation, datasetKeys) {
    return apiCall(`/workspace/${encodeURIComponent(projectId)}/compare/selection`, {
      method: "POST",
      body: JSON.stringify({
        operation,
        dataset_keys: datasetKeys || null,
      }),
    });
  },
  async getExportPreparation(projectId) {
    return apiCall(`/workspace/${encodeURIComponent(projectId)}/exports/preparation`, { method: "GET" });
  },
  async generateResultsCsv(projectId, selectedResultIds) {
    return apiCall(`/workspace/${encodeURIComponent(projectId)}/exports/results-csv`, {
      method: "POST",
      body: JSON.stringify({ selected_result_ids: selectedResultIds || null }),
    });
  },
  async generateDocxReport(projectId, selectedResultIds) {
    return apiCall(`/workspace/${encodeURIComponent(projectId)}/exports/report-docx`, {
      method: "POST",
      body: JSON.stringify({ selected_result_ids: selectedResultIds || null }),
    });
  },
  async pickProjectArchive() {
    return ipcRenderer.invoke("ta:pick-project-archive");
  },
  async pickDatasetFile() {
    return ipcRenderer.invoke("ta:pick-dataset-file");
  },
  async loadProjectArchive(archiveBase64) {
    return apiCall("/project/load", {
      method: "POST",
      body: JSON.stringify({ archive_base64: archiveBase64 }),
    });
  },
  async saveProjectArchive(projectId) {
    return apiCall("/project/save", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId }),
    });
  },
  async importDataset(projectId, fileName, fileBase64, dataType) {
    return apiCall("/dataset/import", {
      method: "POST",
      body: JSON.stringify({
        project_id: projectId,
        file_name: fileName,
        file_base64: fileBase64,
        data_type: dataType || null,
      }),
    });
  },
  async runAnalysis(projectId, datasetKey, analysisType) {
    return apiCall("/analysis/run", {
      method: "POST",
      body: JSON.stringify({
        project_id: projectId,
        dataset_key: datasetKey,
        analysis_type: analysisType,
      }),
    });
  },
  async persistProjectArchive(defaultName, archiveBase64) {
    return ipcRenderer.invoke("ta:save-project-archive", {
      defaultName,
      archiveBase64,
    });
  },
  async persistGeneratedFile(defaultName, artifactBase64) {
    return ipcRenderer.invoke("ta:save-generated-file", {
      defaultName,
      artifactBase64,
    });
  },
});
