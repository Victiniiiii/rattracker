; Inno Setup script for a Nuitka standalone build.
; Run from the repository root:
;   iscc /DMyAppVersion=1.1.0 packaging\windows\rattracker.iss

#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif

#define MyAppName "Morris Water Maze Analysis"
#define MyAppExeName "rattracker.exe"

[Setup]
AppId={{8F2A1D4B-6A3E-4C9B-9F7E-2B1C5D6E8A10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\RatTracker
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=morriswatermazeanalysis_{#MyAppVersion}_amd64-setup
SetupIconFile=packaging\windows\appicon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\build\app_qt.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
