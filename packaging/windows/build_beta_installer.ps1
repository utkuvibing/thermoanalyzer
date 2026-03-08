param(
    [string]$PythonExe = "python",
    [string]$IsccPath = "",
    [string]$VcRedistPath = "",
    [string]$VcRedistUrl = "https://aka.ms/vs/17/release/vc_redist.x64.exe",
    [string]$SetupBaseName = "ThermoAnalyzer_Setup"
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..\..")
$specPath = Join-Path $scriptRoot "ThermoAnalyzerLauncher.spec"
$issPath = Join-Path $scriptRoot "ThermoAnalyzer_Beta.iss"
$distRoot = Join-Path $scriptRoot "dist"
$buildRoot = Join-Path $scriptRoot "build"
$releaseRoot = Join-Path $repoRoot "release"
$prereqRoot = Join-Path $buildRoot "prereqs"

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

function Assert-MicrosoftSignedBinary {
    param([string]$PathToBinary)

    $signature = Get-AuthenticodeSignature -FilePath $PathToBinary
    if ($signature.Status -ne "Valid") {
        throw "Prerequisite binary is not Authenticode-valid: $PathToBinary"
    }

    $subject = $signature.SignerCertificate.Subject
    if ($subject -notmatch "Microsoft") {
        throw "Prerequisite binary is not signed by Microsoft: $PathToBinary"
    }
}

function Resolve-VcRedist {
    param(
        [string]$ExplicitPath,
        [string]$DownloadUrl,
        [string]$TargetRoot
    )

    if ($ExplicitPath) {
        if (-not (Test-Path $ExplicitPath)) {
            throw "The specified VC++ redistributable was not found: $ExplicitPath"
        }

        $resolved = (Resolve-Path $ExplicitPath).Path
        Assert-MicrosoftSignedBinary -PathToBinary $resolved
        return $resolved
    }

    if (-not (Test-Path $TargetRoot)) {
        New-Item -ItemType Directory -Path $TargetRoot | Out-Null
    }

    $target = Join-Path $TargetRoot "vc_redist.x64.exe"
    Write-Host "==> Downloading Microsoft VC++ Redistributable"
    Write-Host "Source: $DownloadUrl"
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $target -UseBasicParsing

    if (-not (Test-Path $target)) {
        throw "VC++ redistributable download did not produce a file at $target"
    }
    if ((Get-Item $target).Length -lt 1MB) {
        throw "VC++ redistributable download looks incomplete: $target"
    }

    Assert-MicrosoftSignedBinary -PathToBinary $target
    return (Resolve-Path $target).Path
}

function Assert-PackagedRuntime {
    param([string]$SourceDistRoot)

    $required = @(
        "ThermoAnalyzerLauncher.exe",
        "_internal\\app.py",
        "_internal\\.streamlit\\config.toml"
    )

    foreach ($relativePath in $required) {
        $fullPath = Join-Path $SourceDistRoot $relativePath
        if (-not (Test-Path $fullPath)) {
            throw "Expected packaged runtime file was not found: $fullPath"
        }
    }
}

Write-Host "==> ThermoAnalyzer Windows beta build"
Write-Host "Repo root: $repoRoot"

$pyInstallerPresent = (& $PythonExe -c "import importlib.util; print('1' if importlib.util.find_spec('PyInstaller') else '0')" 2>$null | Out-String).Trim()
if ($pyInstallerPresent -ne "1") {
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
if (-not $SetupBaseName -or $SetupBaseName.Trim().Length -eq 0) {
    throw "SetupBaseName cannot be empty."
}
$SetupBaseName = $SetupBaseName.Trim()
$expectedInstallerName = "{0}_{1}.exe" -f $SetupBaseName, $appVersion
$expectedInstallerPath = Join-Path $releaseRoot $expectedInstallerName

if (Test-Path $distRoot) {
    Remove-Item -Recurse -Force $distRoot
}
if (Test-Path $buildRoot) {
    Remove-Item -Recurse -Force $buildRoot
}
if (-not (Test-Path $releaseRoot)) {
    New-Item -ItemType Directory -Path $releaseRoot | Out-Null
}
if (-not (Test-Path $prereqRoot)) {
    New-Item -ItemType Directory -Path $prereqRoot | Out-Null
}

Write-Host "==> Running PyInstaller"
& $PythonExe -m PyInstaller $specPath --noconfirm --clean --distpath $distRoot --workpath $buildRoot
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$sourceDist = Join-Path $distRoot "ThermoAnalyzerLauncher"
if (-not (Test-Path (Join-Path $sourceDist "ThermoAnalyzerLauncher.exe"))) {
    throw "PyInstaller output was not created at $sourceDist"
}
Assert-PackagedRuntime -SourceDistRoot $sourceDist

$resolvedVcRedist = Resolve-VcRedist -ExplicitPath $VcRedistPath -DownloadUrl $VcRedistUrl -TargetRoot $prereqRoot

$resolvedIscc = Resolve-Iscc -ExplicitPath $IsccPath
Write-Host "==> Running Inno Setup: $resolvedIscc"
& $resolvedIscc "/DMyAppVersion=$appVersion" "/DMySourceDist=$sourceDist" "/DMyRepoRoot=$repoRoot" "/DMyVcRedistPath=$resolvedVcRedist" "/DMySetupBaseName=$SetupBaseName" $issPath
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup installer build failed."
}
if (-not (Test-Path $expectedInstallerPath)) {
    throw "Installer output was not found at the expected path: $expectedInstallerPath"
}

Write-Host ""
Write-Host "Build complete."
Write-Host "Installer output: $expectedInstallerPath"
