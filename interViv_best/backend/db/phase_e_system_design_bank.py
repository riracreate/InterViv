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


# Server-side only (never in public_system_design_prompt). Per prompt and per
# rubric criterion: concepts a design would usually mention, each with regex
# aliases. Used after submission to compare self-ratings with what the notes
# actually mention. Advisory: never part of the self-assessment score.
SYSTEM_DESIGN_EVIDENCE: dict[str, dict[str, list[tuple[str, list[str]]]]] = {
    "sd_url_shortener": {
        "requirements": [
            ("read/write ratio", [r"read[- ]heavy", r"read[- /]?(?:to[- ])?write", r"reads? per second"]),
            ("expiry", [r"expir", r"\bttl\b"]),
            ("custom alias", [r"custom alias", r"vanity"]),
            ("redirect latency", [r"latency"]),
            ("availability", [r"availab", r"uptime"]),
        ],
        "api_data": [
            ("create/redirect API", [r"\b(?:post|get|put)\s+/", r"endpoint", r"\bapi\b"]),
            ("301 vs 302 redirect", [r"\b30[12]\b", r"redirect"]),
            ("key encoding", [r"base ?62", r"\bhash", r"\bmd5\b", r"sha-?\d"]),
            ("unique ID generation", [r"counter", r"snowflake", r"id generat", r"unique id"]),
            ("key-value store", [r"key[- ]value", r"\bkv\b", r"nosql", r"dynamo", r"cassandra"]),
        ],
        "scale": [
            ("cache for hot links", [r"cache", r"redis", r"memcache"]),
            ("sharding", [r"shard", r"partition"]),
            ("replication", [r"replica"]),
            ("collision handling", [r"collision"]),
            ("load balancing / CDN", [r"load balanc", r"\bcdn\b"]),
        ],
        "tradeoffs": [
            ("hash vs counter", [r"hash.{0,40}counter", r"counter.{0,40}hash"]),
            ("guessable IDs", [r"guess", r"enumerat", r"predictab", r"sequential"]),
            ("301 vs 302 analytics", [r"301.{0,60}302", r"302.{0,60}301", r"analytics"]),
            ("consistency vs availability", [r"consisten"]),
        ],
    },
    "sd_news_feed": {
        "requirements": [
            ("post / follow / timeline", [r"\bfollow", r"timeline"]),
            ("feed latency", [r"latency"]),
            ("freshness", [r"fresh", r"real[- ]time"]),
            ("scale assumptions", [r"\bdau\b", r"million", r"users? per", r"qps", r"rps"]),
        ],
        "api_data": [
            ("feed API", [r"\b(?:post|get)\s+/", r"endpoint", r"/feed", r"\bapi\b"]),
            ("follow graph", [r"follow(?:er|ing)? (?:graph|table)", r"social graph", r"\bgraph\b"]),
            ("posts / timeline storage", [r"posts? (?:table|store)", r"timeline (?:table|store|cache)"]),
            ("pagination", [r"cursor", r"paginat"]),
        ],
        "scale": [
            ("fan-out on write", [r"fan[- ]?out on write", r"\bpush\b"]),
            ("fan-out on read", [r"fan[- ]?out on read", r"\bpull\b"]),
            ("celebrity / hot users", [r"celebrit", r"hot (?:user|key)", r"hybrid"]),
            ("cache", [r"cache", r"redis"]),
            ("queue", [r"queue", r"kafka"]),
        ],
        "tradeoffs": [
            ("push vs pull", [r"push.{0,40}pull", r"pull.{0,40}push", r"write.{0,30}vs.{0,30}read"]),
            ("eventual consistency", [r"eventual", r"consisten"]),
            ("ranking vs chronological", [r"rank", r"chronolog"]),
            ("write amplification / storage", [r"amplif", r"storage cost"]),
        ],
    },
    "sd_rate_limiter": {
        "requirements": [
            ("limit definition", [r"requests? per", r"\brps\b", r"per (?:second|minute)"]),
            ("limit key", [r"per[- ](?:user|ip|api[- ]?key|client)"]),
            ("429 response", [r"\b429\b", r"too many requests"]),
            ("low overhead", [r"latency", r"overhead"]),
            ("distributed", [r"distributed", r"multiple (?:nodes|servers|instances)"]),
        ],
        "api_data": [
            ("algorithm", [r"token bucket", r"sliding window", r"fixed window", r"leaky bucket"]),
            ("shared store", [r"redis", r"memcache"]),
            ("atomic update", [r"\bincr", r"atomic", r"\blua\b"]),
            ("expiry", [r"\bttl\b", r"expir"]),
            ("rate-limit headers", [r"header", r"retry-after", r"x-ratelimit"]),
        ],
        "scale": [
            ("race conditions", [r"race", r"concurren"]),
            ("partitioning", [r"shard", r"consistent hash", r"partition"]),
            ("local cache", [r"local (?:cache|counter)", r"in[- ]memory"]),
            ("store outage", [r"(?:store|redis|limiter) (?:is )?down", r"outage", r"failover", r"unavailab"]),
        ],
        "tradeoffs": [
            ("fail open vs closed", [r"fail[- ]open", r"fail[- ]closed"]),
            ("accuracy vs memory", [r"accura", r"precis", r"approximat", r"memory"]),
            ("token bucket vs sliding window", [r"token bucket.{0,80}sliding", r"sliding.{0,80}token bucket", r"burst"]),
            ("clock skew", [r"clock (?:skew|drift)", r"time sync"]),
        ],
    },
    "sd_chat": {
        "requirements": [
            ("delivery receipts", [r"receipt", r"delivered", r"\bseen\b", r"read status"]),
            ("offline sync", [r"offline", r"\bsync"]),
            ("ordering", [r"\border", r"sequence"]),
            ("latency / presence", [r"latency", r"presence", r"online"]),
        ],
        "api_data": [
            ("connection model", [r"websocket", r"long[- ]poll", r"persistent connection", r"\bsse\b"]),
            ("message IDs", [r"message id", r"sequence (?:number|id)", r"\bseq\b"]),
            ("message store", [r"messages? (?:table|store)", r"cassandra", r"hbase", r"wide[- ]column"]),
            ("conversation keying", [r"conversation id", r"\binbox", r"chat id"]),
        ],
        "scale": [
            ("connection servers", [r"connection (?:server|gateway)", r"gateway", r"sticky"]),
            ("queue", [r"queue", r"kafka", r"pub ?/? ?sub"]),
            ("push notifications", [r"push notif", r"\bapns\b", r"\bfcm\b"]),
            ("acks and retries", [r"\back", r"retr(?:y|ies)", r"idempot"]),
            ("sharding", [r"shard", r"partition"]),
        ],
        "tradeoffs": [
            ("consistency vs latency", [r"consisten", r"latency.{0,40}(?:vs|versus|trade)"]),
            ("delivery semantics", [r"at[- ]least[- ]once", r"exactly[- ]once", r"at[- ]most[- ]once", r"duplicate"]),
            ("encryption", [r"end[- ]to[- ]end", r"\be2ee?\b", r"encrypt"]),
            ("retention / storage cost", [r"retention", r"storage cost"]),
        ],
    },
    "sd_file_share": {
        "requirements": [
            ("upload / download", [r"upload", r"download"]),
            ("share links", [r"share(?:able)?[- ]links?", r"link (?:sharing|token)"]),
            ("file size limits", [r"file size", r"large file", r"\b\d+ ?(?:mb|gb)\b"]),
            ("access control", [r"permission", r"access control", r"\bacl\b", r"private"]),
        ],
        "api_data": [
            ("blob storage", [r"blob", r"object stor", r"\bs3\b", r"\bgcs\b"]),
            ("metadata store", [r"metadata"]),
            ("signed URLs", [r"pre-?signed", r"signed url"]),
            ("chunked upload", [r"chunk", r"multipart", r"resumable"]),
        ],
        "scale": [
            ("CDN", [r"\bcdn\b", r"edge (?:cache|location|server)"]),
            ("deduplication", [r"dedup"]),
            ("durability", [r"replica", r"durab"]),
            ("rate limiting", [r"rate[- ]limit", r"throttl"]),
        ],
        "tradeoffs": [
            ("abuse / virus scanning", [r"virus", r"malware", r"\bscan", r"abuse"]),
            ("encryption", [r"encrypt"]),
            ("link expiry", [r"expir", r"\bttl\b"]),
            ("cost vs latency", [r"\bcost", r"cold storage", r"storage tier"]),
        ],
    },
}
