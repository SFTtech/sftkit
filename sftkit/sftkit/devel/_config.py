import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class SftkitDevelConfig(BaseModel):
    db_code_dir: Path
    db_migrations_dir: Path


def _load_toml(path: Path) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _find_pyproject_toml(start_path: Path | None) -> Path | None:
    for directory in (start_path, *start_path.parents):
        pyproject_path = directory / "pyproject.toml"
        if pyproject_path.is_file():
            pyproject_toml = _load_toml(pyproject_path)
            if "sftkit" in pyproject_toml.get("tool", {}):
                return pyproject_path

    return None


def _parse_pyproject_toml(pyproject_toml_path: Path) -> SftkitDevelConfig:
    pyproject_toml = _load_toml(pyproject_toml_path)
    config: dict[str, Any] = pyproject_toml.get("tool", {}).get("sftkit", {})
    return SftkitDevelConfig.model_validate(config)


def read_config(search_path: Path | None = None) -> SftkitDevelConfig:
    start_path = search_path or Path.cwd()
    pyproject_path = _find_pyproject_toml(start_path)
    if pyproject_path is None:
        raise ValueError(f"Could not find a pyproject.toml file in any directory above {start_path}")
    parsed = _parse_pyproject_toml(pyproject_path)
    return parsed
