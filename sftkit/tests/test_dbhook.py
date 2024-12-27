import asyncio

from sftkit.database import DatabaseHook, Pool


async def test_hook(test_db_pool: Pool):
    initial_run: bool = False
    received_payload: str = ""

    async def trigger(payload):
        nonlocal initial_run, received_payload
        # payload is none when the hook is run without a trigger first.
        if payload is None:
            initial_run = True
            return

        received_payload = payload

    hook: DatabaseHook | None = None

    async def hook_coro(**hook_args):
        nonlocal hook
        hook = DatabaseHook(pool=test_db_pool, **hook_args)
        await hook.run()

    # first round - with initial run
    ht = asyncio.create_task(hook_coro(channel="testchannel", event_handler=trigger, initial_run=True))
    await asyncio.sleep(0.5)  # wait for connection listener to be set up
    await test_db_pool.execute("select pg_notify('testchannel', 'rolf');")
    assert hook is not None
    await asyncio.sleep(0.2)  # wait for the notification to arrive
    hook.stop()
    await ht

    assert initial_run
    assert received_payload == "rolf"

    # second round - without initial run
    initial_run = False
    received_payload = ""

    ht = asyncio.create_task(hook_coro(channel="testchannel", event_handler=trigger, initial_run=False))
    await asyncio.sleep(0.5)  # wait for connection listener to be set up
    await test_db_pool.execute("select pg_notify('testchannel', 'lol');")
    assert hook is not None
    await asyncio.sleep(0.2)  # wait for the notification to arrive
    hook.stop()
    await ht

    assert not initial_run
    assert received_payload == "lol"
