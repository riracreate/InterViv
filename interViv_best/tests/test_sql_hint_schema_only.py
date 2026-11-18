"""SQL item hints name constructs from the schema, never the reference query."""

from __future__ import annotations

import json

from backend.learning_hints import item_hint


def test_sql_hint_ignores_constructs_that_exist_only_in_the_reference_query() -> None:
    item = {
        "difficulty": "medium",
        "schema_ddl": (
            "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT);"
        ),
        "reference_query": (
            "SELECT name FROM employees WHERE secret_token_zz = 1 "
            "GROUP BY name HAVING COUNT(*) > 1 "
            "WINDOW w AS (ORDER BY id)"
        ),
    }
    hint = item_hint("sql", item, "SQL")
    keys = [row["construct"] for row in hint["constructs"]]
    assert keys == []
    blob = json.dumps(hint)
    assert "secret_token_zz" not in blob
    assert "having" not in keys
    assert "window" not in keys
    assert "group_by" not in keys


def test_sql_hint_may_name_a_join_that_the_schema_already_shows() -> None:
    item = {
        "difficulty": "easy",
        "schema_ddl": (
            "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);"
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL);"
        ),
        "reference_query": (
            "SELECT name, DENSE_RANK() OVER (ORDER BY amount) AS secret_rank_token "
            "FROM customers c JOIN orders o ON o.customer_id = c.id"
        ),
    }
    hint = item_hint("sql", item, "SQL")
    keys = [row["construct"] for row in hint["constructs"]]
    assert keys == ["join"]
    blob = json.dumps(hint)
    assert "secret_rank_token" not in blob
    assert "window" not in keys
    assert "DENSE_RANK" not in blob
