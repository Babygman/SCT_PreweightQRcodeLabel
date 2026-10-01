# Windows 11 x64 Package

## Normal installation

The unsigned build output is prepared for future Authenticode signing. Do not distribute it as
signed until the organization supplies and protects an approved signing certificate.

Unsigned internal test builds can trigger Microsoft Defender, SmartScreen, or enterprise EDR
warnings. Authenticode provides publisher and integrity evidence; it does not guarantee antivirus
acceptance or reputation. Never disable security controls or create exclusions to make a build run.

An administrator runs `SCT-Preweight-Scale-Bridge-2.0.0-x64.exe`. The installer:

1. installs standalone service and diagnostic executables (Python is not required on the client);
2. creates automatic service `SCTPreweightScaleBridge` as `NT AUTHORITY\LocalService`;
3. applies restart-on-failure policy;
4. creates restrictive machine configuration and log directories under
   `C:\ProgramData\SCT\ScaleBridge`;
5. starts the service; and
6. creates a diagnostic shortcut that runs without elevation for ordinary inspection.

No inbound firewall rule is created because the API binds only to `127.0.0.1`.

The service runs as the built-in `NT AUTHORITY\LocalService` identity. It requires read/execute
access to immutable binaries below `%ProgramFiles%\SCT\ScaleBridge`, read access to
`%ProgramData%\SCT\ScaleBridge\config.json`, and modify access only to the bounded rotating-log
directory. Administrators and SYSTEM retain full control. Standard users receive no modify or full
control over the service binaries, service definition, machine configuration, or logs.

Configuration is non-secret and is preserved during upgrades and uninstall. Rotating sanitized
logs are also deliberately retained after uninstall for diagnostics. The uninstaller stops and
deletes the service and application binaries. An administrator may separately delete the retained
ProgramData directory after evidence is no longer needed.

## Build on Windows 11

Requirements:

- Windows 11 x64 build machine
- Python 3.13
- Inno Setup 6
- no production credentials or environment files

From a clean repository checkout:

```powershell
powershell -ExecutionPolicy Bypass -File .\scale_bridge\windows\build.ps1
```

The build discovers `ISCC.exe` from an explicit `-InnoSetupPath`, the current process `PATH`,
64-bit and 32-bit Program Files locations, then the supported per-user LocalAppData installation.
An explicit path is useful on managed workstations and paths containing spaces are passed without
shell reconstruction:

```powershell
powershell -ExecutionPolicy Bypass -File .\scale_bridge\windows\build.ps1 `
  -InnoSetupPath "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
```

The script does not modify `PATH`, install, copy, download, or relocate Inno Setup. If discovery
fails, it reports every checked location and exits before signing or artifact verification.

The script creates an isolated build environment, installs pinned build dependencies, runs Scale
Bridge tests, builds two standalone one-directory bundles, then invokes Inno Setup. The bundles
include Python and all runtime dependencies, but avoid self-extracting one-file executable packing.
Windows binaries must be built on Windows; they are not cross-compiled or claimed as tested on
macOS.

UPX is disabled in both PyInstaller specifications and build commands. The build performs no
runtime download or update behavior; dependency installation occurs only on the controlled build
machine.

### Authenticode signing

Supply only the thumbprint of an externally provisioned certificate in the Windows certificate
store. Do not place PFX files, passwords, private keys, or signing tokens in the repository:

```powershell
.\scale_bridge\windows\build.ps1 `
  -CertificateThumbprint 'CERTIFICATE_THUMBPRINT_FROM_SECURE_STORE' `
  -TimestampUrl 'http://timestamp.digicert.com'
```

The build signs every generated executable in both bundles using SHA-256 with an RFC 3161 timestamp
before Inno Setup creates the installer, then signs and verifies the completed installer. A hardware-backed or
managed signing service may replace the `signtool sign` invocation according to that provider's
documented client; keep `/fd SHA256`, `/tr <RFC3161 URL>`, and `/td SHA256`, and never export its
private key. Validate all shipped files with `Get-AuthenticodeSignature` before distribution.

The build-only GitHub Actions workflow runs only on manual dispatch or relevant pull requests,
uploads an unsigned artifact with bounded retention, and performs no deployment, release,
signing, UAT access, or production access.

## Administration and diagnostics

The diagnostic executable runs without elevation and displays service state, detected FTDI
devices, VID/PID, USB serial, COM port, decoded frame status, stable state, Gross, Tare, Actual,
timestamp, and sanitized recent errors. It has no serial-output or scale-control functions.

`Administrator Configuration` launches a separate UAC-elevated instance only when configuration
changes are requested. An administrator configures Workstation Code, Scale Code, preferred FTDI
USB serial, and the exact browser Origins allowed to call the loopback API. UAT is fixed at
`http://preweight-uat.sct.local`; Production accepts a separately supplied exact HTTP/HTTPS Origin.
Either environment or both may be selected, and the utility shows every selected URL before save.
Wildcard, credential-bearing, malformed, or non-Origin URLs are rejected.

Configuration replacement is atomic and preserves the existing hardened DACL. After a successful
save, only `SCTPreweightScaleBridge` is restarted. If save or restart fails, the utility restores
the prior configuration and reports a controlled Thai/English error. The same installer supports
UAT and Production; upgrades and uninstall continue preserving `config.json`.

Service lifecycle commands for troubleshooting are:

```powershell
sc.exe query SCTPreweightScaleBridge
sc.exe start SCTPreweightScaleBridge
sc.exe stop SCTPreweightScaleBridge
```

Use Apps & Features for clean uninstall. Direct `sc.exe delete` is reserved for recovery by an
administrator after the service is stopped.

## Windows 11 enterprise verification

Run these commands from an elevated PowerShell window unless a step explicitly tests a standard
user. Keep Microsoft Defender, SmartScreen, UAC, Windows Firewall, and the organization's EDR
enabled throughout.

### Clean installation and integrity

```powershell
$Installer = Resolve-Path .\SCT-Preweight-Scale-Bridge-2.0.0-x64.exe
Get-FileHash $Installer -Algorithm SHA256
Get-AuthenticodeSignature $Installer | Format-List Status,StatusMessage,SignerCertificate
Start-Process $Installer -Wait -Verb RunAs
$InstallDir = Join-Path $env:ProgramFiles 'SCT\ScaleBridge'
$DataDir = Join-Path $env:ProgramData 'SCT\ScaleBridge'
Get-ChildItem $InstallDir -Filter *.exe | ForEach-Object {
  Get-AuthenticodeSignature $_.FullName | Select-Object Path,Status,SignerCertificate
  Get-FileHash $_.FullName -Algorithm SHA256
}
```

### Service startup and failure recovery

```powershell
Get-CimInstance Win32_Service -Filter "Name='SCTPreweightScaleBridge'" |
  Select-Object Name,State,StartMode,StartName,PathName
sc.exe qc SCTPreweightScaleBridge
sc.exe qfailure SCTPreweightScaleBridge
sc.exe query SCTPreweightScaleBridge
```

Confirm `StartMode` is `Auto`, `StartName` is `NT AUTHORITY\LocalService`, and the executable path
is quoted. In an isolated acceptance workstation, record the service process ID, terminate that
process once, and confirm SCM recovery starts a new process without an interactive sign-in:

```powershell
$Before = Get-CimInstance Win32_Service -Filter "Name='SCTPreweightScaleBridge'"
Stop-Process -Id $Before.ProcessId -Force
Start-Sleep -Seconds 10
$After = Get-CimInstance Win32_Service -Filter "Name='SCTPreweightScaleBridge'"
$After | Select-Object State,ProcessId
```

Do not perform this failure test on an active weighing workstation.

### Upgrade and standard-user operation

Before an upgrade, hash a copy of `config.json`; run the newer installer elevated; then prove the
configuration hash is unchanged and the service is healthy:

```powershell
$Config = Join-Path $env:ProgramData 'SCT\ScaleBridge\config.json'
$BeforeConfigHash = (Get-FileHash $Config -Algorithm SHA256).Hash
Start-Process .\SCT-Preweight-Scale-Bridge-2.0.0-x64.exe -Wait -Verb RunAs
$AfterConfigHash = (Get-FileHash $Config -Algorithm SHA256).Hash
if ($BeforeConfigHash -ne $AfterConfigHash) { throw 'Configuration changed during upgrade.' }
sc.exe query SCTPreweightScaleBridge
```

Sign in as a standard user and open diagnostics plus SCT Preweight in the approved browser. Confirm
diagnostics and weighing pages can read the loopback bridge while attempts to modify files in
`$InstallDir` or `$Config` are denied. Select Administrator Configuration and confirm UAC is
requested only at that boundary.

### Listener, firewall, Defender, and persistence checks

```powershell
$Service = Get-CimInstance Win32_Service -Filter "Name='SCTPreweightScaleBridge'"
Get-NetTCPConnection -State Listen -OwningProcess $Service.ProcessId |
  Select-Object LocalAddress,LocalPort,OwningProcess
Get-NetFirewallRule | Where-Object DisplayName -Match 'SCT|ScaleBridge|Preweight'
$Mp = Get-MpPreference
$Mp.ExclusionPath
$Mp.ExclusionProcess
$Mp.ExclusionExtension
Get-ScheduledTask | Where-Object TaskName -Match 'SCT|ScaleBridge|Preweight'
Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run'
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
Get-ChildItem "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Startup"
Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
```

The only listener must be `127.0.0.1` on the configured port. There must be no matching inbound
firewall rule, Defender exclusion, scheduled task, Run-key entry, or Startup entry.

### ACL verification

```powershell
Get-Acl $InstallDir | Format-List Owner,AccessToString
Get-Acl $Config | Format-List Owner,AccessToString
Get-Acl (Join-Path $DataDir 'logs') | Format-List Owner,AccessToString
icacls.exe $InstallDir
icacls.exe $Config
icacls.exe (Join-Path $DataDir 'logs')
```

Confirm standard users have no write/modify/full-control permission. `LOCAL SERVICE` may read the
configuration and modify only the logs directory.

### Defender and organization EDR scanning

```powershell
Update-MpSignature
Start-MpScan -ScanType CustomScan -ScanPath $InstallDir
Start-MpScan -ScanType CustomScan -ScanPath $Installer
Get-MpThreatDetection | Select-Object InitialDetectionTime,ThreatName,ActionSuccess
```

Also scan the installer and installed files with the organization's actual EDR/antivirus under its
normal policy. Do not disable it, create exclusions, or submit artifacts to a public scanning
service without separate authorization.

### Runtime-download and uninstall verification

Monitor the service with the organization's EDR or Windows network tooling and confirm it makes no
outbound connection or updater/download request. The expected network surface is the loopback HTTP
listener only. Uninstall through Apps & Features, then verify:

```powershell
Get-Service SCTPreweightScaleBridge -ErrorAction SilentlyContinue
Test-Path $InstallDir
Test-Path $Config
Test-Path (Join-Path $DataDir 'logs')
```

The service and application binaries must be absent. Configuration and diagnostic logs must remain
for explicit administrator review and deletion.
