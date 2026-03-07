param(
    [string]$PythonExe = "python",
    [string]$IsccPath = ""
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..\..")
$specPath = Join-Path $scriptRoot "ThermoAnalyzerLauncher.spec"
$issPath = Join-Path $scriptRoot "ThermoAnalyzer_Beta.iss"
$distRoot = Join-Path $scriptRoot "dist"
$buildRoot = Join-Path $scriptRoot "build"
$releaseRoot = Join-Path $repoRoot "release"

Set-Location $repoRoot

function Resolve-Iscc {
    param([string]$ExplicitPath)

    if ($ExplicitPath -and (Test-Path $ExplicitPath)) {
        return (Resolve-Path $ExplicitPath)
    }

    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path $_) }

    if ($candidates.Count -gt 0) {
        return (Resolve-Path $candidates[0])
    }

    throw "Inno Setup compiler (ISCC.exe) was not found. Install Inno Setup 6 or pass -IsccPath."
}

Write-Host "==> ThermoAnalyzer Windows beta build"
Write-Host "Repo root: $repoRoot"

& $PythonExe -c "import PyInstaller" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller not found in the current environment. Installing it..."
    & $PythonExe -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller could not be installed into the active Python environment."
    }
}

$appVersion = (& $PythonExe -c "from utils.license_manager import APP_VERSION; print(APP_VERSION)" | Out-String).Trim()
if (-not $appVersion) {
    throw "APP_VERSION could not be resolved."
}

if (Test-Path $distRoot) {
    Remove-Item -Recurse -Force $distRoot
}
if (Test-Path $buildRoot) {
    Remove-Item -Recurse -Force $buildRoot
}
if (-not (Test-Path $releaseRoot)) {
    New-Item -ItemType Directory -Path $releaseRoot | Out-Null
}

Write-Host "==> Running PyInstaller"
& $PythonExe -m PyInstaller $specPath --noconfirm --clean
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$sourceDist = Join-Path $distRoot "ThermoAnalyzerLauncher"
if (-not (Test-Path (Join-Path $sourceDist "ThermoAnalyzerLauncher.exe"))) {
    throw "PyInstaller output was not created at $sourceDist"
}

$resolvedIscc = Resolve-Iscc -ExplicitPath $IsccPath
Write-Host "==> Running Inno Setup: $resolvedIscc"
& $resolvedIscc "/DMyAppVersion=$appVersion" "/DMySourceDist=$sourceDist" "/DMyRepoRoot=$repoRoot" $issPath
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup installer build failed."
}

Write-Host ""
Write-Host "Build complete."
Write-Host "Installer output: $(Join-Path $releaseRoot ("ThermoAnalyzer_Beta_Setup_" + $appVersion + ".exe"))"
