import asyncio
import threading
import traceback


class AsyncThread:
    def __init__(self, coroutine_callable):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run)
        self.callable = coroutine_callable

    def _run(self):
        async def runner():
            try:
                await self.callable()
            except:  # pylint: disable=bare-except
                traceback.print_exc()
            print("runner exited")

        asyncio.set_event_loop(self.loop)
        self.loop.create_task(runner())
        self.loop.run_forever()

    def run_coroutine(self, coro):
        self.loop.create_task(coro)

    def start(self):
        self.thread.start()

    def join(self):
        self.thread.join()

    def stop(self):
        for task in asyncio.all_tasks(self.loop):
            task.cancel()
        self.loop.stop()
