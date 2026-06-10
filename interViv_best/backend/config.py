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
    interview_module_paths: list[Path]
    interview_model_paths: list[Path]
    interview_data_paths: list[Path]


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


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

    return Settings(
        project_root=project_root,
        modules_dir=modules_dir,
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
        jwt_secret_key=os.getenv("JWT_SECRET_KEY", "dev-only-change-me-with-32-plus-bytes"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        jwt_access_token_minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "1440")),
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
