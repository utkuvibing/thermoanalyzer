const assert = require("assert");
const path = require("path");
const { resolveBackendLaunch } = require("../backend_locator");

function testDevelopmentDefaultPython() {
  const repoRoot = "C:\\repo\\thermoanalyzer";
  const launch = resolveBackendLaunch({
    isPackaged: false,
    env: {},
    platform: "win32",
    repoRoot,
    resourcesPath: "C:\\resources",
  });
  assert.strictEqual(launch.mode, "development");
  assert.strictEqual(launch.command, "python");
  assert.deepStrictEqual(launch.args, [path.join(repoRoot, "backend", "main.py")]);
  assert.strictEqual(launch.cwd, repoRoot);
}

function testDevelopmentOverridePython() {
  const launch = resolveBackendLaunch({
    isPackaged: false,
    env: { TA_PYTHON: "C:\\Python312\\python.exe" },
    platform: "win32",
    repoRoot: "C:\\repo\\thermoanalyzer",
    resourcesPath: "C:\\resources",
  });
  assert.strictEqual(launch.command, "C:\\Python312\\python.exe");
}

function testPackagedResourcesPathResolution() {
  const existing = new Set(["C:\\app\\resources\\backend\\thermoanalyzer_backend.exe"]);
  const launch = resolveBackendLaunch({
    isPackaged: true,
    env: {},
    platform: "win32",
    repoRoot: "C:\\repo\\thermoanalyzer",
    resourcesPath: "C:\\app\\resources",
    existsSync: (candidate) => existing.has(candidate),
  });
  assert.strictEqual(launch.mode, "packaged");
  assert.strictEqual(launch.command, "C:\\app\\resources\\backend\\thermoanalyzer_backend.exe");
  assert.strictEqual(launch.args.length, 0);
}

function testPackagedOverrideResolution() {
  const launch = resolveBackendLaunch({
    isPackaged: true,
    env: { TA_BACKEND_EXE: "D:\\debug\\custom_backend.exe" },
    platform: "win32",
    repoRoot: "C:\\repo\\thermoanalyzer",
    resourcesPath: "C:\\app\\resources",
    existsSync: () => true,
  });
  assert.strictEqual(launch.command, "D:\\debug\\custom_backend.exe");
}

function testPackagedMissingExecutableThrows() {
  let didThrow = false;
  try {
    resolveBackendLaunch({
      isPackaged: true,
      env: {},
      platform: "win32",
      repoRoot: "C:\\repo\\thermoanalyzer",
      resourcesPath: "C:\\app\\resources",
      existsSync: () => false,
    });
  } catch (error) {
    didThrow = true;
    assert.match(String(error), /Bundled backend executable was not found/);
  }
  assert.ok(didThrow, "expected packaged backend resolution to throw");
}

function run() {
  testDevelopmentDefaultPython();
  testDevelopmentOverridePython();
  testPackagedResourcesPathResolution();
  testPackagedOverrideResolution();
  testPackagedMissingExecutableThrows();
  console.log("backend locator tests passed");
}

run();
