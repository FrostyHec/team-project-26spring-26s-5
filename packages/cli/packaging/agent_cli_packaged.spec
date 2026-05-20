# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


spec_dir = Path(SPECPATH)
cli_root = spec_dir.parent
repo_root = cli_root.parent.parent


datas = collect_data_files(
    "agent_core",
    includes=[
        "prompts/**",
        "skills/**/*.json",
        "policy_search/**/*.json",
    ],
)
hiddenimports = (
    collect_submodules("agent_core")
    + collect_submodules("agent_cli")
    + collect_submodules("uvicorn")
    + collect_submodules("uvicorn.protocols")
    + collect_submodules("uvicorn.loops")
)

a = Analysis(
    [str(cli_root / "src" / "agent_cli" / "main.py")],
    pathex=[
        str(cli_root / "src"),
        str(repo_root / "packages" / "core" / "src"),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="react-agent-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
