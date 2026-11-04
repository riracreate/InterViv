from __future__ import annotations

# Phase J: Hub offline defaults must land before huggingface_hub is imported
# (constants read HF_HUB_OFFLINE at import time).
from backend.runtime_env import apply_runtime_env

apply_runtime_env()

from contextlib import asynccontextmanager
import json
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from backend.config import get_settings
from backend.observability import init_sentry
from modules.llm_outbound_gate import question_source_health
from backend.routes.admin import router as admin_router
from backend.routes.answer import router as answer_router
from backend.routes.ats import router as ats_router
from backend.routes.auth import router as auth_router
from backend.routes.av import router as av_router
from backend.routes.ml_primitives import router as ml_primitives_router
from backend.routes.companies import router as companies_router
from backend.routes.dashboard import router as dashboard_router
from backend.routes.gap_analysis import router as gap_analysis_router
from backend.routes.coach import router as coach_router
from backend.routes.jobs import router as jobs_router
from backend.routes.roadmap import router as roadmap_router
from backend.routes.learning import router as learning_router
from backend.routes.learning_hub import router as learning_hub_router
from backend.routes.practice import router as practice_router
from backend.routes.problems import router as problems_router
from backend.routes.target_context import router as target_context_router
from backend.routes.resume import router as resume_router
from backend.routes.resources import router as resources_router
from backend.routes.session import router as session_router
from backend.routes.feedback import router as feedback_router
from backend.routes.follow_ups import router as follow_ups_router
from backend.routes.session_continue import router as session_continue_router
from backend.routes.round_activation import router as round_activation_router
from backend.routes.transcribe import router as transcribe_router
from backend.startup_warmup import warm_runtime_dependencies


logger = logging.getLogger(__name__)


class DashboardLatencyMiddleware(BaseHTTPMiddleware):
    """Log latency for /dashboard* routes (no new APM vendor)."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/dashboard"):
            return await call_next(request)
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        logger.info(
            "dashboard_api_latency path=%s method=%s status=%s duration_ms=%.1f",
            path,
            request.method,
            getattr(response, "status_code", "?"),
            elapsed_ms,
        )
        return response


class PublicTargetSlugMiddleware(BaseHTTPMiddleware):
    """Company and role identifiers leave the API as slugs, whatever row stored them."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        media = response.headers.get("content-type", "")
        if "application/json" not in media:
            return response
        chunks: list[bytes] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        raw = b"".join(chunks)
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(
                content=raw,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        from backend.db.user_target import expose_target_slugs

        encoded = json.dumps(expose_target_slugs(payload)).encode()
        headers = {key: value for key, value in response.headers.items() if key.lower() != "content-length"}
        return Response(
            content=encoded,
            status_code=response.status_code,
            headers=headers,
            media_type="application/json",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global WARMUP_STATUS
    WARMUP_STATUS = warm_runtime_dependencies()

    # Load company hiring graph and seed DB tables idempotently.
    from modules.company_graph import get_company_graph
    from backend.db.company_seed import seed_company_graph

    try:
        graph = get_company_graph()
        logger.info("Loaded company hiring graph: %d companies", len(graph.list_companies()))
        counts = seed_company_graph(graph)
        if any(counts.values()):
            logger.info("Seeded company graph rows: %s", counts)
    except Exception as exc:  # pragma: no cover - startup logs only
        logger.exception("Company hiring graph startup failed: %s", exc)

    try:
        from modules.learning_resources import ensure_seeded

        ensure_seeded()
    except Exception as exc:  # pragma: no cover
        logger.exception("Learning resources seed failed: %s", exc)

    yield


settings = get_settings()
SENTRY_ENABLED = init_sentry()
WARMUP_STATUS: dict[str, object] = {}
app = FastAPI(title="interViv - Interview Readiness Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Always accept loopback origins on any port for local dev, so the app works
    # whether it's opened via localhost or 127.0.0.1 (browsers treat those as
    # distinct origins). Configured production origins still come from CORS_ORIGINS.
    allow_origin_regex=(
        r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
        if settings.environment not in {"production", "prod"}
        else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(DashboardLatencyMiddleware)
app.add_middleware(PublicTargetSlugMiddleware)

app.include_router(resume_router)
app.include_router(auth_router)
app.include_router(companies_router)
app.include_router(gap_analysis_router)
app.include_router(roadmap_router)
app.include_router(session_router)
app.include_router(session_continue_router)
app.include_router(round_activation_router)
app.include_router(feedback_router)
app.include_router(follow_ups_router)
app.include_router(answer_router)
app.include_router(dashboard_router)
app.include_router(learning_router)
app.include_router(learning_hub_router)
app.include_router(practice_router)
app.include_router(problems_router)
app.include_router(target_context_router)
app.include_router(resources_router)
app.include_router(ats_router)
app.include_router(jobs_router)
app.include_router(coach_router)
app.include_router(transcribe_router)
app.include_router(av_router)
app.include_router(ml_primitives_router)
if settings.enable_admin_endpoints:
    app.include_router(admin_router)




@app.get("/health")
def healthcheck() -> dict[str, object]:
    st = WARMUP_STATUS.get("sentence_transformer") or {}
    semantic_loaded = bool(st.get("loaded"))
    fallback_reason = st.get("fallback_reason") or st.get("error")
    return {
        "status": "ok",
        "sentry_enabled": SENTRY_ENABLED,
        "warmup": WARMUP_STATUS,
        # Explicit scoring-mode disclosure (Phase F): lexical fallback is not
        # equivalent to a full SemanticScorer result.
        "scoring": {
            "semantic_scoring_available": semantic_loaded,
            "semantic_fallback_reason": None if semantic_loaded else fallback_reason,
            "mode": "full" if semantic_loaded else "lexical_fallback_degraded",
            "operator_note": (
                None
                if semantic_loaded
                else (
                    "SemanticScorer unavailable; interview NLP scores and the "
                    "off_topic guard use the lexical fallback. Results are not "
                    "equivalent to full-scorer runs."
                )
            ),
        },
        "question_source": question_source_health(),
    }


@app.get("/ready")
def readiness():
    from backend.readiness import readiness_status

    ready, payload = readiness_status()
    return JSONResponse(payload, status_code=200 if ready else 503)
