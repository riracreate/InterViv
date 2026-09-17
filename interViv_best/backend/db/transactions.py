"""Multi-write atomic commits across both store backends.

Phase 3A: session start and answer submit each persist several documents
(candidate + session; scored round + Elo) that must commit or roll back as
one unit — a 503 between two commits must never leave a scored round with
unapplied Elo or a session missing from its candidate.

``atomic(db)`` dispatches on the backend:

* SQLAlchemy: every collection method runs inside ``session_scope()``, so an
  ambient-contextvar session makes all writes in the block share one
  transaction that commits once at the end (see ``ambient_session``).
* In-memory: a global lock plus snapshot/restore of every collection.

Scope notes (single-process server, as with the existing per-session submit
locks): ``atomic`` does not add cross-process isolation. Concurrent writers
in other processes still need store-level conditional claims. Keep atomic
blocks short and free of scoring, network, or other slow work — the commit
sequences they wrap are pure persistence.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


@contextmanager
def atomic(db: Any) -> Iterator[None]:
    """Commit every write in the block as one unit, or roll all of them back.

    Raises ``TypeError`` for unknown backends: silently running a "commit
    sequence" without atomicity would be worse than refusing.
    """
    from backend.db.memory import _MemoryDB

    if isinstance(db, _MemoryDB):
        with db.atomic():
            yield
        return

    from backend.db.sqlalchemy_store import SQLAlchemyDatabase, ambient_session

    if isinstance(db, SQLAlchemyDatabase):
        with ambient_session():
            yield
        return

    raise TypeError(
        f"atomic() supports the memory and SQLAlchemy backends, not {type(db).__name__}."
    )
