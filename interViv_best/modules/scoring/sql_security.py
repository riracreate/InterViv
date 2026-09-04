"""Security sandbox for single-statement read-only SQL query execution.

Enforces:
1. Single read-only statement: ordinary SELECT or read-only WITH ... SELECT.
2. Token-aware parser that ignores semicolons and keywords inside comments and string literals.
3. SQLite authorizer:
   - Allows SQLITE_SELECT, SQLITE_READ, SQLITE_RECURSIVE.
   - Allows safe whitelisted functions only.
   - Denies all writes, DDL, ATTACH, DETACH, PRAGMA, and custom/dangerous functions.
4. Pre-execution hardening: PRAGMA query_only = ON, PRAGMA temp_store = MEMORY, enable_load_extension(False).
5. Monotonic timeout and opcode budget via SQLite progress handler.
6. Row capping at max_rows (default 1,000).
"""

from __future__ import annotations

import re
import sqlite3
import time
from typing import Any


class SQLSecurityError(Exception):
    """Raised when a candidate query violates SQL execution security policies."""


class SQLTimeoutError(SQLSecurityError):
    """Raised when a candidate query exceeds the monotonic timeout or opcode budget."""


class SQLSingleStatementError(SQLSecurityError):
    """Raised when candidate SQL contains multiple statements, non-SELECT, or invalid syntax."""


SAFE_SQLITE_FUNCTIONS = frozenset({
    # Aggregate functions
    "avg", "count", "sum", "min", "max", "total", "group_concat",
    # Math
    "abs", "round",
    # String manipulation
    "lower", "upper", "length", "substr", "substring", "trim", "ltrim", "rtrim",
    "replace", "instr", "printf", "format", "like", "glob",
    # Conditional / Null handling
    "coalesce", "nullif", "ifnull", "iif",
    # Date & time functions
    "date", "time", "datetime", "julianday", "strftime",
    # Type inspection / conversion
    "cast", "typeof",
    # Window functions
    "rank", "dense_rank", "row_number", "percent_rank", "cume_dist",
    "ntile", "lead", "lag", "first_value", "last_value", "nth_value",
})

# Tokenizer pattern matching:
# 1. Single-quoted strings (handling escaped quotes '' as well)
# 2. Block comments /* ... */
# 3. Line comments -- ...
# 4. Words / symbols
_TOKEN_PATTERN = re.compile(
    r"('(?:''|[^'])*')"
    r"|(/\*[\s\S]*?\*/)"
    r"|(--[^\r\n]*)"
    r"|([A-Za-z0-9_]+|;|\S)"
)


def extract_sql_tokens(sql: str) -> tuple[str, list[str]]:
    """Extract code without comments/strings and return a list of lowercased tokens.

    Returns (cleaned_code, tokens).
    Comments and string literals are ignored, preventing false positives on semicolons
    or forbidden keywords inside string literals.
    """
    tokens: list[str] = []
    code_parts: list[str] = []

    for match in _TOKEN_PATTERN.finditer(sql or ""):
        str_lit, blk_comm, line_comm, token = match.groups()
        if str_lit:
            # Replace literal content with empty literal placeholder
            code_parts.append("''")
        elif blk_comm or line_comm:
            # Strip comments
            code_parts.append(" ")
        elif token:
            code_parts.append(token)
            tokens.append(token.lower())

    clean_sql = " ".join(code_parts).strip()
    return clean_sql, tokens


def validate_single_read_only_statement(sql: str) -> None:
    """Validate that sql is exactly one statement starting with SELECT or WITH.

    Raises SQLSingleStatementError if empty, multiple statements, or not read-only.
    """
    if not sql or not sql.strip():
        raise SQLSingleStatementError("SQL query cannot be empty.")

    clean_sql, tokens = extract_sql_tokens(sql)
    if not tokens:
        raise SQLSingleStatementError("SQL query contains no executable statements.")

    # Must start with SELECT or WITH
    first_token = tokens[0]
    if first_token not in ("select", "with"):
        raise SQLSingleStatementError(
            f"Only read-only SELECT or WITH statements are allowed. Got {first_token.upper()!r}."
        )

    # Check for unquoted semicolons
    # Allow at most one semicolon at the very end of the token stream
    semicolon_indices = [i for i, t in enumerate(tokens) if t == ";"]
    if semicolon_indices:
        # If any semicolon is not the last token, it is a multi-statement query
        if len(semicolon_indices) > 1 or semicolon_indices[0] != len(tokens) - 1:
            raise SQLSingleStatementError(
                "Multiple SQL statements are not permitted. Only a single statement is allowed."
            )

    # If it starts with WITH, verify that SELECT is present
    if first_token == "with" and "select" not in tokens:
        raise SQLSingleStatementError("WITH statements must terminate in a SELECT query.")


def check_forbidden_constructs(sql: str, forbidden_constructs: list[str] | None) -> list[str]:
    """Check if any forbidden keywords are present in the SQL tokens.

    Ignores occurrences inside strings and comments.
    Returns list of forbidden constructs found.
    """
    if not forbidden_constructs:
        return []

    _, tokens = extract_sql_tokens(sql)
    token_set = set(tokens)
    found = []
    for item in forbidden_constructs:
        item_lower = item.strip().lower()
        if not item_lower:
            continue
        # If item has multiple words (e.g. "group by"), check token sequence
        item_parts = item_lower.split()
        if len(item_parts) == 1:
            if item_lower in token_set:
                found.append(item)
        else:
            # Sequence check
            for i in range(len(tokens) - len(item_parts) + 1):
                if tokens[i:i + len(item_parts)] == item_parts:
                    found.append(item)
                    break

    return sorted(set(found))


def create_sqlite_authorizer():
    """Create a strict authorizer callback for candidate query execution."""
    def authorizer(action: int, p1: Any, p2: Any, dbname: Any, trigger: Any) -> int:
        # Read-only operations allowed
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_RECURSIVE):
            return sqlite3.SQLITE_OK

        # Function calls: check whitelist
        if action == sqlite3.SQLITE_FUNCTION:
            # In SQLite C authorizer, p2 is the function name for SQLITE_FUNCTION
            func_name = str(p2 or p1 or "").lower()
            if func_name in SAFE_SQLITE_FUNCTIONS:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        # All writes, DDL, transactions, PRAGMA, ATTACH, DETACH are denied
        return sqlite3.SQLITE_DENY

    return authorizer


def execute_sandboxed_sql(
    conn: sqlite3.Connection,
    query: str,
    *,
    timeout_seconds: float = 2.0,
    max_opcodes: int = 100_000,
    max_rows: int = 1000,
) -> tuple[list[str], list[tuple[Any, ...]], bool, float]:
    """Execute a candidate SQL query inside the SQLite sandbox.

    Parameters:
      conn: SQLite connection with schema and test case data already loaded.
      query: The candidate's SQL query string.
      timeout_seconds: Hard monotonic deadline in seconds.
      max_opcodes: Maximum SQLite VM steps before abortion.
      max_rows: Maximum rows to fetch before marking truncated.

    Returns:
      (columns, rows, truncated, elapsed_ms)

    Raises:
      SQLSingleStatementError: if query violates single statement / SELECT rule.
      SQLTimeoutError: if execution exceeds monotonic timeout or opcode budget.
      SQLSecurityError: if authorizer denies an operation (e.g. write, DDL, unsafe function).
      sqlite3.DatabaseError: on syntax or semantic query errors.
    """
    # 1. Structural validation
    validate_single_read_only_statement(query)

    # 2. Connection hardening
    try:
        conn.execute("PRAGMA query_only = ON;")
        conn.execute("PRAGMA temp_store = MEMORY;")
    except Exception:
        pass

    if hasattr(conn, "enable_load_extension"):
        try:
            conn.enable_load_extension(False)
        except Exception:
            pass

    # 3. Setup progress handler for monotonic timeout & opcode limiting
    deadline = time.monotonic() + timeout_seconds
    opcode_counter = [0]

    def progress_callback() -> int:
        opcode_counter[0] += 10
        if time.monotonic() > deadline or opcode_counter[0] > max_opcodes:
            # Non-zero return value interrupts execution
            return 1
        return 0

    # Every 10 opcodes, SQLite calls progress_callback
    conn.set_progress_handler(progress_callback, 10)

    # 4. Attach authorizer
    authorizer = create_sqlite_authorizer()
    conn.set_authorizer(authorizer)

    start_time = time.monotonic()
    try:
        cur = conn.cursor()
        # Single statement execution using cursor.execute() — NEVER executescript()
        cur.execute(query)
        fetched = cur.fetchmany(max_rows + 1)
        truncated = len(fetched) > max_rows
        rows = fetched[:max_rows]
        columns = [col[0] for col in cur.description] if cur.description else []
        elapsed_ms = round((time.monotonic() - start_time) * 1000.0, 2)
        return columns, rows, truncated, elapsed_ms
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        if "interrupted" in msg:
            raise SQLTimeoutError(
                f"Query execution exceeded resource limit ({timeout_seconds:.1f}s timeout or opcode budget)."
            ) from exc
        if "not authorized" in msg:
            raise SQLSecurityError(f"Security violation: {exc}") from exc
        raise
    except sqlite3.DatabaseError as exc:
        msg = str(exc).lower()
        if "not authorized" in msg:
            raise SQLSecurityError(f"Security violation: {exc}") from exc
        raise
    finally:
        # Reset handlers so subsequent setup or cleanup is not constrained
        conn.set_progress_handler(None, 0)
        conn.set_authorizer(None)
