[Setup]
AppName=Flowkeeper
AppVersion=1.0.0
AppPublisher=flowkeeper.org
AppPublisherURL=https://flowkeeper.org
AppSupportURL=https://flowkeeper.org
AppUpdatesURL=https://flowkeeper.org
DefaultDirName={userpf}\Flowkeeper
DefaultGroupName=Flowkeeper
SetupIconFile={#GetEnv('FK_REPO_ROOT')}\res\flowkeeper.ico
UninstallDisplayIcon={app}\Flowkeeper.exe
PrivilegesRequired=lowest
UninstallDisplayName=Flowkeeper
SourceDir={#GetEnv('FK_REPO_ROOT')}
OutputDir={#GetEnv('FK_REPO_ROOT')}\dist

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"
Name: "autostart"; Description: "Launch Flowkeeper when the system boots"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\standalone\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Flowkeeper"; Filename: "{app}\Flowkeeper.exe"
Name: "{userdesktop}\Flowkeeper"; Filename: "{app}\Flowkeeper.exe"; Tasks: desktopicon
Name: "{userstartup}\Flowkeeper"; Parameters: "--autostart"; Filename: "{app}\Flowkeeper.exe"; Tasks: autostart

[Run]
Filename: "{app}\Flowkeeper.exe"; Description: "Launch Flowkeeper"; Flags: nowait postinstall skipifsilent
