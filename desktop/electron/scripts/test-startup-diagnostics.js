const assert = require("assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { createStartupDiagnostics } = require("../startup_diagnostics");

function run() {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "ta-startup-diag-"));
  try {
    const diagnostics = createStartupDiagnostics({
      appName: "ThermoAnalyzer Desktop",
      appVersion: "0.1.0-test",
      isPackaged: true,
      platform: "win32",
      userDataPath: tempRoot,
    });

    diagnostics.log("custom_message=true");
    diagnostics.logBackendOutput("backend_stdout", "line-1\nline-2");
    const failure = diagnostics.recordFailure(new Error("simulated startup failure"));

    assert.strictEqual(failure.logPath, diagnostics.logPath);
    assert.ok(String(failure.reason).includes("simulated startup failure"));
    assert.ok(fs.existsSync(diagnostics.logPath), "diagnostics log should be created");

    const content = fs.readFileSync(diagnostics.logPath, "utf8");
    assert.match(content, /ThermoAnalyzer Desktop startup diagnostics/);
    assert.match(content, /custom_message=true/);
    assert.match(content, /backend_stdout: line-1/);
    assert.match(content, /backend_stdout: line-2/);
    assert.match(content, /startup_failure: Error: simulated startup failure/);

    console.log("startup diagnostics tests passed");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
}

run();
