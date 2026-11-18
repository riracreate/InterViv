"""Level-2 curated hints come from the topic templates, not one hash-map line."""

from __future__ import annotations

from backend.coding_coach import curated_hint
from backend.learning_hints import templates

FIXED_HASH_MAP_LINE = "hash map / set / running state"


def test_level_two_hint_uses_each_matching_topic() -> None:
    catalog = templates()["coding_topics"]
    hashing = curated_hint({"title": "Two Sum", "function": "two_sum", "topics": ["hashing"]}, 2)
    assert hashing == catalog["hashing"]
    both = curated_hint(
        {"title": "Maze", "function": "solve", "topics": ["graphs", "bfs"]},
        2,
    )
    assert catalog["graphs"] in both
    assert catalog["bfs"] in both
    assert FIXED_HASH_MAP_LINE not in both


def test_unknown_topic_uses_the_general_template_not_the_hash_map_line() -> None:
    text = curated_hint({"title": "Odd", "function": "f", "topics": ["not-a-topic"]}, 2)
    assert text == templates()["coding_general"]
    assert FIXED_HASH_MAP_LINE not in text


def test_hash_map_alias_selects_the_hashing_template() -> None:
    text = curated_hint({"title": "Pairs", "function": "f", "topics": ["hash map"]}, 2)
    assert text == templates()["coding_topics"]["hashing"]
    assert FIXED_HASH_MAP_LINE not in text
