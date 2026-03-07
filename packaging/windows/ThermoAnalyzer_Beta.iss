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
Source: "{#MyRepoRoot}\PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#MyRepoRoot}\PROFESSOR_SETUP_AND_USAGE_GUIDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#MyRepoRoot}\PROFESSOR_BETA_GUIDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#MyRepoRoot}\README.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\ThermoAnalyzer Beta"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Turkish Setup Guide"; Filename: "{app}\docs\PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md"
Name: "{group}\English Setup Guide"; Filename: "{app}\docs\PROFESSOR_SETUP_AND_USAGE_GUIDE.md"
Name: "{group}\Professor Beta Guide"; Filename: "{app}\docs\PROFESSOR_BETA_GUIDE.md"
Name: "{autodesktop}\ThermoAnalyzer Beta"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,ThermoAnalyzer Beta}"; Flags: nowait postinstall skipifsilent
