const path = require("path");

function _defaultPython(platform) {
  return platform === "win32" ? "python" : "python3";
}

function _backendExecutableName(platform) {
  return platform === "win32" ? "thermoanalyzer_backend.exe" : "thermoanalyzer_backend";
}

function resolveBackendLaunch(options) {
  const {
    isPackaged,
    env,
    platform,
    repoRoot,
    resourcesPath,
    existsSync,
  } = options;

  if (!isPackaged) {
    const pythonExe = env.TA_PYTHON && env.TA_PYTHON.trim() ? env.TA_PYTHON.trim() : _defaultPython(platform);
    return {
      mode: "development",
      command: pythonExe,
      args: [path.join(repoRoot, "backend", "main.py")],
      cwd: repoRoot,
      resolvedPath: pythonExe,
      candidates: [],
    };
  }

  const exeName = _backendExecutableName(platform);
  const candidates = [];
  if (env.TA_BACKEND_EXE && env.TA_BACKEND_EXE.trim()) {
    candidates.push(env.TA_BACKEND_EXE.trim());
  } else {
    candidates.push(path.join(resourcesPath, "backend", exeName));
    candidates.push(path.join(resourcesPath, "backend", "thermoanalyzer_backend", exeName));
  }

  const check = typeof existsSync === "function" ? existsSync : () => true;
  const resolved = candidates.find((item) => check(item));
  if (!resolved) {
    throw new Error(
      `Bundled backend executable was not found. Checked: ${candidates.join("; ")}`
    );
  }

  return {
    mode: "packaged",
    command: resolved,
    args: [],
    cwd: path.dirname(resolved),
    resolvedPath: resolved,
    candidates,
  };
}

module.exports = {
  resolveBackendLaunch,
};
