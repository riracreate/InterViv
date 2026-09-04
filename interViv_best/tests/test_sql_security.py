"""Unit and security regression tests for the SQL sandboxed execution environment."""

from __future__ import annotations

import sqlite3
import pytest

from modules.scoring.sql_security import (
    SQLSecurityError,
    SQLSingleStatementError,
    SQLTimeoutError,
    check_forbidden_constructs,
    execute_sandboxed_sql,
    extract_sql_tokens,
    validate_single_read_only_statement,
)


@pytest.fixture
def sandbox_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users (id INT, name TEXT, salary REAL);")
    conn.execute("INSERT INTO users VALUES (1, 'Alice', 50000.0), (2, 'Bob', 60000.0), (3, 'Charlie', 70000.0);")
    yield conn
    conn.close()


# ── 1. Single statement & read-only validation ──────────────────────────────

def test_rejects_empty_or_whitespace_query():
    with pytest.raises(SQLSingleStatementError, match="cannot be empty"):
        validate_single_read_only_statement("")
    with pytest.raises(SQLSingleStatementError, match="cannot be empty"):
        validate_single_read_only_statement("   \n\t  ")


def test_rejects_non_select_statements():
    for stmt in ["INSERT INTO users VALUES (4, 'Dave', 40000);", "DELETE FROM users;", "UPDATE users SET salary = 0;", "DROP TABLE users;"]:
        with pytest.raises(SQLSingleStatementError, match="Only read-only SELECT or WITH"):
            validate_single_read_only_statement(stmt)


def test_allows_select_and_with_statements():
    validate_single_read_only_statement("SELECT * FROM users;")
    validate_single_read_only_statement("WITH high_earners AS (SELECT * FROM users WHERE salary > 55000) SELECT * FROM high_earners;")
    validate_single_read_only_statement("SELECT id, name FROM users")  # without trailing semicolon


def test_rejects_multiple_statements():
    with pytest.raises(SQLSingleStatementError, match="Multiple SQL statements are not permitted"):
        validate_single_read_only_statement("SELECT 1; SELECT 2;")
    with pytest.raises(SQLSingleStatementError, match="Multiple SQL statements are not permitted"):
        validate_single_read_only_statement("SELECT 1; DROP TABLE users;")


def test_ignores_semicolons_in_strings_and_comments():
    # Semicolons inside comments and strings must not trigger multiple-statement rejection
    query = """
    -- line comment with a semicolon ; and DROP TABLE users;
    SELECT 'hello; world; -- still in string' AS msg /* block comment ; */
    FROM users
    WHERE name = 'Alice;';
    """
    validate_single_read_only_statement(query)


# ── 2. Authorizer enforcement ───────────────────────────────────────────────

def test_authorizer_allows_safe_select_and_aggregates(sandbox_db: sqlite3.Connection):
    cols, rows, trunc, ms = execute_sandboxed_sql(
        conn=sandbox_db,
        query="SELECT COUNT(*), AVG(salary), MAX(salary), MIN(salary), SUM(salary) FROM users;",
    )
    assert cols == ["COUNT(*)", "AVG(salary)", "MAX(salary)", "MIN(salary)", "SUM(salary)"]
    assert rows == [(3, 60000.0, 70000.0, 50000.0, 180000.0)]
    assert not trunc


def test_authorizer_allows_window_functions(sandbox_db: sqlite3.Connection):
    query = """
    SELECT id, name, salary,
           RANK() OVER (ORDER BY salary DESC) as sal_rank,
           DENSE_RANK() OVER (ORDER BY salary DESC) as dense_rank,
           ROW_NUMBER() OVER (ORDER BY salary DESC) as row_num
    FROM users;
    """
    cols, rows, trunc, ms = execute_sandboxed_sql(conn=sandbox_db, query=query)
    assert len(rows) == 3
    assert rows[0][3] == 1  # top rank


def test_authorizer_denies_all_write_and_ddl_actions():
    from modules.scoring.sql_security import create_sqlite_authorizer
    authorizer = create_sqlite_authorizer()

    # DML actions
    assert authorizer(sqlite3.SQLITE_INSERT, "users", None, "main", None) == sqlite3.SQLITE_DENY
    assert authorizer(sqlite3.SQLITE_UPDATE, "users", "salary", "main", None) == sqlite3.SQLITE_DENY
    assert authorizer(sqlite3.SQLITE_DELETE, "users", None, "main", None) == sqlite3.SQLITE_DENY

    # DDL actions
    assert authorizer(sqlite3.SQLITE_CREATE_TABLE, "hacked", None, "main", None) == sqlite3.SQLITE_DENY
    assert authorizer(sqlite3.SQLITE_DROP_TABLE, "users", None, "main", None) == sqlite3.SQLITE_DENY
    assert authorizer(sqlite3.SQLITE_ALTER_TABLE, "users", None, "main", None) == sqlite3.SQLITE_DENY

    # PRAGMA, ATTACH, TRANSACTION
    assert authorizer(sqlite3.SQLITE_PRAGMA, "table_info", None, "main", None) == sqlite3.SQLITE_DENY
    assert authorizer(sqlite3.SQLITE_ATTACH, "test.db", None, "main", None) == sqlite3.SQLITE_DENY
    assert authorizer(sqlite3.SQLITE_TRANSACTION, "BEGIN", None, "main", None) == sqlite3.SQLITE_DENY


def test_authorizer_blocks_pragma(sandbox_db: sqlite3.Connection):
    with pytest.raises((SQLSecurityError, SQLSingleStatementError)):
        execute_sandboxed_sql(conn=sandbox_db, query="PRAGMA table_info(users);")


def test_authorizer_blocks_attach_detach(sandbox_db: sqlite3.Connection):
    with pytest.raises((SQLSecurityError, SQLSingleStatementError)):
        execute_sandboxed_sql(conn=sandbox_db, query="ATTACH DATABASE ':memory:' AS shadow;")


def test_authorizer_blocks_dangerous_functions(sandbox_db: sqlite3.Connection):
    # Built-in load_extension function
    with pytest.raises(SQLSecurityError, match="not authorized to use function"):
        execute_sandboxed_sql(conn=sandbox_db, query="SELECT load_extension('malicious');")

    # Custom untrusted Python function registered on the connection
    sandbox_db.create_function("custom_evil_payload", 1, lambda x: x)
    with pytest.raises(SQLSecurityError, match="not authorized to use function"):
        execute_sandboxed_sql(conn=sandbox_db, query="SELECT custom_evil_payload('test');")


# ── 3. Monotonic timeout & opcode budget ────────────────────────────────────

def test_progress_handler_interrupts_infinite_recursive_cte(sandbox_db: sqlite3.Connection):
    infinite_query = """
    WITH RECURSIVE loop(x) AS (
        SELECT 1
        UNION ALL
        SELECT x + 1 FROM loop
    )
    SELECT * FROM loop;
    """
    with pytest.raises(SQLTimeoutError, match="exceeded resource limit"):
        execute_sandboxed_sql(
            conn=sandbox_db,
            query=infinite_query,
            timeout_seconds=0.2,
            max_opcodes=5000,
        )


# ── 4. Row capping & truncation ─────────────────────────────────────────────

def test_row_capping_and_truncation():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE large_table (n INT);")
    for i in range(1500):
        conn.execute("INSERT INTO large_table VALUES (?);", (i,))

    cols, rows, trunc, ms = execute_sandboxed_sql(
        conn=conn,
        query="SELECT n FROM large_table;",
        max_rows=1000,
    )
    assert trunc is True
    assert len(rows) == 1000
    assert rows[0] == (0,)
    assert rows[-1] == (999,)
    conn.close()


# ── 5. Token-aware forbidden constructs checker ─────────────────────────────

def test_check_forbidden_constructs_flags_actual_usage():
    query = "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id;"
    found = check_forbidden_constructs(query, ["join"])
    assert found == ["join"]

    query_multi = "SELECT name FROM users GROUP BY name HAVING count(*) > 1;"
    found_multi = check_forbidden_constructs(query_multi, ["group by", "having"])
    assert found_multi == ["group by", "having"]


def test_check_forbidden_constructs_ignores_strings_and_comments():
    query = """
    -- Note: We do not use join here
    /* Also avoid any join */
    SELECT 'join us in this union' AS invitation, 'group by group' AS phrase
    FROM users;
    """
    found = check_forbidden_constructs(query, ["join", "group by"])
    assert found == []
