"""Unit tests for truncated on-topic fragment guard."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.answer_guard import check_answer_quality_v2


def test_truncated_zk_rollup_fragment():
    # Report example: topical start, cut off on dangling "to."
    answer = "ZK-Rollups use validity proofs (zero-knowledge) to."
    r = check_answer_quality_v2(
        answer,
        question_text="How does a ZK-Rollup differ from Optimistic Rollup?",
        ideal_keywords="zk-rollup, validity, proof, zero-knowledge, optimistic",
        ideal_answer=(
            "ZK-Rollups use validity proofs (zero-knowledge) to prove correct "
            "execution of batches, while Optimistic Rollups assume correctness "
            "and rely on fraud proofs during a challenge window."
        ),
    )
    assert r["cap_required"] is True
    assert r["reason"] == "truncated_fragment"
    assert r["score_cap"] == 25


def test_truncated_waf_fragment():
    answer = "WAFs protect web applications from common."
    r = check_answer_quality_v2(
        answer,
        question_text="Describe the function of cloud web application firewalls (WAF).",
        ideal_keywords="waf, firewall, web, application, protect",
        ideal_answer=(
            "WAFs protect web applications from common attacks such as SQL injection "
            "and XSS by filtering HTTP traffic against known threat patterns."
        ),
    )
    assert r["cap_required"] is True
    assert r["reason"] == "truncated_fragment"


def test_truncated_trailing_comma_fragment():
    answer = "A consistent tagging schema enables automation,"
    r = check_answer_quality_v2(
        answer,
        question_text="Explain the concept of cloud resource tagging strategy.",
        ideal_keywords="tagging, schema, automation, cloud, resource",
        ideal_answer=(
            "A consistent tagging schema enables automation, cost allocation, "
            "and access control across cloud resources."
        ),
    )
    assert r["cap_required"] is True
    assert r["reason"] == "truncated_fragment"


def test_complete_on_topic_answer_not_truncated():
    answer = (
        "A decision tree recursively splits on the feature that best separates "
        "classes, using Gini or information gain, until a stopping rule is met."
    )
    r = check_answer_quality_v2(
        answer,
        question_text="Explain how a decision tree works.",
        ideal_keywords="decision, tree, split, gini, information, gain",
        ideal_answer=(
            "A decision tree recursively partitions data by selecting the feature "
            "and threshold that best separates classes."
        ),
    )
    assert r["cap_required"] is False
    assert r["reason"] == ""


def test_dangling_but_off_topic_not_truncated():
    # Ends with dangling word but no topical overlap → not truncated_fragment.
    answer = "Cooking risotto requires constant stirring of."
    r = check_answer_quality_v2(
        answer,
        question_text="What is Docker?",
        ideal_keywords="container, docker, isolation, kernel",
        ideal_answer=(
            "Docker is a container runtime that packages applications with their "
            "dependencies into isolated environments sharing the host OS kernel."
        ),
    )
    # May hit too_short or pass; must not be labeled truncated_fragment.
    assert r.get("reason") != "truncated_fragment"
