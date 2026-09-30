# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "windows" / "diagnostics.py")],
    pathex=[str(ROOT.parent)],
    binaries=[],
    datas=[],
    hiddenimports=["serial.tools.list_ports_windows"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["flask", "sqlalchemy", "psycopg", "pyodbc"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SCTPreweightScaleBridgeDiagnostics",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
)
bundle = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SCTPreweightScaleBridgeDiagnostics",
)
