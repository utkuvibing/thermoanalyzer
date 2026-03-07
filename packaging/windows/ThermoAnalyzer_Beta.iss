#define MyAppName "ThermoAnalyzer Beta"
#define MyAppPublisher "Utku Sahin"
#define MyAppExeName "ThermoAnalyzerLauncher.exe"

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#ifndef MySourceDist
  #error "MySourceDist must point to the PyInstaller dist\\ThermoAnalyzerLauncher folder."
#endif

#ifndef MyRepoRoot
  #error "MyRepoRoot must point to the repository root."
#endif

#ifndef MyVcRedistPath
  #error "MyVcRedistPath must point to the official VC++ redistributable installer."
#endif

[Setup]
AppId={{A1F0F66E-37BF-4F0D-B4CF-6C87601A5D6D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\ThermoAnalyzer Beta
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma
SolidCompression=yes
WizardStyle=modern
OutputDir={#MyRepoRoot}\release
OutputBaseFilename=ThermoAnalyzer_Beta_Setup_{#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MySourceDist}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MySourceDist}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#MyRepoRoot}\packaging\windows\end_user_docs\README.txt"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#MyRepoRoot}\packaging\windows\end_user_docs\HELP.html"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#MyRepoRoot}\PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#MyRepoRoot}\PROFESSOR_SETUP_AND_USAGE_GUIDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#MyRepoRoot}\PROFESSOR_BETA_GUIDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#MyRepoRoot}\README.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#MyVcRedistPath}"; Flags: dontcopy

[Icons]
Name: "{group}\ThermoAnalyzer Beta"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Yardim"; Filename: "{app}\docs\HELP.html"
Name: "{group}\Hizli Baslangic"; Filename: "{app}\docs\README.txt"
Name: "{autodesktop}\ThermoAnalyzer Beta"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,ThermoAnalyzer Beta}"; Flags: nowait postinstall skipifsilent

[Code]
const
  RequiredInstallFreeMB = 900;
  RequiredRuntimeFreeMB = 150;

var
  VcRedistMissing: Boolean;
  VcRedistAttempted: Boolean;
  VcRedistInstallFailed: Boolean;
  VcRedistRestartRecommended: Boolean;
  VcRedistExitCode: Integer;

function GetUserRuntimeRoot: String;
begin
  Result := ExpandConstant('{localappdata}\ThermoAnalyzer Beta');
end;

function EnsureFreeSpace(TargetPath: String; RequiredMB: Cardinal; LabelText: String): String;
var
  FreeMB: Cardinal;
  TotalMB: Cardinal;
begin
  Result := '';

  if not GetSpaceOnDisk(TargetPath, True, FreeMB, TotalMB) then
  begin
    Result := 'Setup could not verify free disk space for ' + LabelText + '.';
    exit;
  end;

  if FreeMB < RequiredMB then
  begin
    Result :=
      'Not enough free disk space for ' + LabelText + '.' + #13#10#13#10 +
      'Available: ' + IntToStr(Integer(FreeMB)) + ' MB' + #13#10 +
      'Required: at least approximately ' + IntToStr(Integer(RequiredMB)) + ' MB';
  end;
end;

function EnsureWritableDirectory(TargetPath: String; LabelText: String): String;
var
  ProbeFile: String;
begin
  Result := '';

  if not DirExists(TargetPath) then
  begin
    if not ForceDirectories(TargetPath) then
    begin
      Result := 'Setup could not create ' + LabelText + ' at:' + #13#10 + TargetPath;
      exit;
    end;
  end;

  ProbeFile := AddBackslash(TargetPath) + 'thermoanalyzer_write_probe.tmp';
  if not SaveStringToFile(ProbeFile, 'ThermoAnalyzer write test', False) then
  begin
    Result := 'Setup could not write to ' + LabelText + ' at:' + #13#10 + TargetPath;
    exit;
  end;

  DeleteFile(ProbeFile);
end;

function IsVcRedistInstalled: Boolean;
var
  Installed: Cardinal;
begin
  Result := False;

  if IsWin64 then
  begin
    if RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
      Result := Installed = 1;
  end;

  if (not Result) and RegQueryDWordValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
    Result := Installed = 1;
end;

procedure TryInstallVcRedist;
var
  RedistExe: String;
  Parameters: String;
  ResultCode: Integer;
begin
  VcRedistMissing := not IsVcRedistInstalled;
  if not VcRedistMissing then
    exit;

  VcRedistAttempted := True;
  ExtractTemporaryFile('vc_redist.x64.exe');
  RedistExe := ExpandConstant('{tmp}\vc_redist.x64.exe');
  Parameters := '/install /quiet /norestart /log "' + ExpandConstant('{tmp}\thermoanalyzer_vcredist.log') + '"';

  if not ShellExec('open', RedistExe, Parameters, '', SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) then
  begin
    VcRedistInstallFailed := True;
    VcRedistExitCode := ResultCode;
    exit;
  end;

  VcRedistExitCode := ResultCode;
  if ResultCode = 3010 then
    VcRedistRestartRecommended := True;

  if (ResultCode <> 0) and (ResultCode <> 1638) and (ResultCode <> 3010) then
    VcRedistInstallFailed := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := EnsureFreeSpace(ExpandConstant('{app}'), RequiredInstallFreeMB, 'the selected install location');
  if Result <> '' then
    exit;

  Result := EnsureFreeSpace(ExpandConstant('{localappdata}'), RequiredRuntimeFreeMB, 'the ThermoAnalyzer user runtime area');
  if Result <> '' then
    exit;

  Result := EnsureWritableDirectory(GetUserRuntimeRoot, 'the ThermoAnalyzer user runtime area');
  if Result <> '' then
    exit;

  TryInstallVcRedist;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  MessageText: String;
begin
  if CurStep <> ssPostInstall then
    exit;

  if VcRedistInstallFailed then
  begin
    MessageText :=
      'ThermoAnalyzer Beta could not install the Microsoft Visual C++ compatibility package automatically.' + #13#10#13#10 +
      'The application was still installed because the packaged runtime already includes Python and the app dependencies.' + #13#10 +
      'If ThermoAnalyzer does not start on this machine, rerun Setup with administrator approval or contact support.' + #13#10#13#10 +
      'VC++ installer exit code: ' + IntToStr(VcRedistExitCode);
    SuppressibleMsgBox(MessageText, mbInformation, MB_OK, IDOK);
  end
  else if VcRedistAttempted and VcRedistRestartRecommended then
  begin
    MessageText :=
      'ThermoAnalyzer Beta installed the Microsoft Visual C++ compatibility package.' + #13#10#13#10 +
      'Windows reported that a restart may be recommended before the packaged app is used for the first time.';
    SuppressibleMsgBox(MessageText, mbInformation, MB_OK, IDOK);
  end;
end;
