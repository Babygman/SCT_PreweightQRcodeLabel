param(
    [string]$CertificateThumbprint = '',
    [string]$TimestampUrl = 'http://timestamp.digicert.com'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$BuildRequirements = Join-Path $RepoRoot 'scale_bridge\packaging\requirements-build-windows.txt'
$ServiceSpec = Join-Path $RepoRoot 'scale_bridge\packaging\scale_bridge_service.spec'
$DiagnosticsSpec = Join-Path $RepoRoot 'scale_bridge\packaging\scale_bridge_diagnostics.spec'
$Dist = Join-Path $RepoRoot 'dist\scale-bridge'

Set-Location $RepoRoot
py -3.13 -m venv .venv-scale-build
& .\.venv-scale-build\Scripts\python.exe -m pip install --disable-pip-version-check `
    --requirement $BuildRequirements
& .\.venv-scale-build\Scripts\python.exe -m pytest -q scale_bridge\tests
Remove-Item -Recurse -Force $Dist -ErrorAction SilentlyContinue
& .\.venv-scale-build\Scripts\pyinstaller.exe --noconfirm --clean --noupx `
    --distpath $Dist $ServiceSpec
& .\.venv-scale-build\Scripts\pyinstaller.exe --noconfirm --clean --noupx `
    --distpath $Dist $DiagnosticsSpec

function Invoke-AuthenticodeSign {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not $CertificateThumbprint) {
        return
    }
    $SignTool = (Get-Command signtool.exe -ErrorAction Stop).Source
    & $SignTool sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $Path
    & $SignTool verify /pa /v $Path
}

Get-ChildItem $Dist -Recurse -File -Filter *.exe | ForEach-Object {
    Invoke-AuthenticodeSign $_.FullName
}

$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $Iscc)) {
    throw 'Inno Setup 6 is required.'
}
& $Iscc (Join-Path $RepoRoot 'scale_bridge\windows\installer.iss')

$Installer = Join-Path $RepoRoot 'dist\installer\SCT-Preweight-Scale-Bridge-2.0.0-x64.exe'
Invoke-AuthenticodeSign $Installer
