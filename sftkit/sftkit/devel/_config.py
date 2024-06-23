import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class BuildSystem(BaseModel):
    requires: list[str] = []
    build_backend: str | None = None
    backend_path: list[str] = []


class Readme(BaseModel):
    file: str | None = None
    text: str | None = None
    content_type: str | None = None


class License(BaseModel):
    file: str | None = None
    text: str | None = None


class Contributor(BaseModel):
    name: str | None = None
    email: str | None = None


class ProjectConfig(BaseModel):
    name: str | None = None
    version: str | None = None
    description: str | None = None
    readme: str | Readme | None = None
    license: str | License | None = None
    authors: list[Contributor] = []
    maintainers: list[Contributor] = []
    keywords: list[str] = []
    classifiers: list[str] = []
    urls: dict[str, str] = {}
    requires_python: str | None = None
    dependencies: list[str] = []
    optional_dependencies: dict[str, list[str]] = {}
    scripts: dict[str, str] = {}
    gui_scripts: dict[str, str] = {}
    entry_points: dict[str, dict[str, str]] = {}
    dynamic: list[str] = []


class PyprojectTOML(BaseModel):
    build_system: BuildSystem | None = None
    project: ProjectConfig | None = None
    tool: dict[str, dict[str, Any]] = {}


class SftkitDevelConfig(BaseModel):
    db_code_dir: Path
    db_migrations_dir: Path

    target_debian_distros: list[str] | None = None


def _load_toml(path: Path) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _find_pyproject_toml(start_path: Path) -> Path | None:
    for directory in (start_path, *start_path.parents):
        pyproject_path = directory / "pyproject.toml"
        if pyproject_path.is_file():
            pyproject_toml = _load_toml(pyproject_path)
            if "sftkit" in pyproject_toml.get("tool", {}):
                return pyproject_path

    return None


def _parse_pyproject_toml(pyproject_toml_path: Path) -> tuple[PyprojectTOML, SftkitDevelConfig]:
    pyproject_toml = _load_toml(pyproject_toml_path)
    pyproject_config = PyprojectTOML.model_validate(pyproject_toml)
    sftkit_config: dict[str, Any] = pyproject_toml.get("tool", {}).get("sftkit", {})
    sftkit_parsed = SftkitDevelConfig.model_validate(sftkit_config)
    return pyproject_config, sftkit_parsed


def read_config(search_path: Path | None = None) -> tuple[Path, PyprojectTOML, SftkitDevelConfig]:
    start_path = search_path or Path.cwd()
    pyproject_path = _find_pyproject_toml(start_path)
    if pyproject_path is None:
        raise ValueError(f"Could not find a pyproject.toml file in any directory above {start_path}")
    pyproject_toml, sftkit_config = _parse_pyproject_toml(pyproject_path)
    return pyproject_path.parent, pyproject_toml, sftkit_config
