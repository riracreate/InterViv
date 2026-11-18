"""A plan is created only for an explicit action or a clear plan request."""

from __future__ import annotations

import os

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from modules.coach_conversation import (  # noqa: E402
    get_conversation,
    get_or_create_conversation,
    is_clear_plan_request,
    is_explanation_question,
    owner_key,
    post_message,
    update_goals,
)


def _say(user_id: str, text: str, action: str | None = None, payload: dict | None = None):
    doc = get_or_create_conversation(user_id=user_id, role_id="amazon_sde_intern")
    result = post_message(
        doc["conversation_id"],
        owner=owner_key(user_id),
        user_id=user_id,
        text=text,
        action=action,
        action_payload=payload or {},
    )
    saved = get_conversation(doc["conversation_id"], owner=owner_key(user_id))
    return result, saved


def test_clear_requests_create_a_plan() -> None:
    assert is_clear_plan_request("Please create my plan")
    assert is_clear_plan_request("update my plan")
    assert is_clear_plan_request("Build a starter plan")
    created, _saved = _say("u-clear-plan", "Please create my plan")
    assert created["plan"] is not None
    assert created["plan"]["tasks"]
    updated, _saved = _say("u-update-plan", "update my plan")
    assert updated["plan"] is not None


def test_a_mention_of_plan_or_roadmap_is_not_enough() -> None:
    assert not is_clear_plan_request("I need a roadmap")
    assert not is_clear_plan_request("what is in the plan?")
    result, saved = _say("u-roadmap-mention", "I need a roadmap")
    assert result["plan"] is None
    assert saved["goals"]["confirmed_goal"] is None


def test_explanation_questions_do_not_create_a_plan_or_change_the_goal() -> None:
    assert is_explanation_question("why is SQL on my plan?")
    assert is_explanation_question("Explain the next task")
    assert is_explanation_question("how do I create my plan?")
    assert not is_clear_plan_request("how do I create my plan?")
    doc = get_or_create_conversation(user_id="u-explain", role_id="amazon_sde_intern")
    update_goals(
        doc["conversation_id"],
        owner=owner_key("u-explain"),
        confirmed_goal="Backend SDE",
    )
    for text in (
        "why is SQL on my plan?",
        "explain the next task",
        "how do I create my plan?",
    ):
        result = post_message(
            doc["conversation_id"],
            owner=owner_key("u-explain"),
            user_id="u-explain",
            text=text,
        )
        assert result["plan"] is None
        saved = get_conversation(doc["conversation_id"], owner=owner_key("u-explain"))
        assert saved["goals"]["confirmed_goal"] == "Backend SDE"

    blocked = post_message(
        doc["conversation_id"],
        owner=owner_key("u-explain"),
        user_id="u-explain",
        text="why should I?",
        action="create_plan",
    )
    assert blocked["plan"] is None
    changed = post_message(
        doc["conversation_id"],
        owner=owner_key("u-explain"),
        user_id="u-explain",
        text="why SQL?",
        action="update_goal",
        action_payload={"confirmed_goal": "A different goal"},
    )
    assert changed["plan"] is None
    saved = get_conversation(doc["conversation_id"], owner=owner_key("u-explain"))
    assert saved["goals"]["confirmed_goal"] == "Backend SDE"
