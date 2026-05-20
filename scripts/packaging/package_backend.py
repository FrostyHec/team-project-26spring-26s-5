#!/usr/bin/env python3
"""Build the packaged backend staging directory."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUILD_ROOT = ROOT / "build" / "package"
DEFAULT_STAGING_DIR = DEFAULT_BUILD_ROOT / "backend-staging"
DEFAULT_PYINSTALLER_WORK = DEFAULT_BUILD_ROOT / "pyinstaller-work"
DEFAULT_PYINSTALLER_DIST = DEFAULT_BUILD_ROOT / "pyinstaller-dist"


def _run(command: list[str], *, cwd: Path = ROOT) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def _copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _backend_binary_name() -> str:
    return "react-agent-backend.exe" if platform.system() == "Windows" else "react-agent-backend"


def _find_backend_binary(dist_dir: Path) -> Path:
    expected = dist_dir / _backend_binary_name()
    if expected.exists():
        return expected
    candidates = list(dist_dir.rglob(_backend_binary_name()))
    if candidates:
        return candidates[0]
    raise FileNotFoundError(f"PyInstaller output not found: {expected}")


def _write_packaged_env(env_example: Path, env_file: Path) -> None:
    """Write the editable packaged env file with release layout defaults."""
    lines = env_example.read_text(encoding="utf-8").splitlines()
    patched: list[str] = []
    data_path_written = False
    for line in lines:
        if line.startswith("DATA_PATH="):
            patched.append("DATA_PATH=../output")
            data_path_written = True
        else:
            patched.append(line)
    if not data_path_written:
        patched.append("DATA_PATH=../output")
    env_file.write_text("\n".join(patched) + "\n", encoding="utf-8")


def build_backend(args: argparse.Namespace) -> Path:
    staging_dir = args.staging_dir.resolve()
    gui_dist = args.gui_dist.resolve()
    env_example = args.env_example.resolve()
    pyinstaller_work = args.pyinstaller_work.resolve()
    pyinstaller_dist = args.pyinstaller_dist.resolve()

    if not args.skip_gui_build:
        _run(["pnpm", "--dir", "packages/gui", "build"])

    index_file = gui_dist / "index.html"
    if not index_file.is_file():
        raise FileNotFoundError(f"GUI dist is missing index.html: {gui_dist}")
    if not env_example.is_file():
        raise FileNotFoundError(f"Env template not found: {env_example}")

    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    pyinstaller_work.mkdir(parents=True, exist_ok=True)
    pyinstaller_dist.mkdir(parents=True, exist_ok=True)

    _run(
        [
            "uv",
            "run",
            "--extra",
            "dev",
            "pyinstaller",
            "packaging/agent_cli_packaged.spec",
            "--noconfirm",
            "--clean",
            "--workpath",
            str(pyinstaller_work),
            "--distpath",
            str(pyinstaller_dist),
        ],
        cwd=ROOT / "packages" / "cli",
    )

    backend_bin = _find_backend_binary(pyinstaller_dist)
    bin_dir = staging_dir / "bin"
    config_dir = staging_dir / "config"
    output_dir = staging_dir / "output"
    bin_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    staged_backend = bin_dir / backend_bin.name
    shutil.copy2(backend_bin, staged_backend)
    staged_backend.chmod(staged_backend.stat().st_mode | 0o111)
    _copy_tree(gui_dist, staging_dir / "gui")
    _write_packaged_env(env_example, config_dir / ".env")
    shutil.copy2(config_dir / ".env", config_dir / "env.template")
    _copy_tree(ROOT / "pdfs", output_dir / "pdfs")
    (output_dir / "pdfs").mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": "react-agent",
        "version": args.version,
        "platform": platform.platform(),
        "backend": str(Path("bin") / staged_backend.name),
        "gui": "gui",
        "env_file": "config/.env",
        "default_data_path": "output",
        "default_policy_pdf_dir": "output/pdfs",
    }
    (staging_dir / "package-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Backend staging created: {staging_dir}", flush=True)
    return staging_dir


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-dir", type=Path, default=DEFAULT_STAGING_DIR)
    parser.add_argument("--gui-dist", type=Path, default=ROOT / "packages" / "gui" / "dist")
    parser.add_argument("--env-example", type=Path, default=ROOT / ".env.example")
    parser.add_argument("--pyinstaller-work", type=Path, default=DEFAULT_PYINSTALLER_WORK)
    parser.add_argument("--pyinstaller-dist", type=Path, default=DEFAULT_PYINSTALLER_DIST)
    parser.add_argument("--version", default="internal")
    parser.add_argument("--skip-gui-build", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    build_backend(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
