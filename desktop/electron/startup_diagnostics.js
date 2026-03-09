const fs = require("fs");
const os = require("os");
const path = require("path");

function _utcStamp() {
  return new Date().toISOString();
}

function _fileStamp() {
  return _utcStamp().replace(/[:.]/g, "-");
}

function _safeErrorText(error) {
  if (!error) {
    return "Unknown error";
  }
  if (error instanceof Error) {
    return `${error.name}: ${error.message}`;
  }
  return String(error);
}

function createStartupDiagnostics(options) {
  const userDataPath = options.userDataPath || process.cwd();
  const logsDir = path.join(userDataPath, "logs");
  fs.mkdirSync(logsDir, { recursive: true });

  const logPath = path.join(logsDir, `startup-${_fileStamp()}.log`);

  function appendLine(message) {
    const line = `[${_utcStamp()}] ${message}`;
    fs.appendFileSync(logPath, `${line}${os.EOL}`, "utf8");
  }

  appendLine("ThermoAnalyzer Desktop startup diagnostics");
  appendLine(`app_name=${options.appName || "ThermoAnalyzer Desktop"}`);
  appendLine(`app_version=${options.appVersion || "unknown"}`);
  appendLine(`mode=${options.isPackaged ? "packaged" : "development"}`);
  appendLine(`platform=${options.platform || process.platform}`);
  appendLine(`node_version=${process.version}`);
  appendLine(`electron_version=${process.versions.electron || "unknown"}`);
  appendLine(`chrome_version=${process.versions.chrome || "unknown"}`);

  function log(message) {
    appendLine(message);
  }

  function logError(label, error) {
    appendLine(`${label}: ${_safeErrorText(error)}`);
    if (error && error.stack) {
      appendLine(`stack=${String(error.stack).replace(/\r?\n/g, " | ")}`);
    }
  }

  function logBackendOutput(streamName, chunk) {
    const text = String(chunk || "");
    if (!text.trim()) {
      return;
    }
    text.split(/\r?\n/).forEach((line) => {
      const trimmed = line.trim();
      if (trimmed) {
        appendLine(`${streamName}: ${trimmed}`);
      }
    });
  }

  function recordFailure(error) {
    logError("startup_failure", error);
    return {
      reason: _safeErrorText(error),
      logPath,
    };
  }

  return {
    logPath,
    log,
    logError,
    logBackendOutput,
    recordFailure,
  };
}

module.exports = {
  createStartupDiagnostics,
};
