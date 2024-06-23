import asyncio
from types import SimpleNamespace
from typing import Annotated

import typer

from sftkit import database
from sftkit.devel._config import read_config
from sftkit.util import log_setup

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

    config = read_config()
    ctx.obj = SimpleNamespace(config=config)


@cli.command()
def create_migration(ctx: typer.Context, name: str):
    """Create a new database migration"""
    database.create_migration(ctx.obj.config.db_migrations_dir, name)


def cli_main():
    cli()
