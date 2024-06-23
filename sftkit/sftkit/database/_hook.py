"""
database notification subscriber
"""

import asyncio
import contextlib
import inspect
import logging
from typing import Callable, Coroutine, Optional

import asyncpg.exceptions

from ._connection import Connection


class DatabaseHook:
    """
    Implements a database hook to subscribe to one specific pg_notify notification channel.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        channel: str,
        event_handler: Callable[[Optional[str]], Coroutine],
        initial_run: bool = False,
        hook_timeout: int = 5,
    ):
        """
        connection: open database connection
        channel: subscription channel of the database
        event_handler: async function which receives the payload of the database notification as argument
        initial_run: true if we shall call the handler once after startup with None as argument.
        """
        self.db_pool = pool
        self.channel = channel
        self.event_handler = event_handler
        assert inspect.iscoroutinefunction(event_handler)
        self.initial_run = initial_run
        self.timelimit = hook_timeout

        self.events: asyncio.Queue[str | StopIteration] = asyncio.Queue(maxsize=2048)
        self.logger = logging.getLogger(__name__)

        self.current_tasks: set[asyncio.Task] = set()

    @contextlib.asynccontextmanager
    async def acquire_conn(self):
        async with self.db_pool.acquire() as conn:
            await self._register(conn=conn)
            try:
                yield conn
            finally:
                await self._deregister(conn=conn)

    async def _register(self, conn: Connection):
        await conn.add_listener(self.channel, self.notification_callback)

    async def _deregister(self, conn: Connection):
        await conn.remove_listener(self.channel, self.notification_callback)

    def stop(self):
        # proper way of clearing asyncio queue
        for _ in range(self.events.qsize()):
            self.events.get_nowait()
            self.events.task_done()
        self.events.put_nowait(StopIteration())

    async def stop_async(self):
        # proper way of clearing asyncio queue
        for _ in range(self.events.qsize()):
            self.events.get_nowait()
            self.events.task_done()
        await self.events.put(StopIteration())

    async def run(self, num_parallel=1):
        async with asyncio.TaskGroup() as tg:
            while True:
                try:
                    async with self.acquire_conn():
                        if self.initial_run:
                            # run the handler once to process pending data
                            await self.event_handler(None)

                        # handle events
                        while True:
                            event: str | StopIteration = await self.events.get()
                            if isinstance(event, StopIteration):
                                return

                            task: asyncio.Task = tg.create_task(self.event_handler(event))
                            self.current_tasks.add(task)

                            if len(self.current_tasks) >= num_parallel:
                                done, _ = await asyncio.wait(self.current_tasks, return_when=asyncio.FIRST_COMPLETED)
                                self.current_tasks.difference_update(done)

                            self.events.task_done()
                except asyncio.exceptions.TimeoutError:
                    self.logger.error("Timout occurred during DBHook.run")
                except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
                    self.logger.debug("Stopping DBHook.run due to cancellation")
                    return
                except Exception:
                    import traceback

                    self.logger.error(f"Error occurred during DBHook.run: {traceback.format_exc()}")
                    await asyncio.sleep(1)

    def notification_callback(self, connection: Connection, pid: int, channel: str, payload: str):
        """
        runs whenever we get a psql notification through pg_notify
        """
        del connection, pid
        assert channel == self.channel
        self.events.put_nowait(payload)
