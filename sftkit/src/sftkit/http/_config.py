from pydantic import BaseModel


class HTTPServerConfig(BaseModel):
    base_url: str
    host: str
    port: int
