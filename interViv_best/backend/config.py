from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    project_root: Path
    modules_dir: Path
    environment: str
    database_url: str | None
    mongodb_uri: str
    mongodb_db: str
    mongodb_timeout_ms: int
    cors_origins: list[str]
    max_rounds: int
    initial_elo: float
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_access_token_minutes: int
    enable_admin_endpoints: bool
    # Phase 1A: authenticated users allowed to act on admin bundle-review routes.
    # Empty (default) means every review action is 403 even when the router is mounted.
    admin_user_emails: frozenset[str]
    # Phase 1A/1B: selector flag. Default off. When on, technical interview
    # selection uses reviewed bundles only (no draft/legacy scored fallback).
    reviewed_bundles_only: bool
    # Phase 1B: experimental concept evaluator (research/admin). Default off;
    # never feeds production scoring, mastery, Elo, or readiness.
    experimental_concept_evaluator: bool
    length_ratio_multiplier_enabled: bool
    adzuna_app_id: str | None
    adzuna_app_key: str | None
    jobs_live_fetch: bool
    jobs_cache_ttl_seconds: int
    jobs_rate_limit_per_minute: int
    interview_module_paths: list[Path]
    interview_model_paths: list[Path]
    interview_data_paths: list[Path]


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _validate_security_settings(settings: Settings) -> Settings:
    if settings.jwt_algorithm != "HS256":
        raise RuntimeError("JWT_ALGORITHM must be HS256.")

    if settings.environment in {"production", "prod"}:
        secret = settings.jwt_secret_key.strip()
        weak_markers = {"change-me", "dev-only", "local-dev", "example", "placeholder"}
        if len(secret) < 32 or any(marker in secret.lower() for marker in weak_markers):
            raise RuntimeError(
                "Production requires a unique JWT_SECRET_KEY of at least 32 characters."
            )
        if "*" in settings.cors_origins:
            raise RuntimeError("Production CORS_ORIGINS must not contain '*'.")
    return settings


def _resolve_paths(raw_value: str | None, defaults: list[Path]) -> list[Path]:
    if not raw_value:
        return defaults

    resolved: list[Path] = []
    for entry in raw_value.split(os.pathsep):
        candidate = entry.strip()
        if not candidate:
            continue
        resolved.append(Path(candidate).expanduser().resolve())
    return resolved or defaults


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    modules_dir = project_root / "modules"
    load_dotenv(project_root / ".env", override=False)

    default_module_paths = [
        modules_dir,
        project_root / "backend",
        project_root,
    ]
    default_model_paths = [
        modules_dir,
        project_root / "backend" / "scoring",
        project_root / "backend",
    ]
    default_data_paths = [
        modules_dir,
        project_root,
    ]

    settings = Settings(
        project_root=project_root,
        modules_dir=modules_dir,
        environment=(os.getenv("ENVIRONMENT") or "development").strip().lower(),
        database_url=os.getenv("DATABASE_URL") or None,
        mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        mongodb_db=os.getenv("MONGODB_DB", "adaptive_mock_interview"),
        mongodb_timeout_ms=int(os.getenv("MONGODB_TIMEOUT_MS", "2000")),
        cors_origins=_split_csv(
            os.getenv(
                "CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
            )
        ),
        max_rounds=int(os.getenv("MAX_ROUNDS", "5")),
        initial_elo=float(os.getenv("INITIAL_ELO", "1200")),
        jwt_secret_key=os.getenv("JWT_SECRET_KEY") or "dev-only-change-me-with-32-plus-bytes",
        jwt_algorithm=(os.getenv("JWT_ALGORITHM") or "HS256").strip().upper(),
        jwt_access_token_minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "1440")),
        enable_admin_endpoints=_env_bool("ENABLE_ADMIN_ENDPOINTS", False),
        admin_user_emails=frozenset(
            item.lower() for item in _split_csv(os.getenv("ADMIN_USER_EMAILS", ""))
        ),
        reviewed_bundles_only=_env_bool("REVIEWED_BUNDLES_ONLY", False),
        experimental_concept_evaluator=_env_bool("EXPERIMENTAL_CONCEPT_EVALUATOR", False),
        length_ratio_multiplier_enabled=_env_bool("LENGTH_RATIO_MULTIPLIER_ENABLED", False),
        adzuna_app_id=(os.getenv("ADZUNA_APP_ID") or "").strip() or None,
        adzuna_app_key=(os.getenv("ADZUNA_APP_KEY") or "").strip() or None,
        jobs_live_fetch=_env_bool("JOBS_LIVE_FETCH", False),
        jobs_cache_ttl_seconds=int(os.getenv("JOBS_CACHE_TTL_SECONDS", str(6 * 3600))),
        jobs_rate_limit_per_minute=int(os.getenv("JOBS_RATE_LIMIT_PER_MINUTE", "30")),
        interview_module_paths=_resolve_paths(
            os.getenv("INTERVIEW_MODULE_PATHS"),
            default_module_paths,
        ),
        interview_model_paths=_resolve_paths(
            os.getenv("INTERVIEW_MODEL_PATHS"),
            default_model_paths,
        ),
        interview_data_paths=_resolve_paths(
            os.getenv("INTERVIEW_DATA_PATHS"),
            default_data_paths,
        ),
    )
    return _validate_security_settings(settings)
