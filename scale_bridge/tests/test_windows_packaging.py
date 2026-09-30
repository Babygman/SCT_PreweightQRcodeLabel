from pathlib import Path
from types import SimpleNamespace

import pytest

from scale_bridge.windows.service_control import SERVICE_NAME, service_command

ROOT = Path(__file__).parents[1]


def test_service_lifecycle_helper_allows_only_safe_lifecycle_actions():
    calls = []

    def runner(command, **options):
        calls.append((command, options))
        return SimpleNamespace(returncode=0, stdout="STATE: RUNNING", stderr="")

    result = service_command("query", runner=runner)
    assert result == {"action": "query", "returncode": 0, "output": "STATE: RUNNING"}
    assert calls[0][0] == ["sc.exe", "query", SERVICE_NAME]
    with pytest.raises(ValueError, match="unsupported"):
        service_command("delete", runner=runner)


def test_pyinstaller_metadata_is_standalone_receive_only_and_unsigned():
    packaging = ROOT / "packaging"
    build_requirements = (packaging / "requirements-build-windows.txt").read_text()
    assert "pyinstaller==" in build_requirements.lower()
    assert "pyserial==3.5" in build_requirements.lower()
    assert "pywin32==" in build_requirements.lower()
    assert "pytest==" in build_requirements.lower()
    service_spec = (packaging / "scale_bridge_service.spec").read_text()
    diagnostics_spec = (packaging / "scale_bridge_diagnostics.spec").read_text()
    assert 'name="SCTPreweightScaleBridgeService"' in service_spec
    assert 'name="SCTPreweightScaleBridgeDiagnostics"' in diagnostics_spec
    assert "uac_admin=True" in diagnostics_spec
    assert "codesign_identity=None" in service_spec + diagnostics_spec
    assert "flask" in service_spec and "sqlalchemy" in service_spec
    assert service_spec.count("upx=False") == 2
    assert diagnostics_spec.count("upx=False") == 2
    assert "exclude_binaries=True" in service_spec + diagnostics_spec
    assert "COLLECT(" in service_spec + diagnostics_spec


def test_installer_creates_auto_recovering_least_privilege_service_and_preserves_config():
    installer = (ROOT / "windows" / "installer.iss").read_text()
    assert "ArchitecturesAllowed=x64compatible" in installer
    assert "PrivilegesRequired=admin" in installer
    assert "start= auto" in installer
    assert 'NT AUTHORITY\\LocalService' in installer
    assert "failure {#ServiceName}" in installer
    assert "restart/5000/restart/15000/restart/60000" in installer
    assert "function PrepareToInstall" in installer
    assert "config {#ServiceName}" in installer
    assert "onlyifdoesntexist uninsneveruninstall" in installer
    assert "[UninstallRun]" in installer
    assert "stop {#ServiceName}" in installer
    assert "delete {#ServiceName}" in installer
    assert "Scale Bridge Diagnostics" in installer
    assert "netsh" not in installer.lower()
    assert "firewall" not in installer.lower()


def test_build_script_and_ci_build_artifacts_without_release_or_deployment():
    build = (ROOT / "windows" / "build.ps1").read_text()
    assert "pyinstaller.exe" in build
    assert "ISCC.exe" in build
    workflow_path = (
        ROOT.parent / ".github" / "workflows" / "scale-bridge-windows-build.yml"
    )
    workflow = workflow_path.read_text()
    assert "runs-on: windows-2022" in workflow
    assert "workflow_dispatch:" in workflow
    assert "upload-artifact@v4" in workflow
    forbidden = ("release", "deploy", "environment:", "secrets.", "signing certificate")
    assert not any(term in workflow.lower() for term in forbidden)


def test_windows_security_controls_are_not_bypassed_and_upx_is_disabled():
    windows = ROOT / "windows"
    packaging = ROOT / "packaging"
    implementation = "\n".join(
        path.read_text()
        for path in (
            windows / "build.ps1",
            windows / "diagnostics.py",
            windows / "installer.iss",
            windows / "service.py",
            windows / "service_control.py",
            packaging / "scale_bridge_service.spec",
            packaging / "scale_bridge_diagnostics.spec",
        )
    ).lower()
    forbidden = (
        "add-mppreference",
        "set-mppreference",
        "netsh advfirewall",
        "new-netfirewallrule",
        "schtasks",
        "register-scheduledtask",
        "currentversion\\run",
        "startup\\",
        "--upx",
        "upx=true",
        "urlretrieve",
        "invoke-webrequest",
        "start-bitstransfer",
        "certutil -urlcache",
        "wget ",
        "curl ",
        "begin private key",
    )
    assert not any(item in implementation for item in forbidden)
    assert implementation.count("upx=false") == 4
    assert "--noupx" not in implementation


def test_installer_paths_identity_acls_and_service_registration_are_restricted():
    installer = (ROOT / "windows" / "installer.iss").read_text()
    lowered = installer.lower()
    assert "defaultdirname={autopf}\\sct\\scalebridge" in lowered
    assert "{commonappdata}\\sct\\scalebridge" in lowered
    assert (
        'binpath= ""{app}\\service\\sctpreweightscalebridgeservice.exe""'
        in lowered
    )
    assert 'obj= ""nt authority\\localservice""' in lowered
    assert "users-modify" not in lowered
    assert "users-full" not in lowered
    assert "everyone" not in lowered
    assert "authusers-modify" not in lowered
    assert "{userappdata}" not in lowered
    assert "{localappdata}" not in lowered
    assert "{userstartup}" not in lowered
    assert "{commonstartup}" not in lowered
    assert '""local service:(oi)(ci)rx""' in lowered
    assert '""local service:(oi)(ci)m""' in lowered


def test_runtime_has_no_remote_download_or_unexpected_listener_surface():
    diagnostics = (ROOT / "windows" / "diagnostics.py").read_text()
    host = (ROOT / "host.py").read_text()
    api = (ROOT / "api.py").read_text()
    assert 'urlopen(f"http://127.0.0.1:' in diagnostics
    assert "https://" not in diagnostics
    assert 'LOOPBACK_HOST = "127.0.0.1"' in api
    assert "0.0.0.0" not in api + host
    assert "subprocess" not in host + api


def test_signing_is_external_sha256_timestamped_and_contains_no_key_material():
    build = (ROOT / "windows" / "build.ps1").read_text()
    assert "'/fd', 'SHA256'" in build
    assert "'/tr', $TimestampUrl" in build
    assert "'/td', 'SHA256'" in build
    assert "Get-Command signtool.exe" in build
    lowered = build.lower()
    assert ".pfx" not in lowered
    assert "certificatepassword" not in lowered
    assert "private key" not in lowered


def test_build_script_stops_after_failed_native_stage_and_checks_artifacts():
    build = (ROOT / "windows" / "build.ps1").read_text()
    assert "function Invoke-NativeStage" in build
    assert "if ($LASTEXITCODE -ne 0)" in build
    assert 'throw "Build stage failed: $Stage' in build
    assert "function Assert-BuildPath" in build
    for stage in (
        "Install pinned build dependencies",
        "Run Scale Bridge tests",
        "Build Scale Bridge service bundle",
        "Build diagnostics bundle",
        "Compile Inno Setup installer",
        "Verify final installer artifact",
    ):
        assert stage in build
    assert "Get-FileHash -LiteralPath $Installer -Algorithm SHA256" in build
    assert "--noupx" not in build
