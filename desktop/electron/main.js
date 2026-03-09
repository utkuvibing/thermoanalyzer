const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const childProcess = require("child_process");
const fs = require("fs");
const net = require("net");
const path = require("path");
const crypto = require("crypto");
const { resolveBackendLaunch } = require("./backend_locator");

let backendProcess = null;
let backendPort = null;
let backendToken = null;
let backendBaseUrl = null;

function getRepoRoot() {
  return path.resolve(__dirname, "..", "..");
}

function reservePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => resolve(address.port));
    });
  });
}

async function waitForBackendReady(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${url}/health`);
      if (response.ok) {
        return;
      }
    } catch (_err) {
      // Backend not ready yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error("Backend readiness timeout.");
}

async function startBackend() {
  backendPort = await reservePort();
  backendToken = crypto.randomBytes(16).toString("hex");
  backendBaseUrl = `http://127.0.0.1:${backendPort}`;

  const launch = resolveBackendLaunch({
    isPackaged: app.isPackaged,
    env: process.env,
    platform: process.platform,
    repoRoot: getRepoRoot(),
    resourcesPath: process.resourcesPath,
    existsSync: fs.existsSync,
  });

  const spawnArgs = [
    ...launch.args,
    "--host",
    "127.0.0.1",
    "--port",
    String(backendPort),
    "--token",
    backendToken,
  ];

  process.stdout.write(`[backend] launch mode=${launch.mode} command=${launch.resolvedPath}\n`);

  backendProcess = childProcess.spawn(launch.command, spawnArgs, {
    cwd: launch.cwd,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", "pipe", "pipe"],
  });

  backendProcess.stdout.on("data", (chunk) => {
    process.stdout.write(`[backend] ${chunk}`);
  });
  backendProcess.stderr.on("data", (chunk) => {
    process.stderr.write(`[backend] ${chunk}`);
  });
  backendProcess.on("exit", (code, signal) => {
    process.stdout.write(`[backend] exited code=${code} signal=${signal}\n`);
  });

  await waitForBackendReady(backendBaseUrl, 15000);
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
}

function createWindow() {
  const window = new BrowserWindow({
    width: 980,
    height: 700,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      additionalArguments: [
        `--ta-backend-url=${backendBaseUrl}`,
        `--ta-backend-token=${backendToken}`,
      ],
    },
  });
  window.loadFile(path.join(__dirname, "index.html"));
}

ipcMain.handle("ta:pick-project-archive", async () => {
  const result = await dialog.showOpenDialog({
    title: "Open ThermoAnalyzer Project",
    properties: ["openFile"],
    filters: [{ name: "ThermoAnalyzer Project", extensions: ["thermozip"] }],
  });

  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true };
  }

  const filePath = result.filePaths[0];
  const fileBuffer = fs.readFileSync(filePath);
  return {
    canceled: false,
    filePath,
    archiveBase64: fileBuffer.toString("base64"),
  };
});

ipcMain.handle("ta:save-project-archive", async (_event, payload) => {
  const defaultName = (payload && payload.defaultName) || "thermoanalyzer_project.thermozip";
  const archiveBase64 = payload && payload.archiveBase64;
  if (!archiveBase64) {
    throw new Error("Missing archiveBase64 payload.");
  }

  const result = await dialog.showSaveDialog({
    title: "Save ThermoAnalyzer Project",
    defaultPath: defaultName,
    filters: [{ name: "ThermoAnalyzer Project", extensions: ["thermozip"] }],
  });
  if (result.canceled || !result.filePath) {
    return { canceled: true };
  }

  const fileBuffer = Buffer.from(archiveBase64, "base64");
  fs.writeFileSync(result.filePath, fileBuffer);
  return { canceled: false, filePath: result.filePath };
});

ipcMain.handle("ta:save-generated-file", async (_event, payload) => {
  const defaultName = (payload && payload.defaultName) || "thermoanalyzer_export.bin";
  const artifactBase64 = payload && payload.artifactBase64;
  if (!artifactBase64) {
    throw new Error("Missing artifactBase64 payload.");
  }

  const extension = path.extname(defaultName).toLowerCase();
  let filters = [{ name: "All Files", extensions: ["*"] }];
  if (extension === ".csv") {
    filters = [{ name: "CSV", extensions: ["csv"] }];
  } else if (extension === ".docx") {
    filters = [{ name: "Word Document", extensions: ["docx"] }];
  }

  const result = await dialog.showSaveDialog({
    title: "Save Export/Report",
    defaultPath: defaultName,
    filters,
  });
  if (result.canceled || !result.filePath) {
    return { canceled: true };
  }

  const fileBuffer = Buffer.from(artifactBase64, "base64");
  fs.writeFileSync(result.filePath, fileBuffer);
  return { canceled: false, filePath: result.filePath };
});

ipcMain.handle("ta:pick-dataset-file", async () => {
  const result = await dialog.showOpenDialog({
    title: "Import Dataset",
    properties: ["openFile"],
    filters: [
      { name: "Thermal Data", extensions: ["csv", "txt", "tsv", "xlsx", "xls"] },
      { name: "All Files", extensions: ["*"] },
    ],
  });
  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true };
  }

  const filePath = result.filePaths[0];
  const fileBuffer = fs.readFileSync(filePath);
  return {
    canceled: false,
    filePath,
    fileName: path.basename(filePath),
    fileBase64: fileBuffer.toString("base64"),
  };
});

app.whenReady().then(async () => {
  try {
    await startBackend();
    createWindow();
  } catch (error) {
    dialog.showErrorBox(
      "ThermoAnalyzer Desktop Bootstrap",
      `Backend startup failed.\n\n${error}`
    );
    app.quit();
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopBackend();
});
