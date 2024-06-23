from typing import Generic, TypeVar

from fastapi import Request, WebSocket
from starlette.types import ASGIApp, Receive, Scope, Send

ContextT = TypeVar("ContextT")


class ContextMiddleware(Generic[ContextT]):
    """
    FastAPI middleware to make any variable available in a request.
    Works through ASGI magic: https://www.starlette.io/middleware/

    # Usage:
    from fastapi import FastAPI, Request, Depends
    api = FastAPI()
    context = Context(...)
    api.add_middleware(ContextMiddleware,
                       context=context,
                       example_query="select version();")

    # define dependency extractor
    def get_context(request: Request) -> Any:
        return request.state.context

    def get_db_pool(request: Request) -> asyncpg.Pool:
        return request.state.context.db_pool

    async def get_db_conn(
        db_pool: asyncpg.Pool = Depends(get_db_pool),
    ) -> Connection:
    async with db_pool.acquire() as conn:
        yield conn

    # in the request:
    @router.get("/dbversion")
    async def dbver(req: Request,
                    conn=Depends(get_db_conn),
                    ctx=Depends(get_context)):
        query = req.state.args.example_query
        # another way:
        # example_value == ctx.example_value
        dbver = await conn.fetchrow(query)
        return {"db_version": f"{dbver[0]}"}
    """

    def __init__(
        self,
        app: ASGIApp,
        context: ContextT,
        **args,
    ) -> None:
        self._app = app

        # store whatever else we need in request handling
        self.context = context
        self.args = args

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # build the request object that is available in the request handler
        # it magically gets passed through the "scope" parameter...
        # https://www.starlette.io/middleware/
        if scope["type"] == "http":
            req: Request | WebSocket = Request(scope, receive, send)
        elif scope["type"] == "websocket":
            req = WebSocket(scope, receive, send)
        else:
            return await self._app(scope, receive, send)

        # add links in the request.state to our shared members
        req.state.context = self.context
        req.state.args = self.args

        await self._app(scope, receive, send)
