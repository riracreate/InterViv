"""
db_memory.py — In-memory DB for mid-eval demo (no MongoDB required).

Mirrors the minimal subset of pymongo's API that the interViv backend uses:
  - db["collection"].find_one({...})
  - db["collection"].insert_one(doc)
  - db["collection"].update_one(filter, update)

Enough to run the full demo without running a MongoDB server. Switch back to
real MongoDB by setting INTERVIV_USE_MEMORY_DB=false in .env.

Thread-safe for single-process development server; not for production.
"""
from __future__ import annotations

import copy
import threading
from contextlib import contextmanager
from typing import Any, Iterator
from dataclasses import dataclass, field


# Global write lock for _MemoryDB.atomic(). Lock order is always
# global -> db -> collection, and plain ops never hold more than one, so
# snapshotting under this lock cannot deadlock. RLock: atomic() nests.
_ATOMIC_LOCK = threading.RLock()


class _UpdateResult:
    def __init__(self, matched: int, modified: int):
        self.matched_count = matched
        self.modified_count = modified


class _InsertResult:
    def __init__(self, inserted_id: Any):
        self.inserted_id = inserted_id


def _matches(doc: dict, query: dict) -> bool:
    for k, v in query.items():
        # Dotted paths (e.g. "elo_ratings.Python")
        if "." in k:
            parts = k.split(".")
            cur: Any = doc
            for p in parts:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    cur = None
                    break
            if cur != v:
                return False
            continue
        if doc.get(k) != v:
            return False
    return True


def _apply_update(doc: dict, update: dict) -> bool:
    """Apply $set, $addToSet, $push, $inc. Returns True if modified."""
    def target(path: str) -> tuple[dict, str]:
        if "." not in path:
            return doc, path
        parts = path.split(".")
        cur = doc
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        return cur, parts[-1]

    # Stored values are deep-copied, like insert_one: the live document must
    # never alias caller-owned mutables, or later caller-side mutation would
    # corrupt the store without any write (and defeat atomic rollback).
    modified = False
    for op, body in update.items():
        if op == "$set":
            for k, v in body.items():
                cur, leaf = target(k)
                if cur.get(leaf) != v:
                    cur[leaf] = copy.deepcopy(v)
                    modified = True
        elif op == "$addToSet":
            for k, v in body.items():
                cur, leaf = target(k)
                existing = cur.setdefault(leaf, [])
                if not isinstance(existing, list):
                    existing = [existing]
                    cur[leaf] = existing
                    modified = True
                values = v["$each"] if isinstance(v, dict) and "$each" in v else [v]
                for item in values:
                    if item not in existing:
                        existing.append(copy.deepcopy(item))
                        modified = True
        elif op == "$push":
            for k, v in body.items():
                cur, leaf = target(k)
                existing = cur.setdefault(leaf, [])
                values = v["$each"] if isinstance(v, dict) and "$each" in v else [v]
                existing.extend(copy.deepcopy(values))
                if values:
                    modified = True
        elif op == "$inc":
            for k, v in body.items():
                cur, leaf = target(k)
                cur[leaf] = cur.get(leaf, 0) + v
                modified = True
    return modified


@dataclass
class _Collection:
    name: str
    _docs: list[dict] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        with self._lock:
            for doc in self._docs:
                if _matches(doc, query):
                    result = copy.deepcopy(doc)
                    if projection:
                        excludes = {k for k, v in projection.items() if not v}
                        for k in excludes:
                            result.pop(k, None)
                    return result
        return None

    def find(self, query: dict | None = None) -> Iterator[dict]:
        with self._lock:
            if not query:
                return iter([copy.deepcopy(d) for d in self._docs])
            return iter([copy.deepcopy(d) for d in self._docs if _matches(d, query)])

    def insert_one(self, doc: dict) -> _InsertResult:
        with self._lock:
            doc_copy = copy.deepcopy(doc)
            self._docs.append(doc_copy)
            return _InsertResult(doc_copy.get("_id"))

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> _UpdateResult:
        with self._lock:
            for doc in self._docs:
                if _matches(doc, query):
                    modified = _apply_update(doc, update)
                    return _UpdateResult(matched=1, modified=1 if modified else 0)
            if upsert:
                new_doc = {**query}
                _apply_update(new_doc, update)
                self._docs.append(new_doc)
                return _UpdateResult(matched=0, modified=1)
            return _UpdateResult(matched=0, modified=0)

    def delete_one(self, query: dict) -> None:
        with self._lock:
            for i, doc in enumerate(self._docs):
                if _matches(doc, query):
                    self._docs.pop(i)
                    return

    def count_documents(self, query: dict) -> int:
        with self._lock:
            return sum(1 for d in self._docs if _matches(d, query))


class _MemoryDB:
    def __init__(self) -> None:
        self._cols: dict[str, _Collection] = {}
        self._lock = threading.Lock()

    def __getitem__(self, name: str) -> _Collection:
        with self._lock:
            if name not in self._cols:
                self._cols[name] = _Collection(name=name)
            return self._cols[name]

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """Commit every write in the block as one unit, or roll it back.

        Snapshot/restore under the global write lock: on exception every
        collection returns to its entry state and collections created
        inside the block disappear. Single-process only, like the rest of
        this adapter. Keep blocks short and purely persistence.
        """
        with _ATOMIC_LOCK:
            with self._lock:
                names = sorted(self._cols)
            snapshot = {}
            for name in names:
                col = self._cols[name]
                with col._lock:
                    snapshot[name] = copy.deepcopy(col._docs)
            try:
                yield
            except Exception:
                with self._lock:
                    live = sorted(self._cols)
                for name in live:
                    col = self._cols[name]
                    with col._lock:
                        if name in snapshot:
                            col._docs[:] = snapshot[name]
                with self._lock:
                    for name in live:
                        if name not in snapshot:
                            del self._cols[name]
                raise


_SINGLETON = _MemoryDB()


def get_memory_database() -> _MemoryDB:
    """Return the process-wide singleton memory DB."""
    return _SINGLETON


if __name__ == "__main__":
    # Self-test
    db = get_memory_database()
    db["candidates"].insert_one({"candidate_id": "c1", "skills": ["Python"], "elo_ratings": {}})
    assert db["candidates"].find_one({"candidate_id": "c1"})["skills"] == ["Python"]
    db["candidates"].update_one(
        {"candidate_id": "c1"},
        {"$set": {"elo_ratings.Python": 1400}, "$addToSet": {"session_history": "s1"}},
    )
    doc = db["candidates"].find_one({"candidate_id": "c1"})
    assert doc["elo_ratings"]["Python"] == 1400
    assert doc["session_history"] == ["s1"]
    print("✅ memory DB self-test passed")
