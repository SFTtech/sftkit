from sftkit.database import Database


async def test_reload_code(test_db: Database):
    await test_db.reload_code()
