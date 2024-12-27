from sftkit.database import Connection
from sftkit.database.introspection import list_constraints, list_functions, list_triggers, list_views


async def test_introspection_functions(test_db_conn: Connection):
    funcs = await list_functions(test_db_conn, "public")
    assert len([x for x in funcs if x.proname == "test_func"]) > 0


async def test_introspection_view(test_db_conn: Connection):
    views = await list_views(test_db_conn, "public")
    assert len([x for x in views if x.table_name == "user_with_post_count"]) > 0


async def test_introspection_triggers(test_db_conn: Connection):
    triggers = await list_triggers(test_db_conn, "public")
    assert len([x for x in triggers if x.trigger_name == "create_user_trigger"]) > 0


async def test_introspection_constraints(test_db_conn: Connection):
    constraints = await list_constraints(test_db_conn, "public")
    assert len([x for x in constraints if x.conname == "username_allowlist"]) > 0
