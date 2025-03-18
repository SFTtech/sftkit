# SFTKit

A general purpose collection of base building blocks and utilities to make building 
python applications on the basis of postgresql (asyncpg) + fastapi a breeze.

## Getting Started
To get started simply run

```bash
pip install sftkit
```

A basic server could look like this
```python
import asyncio
from dataclasses import dataclass

from sftkit.http import Server, HTTPServerConfig
from fastapi import APIRouter


config = HTTPServerConfig(base_url="/api/v1", port=8074, host="127.0.0.1")

router = APIRouter(
    responses={404: {"description": "not found"}},
)

@router.get("/ping")
async def ping():
    return "pong"


@dataclass
class Context:
    config: HTTPServerConfig


class Api:
    def __init__(self, config: HTTPServerConfig = config):
        self.config = config
        self.server = Server(
            title="<your title>",
            config=config,
            license_name="<your license>",
            version="0.1.0"

        )
        self.server.add_router(router)

    async def run(self):
        context = Context(config=self.config)
        await self.server.run(context)

if __name__ == "__main__":
    server = Api()
    asyncio.run(server.run())
```

Copy the code to `main.py` and run the server using `python main.py`.

You can ping the server at [http://127.0.0.1:8074/api/v1/ping](http://127.0.0.1:8074/api/v1/ping) or inspect the API specification at [http://127.0.0.1:8074/api/v1/docs](http://127.0.0.1:8074/api/v1/docs).

## Usage


### Dev CLI

Configure sftkit in your `pyproject.toml`

```toml
[tool.sftkit]
db_code_dir = "<path-to-your-sql-code-folder>"
db_migrations_dir = "<path-to-your-sql-data-migrations>"
```

Create new migrations via

```bash
sftkit create-migration <name>
```
