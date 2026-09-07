"""Phase E system-design prompt bank (candidate-safe fields only).

Each prompt is a free-response system-design scenario. Evaluation is
structured self-assessment against an explicit rubric — never automatic
diagram correctness. Reference outlines stay server-side and must not be
served to candidates.
"""

from __future__ import annotations

from typing import Any

# Explicit rubric criteria shown to the candidate. Scores are self-ratings.
SYSTEM_DESIGN_RUBRIC: list[dict[str, str]] = [
    {
        "id": "requirements",
        "name": "Requirements clarity",
        "description": "Functional and non-functional requirements stated.",
    },
    {
        "id": "api_data",
        "name": "API and data model",
        "description": "Key APIs and storage choices sketched with trade-offs.",
    },
    {
        "id": "scale",
        "name": "Scale and reliability",
        "description": "Capacity, bottlenecks, and failure modes addressed.",
    },
    {
        "id": "tradeoffs",
        "name": "Trade-offs",
        "description": "At least one meaningful alternative considered.",
    },
]

SYSTEM_DESIGN_PROMPTS: list[dict[str, Any]] = [
    {
        "id": "sd_url_shortener",
        "title": "URL shortener",
        "topic": "System Design",
        "difficulty": "medium",
        "prompt": (
            "Design a URL shortener that creates short links and redirects. "
            "Cover requirements, API, storage, uniqueness, and scale."
        ),
        "constraints": [
            "State assumptions explicitly.",
            "Do not claim a diagram is auto-validated.",
        ],
    },
    {
        "id": "sd_news_feed",
        "title": "News feed",
        "topic": "System Design",
        "difficulty": "medium",
        "prompt": (
            "Design a social news feed (post, follow, home timeline). "
            "Discuss fan-out, ranking, and consistency trade-offs."
        ),
        "constraints": [
            "Call out what you would measure in production.",
        ],
    },
    {
        "id": "sd_rate_limiter",
        "title": "API rate limiter",
        "topic": "System Design",
        "difficulty": "easy",
        "prompt": (
            "Design a distributed rate limiter for a public API. "
            "Compare token bucket vs sliding window and where state lives."
        ),
        "constraints": [
            "Include a failure mode if the limiter store is down.",
        ],
    },
    {
        "id": "sd_chat",
        "title": "1:1 chat",
        "topic": "System Design",
        "difficulty": "hard",
        "prompt": (
            "Design a 1:1 messaging system with delivery receipts and "
            "offline sync. Cover connection model, storage, and fan-out."
        ),
        "constraints": [
            "Mention at least one consistency vs latency trade-off.",
        ],
    },
    {
        "id": "sd_file_share",
        "title": "File sharing",
        "topic": "System Design",
        "difficulty": "medium",
        "prompt": (
            "Design a file-sharing service (upload, share link, download). "
            "Discuss blob storage, metadata, and access control."
        ),
        "constraints": [
            "Note virus-scanning or abuse controls at a high level.",
        ],
    },
]


def list_system_design_prompts(
    *,
    difficulty: str | None = None,
    topic: str | None = None,
) -> list[dict[str, Any]]:
    items = list(SYSTEM_DESIGN_PROMPTS)
    if difficulty:
        items = [p for p in items if p.get("difficulty") == difficulty]
    if topic:
        wanted = topic.strip().lower()
        items = [p for p in items if wanted in str(p.get("topic") or "").lower()]
    return items


def get_system_design_prompt(prompt_id: str) -> dict[str, Any] | None:
    for prompt in SYSTEM_DESIGN_PROMPTS:
        if prompt["id"] == prompt_id:
            return prompt
    return None


def public_system_design_prompt(prompt: dict[str, Any]) -> dict[str, Any]:
    """Candidate-safe projection (no private outlines)."""
    return {
        "id": prompt["id"],
        "title": prompt["title"],
        "topic": prompt["topic"],
        "difficulty": prompt["difficulty"],
        "prompt": prompt["prompt"],
        "constraints": list(prompt.get("constraints") or []),
        "rubric": list(SYSTEM_DESIGN_RUBRIC),
        "evaluation_boundary": (
            "Structured self-assessment against the named rubric. "
            "Diagrams and component lists are not auto-scored for correctness."
        ),
    }
