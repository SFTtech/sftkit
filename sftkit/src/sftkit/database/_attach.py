import contextlib
import os
import shutil
import tempfile

from sftkit import util
from sftkit.database._config import DatabaseConfig


async def psql_attach(config: DatabaseConfig):
    with contextlib.ExitStack() as exitstack:
        env = dict(os.environ)
        env["PGDATABASE"] = config.dbname

        if config.user is None:
            if config.host is not None:
                raise ValueError("database user is None, but host is set")
            if config.password is not None:
                raise ValueError("database user is None, but password is set")
        else:

            def escape_colon(value: str):
                return value.replace("\\", "\\\\").replace(":", "\\:")

            if config.user is not None and config.password is not None and config.host is not None:
                passfile = exitstack.enter_context(tempfile.NamedTemporaryFile("w"))
                os.chmod(passfile.name, 0o600)

                passfile.write(
                    ":".join(
                        [
                            escape_colon(config.host),
                            "*",
                            escape_colon(config.dbname),
                            escape_colon(config.user),
                            escape_colon(config.password),
                        ]
                    )
                )
                passfile.write("\n")
                passfile.flush()
                env["PGPASSFILE"] = passfile.name
                env["PGHOST"] = config.host
                env["PGUSER"] = config.user

        command = ["psql", "--variable", "ON_ERROR_STOP=1"]
        if shutil.which("pgcli") is not None:
            # if pgcli is installed, use that instead!
            command = ["pgcli"]

        ret = await util.run_as_fg_process(command, env=env)
        return ret
