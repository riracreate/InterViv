"""Research comparison harness for answer grading and evidence auditability."""

from .schema import Example, SchemaValidationError, load_jsonl

__all__ = ["Example", "SchemaValidationError", "load_jsonl"]
