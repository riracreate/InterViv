"""Local coding coach — progressive hints that never affect scores.

Uses curated text by default. Optional Ollama on 127.0.0.1 only
(``CODING_COACH_URL``, default ``http://127.0.0.1:11434``).
Never calls cloud LLM providers. Never receives hidden tests or
reference solutions.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

DEFAULT_COACH_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma2:2b"
MAX_SOURCE_CHARS = 4000
MAX_HINT_CHARS = 1200
MAX_HINT_CODE_LINES = 3

# Model output is checked before it reaches the candidate: the prompt asks for
# no solution code, but a small local model does not always comply.
_FENCED_BLOCK = re.compile(r"```[^\n]*\n(.*?)(?:```|\Z)", re.S)
_SOLUTION_SIGNATURES = (
    re.compile(r"^\s*(?:async\s+)?def\s+\w+\s*\(", re.M),
    re.compile(r"^\s*class\s+\w+", re.M),
    re.compile(r"\bpublic\s+(?:static\s+)?[\w<>\[\],]+\s+\w+\s*\("),
    re.compile(r"\bfunction\s+\w+\s*\("),
    re.compile(r"^\s*(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>", re.M),
    re.compile(r"#include\s*<"),
)


def coach_endpoint() -> str:
    return (os.environ.get("CODING_COACH_URL") or DEFAULT_COACH_URL).strip().rstrip("/")


def coach_model() -> str:
    return (os.environ.get("CODING_COACH_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _localhost_only(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "http"
        and parsed.hostname == "127.0.0.1"
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and parsed.path in ("", "/")
    )


def curated_hint(problem: dict[str, Any], level: int) -> str:
    title = problem.get("title") or "this problem"
    topics = ", ".join(problem.get("topics") or []) or "the stated constraints"
    function = problem.get("function") or "your function"
    if level <= 1:
        return (
            f"Start from the examples for {title}. Identify what {function} must "
            f"return for each input before writing code. Topics to keep in mind: {topics}."
        )
    if level == 2:
        return (
            f"Look for a pattern that avoids checking every pair or every order blindly. "
            f"A single linear pass with memory (hash map / set / running state) often fits "
            f"{topics}. Name the invariant you will maintain."
        )
    return (
        f"Walk one visible example line by line: after each input element, what must your "
        f"data structure contain so the answer for that prefix is correct? Implement that "
        f"update, then verify the remaining examples. Do not paste a full solution from memory."
    )


def _ollama_hint(
    *,
    problem: dict[str, Any],
    level: int,
    source: str | None,
    last_error: str | None,
) -> str | None:
    base = coach_endpoint()
    if not _localhost_only(base):
        return None
    statement = str(problem.get("statement") or problem.get("prompt") or "")[:2000]
    prompt = (
        "You are a local coding tutor. Give ONE progressive hint for a practice problem.\n"
        f"Hint level {level} of 3 (1=gentle nudge, 3=more specific, still no full solution).\n"
        "Rules: no complete solution, no full code dump, no hidden-test content, under 80 words.\n"
        f"Title: {problem.get('title')}\n"
        f"Function: {problem.get('function')}\n"
        f"Topics: {', '.join(problem.get('topics') or [])}\n"
        f"Statement:\n{statement}\n"
    )
    if last_error:
        prompt += f"Recent runner message (may be empty):\n{str(last_error)[:500]}\n"
    if source:
        prompt += f"Candidate draft (truncated):\n{source[:MAX_SOURCE_CHARS]}\n"
    prompt += "Reply with only the hint text."
    payload = {
        "model": coach_model(),
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 180},
        "messages": [
            {"role": "system", "content": "You tutor coding practice locally. Never output a full solution."},
            {"role": "user", "content": prompt},
        ],
    }
    request = Request(
        base + "/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=45) as response:
            body = json.loads(response.read(200_000))
    except (OSError, HTTPError, URLError, ValueError, TimeoutError):
        return None
    message = body.get("message") if isinstance(body, dict) else None
    text = (message or {}).get("content") if isinstance(message, dict) else None
    if not isinstance(text, str) or not text.strip():
        return None
    return text.strip()


def leaks_solution(text: str) -> bool:
    """True when a hint contains solution-shaped code.

    Flags a fenced block longer than MAX_HINT_CODE_LINES non-blank lines, or a
    function/class definition anywhere. Short inline snippets
    (`seen = set()`) are allowed.
    """
    for match in _FENCED_BLOCK.finditer(text or ""):
        lines = [line for line in match.group(1).splitlines() if line.strip()]
        if len(lines) > MAX_HINT_CODE_LINES:
            return True
    return any(pattern.search(text or "") for pattern in _SOLUTION_SIGNATURES)


def build_hint(
    *,
    problem: dict[str, Any],
    level: int,
    source: str | None = None,
    last_error: str | None = None,
    prefer_ai: bool = True,
) -> dict[str, Any]:
    level = max(1, min(3, int(level)))
    withheld = False
    if prefer_ai:
        ai = _ollama_hint(problem=problem, level=level, source=source, last_error=last_error)
        if ai and leaks_solution(ai):
            withheld = True
        elif ai:
            return {
                "level": level,
                "kind": "ai",
                "hint": ai[:MAX_HINT_CHARS],
                "model": coach_model(),
                "endpoint": coach_endpoint(),
            }
    payload = {
        "level": level,
        "kind": "curated",
        "hint": curated_hint(problem, level),
        "model": None,
        "endpoint": None,
    }
    if withheld:
        payload["ai_withheld"] = "solution_code"
    return payload


def coach_status() -> dict[str, Any]:
    base = coach_endpoint()
    ok = False
    detail = "Coach URL must be http://127.0.0.1 (local Ollama only)."
    if _localhost_only(base):
        try:
            request = Request(base + "/api/tags", method="GET")
            with build_opener(ProxyHandler({})).open(request, timeout=2) as response:
                payload = json.loads(response.read(100_000))
            names = {
                str(m.get("name") or "")
                for m in (payload.get("models") or [])
                if isinstance(m, dict)
            }
            model = coach_model()
            ok = model in names or any(n.startswith(model.split(":")[0]) for n in names)
            detail = None if ok else f"Ollama reachable; install model `{model}`."
        except (OSError, HTTPError, URLError, ValueError, TimeoutError):
            detail = "Ollama not reachable on 127.0.0.1:11434. Curated hints still work."
    return {
        "available": ok,
        "model": coach_model(),
        "endpoint": base if _localhost_only(base) else None,
        "detail": detail,
        "fallback": "curated",
    }
