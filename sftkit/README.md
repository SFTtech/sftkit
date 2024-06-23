# SFTKit

A general purpose collection of base building blocks and utilities to make building 
python applications on the basis of postgresql (asyncpg) + fastapi a breeze.

To get started simply run

```bash
pip install sftkit
```

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