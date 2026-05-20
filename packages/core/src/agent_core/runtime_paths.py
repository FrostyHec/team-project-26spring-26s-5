"""Runtime path helpers shared by packaged and development entry points."""

import os
from pathlib import Path

ENV_FILE_ENV_KEY = "REACT_AGENT_ENV_FILE"
DEFAULT_DATA_PATH = "./output"


def set_runtime_env_file(env_file: str | Path | None) -> None:
    """Record the active env file path for later path resolution."""
    if env_file is not None:
        os.environ[ENV_FILE_ENV_KEY] = str(Path(env_file).expanduser())


def get_runtime_env_file(env_file: str | Path | None = None) -> Path | None:
    """Return the explicit runtime env file, if one is configured."""
    raw = str(env_file) if env_file is not None else os.getenv(ENV_FILE_ENV_KEY, "")
    if not raw.strip():
        return None
    return Path(raw).expanduser()


def get_runtime_base_dir(env_file: str | Path | None = None) -> Path | None:
    """Return the directory relative runtime paths should resolve from."""
    resolved_env_file = get_runtime_env_file(env_file)
    if resolved_env_file is None:
        return None
    return resolved_env_file.resolve().parent


def resolve_runtime_path(value: str | Path, base_dir: Path | None = None) -> Path:
    """Resolve a runtime path, keeping normal cwd-relative behavior by default."""
    path = Path(value).expanduser()
    if path.is_absolute() or base_dir is None:
        return path
    return base_dir / path


def resolve_path_env(
    name: str,
    default: str | Path,
    *,
    base_dir: Path | None = None,
) -> Path:
    """Resolve a path env var, treating missing or empty values as unset."""
    effective_base_dir = base_dir if base_dir is not None else get_runtime_base_dir()
    raw = os.getenv(name, "")
    value = raw if raw.strip() else default
    return resolve_runtime_path(value, effective_base_dir)


def resolve_data_path(*, base_dir: Path | None = None) -> Path:
    """Resolve DATA_PATH with the project default when unset."""
    return resolve_path_env("DATA_PATH", DEFAULT_DATA_PATH, base_dir=base_dir)
