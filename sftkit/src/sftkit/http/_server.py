"""
http server base class
"""

import asyncio
import logging
from typing import Generic, TypeVar
from urllib.parse import urlparse

import asyncpg
import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from ._config import HTTPServerConfig
from ._context import ContextMiddleware
from ._error import (
    AccessDenied,
    NotFound,
    ServiceException,
    Unauthorized,
    access_exception_handler,
    bad_request_exception_handler,
    catchall_exception_handler,
    not_found_exception_handler,
    service_exception_handler,
    try_again_later_exception_handler,
    unauthorized_exception_handler,
)

ContextT = TypeVar("ContextT")


def use_route_names_as_operation_ids(app: FastAPI) -> None:
    """
    Simplify operation IDs so that generated API clients have simpler function
    names.

    Should be called only after all routes have been added.
    """
    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name


class Server(Generic[ContextT]):
    def __init__(self, title: str, config: HTTPServerConfig, version: str, license_name: str, cors: bool = False):
        parsed_base_url = urlparse(config.base_url)
        root_path = parsed_base_url.path
        self.api = FastAPI(
            title=title,
            version=version,
            license_info={"name": license_name},
            root_path=root_path,
        )

        self.api.add_exception_handler(NotFound, not_found_exception_handler)
        self.api.add_exception_handler(ServiceException, service_exception_handler)
        self.api.add_exception_handler(AccessDenied, access_exception_handler)
        self.api.add_exception_handler(Unauthorized, unauthorized_exception_handler)
        self.api.add_exception_handler(
            asyncpg.exceptions.IntegrityConstraintViolationError, bad_request_exception_handler
        )
        self.api.add_exception_handler(asyncpg.exceptions.DeadlockDetectedError, try_again_later_exception_handler)
        self.api.add_exception_handler(asyncpg.exceptions.SerializationError, try_again_later_exception_handler)
        self.api.add_exception_handler(asyncpg.exceptions.RaiseError, bad_request_exception_handler)
        self.api.add_exception_handler(Exception, catchall_exception_handler)

        if cors:
            self.api.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
                expose_headers=["Content-Range"],
            )

        forward_allowed_ips = None

        # TODO: IPv6
        if config.host == "localhost" or config.host.startswith("127.") or config.host == "::1":
            forward_allowed_ips = "*"

        self.tasks: list[asyncio.Task] = []

        self.uvicorn_config = uvicorn.Config(
            self.api,
            host=config.host,
            port=config.port,
            log_level=logging.root.level,
            forwarded_allow_ips=forward_allowed_ips,
        )

    def add_router(self, router: APIRouter):
        self.api.include_router(router)
        use_route_names_as_operation_ids(self.api)

    def add_task(self, task: asyncio.Task):
        self.tasks.append(task)

    def get_openapi_spec(self) -> dict:
        return self.api.openapi()

    async def run(self, context: ContextT):
        # register service instances so they are available in api routes
        # kwargs set here can then be fetched with `name = Depends($name)`
        # in the router kwargs.

        self.api.add_middleware(
            ContextMiddleware,  # type: ignore
            context=context,  # type: ignore
        )
        webserver = uvicorn.Server(self.uvicorn_config)
        await webserver.serve()

        for task in self.tasks:
            task.cancel()
