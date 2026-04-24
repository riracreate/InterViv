"""
question_bank_v2.py — Drop-in replacement for modules/question_bank.py

Fixes:
  • SKILL_ALIASES map — C++, Docker, DevOps, Java, JavaScript, etc. all resolve
    to stable skill domains instead of crashing or returning generic templates
  • Live question generation is LLM-first by default
  • The CSV bank remains available for evaluation/reference workflows or as an
    explicit fallback mode, but it is no longer the default live question source
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
    "aws":            ("System Design", "cloud"),
    "azure":          ("System Design", "cloud"),
    "gcp":            ("System Design", "cloud"),
    "google cloud":   ("System Design", "cloud"),
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
    "os":             ("OS", "os_core"),
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
# LLM generation — uses stdlib only
# ───────────────────────────────────────────────────────────────────────────

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_OPENROUTER_MODEL = "anthropic/claude-haiku-4-5"
_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

_QUESTION_MODES = {
    "llm",
    "llm_csv_fallback",
    "csv",
    "template",
}

_DIFFICULTY_DESCRIPTORS = {
    "easy": "foundational — definitions, common use-cases, syntax (0–1 yrs).",
    "medium": "intermediate — applied understanding, trade-offs, best practices (1–3 yrs).",
    "hard": "advanced — internals, edge cases, architecture, performance (3+ yrs).",
}


def _question_generation_mode() -> str:
    raw = (
        os.getenv("QUESTION_GENERATION_MODE")
        or os.getenv("INTERVIV_QUESTION_SOURCE")
        or "llm"
    )
    mode = raw.strip().lower().replace("-", "_")
    aliases = {
        "llm_with_csv_fallback": "llm_csv_fallback",
        "llm_csv": "llm_csv_fallback",
        "dataset": "csv",
        "question_bank": "csv",
    }
    mode = aliases.get(mode, mode)
    return mode if mode in _QUESTION_MODES else "llm"


def _llm_provider() -> tuple[str | None, str | None, str | None]:
    provider = (os.getenv("QUESTION_LLM_PROVIDER") or "auto").strip().lower()
    if provider == "openai" or (provider == "auto" and os.getenv("OPENAI_API_KEY")):
        return (
            "openai",
            os.getenv("OPENAI_API_KEY"),
            os.getenv("QUESTION_LLM_MODEL") or os.getenv("OPENAI_MODEL") or _DEFAULT_OPENAI_MODEL,
        )
    if provider == "openrouter" or (provider == "auto" and os.getenv("OPENROUTER_API_KEY")):
        return (
            "openrouter",
            os.getenv("OPENROUTER_API_KEY"),
            os.getenv("QUESTION_LLM_MODEL") or os.getenv("OPENROUTER_MODEL") or _DEFAULT_OPENROUTER_MODEL,
        )
    return (None, None, None)


def _domain_hint(skill: str, sub_domain: Optional[str]) -> str:
    focus_map = {
        "dsa_core": "arrays, hash maps, recursion, trees, graphs, dynamic programming, and Big-O analysis",
        "python_core": "iterators, decorators, context managers, exceptions, memory, and concurrency",
        "python_web": "request lifecycle, async I/O, dependency injection, ORMs, and API design",
        "web_frontend": "component state, rendering performance, accessibility, browser APIs, and testing",
        "web_backend": "API boundaries, data consistency, caching, queues, and failure handling",
        "api_design": "REST, GraphQL, pagination, idempotency, versioning, and authentication",
        "devops": "containers, orchestration, CI/CD, observability, rollbacks, and incident response",
        "cloud": "managed services, scaling, IAM, reliability, and cost trade-offs",
        "relational": "schema design, joins, transactions, indexing, and query planning",
        "nosql": "document/key-value modeling, consistency, partitioning, and indexing",
        "ml_core": "model evaluation, overfitting, features, data leakage, and deployment",
        "dl_frameworks": "training loops, tensors, GPU usage, transfer learning, and debugging",
        "nlp": "tokenization, embeddings, transformers, retrieval, and evaluation",
        "cv": "image preprocessing, CNNs, augmentation, metrics, and deployment constraints",
        "oop_core": "encapsulation, inheritance, polymorphism, composition, and interfaces",
        "os_core": "processes, threads, memory, scheduling, and synchronization",
        "cn_core": "TCP/IP, DNS, HTTP, latency, reliability, and congestion control",
        "distributed_systems": "replication, sharding, consensus, consistency, and fault tolerance",
        "hr_core": "behavioral examples, communication, conflict, ownership, and learning",
    }
    focus = focus_map.get((sub_domain or "").lower())
    if focus:
        return f"Make the question domain-specific for {skill}: focus on {focus}."
    return f"Make the question domain-specific for {skill}, not a generic meta-question."


def _build_llm_prompt(skill: str, sub_domain: Optional[str], difficulty: str, asked: list[str]) -> str:
    diff_desc = _DIFFICULTY_DESCRIPTORS.get(
        difficulty.lower(), _DIFFICULTY_DESCRIPTORS["medium"]
    )
    sub_part = f" (sub-topic: {sub_domain})" if sub_domain and sub_domain != "general" else ""
    asked_part = ""
    if asked:
        previous = "\n".join(f"- {q}" for q in asked[-8:])
        asked_part = f"\n\nAVOID repeating these previous questions:\n{previous}"

    return (
        f"Generate ONE interview question for a candidate with {skill}{sub_part} "
        f"at {difficulty} difficulty level.\n"
        f"Difficulty is {diff_desc}\n"
        f"{_domain_hint(skill, sub_domain)}{asked_part}\n\n"
        f"Respond with STRICT JSON ONLY (no prose, no markdown fences):\n"
        f'{{"question":"...","ideal_answer":"...","ideal_keywords":"k1, k2, k3, k4, k5"}}\n\n'
        f"Requirements:\n"
        f"- question: 1-2 sentences, specific and technical\n"
        f"- ideal_answer: 4-6 sentences with a concrete example and a trade-off\n"
        f"- ideal_keywords: 5 comma-separated technical terms that a strong answer should contain\n"
    )


def _chat_completion_url(provider: str) -> str:
    return _OPENAI_URL if provider == "openai" else _OPENROUTER_URL


def _generate_via_llm(skill: str, sub_domain: Optional[str], difficulty: str, asked: list[str]) -> Optional[dict]:
    provider, api_key, model = _llm_provider()
    if not provider or not api_key or not model:
        return None

    prompt = _build_llm_prompt(skill, sub_domain, difficulty, asked)

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 600,
        "temperature": 0.7,
    }).encode("utf-8")

    req = urllib.request.Request(
        _chat_completion_url(provider),
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
            "llm_provider": provider,
            "llm_model": model,
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
    "easy": [
        "What is {topic} in {skill}, and why is it useful?",
        "Explain a common use case for {topic} in {skill}.",
        "What problem does {topic} solve in {skill}?",
        "Describe the main components of {topic} in {skill}.",
    ],
    "medium": [
        "Compare two approaches to {topic} in {skill}. When would you choose each?",
        "Walk through how you would use {topic} in a real {skill} project.",
        "What are common mistakes candidates make with {topic} in {skill}, and how would you avoid them?",
        "Explain the trade-offs of using {topic} in {skill}.",
        "How would you debug a production issue related to {topic} in {skill}?",
    ],
    "hard": [
        "Design a solution involving {topic} in {skill} at scale. Discuss trade-offs.",
        "How would you optimize a high-traffic system that relies on {topic} in {skill}?",
        "Describe edge cases and failure modes for {topic} in {skill}.",
        "How would you evaluate, monitor, and improve a production implementation of {topic} in {skill}?",
    ],
}


_DOMAIN_FALLBACK_BANK = {
    "dsa_core": [
        {
            "question": "Given an array of integers, how would you find the longest subarray whose sum equals k? Explain the data structure, complexity, and an edge case.",
            "ideal_keywords": "prefix sum, hash map, O(n), subarray, edge case",
        },
        {
            "question": "How would you detect a cycle in a directed graph? Compare DFS coloring with Kahn's algorithm and explain when each is useful.",
            "ideal_keywords": "DFS, topological sort, in-degree, directed graph, cycle",
        },
        {
            "question": "For the coin change problem, how would you decide whether a greedy approach is valid or dynamic programming is required?",
            "ideal_keywords": "dynamic programming, greedy, optimal substructure, recurrence, complexity",
        },
        {
            "question": "How would you design an LRU cache with O(1) get and put operations? Explain the role of each data structure.",
            "ideal_keywords": "hash map, doubly linked list, O(1), eviction, cache",
        },
    ],
    "python_core": [
        {
            "question": "When would you use a generator instead of a list in Python? Discuss memory behavior, one practical example, and one limitation.",
            "ideal_keywords": "generator, yield, lazy evaluation, memory, iterator",
        },
        {
            "question": "How do decorators work in Python, and why is functools.wraps important in production code?",
            "ideal_keywords": "decorator, closure, wrapper, functools.wraps, metadata",
        },
        {
            "question": "How would you choose between threading, multiprocessing, and asyncio for a Python service?",
            "ideal_keywords": "GIL, threading, multiprocessing, asyncio, I/O-bound",
        },
        {
            "question": "Explain Python context managers. How would you implement one for safely opening and closing a resource?",
            "ideal_keywords": "__enter__, __exit__, with statement, resource cleanup, exception",
        },
    ],
    "python_web": [
        {
            "question": "In FastAPI, how would you structure dependency injection for authentication and database sessions?",
            "ideal_keywords": "FastAPI, dependency injection, authentication, database session, request scope",
        },
        {
            "question": "What changes when a Python API endpoint is async? Explain where async helps and where it does not.",
            "ideal_keywords": "async, await, event loop, I/O-bound, blocking",
        },
        {
            "question": "How would you design validation and error responses for a production Python REST API?",
            "ideal_keywords": "Pydantic, validation, HTTP status, error schema, REST",
        },
    ],
    "web_frontend": [
        {
            "question": "In React, how would you prevent unnecessary re-renders in a component tree with expensive child components?",
            "ideal_keywords": "React.memo, useMemo, useCallback, props, rendering",
        },
        {
            "question": "How would you manage server data and local UI state differently in a frontend application?",
            "ideal_keywords": "server state, local state, cache, invalidation, optimistic update",
        },
        {
            "question": "How would you debug a slow page caused by JavaScript bundle size and rendering work?",
            "ideal_keywords": "bundle splitting, profiler, lazy loading, render, performance",
        },
    ],
    "web_backend": [
        {
            "question": "How would you make an API endpoint idempotent when clients may retry the same request?",
            "ideal_keywords": "idempotency key, retry, transaction, duplicate request, API",
        },
        {
            "question": "How would you decide what to cache in a backend service, and how would you handle invalidation?",
            "ideal_keywords": "cache, TTL, invalidation, consistency, Redis",
        },
        {
            "question": "How would you process a slow background task without blocking an HTTP request?",
            "ideal_keywords": "queue, worker, asynchronous job, message broker, retry",
        },
    ],
    "api_design": [
        {
            "question": "Design pagination for a high-volume API. Compare offset pagination with cursor pagination.",
            "ideal_keywords": "cursor pagination, offset, ordering, consistency, API",
        },
        {
            "question": "How would you version a public API without breaking existing clients?",
            "ideal_keywords": "versioning, backward compatibility, deprecation, contract, clients",
        },
        {
            "question": "When would you choose GraphQL over REST, and what operational trade-offs come with that choice?",
            "ideal_keywords": "GraphQL, REST, overfetching, schema, caching",
        },
    ],
    "devops": [
        {
            "question": "How would you design a CI/CD pipeline that can safely roll back a failed production deployment?",
            "ideal_keywords": "CI/CD, rollback, blue-green, canary, deployment",
        },
        {
            "question": "What should go into a Docker image for a production service, and what should stay outside it?",
            "ideal_keywords": "Docker, image, environment variables, secrets, layers",
        },
        {
            "question": "How would you debug a Kubernetes pod that repeatedly restarts after deployment?",
            "ideal_keywords": "Kubernetes, logs, liveness probe, crash loop, resources",
        },
    ],
    "cloud": [
        {
            "question": "How would you design a cloud service for high availability across availability zones?",
            "ideal_keywords": "availability zone, load balancer, replication, failover, SLA",
        },
        {
            "question": "How would you control cloud cost for a service that has unpredictable traffic spikes?",
            "ideal_keywords": "autoscaling, cost, reserved capacity, monitoring, scaling",
        },
        {
            "question": "What IAM design choices reduce blast radius in a cloud application?",
            "ideal_keywords": "IAM, least privilege, role, policy, blast radius",
        },
    ],
    "relational": [
        {
            "question": "Given queries filtering by user_id and sorting by created_at, how would you design a composite index and why does column order matter?",
            "ideal_keywords": "composite index, user_id, created_at, query planner, sort",
        },
        {
            "question": "Explain how transaction isolation can prevent a lost update. Which isolation level would you choose and why?",
            "ideal_keywords": "transaction, isolation, lost update, lock, consistency",
        },
        {
            "question": "How would you investigate and fix a slow SQL query in production?",
            "ideal_keywords": "EXPLAIN, index, query plan, join, latency",
        },
    ],
    "nosql": [
        {
            "question": "How would you model orders and users in a document database? Discuss embedding versus referencing.",
            "ideal_keywords": "document model, embedding, referencing, access pattern, denormalization",
        },
        {
            "question": "How do partition keys affect scalability and hot partitions in a NoSQL database?",
            "ideal_keywords": "partition key, hot partition, scalability, distribution, throughput",
        },
        {
            "question": "When is eventual consistency acceptable in a NoSQL system, and when would it be dangerous?",
            "ideal_keywords": "eventual consistency, strong consistency, stale read, availability, trade-off",
        },
    ],
    "ml_core": [
        {
            "question": "How would you detect data leakage before training a machine learning model?",
            "ideal_keywords": "data leakage, train test split, features, validation, target",
        },
        {
            "question": "A model performs well offline but poorly in production. What would you check first?",
            "ideal_keywords": "data drift, monitoring, distribution shift, evaluation, production",
        },
        {
            "question": "How would you choose evaluation metrics for an imbalanced classification problem?",
            "ideal_keywords": "precision, recall, F1, ROC-AUC, imbalance",
        },
    ],
    "dl_frameworks": [
        {
            "question": "How would you debug a neural network whose training loss is not decreasing?",
            "ideal_keywords": "learning rate, gradients, loss, initialization, data",
        },
        {
            "question": "When would you use transfer learning instead of training a deep model from scratch?",
            "ideal_keywords": "transfer learning, pretrained model, fine tuning, dataset size, features",
        },
        {
            "question": "How do batch size and learning rate interact during deep learning training?",
            "ideal_keywords": "batch size, learning rate, convergence, gradient, GPU",
        },
    ],
    "nlp": [
        {
            "question": "How do tokenization choices affect an NLP model's behavior on rare words and code-mixed text?",
            "ideal_keywords": "tokenization, subword, vocabulary, rare words, NLP",
        },
        {
            "question": "Explain how embeddings are used in semantic search and what can go wrong during retrieval.",
            "ideal_keywords": "embeddings, semantic search, retrieval, similarity, vector database",
        },
        {
            "question": "How would you evaluate a RAG system beyond checking whether the final answer looks correct?",
            "ideal_keywords": "RAG, retrieval, grounding, hallucination, evaluation",
        },
    ],
    "cv": [
        {
            "question": "How would you handle class imbalance in an image classification dataset?",
            "ideal_keywords": "class imbalance, augmentation, sampling, metrics, dataset",
        },
        {
            "question": "What preprocessing steps matter before training a CNN on real-world images?",
            "ideal_keywords": "normalization, resizing, augmentation, CNN, preprocessing",
        },
        {
            "question": "How would you evaluate an object detection model for a production use case?",
            "ideal_keywords": "object detection, mAP, precision, recall, IoU",
        },
    ],
    "oop_core": [
        {
            "question": "When would you prefer composition over inheritance in an object-oriented design?",
            "ideal_keywords": "composition, inheritance, coupling, polymorphism, design",
        },
        {
            "question": "How do interfaces or abstract classes help manage change in a large codebase?",
            "ideal_keywords": "interface, abstraction, dependency inversion, contract, codebase",
        },
        {
            "question": "Explain polymorphism with an example where it removes conditional logic.",
            "ideal_keywords": "polymorphism, subtype, method override, conditional, OOP",
        },
    ],
    "os_core": [
        {
            "question": "Explain the difference between a process and a thread, including memory sharing and failure isolation.",
            "ideal_keywords": "process, thread, memory, isolation, scheduling",
        },
        {
            "question": "How can a deadlock happen, and what strategies can prevent it?",
            "ideal_keywords": "deadlock, lock ordering, mutual exclusion, wait, prevention",
        },
        {
            "question": "What happens during a context switch, and why can too many context switches hurt performance?",
            "ideal_keywords": "context switch, scheduler, CPU, overhead, performance",
        },
    ],
    "cn_core": [
        {
            "question": "Walk through what happens from entering a URL in the browser to receiving the first byte of the response.",
            "ideal_keywords": "DNS, TCP, TLS, HTTP, latency",
        },
        {
            "question": "How does TCP provide reliable delivery, and what trade-offs does it introduce?",
            "ideal_keywords": "TCP, reliability, retransmission, congestion control, latency",
        },
        {
            "question": "How would you debug high latency between a client and a backend service?",
            "ideal_keywords": "latency, traceroute, DNS, network, monitoring",
        },
    ],
    "distributed_systems": [
        {
            "question": "How would you shard a key-value store, and what problems appear when adding or removing nodes?",
            "ideal_keywords": "sharding, consistent hashing, rebalancing, replication, key-value",
        },
        {
            "question": "Compare strong consistency and eventual consistency for a shopping cart service.",
            "ideal_keywords": "strong consistency, eventual consistency, availability, partition, trade-off",
        },
        {
            "question": "How would you design retries so they do not overload a failing distributed system?",
            "ideal_keywords": "retry, backoff, jitter, circuit breaker, overload",
        },
    ],
    "hr_core": [
        {
            "question": "Tell me about a time you disagreed with a teammate on a technical decision. How did you handle it?",
            "ideal_keywords": "conflict, communication, trade-off, ownership, outcome",
        },
        {
            "question": "Describe a project where you had to learn something quickly to deliver. What was your approach?",
            "ideal_keywords": "learning, prioritization, delivery, feedback, reflection",
        },
        {
            "question": "Tell me about a production issue or failure you were involved in. What did you change afterward?",
            "ideal_keywords": "incident, ownership, root cause, prevention, learning",
        },
    ],
}


def _template_topic(skill: str, sub_domain: Optional[str]) -> str:
    raw = (sub_domain or "").strip()
    if not raw or raw == "general":
        return skill

    normalized = raw.replace("_", " ").strip()
    replacements = {
        "python core": "core Python",
        "python web": "Python web development",
        "dsa core": "data structures and algorithms",
        "oop core": "object-oriented programming",
        "os core": "operating systems",
        "cn core": "computer networks",
        "dbms core": "database systems",
        "ml core": "machine learning fundamentals",
        "hr core": "behavioral interviewing",
    }
    return replacements.get(normalized.lower(), normalized)


def _template_question(skill: str, sub_domain: Optional[str], difficulty: str) -> dict:
    topic = _template_topic(skill, sub_domain)
    template = random.choice(_TEMPLATES.get(difficulty.lower(), _TEMPLATES["medium"]))
    return {
        "question": template.format(topic=topic, skill=skill),
        "ideal_answer": "",          # empty → scorer's empty-ideal fallback path
        "ideal_keywords": "",
        "source": "template",
    }


def _domain_fallback_keys(skill: str, sub_domain: Optional[str]) -> list[str]:
    keys: list[str] = []
    sub_key = (sub_domain or "").strip().lower()
    if sub_key and sub_key != "general":
        keys.append(sub_key)
        if sub_key in _DOMAIN_FALLBACK_BANK:
            return keys

    skill_key = (skill or "").strip().lower()
    skill_defaults = {
        "python": "python_core",
        "dsa": "dsa_core",
        "oop": "oop_core",
        "os": "os_core",
        "cn": "cn_core",
        "dbms": "relational",
        "ml": "ml_core",
        "system design": "distributed_systems",
        "hr": "hr_core",
        "javascript": "web_frontend",
        "typescript": "web_frontend",
        "react": "web_frontend",
        "node.js": "web_backend",
        "nodejs": "web_backend",
        "fastapi": "python_web",
        "django": "python_web",
        "flask": "python_web",
        "docker": "devops",
        "kubernetes": "devops",
        "aws": "cloud",
        "gcp": "cloud",
        "azure": "cloud",
        "mongodb": "nosql",
        "redis": "nosql",
        "postgresql": "relational",
        "mysql": "relational",
    }
    default = skill_defaults.get(skill_key)
    if default and default not in keys:
        keys.append(default)
    if skill_key and skill_key not in keys:
        keys.append(skill_key)
    return keys


def _domain_fallback_question(skill: str, sub_domain: Optional[str], asked: list[str]) -> Optional[dict]:
    rows: list[dict[str, str]] = []
    for key in _domain_fallback_keys(skill, sub_domain):
        rows.extend(_DOMAIN_FALLBACK_BANK.get(key, []))

    if not rows:
        return None

    asked_norm = {q.lower().strip() for q in asked}
    fresh = [
        row for row in rows
        if row["question"].lower().strip() not in asked_norm
    ]
    row = random.choice(fresh or rows)
    return {
        "question": row["question"],
        "ideal_answer": "",
        "ideal_keywords": row.get("ideal_keywords", ""),
        "source": "domain_fallback",
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

    mode = _question_generation_mode()

    # 2) Live interviews are LLM-first by default.
    if mode in {"llm", "llm_csv_fallback"}:
        row = _generate_via_llm(resolved_skill, sub_domain, difficulty, asked)
        if row:
            row["skill"] = resolved_skill
            row["sub_domain"] = sub_domain or "general"
            row["difficulty"] = difficulty
            return row

    # 3) CSV is kept for evaluation/reference and is used only when configured.
    if mode in {"csv", "llm_csv_fallback"}:
        bank = _get_bank()
        row = bank.pick(resolved_skill, sub_domain, difficulty, asked)
        if row:
            row["skill"] = resolved_skill
            row["sub_domain"] = sub_domain or "general"
            row["difficulty"] = difficulty
            return row

    # 4) Domain fallback — real technical questions when no LLM key is configured.
    row = _domain_fallback_question(resolved_skill, sub_domain, asked)
    if row:
        row["skill"] = resolved_skill
        row["sub_domain"] = sub_domain or "general"
        row["difficulty"] = difficulty
        return row

    # 5) Generic template fallback — always succeeds for unknown skills.
    row = _template_question(resolved_skill, sub_domain, difficulty)
    templates = _TEMPLATES.get(difficulty.lower(), _TEMPLATES["medium"])
    topic = _template_topic(resolved_skill, sub_domain)
    asked_norm = {q.lower().strip() for q in asked}
    available = [
        template.format(topic=topic, skill=resolved_skill)
        for template in templates
        if template.format(topic=topic, skill=resolved_skill).lower().strip() not in asked_norm
    ]
    if available:
        row["question"] = random.choice(available)
    else:
        row["question"] = (
            f"For {resolved_skill}, explain a concrete lesson learned from working with "
            f"{topic}. Include trade-offs and one edge case."
        )
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
