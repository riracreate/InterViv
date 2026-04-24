"""
question_bank_v2.py — Drop-in replacement for modules/question_bank.py

Fixes:
  • SKILL_ALIASES map — C++, Docker, DevOps, Java, JavaScript, etc. all resolve
    to real dataset skills instead of crashing or returning generic templates
  • LLM path is optional (controlled by OPENROUTER_API_KEY env var)
  • CSV fallback always works — never crashes the session
  • Template fallback as last resort — always returns a valid question dict
  • Deduplicates by question text — no repeats within a session

Exposes the single module-level function the backend expects:
    get_next_question(skill, sub_domain, difficulty, asked) -> dict
"""
from __future__ import annotations

import csv
import json
import os
import random
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = None


# ───────────────────────────────────────────────────────────────────────────
# SKILL ALIASES — resume-skill → (dataset_skill, sub_domain)
# Any skill a candidate lists on a resume is mapped here to a real dataset
# skill. Unknown skills fall through to direct match or 'general' domain.
# ───────────────────────────────────────────────────────────────────────────

SKILL_ALIASES: dict[str, tuple[str, str]] = {
    # programming languages (non-Python) → OOP / DSA
    "c++":            ("DSA", "dsa_core"),
    "c":              ("DSA", "dsa_core"),
    "cpp":            ("DSA", "dsa_core"),
    "java":           ("OOP", "oop_core"),
    "c#":             ("OOP", "oop_core"),
    "csharp":         ("OOP", "oop_core"),
    "kotlin":         ("OOP", "oop_core"),
    "swift":          ("OOP", "oop_core"),
    "scala":          ("OOP", "oop_core"),
    "ruby":           ("OOP", "oop_core"),
    "go":             ("System Design", "web_backend"),
    "golang":         ("System Design", "web_backend"),
    "rust":           ("System Design", "web_backend"),

    # frontend stacks → System Design / web_frontend
    "react":          ("System Design", "web_frontend"),
    "reactjs":        ("System Design", "web_frontend"),
    "angular":        ("System Design", "web_frontend"),
    "vue":            ("System Design", "web_frontend"),
    "vuejs":          ("System Design", "web_frontend"),
    "svelte":         ("System Design", "web_frontend"),
    "next.js":        ("System Design", "web_frontend"),
    "nextjs":         ("System Design", "web_frontend"),
    "redux":          ("System Design", "web_frontend"),
    "tailwind":       ("System Design", "web_frontend"),
    "html":           ("System Design", "web_frontend"),
    "css":            ("System Design", "web_frontend"),
    "sass":           ("System Design", "web_frontend"),
    "typescript":     ("System Design", "web_frontend"),
    "javascript":     ("System Design", "web_frontend"),
    "js":             ("System Design", "web_frontend"),

    # backend web → System Design or Python
    "node.js":        ("System Design", "web_backend"),
    "nodejs":         ("System Design", "web_backend"),
    "express":        ("System Design", "web_backend"),
    "fastapi":        ("Python", "python_web"),
    "flask":          ("Python", "python_web"),
    "django":         ("Python", "python_web"),
    "spring":         ("OOP", "spring"),
    "spring boot":    ("OOP", "spring"),
    ".net":           ("OOP", "oop_core"),
    "dotnet":         ("OOP", "oop_core"),
    "php":            ("System Design", "web_backend"),
    "laravel":        ("System Design", "web_backend"),
    "rest":           ("System Design", "api_design"),
    "graphql":        ("System Design", "api_design"),
    "grpc":           ("System Design", "api_design"),
    "websocket":      ("System Design", "api_design"),

    # databases
    "mysql":          ("DBMS", "relational"),
    "postgresql":     ("DBMS", "relational"),
    "postgres":       ("DBMS", "relational"),
    "sqlite":         ("DBMS", "relational"),
    "sql":            ("DBMS", "relational"),
    "mongodb":        ("DBMS", "nosql"),
    "mongo":          ("DBMS", "nosql"),
    "redis":          ("DBMS", "nosql"),
    "cassandra":      ("DBMS", "nosql"),
    "dynamodb":       ("DBMS", "nosql"),
    "elasticsearch":  ("DBMS", "nosql"),
    "firebase":       ("DBMS", "nosql"),
    "neo4j":          ("DBMS", "nosql"),

    # devops / cloud → System Design / devops
    "aws":            ("System Design", "devops"),
    "azure":          ("System Design", "devops"),
    "gcp":            ("System Design", "devops"),
    "google cloud":   ("System Design", "devops"),
    "docker":         ("System Design", "devops"),
    "kubernetes":     ("System Design", "devops"),
    "k8s":            ("System Design", "devops"),
    "terraform":      ("System Design", "devops"),
    "ansible":        ("System Design", "devops"),
    "jenkins":        ("System Design", "devops"),
    "github actions": ("System Design", "devops"),
    "ci/cd":          ("System Design", "devops"),
    "cicd":           ("System Design", "devops"),
    "devops":         ("System Design", "devops"),
    "nginx":          ("System Design", "devops"),
    "kafka":          ("System Design", "devops"),
    "rabbitmq":       ("System Design", "devops"),

    # ML / data
    "machine learning":("ML", "ml_core"),
    "ml":             ("ML", "ml_core"),
    "deep learning":  ("ML", "dl_frameworks"),
    "tensorflow":     ("ML", "dl_frameworks"),
    "pytorch":        ("ML", "dl_frameworks"),
    "keras":          ("ML", "dl_frameworks"),
    "scikit-learn":   ("ML", "ml_core"),
    "sklearn":        ("ML", "ml_core"),
    "numpy":          ("ML", "ml_core"),
    "pandas":         ("ML", "ml_core"),
    "opencv":         ("ML", "cv"),
    "nlp":            ("ML", "nlp"),
    "natural language processing": ("ML", "nlp"),
    "computer vision":("ML", "cv"),
    "cv":             ("ML", "cv"),
    "hugging face":   ("ML", "nlp"),
    "huggingface":    ("ML", "nlp"),
    "llm":            ("ML", "nlp"),
    "rag":            ("ML", "nlp"),
    "langchain":      ("ML", "nlp"),

    # systems / concepts
    "python":         ("Python", "python_core"),
    "linux":          ("OS", "os_core"),
    "unix":           ("OS", "os_core"),
    "bash":           ("OS", "os_core"),
    "shell":          ("OS", "os_core"),
    "data structures":("DSA", "dsa_core"),
    "algorithms":     ("DSA", "dsa_core"),
    "dsa":            ("DSA", "dsa_core"),
    "system design":  ("System Design", "distributed_systems"),
    "distributed systems": ("System Design", "distributed_systems"),
    "oop":            ("OOP", "oop_core"),
    "object oriented":("OOP", "oop_core"),
    "operating systems":("OS", "os_core"),
    "dbms":           ("DBMS", "relational"),
    "database":       ("DBMS", "relational"),
    "networking":     ("CN", "cn_core"),
    "computer networks":("CN", "cn_core"),
    "cn":             ("CN", "cn_core"),

    # soft skills
    "hr":             ("HR", "hr_core"),
    "behavioural":    ("HR", "hr_core"),
    "behavioral":     ("HR", "hr_core"),
    "communication":  ("HR", "hr_core"),

    # tools — default to general devops
    "git":            ("System Design", "devops"),
    "github":         ("System Design", "devops"),
}


def resolve_skill(raw_skill: str) -> tuple[str, Optional[str]]:
    """Resolve any resume skill string to a (dataset_skill, sub_domain) pair.

    Precedence:
      1. Direct lower-case alias match
      2. Direct match to a dataset skill (by exact name)
      3. Fallback: return the input as-is with 'general' sub_domain.
    """
    key = (raw_skill or "").strip().lower()
    if not key:
        return ("System Design", "distributed_systems")
    if key in SKILL_ALIASES:
        return SKILL_ALIASES[key]
    # valid dataset skill name (case-insensitive match against known canonicals)
    known = {"python", "dsa", "oop", "os", "dbms", "cn", "ml", "system design", "hr"}
    if key in known:
        return (raw_skill.strip().title() if key != "system design" else "System Design", None)
    return (raw_skill.strip(), "general")


# ───────────────────────────────────────────────────────────────────────────
# LLM generation — unchanged structure, uses stdlib only
# ───────────────────────────────────────────────────────────────────────────

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "anthropic/claude-haiku-4-5"

_DIFFICULTY_DESCRIPTORS = {
    "easy": "foundational — definitions, common use-cases, syntax (0–1 yrs).",
    "medium": "intermediate — applied understanding, trade-offs, best practices (1–3 yrs).",
    "hard": "advanced — internals, edge cases, architecture, performance (3+ yrs).",
}


def _generate_via_llm(skill: str, sub_domain: Optional[str], difficulty: str, asked: list[str]) -> Optional[dict]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None

    model = os.getenv("OPENROUTER_MODEL", _DEFAULT_MODEL)
    diff_desc = _DIFFICULTY_DESCRIPTORS.get(difficulty.lower(), _DIFFICULTY_DESCRIPTORS["medium"])
    sub_part = f" (sub-topic: {sub_domain})" if sub_domain and sub_domain != "general" else ""
    asked_part = ""
    if asked:
        previous = "\n".join(f"- {q}" for q in asked[-8:])
        asked_part = f"\n\nAVOID repeating these previous questions:\n{previous}"

    prompt = (
        f"Generate ONE interview question for a candidate with {skill}{sub_part} "
        f"at {difficulty} difficulty level.\n"
        f"Difficulty is {diff_desc}{asked_part}\n\n"
        f"Respond with STRICT JSON ONLY (no prose, no markdown fences):\n"
        f'{{"question":"...","ideal_answer":"...","ideal_keywords":"k1, k2, k3, k4, k5"}}\n\n'
        f"Requirements:\n"
        f"- question: 1–2 sentences, specific and technical\n"
        f"- ideal_answer: 4–6 sentences with a concrete example and a trade-off\n"
        f"- ideal_keywords: 5 comma-separated technical terms that a strong answer should contain\n"
    )

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 600,
        "temperature": 0.7,
    }).encode("utf-8")

    req = urllib.request.Request(
        _OPENROUTER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
            raw = resp.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None
    except Exception:
        return None

    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"].strip()
        # strip possible fences
        content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.I | re.M).strip()
        payload = json.loads(content)
        return {
            "question": payload["question"].strip(),
            "ideal_answer": payload.get("ideal_answer", "").strip(),
            "ideal_keywords": payload.get("ideal_keywords", ""),
            "source": "llm",
        }
    except Exception:
        return None


# ───────────────────────────────────────────────────────────────────────────
# CSV-based bank
# ───────────────────────────────────────────────────────────────────────────

class _CSVBank:
    def __init__(self, csv_path: Optional[Path]) -> None:
        self.rows: list[dict[str, str]] = []
        if not csv_path or not csv_path.exists():
            return
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            seen_qs: set[tuple[str, str]] = set()
            for row in reader:
                q = (row.get("question") or "").strip()
                s = (row.get("skill") or "").strip()
                if not q or not s:
                    continue
                # Dedupe on (skill, question) — v5 repeats questions for Good/Avg/Poor
                key = (s.lower(), q.lower())
                if key in seen_qs:
                    continue
                seen_qs.add(key)
                self.rows.append(row)

    def pick(self, skill: str, sub_domain: Optional[str], difficulty: str,
             asked: list[str]) -> Optional[dict]:
        asked_norm = {q.lower().strip() for q in asked}
        # progressively relax filters: exact → drop sub → drop difficulty → skill only
        filters = [
            lambda r: r.get("skill", "").lower() == skill.lower()
                      and (sub_domain is None or r.get("sub_domain", "").lower() == sub_domain.lower())
                      and r.get("difficulty", "").lower() == difficulty.lower(),
            lambda r: r.get("skill", "").lower() == skill.lower()
                      and (sub_domain is None or r.get("sub_domain", "").lower() == sub_domain.lower()),
            lambda r: r.get("skill", "").lower() == skill.lower()
                      and r.get("difficulty", "").lower() == difficulty.lower(),
            lambda r: r.get("skill", "").lower() == skill.lower(),
        ]
        for filt in filters:
            candidates = [
                r for r in self.rows
                if filt(r) and (r.get("question") or "").lower().strip() not in asked_norm
            ]
            if candidates:
                r = random.choice(candidates)
                return {
                    "question": r["question"].strip(),
                    "ideal_answer": (r.get("ideal_answer") or "").strip(),
                    "ideal_keywords": (r.get("ideal_keywords") or "").strip(),
                    "source": "csv",
                }
        return None


# ───────────────────────────────────────────────────────────────────────────
# Template fallback
# ───────────────────────────────────────────────────────────────────────────

_TEMPLATES = {
    "easy":   "What is {topic} in {skill}, and why is it useful?",
    "medium": "Compare two approaches to {topic} in {skill}. When would you choose each?",
    "hard":   "Design a solution involving {topic} in {skill} at scale. Discuss trade-offs.",
}


def _template_question(skill: str, sub_domain: Optional[str], difficulty: str) -> dict:
    topic = (sub_domain or "").replace("_", " ").strip() or skill.lower()
    template = _TEMPLATES.get(difficulty.lower(), _TEMPLATES["medium"])
    return {
        "question": template.format(topic=topic, skill=skill),
        "ideal_answer": "",          # empty → scorer's empty-ideal fallback path
        "ideal_keywords": "",
        "source": "template",
    }


# ───────────────────────────────────────────────────────────────────────────
# Module-level cache — CSV parsed once per process
# ───────────────────────────────────────────────────────────────────────────

_CACHED_BANK: Optional[_CSVBank] = None


def _locate_csv() -> Optional[Path]:
    """Find the active dataset CSV across common locations."""
    env_path = os.getenv("INTERVIV_DATASET_CSV")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    here = Path(__file__).resolve().parent
    candidates = [
        here / "interview_dataset_v6.csv",  # post-merge (this fix-pack)
        here / "interview_dataset_v5.csv",
        here / "interview_dataset_v4.csv",
        here.parent / "data" / "interview_dataset_v6.csv",
        here.parent / "data" / "interview_dataset_v5.csv",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _get_bank() -> _CSVBank:
    global _CACHED_BANK
    if _CACHED_BANK is None:
        _CACHED_BANK = _CSVBank(_locate_csv())
    return _CACHED_BANK


# ───────────────────────────────────────────────────────────────────────────
# Public API — backend calls this single function
# ───────────────────────────────────────────────────────────────────────────

def get_next_question(skill: str, sub_domain: Optional[str], difficulty: str,
                      asked: list[str]) -> dict:
    """Return a question dict. Never raises — always returns something usable."""
    # 1) Resolve the raw skill to (dataset_skill, sub_domain)
    resolved_skill, resolved_sub = resolve_skill(skill)
    if sub_domain is None or sub_domain == "general":
        sub_domain = resolved_sub

    # 2) Try LLM first if key is available
    if os.getenv("OPENROUTER_API_KEY"):
        row = _generate_via_llm(resolved_skill, sub_domain, difficulty, asked)
        if row:
            row["skill"] = resolved_skill
            row["sub_domain"] = sub_domain or "general"
            row["difficulty"] = difficulty
            return row

    # 3) Fall back to CSV bank
    bank = _get_bank()
    row = bank.pick(resolved_skill, sub_domain, difficulty, asked)
    if row:
        row["skill"] = resolved_skill
        row["sub_domain"] = sub_domain or "general"
        row["difficulty"] = difficulty
        return row

    # 4) Template fallback — always succeeds
    row = _template_question(resolved_skill, sub_domain, difficulty)
    row["skill"] = resolved_skill
    row["sub_domain"] = sub_domain or "general"
    row["difficulty"] = difficulty
    return row


# ───────────────────────────────────────────────────────────────────────────
# Self-test
# ───────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("SELF-TEST — question_bank_v2.py")
    print("=" * 70)
    tests = ["C++", "Docker", "DevOps", "React", "PyTorch", "FastAPI", "Python", "Angular", "UnknownXYZ"]
    for raw in tests:
        resolved = resolve_skill(raw)
        q = get_next_question(raw, None, "medium", asked=[])
        print(f"\n{raw:14} -> {resolved[0]}/{resolved[1] or 'general'}")
        print(f"   source={q['source']}  q={q['question'][:100]}")
