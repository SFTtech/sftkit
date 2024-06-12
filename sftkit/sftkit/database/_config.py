from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    user: str | None = None
    password: str | None = None
    host: str | None = None
    port: int | None = 5432
    dbname: str
    require_ssl: bool = False
    sslrootcert: str | None = None
