#define AppName "SCT Preweight Scale Bridge"
#define AppVersion "2.0.0"
#define ServiceName "SCTPreweightScaleBridge"

[Setup]
AppId={{B7199E9C-46A3-4C58-A502-48F59C84D401}
AppName={#AppName}
AppVersion={#AppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DefaultDirName={autopf}\SCT\ScaleBridge
DefaultGroupName=SCT Preweight
OutputDir=..\..\dist\installer
OutputBaseFilename=SCT-Preweight-Scale-Bridge-{#AppVersion}-x64
PrivilegesRequired=admin
DisableProgramGroupPage=yes
Compression=lzma2
SolidCompression=yes
UninstallDisplayName={#AppName}
SetupLogging=yes
CloseApplications=yes

[Dirs]
Name: "{commonappdata}\SCT\ScaleBridge"; Permissions: "admins-full system-full"
Name: "{commonappdata}\SCT\ScaleBridge\logs"; Permissions: "admins-full system-full"

[Files]
Source: "..\..\dist\scale-bridge\SCTPreweightScaleBridgeService\*"; DestDir: "{app}\Service"; Flags: ignoreversion restartreplace recursesubdirs createallsubdirs
Source: "..\..\dist\scale-bridge\SCTPreweightScaleBridgeDiagnostics\*"; DestDir: "{app}\Diagnostics"; Flags: ignoreversion restartreplace recursesubdirs createallsubdirs
Source: "..\config.example.json"; DestDir: "{commonappdata}\SCT\ScaleBridge"; DestName: "config.json"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\Scale Bridge Diagnostics"; Filename: "{app}\Diagnostics\SCTPreweightScaleBridgeDiagnostics.exe"

[Run]
Filename: "{sys}\sc.exe"; Parameters: "create {#ServiceName} binPath= ""{app}\Service\SCTPreweightScaleBridgeService.exe"" start= auto obj= ""NT AUTHORITY\LocalService"" DisplayName= ""SCT Preweight IDS701 Scale Bridge"""; Flags: runhidden waituntilterminated
Filename: "{sys}\sc.exe"; Parameters: "config {#ServiceName} binPath= ""{app}\Service\SCTPreweightScaleBridgeService.exe"" start= auto obj= ""NT AUTHORITY\LocalService"" DisplayName= ""SCT Preweight IDS701 Scale Bridge"""; Flags: runhidden waituntilterminated
Filename: "{sys}\sc.exe"; Parameters: "description {#ServiceName} ""Receive-only local bridge for the IDS701 weighing scale."""; Flags: runhidden waituntilterminated
Filename: "{sys}\sc.exe"; Parameters: "failure {#ServiceName} reset= 86400 actions= restart/5000/restart/15000/restart/60000"; Flags: runhidden waituntilterminated
Filename: "{sys}\icacls.exe"; Parameters: """{commonappdata}\SCT\ScaleBridge"" /inheritance:r /grant:r ""Administrators:(OI)(CI)F"" ""SYSTEM:(OI)(CI)F"" ""LOCAL SERVICE:(OI)(CI)RX"""; Flags: runhidden waituntilterminated
Filename: "{sys}\icacls.exe"; Parameters: """{commonappdata}\SCT\ScaleBridge\config.json"" /inheritance:r /grant:r ""Administrators:F"" ""SYSTEM:F"" ""LOCAL SERVICE:R"""; Flags: runhidden waituntilterminated
Filename: "{sys}\icacls.exe"; Parameters: """{commonappdata}\SCT\ScaleBridge\logs"" /inheritance:r /grant:r ""Administrators:F"" ""SYSTEM:F"" ""LOCAL SERVICE:(OI)(CI)M"""; Flags: runhidden waituntilterminated
Filename: "{sys}\sc.exe"; Parameters: "start {#ServiceName}"; Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "{sys}\sc.exe"; Parameters: "stop {#ServiceName}"; Flags: runhidden waituntilterminated; RunOnceId: "StopScaleBridge"
Filename: "{sys}\sc.exe"; Parameters: "delete {#ServiceName}"; Flags: runhidden waituntilterminated; RunOnceId: "DeleteScaleBridge"

; Configuration and rotating diagnostic logs are retained intentionally on uninstall.
; Administrators may remove C:\ProgramData\SCT\ScaleBridge after collecting diagnostics.

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  { Stop an existing installation before replacing its executable. A missing }
  { service is expected during first installation and is intentionally ignored. }
  Exec(ExpandConstant('{sys}\sc.exe'), 'stop {#ServiceName}', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
