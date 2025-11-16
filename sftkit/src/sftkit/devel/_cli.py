import asyncio
import json
from types import SimpleNamespace
from typing import Annotated, Optional

import typer

from sftkit import database
from sftkit.util import log_setup

from ._config import read_config
from ._debian import build_debian_packages as _build_debian_packages

cli = typer.Typer()


@cli.callback()
def get_config(
    ctx: typer.Context,
    quiet: Annotated[int, typer.Option("--quiet", "-q", count=True, help="decrease program verbosity")] = 0,
    verbose: Annotated[int, typer.Option("--verbose", "-v", count=True, help="increase program verbosity")] = 0,
    debug: Annotated[bool, typer.Option(help="enable asyncio debugging")] = False,
):
    log_setup(verbose - quiet)
    asyncio.get_event_loop().set_debug(debug)

    project_root, pyproject_toml, config = read_config()
    ctx.obj = SimpleNamespace(pyproject_toml=pyproject_toml, sftkit_config=config, project_root=project_root)


@cli.command()
def create_migration(ctx: typer.Context, name: str):
    """Create a new database migration"""
    database.create_migration(ctx.obj.sftkit_config.db_migrations_dir, name)


@cli.command()
def build_debian_packages(
    ctx: typer.Context,
    jobs: Annotated[int, typer.Option("--jobs", "-j", help="specify the number of builds to run in parallel")] = 1,
    no_check: Annotated[bool, typer.Option("--no-check", help="skip running tests after building")] = False,
    docker_executable: Annotated[
        str, typer.Option("--docker-executable", help="path to the docker executable")
    ] = "docker",
    docker_build_args: Annotated[
        Optional[list[str]], typer.Option("--docker-build-arg", help="arguments to pass to the underlying docker build")
    ] = None,
    dists: Annotated[Optional[list[str]], typer.Argument(help="a list of distributions to build for")] = None,
):
    """Build debian packages in docker container runners"""
    target_distros = dists or ctx.obj.sftkit_config.target_debian_distros
    if target_distros is None:
        print("No target distributions were configured in the [tool.sftkit] section in the pyproject.toml")
        raise typer.Exit(1)

    project_name = ctx.obj.pyproject_toml.project.name

    _build_debian_packages(
        project_name=project_name,
        jobs=jobs,
        distributions=target_distros,
        no_check=no_check,
        docker_executable=docker_executable,
        docker_build_args=docker_build_args or [],
        project_root=ctx.obj.project_root,
    )


@cli.command()
def list_debian_distros(
    ctx: typer.Context,
):
    """List configured debian package targets"""
    target_distros = ctx.obj.sftkit_config.target_debian_distros
    if target_distros is None:
        print("No target distributions were configured in the [tool.sftkit] section in the pyproject.toml")
        raise typer.Exit(1)

    print(json.dumps(ctx.obj.sftkit_config.target_debian_distros))


def cli_main():
    cli()
