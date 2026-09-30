param(
    [string]$CertificateThumbprint = '',
    [string]$TimestampUrl = 'http://timestamp.digicert.com',
    [string]$InnoSetupPath = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-NativeStage {
    param(
        [Parameter(Mandatory = $true)][string]$Stage,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    try {
        & $FilePath @Arguments
    }
    catch {
        throw "Build stage failed: $Stage. $($_.Exception.Message)"
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Build stage failed: $Stage (exit code $LASTEXITCODE)."
    }
}

function Assert-BuildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Stage,
        [Parameter(Mandatory = $true)][string]$Path
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Build stage failed: $Stage did not produce expected path: $Path"
    }
}

function Resolve-InnoCandidate {
    param(
        [Parameter(Mandatory = $true)][string]$Candidate,
        [Parameter(Mandatory = $true)]$CheckedLocations
    )
    $Expanded = [Environment]::ExpandEnvironmentVariables($Candidate)
    if ([IO.Path]::IsPathRooted($Expanded)) {
        $Absolute = [IO.Path]::GetFullPath($Expanded)
    }
    else {
        $Absolute = [IO.Path]::GetFullPath((Join-Path (Get-Location) $Expanded))
    }
    $CheckedLocations.Add($Absolute)
    if (Test-Path -LiteralPath $Absolute -PathType Leaf) {
        return (Resolve-Path -LiteralPath $Absolute).Path
    }
    return $null
}

function Resolve-InnoSetupCompiler {
    param([string]$ExplicitPath = '')
    $CheckedLocations = [Collections.Generic.List[string]]::new()

    if ($ExplicitPath) {
        $Resolved = Resolve-InnoCandidate $ExplicitPath $CheckedLocations
        if ($Resolved) { return $Resolved }
    }

    $PathCommand = Get-Command ISCC.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($PathCommand -and $PathCommand.Source) {
        $Resolved = Resolve-InnoCandidate $PathCommand.Source $CheckedLocations
        if ($Resolved) { return $Resolved }
    }
    else {
        $CheckedLocations.Add('PATH:ISCC.exe')
    }

    $Candidates = @(
        $(if (${env:ProgramFiles(x86)}) {
            Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
        } else { '%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe' }),
        $(if ($env:ProgramFiles) {
            Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'
        } else { '%ProgramFiles%\Inno Setup 6\ISCC.exe' }),
        $(if ($env:LOCALAPPDATA) {
            Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'
        } else { '%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe' })
    )
    foreach ($Candidate in $Candidates) {
        $Resolved = Resolve-InnoCandidate $Candidate $CheckedLocations
        if ($Resolved) { return $Resolved }
    }

    $Checked = $CheckedLocations -join '; '
    throw "Build stage failed: locate Inno Setup compiler. Checked: $Checked. " +
        "Install Inno Setup 6 or pass -InnoSetupPath with the full ISCC.exe path."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$BuildRequirements = Join-Path $RepoRoot 'scale_bridge\packaging\requirements-build-windows.txt'
$ServiceSpec = Join-Path $RepoRoot 'scale_bridge\packaging\scale_bridge_service.spec'
$DiagnosticsSpec = Join-Path $RepoRoot 'scale_bridge\packaging\scale_bridge_diagnostics.spec'
$BuildVenv = Join-Path $RepoRoot '.venv-scale-build'
$BuildPython = Join-Path $BuildVenv 'Scripts\python.exe'
$PyInstaller = Join-Path $BuildVenv 'Scripts\pyinstaller.exe'
$Dist = Join-Path $RepoRoot 'dist\scale-bridge'
$InstallerOutput = Join-Path $RepoRoot 'dist\installer'
$ServiceBundle = Join-Path $Dist 'SCTPreweightScaleBridgeService'
$DiagnosticsBundle = Join-Path $Dist 'SCTPreweightScaleBridgeDiagnostics'
$ServiceExe = Join-Path $ServiceBundle 'SCTPreweightScaleBridgeService.exe'
$DiagnosticsExe = Join-Path $DiagnosticsBundle 'SCTPreweightScaleBridgeDiagnostics.exe'
$Installer = Join-Path $InstallerOutput 'SCT-Preweight-Scale-Bridge-2.0.0-x64.exe'

Set-Location $RepoRoot
Remove-Item -LiteralPath $BuildVenv -Recurse -Force -ErrorAction SilentlyContinue
Invoke-NativeStage -Stage 'Create Python build environment' -FilePath 'py' `
    -Arguments @('-3.13', '-m', 'venv', $BuildVenv)
Assert-BuildPath -Stage 'Create Python build environment' -Path $BuildPython
Invoke-NativeStage -Stage 'Install pinned build dependencies' -FilePath $BuildPython `
    -Arguments @('-m', 'pip', 'install', '--disable-pip-version-check', `
        '--requirement', $BuildRequirements)
Invoke-NativeStage -Stage 'Run Scale Bridge tests' -FilePath $BuildPython `
    -Arguments @('-m', 'pytest', '-q', 'scale_bridge\tests')

# A new build deliberately starts with clean output directories only after prerequisites and tests pass.
Remove-Item -LiteralPath $Dist -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $InstallerOutput -Recurse -Force -ErrorAction SilentlyContinue
Invoke-NativeStage -Stage 'Build Scale Bridge service bundle' -FilePath $PyInstaller `
    -Arguments @('--noconfirm', '--clean', '--distpath', $Dist, $ServiceSpec)
Assert-BuildPath -Stage 'Build Scale Bridge service bundle' -Path $ServiceExe
Invoke-NativeStage -Stage 'Build diagnostics bundle' -FilePath $PyInstaller `
    -Arguments @('--noconfirm', '--clean', '--distpath', $Dist, $DiagnosticsSpec)
Assert-BuildPath -Stage 'Build diagnostics bundle' -Path $DiagnosticsExe

function Invoke-AuthenticodeSign {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not $CertificateThumbprint) {
        return
    }
    $SignTool = (Get-Command signtool.exe -ErrorAction Stop).Source
    Invoke-NativeStage -Stage "Sign $Path" -FilePath $SignTool `
        -Arguments @('sign', '/sha1', $CertificateThumbprint, '/fd', 'SHA256', `
            '/tr', $TimestampUrl, '/td', 'SHA256', $Path)
    Invoke-NativeStage -Stage "Verify signature for $Path" -FilePath $SignTool `
        -Arguments @('verify', '/pa', '/v', $Path)
}

Assert-BuildPath -Stage 'Inspect application bundles' -Path $Dist
Get-ChildItem $Dist -Recurse -File -Filter *.exe | ForEach-Object {
    Invoke-AuthenticodeSign $_.FullName
}

$Iscc = Resolve-InnoSetupCompiler -ExplicitPath $InnoSetupPath
Invoke-NativeStage -Stage 'Compile Inno Setup installer' -FilePath $Iscc `
    -Arguments @((Join-Path $RepoRoot 'scale_bridge\windows\installer.iss'))

Assert-BuildPath -Stage 'Compile Inno Setup installer' -Path $Installer
Invoke-AuthenticodeSign $Installer
Assert-BuildPath -Stage 'Verify final installer artifact' -Path $Installer
try {
    $InstallerHash = Get-FileHash -LiteralPath $Installer -Algorithm SHA256
}
catch {
    throw "Build stage failed: final installer SHA-256 verification. $($_.Exception.Message)"
}
if (-not $InstallerHash.Hash) {
    throw 'Build stage failed: final installer SHA-256 verification returned no hash.'
}
Write-Host "Installer SHA-256: $($InstallerHash.Hash)"
