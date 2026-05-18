from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routes.admin import router as admin_router
from backend.routes.answer import router as answer_router
from backend.routes.auth import router as auth_router
from backend.routes.companies import router as companies_router
from backend.routes.dashboard import router as dashboard_router
from backend.routes.gap_analysis import router as gap_analysis_router
from backend.routes.roadmap import router as roadmap_router
from backend.routes.learning import router as learning_router
from backend.routes.resume import router as resume_router
from backend.routes.session import router as session_router
from backend.routes.transcribe import router as transcribe_router
from backend.scoring.pipeline import get_model_metadata


settings = get_settings()
app = FastAPI(title="interViv - Interview Readiness Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_router)
app.include_router(auth_router)
app.include_router(companies_router)
app.include_router(gap_analysis_router)
app.include_router(roadmap_router)
app.include_router(session_router)
app.include_router(answer_router)
app.include_router(dashboard_router)
app.include_router(learning_router)
app.include_router(transcribe_router)
app.include_router(admin_router)


@app.on_event("startup")
def verify_model_metadata() -> None:
    get_model_metadata()


@app.on_event("startup")
def warm_company_graph() -> None:
    """Load company hiring graph and seed DB tables idempotently."""
    import logging

    from modules.company_graph import get_company_graph
    from backend.db.company_seed import seed_company_graph

    logger = logging.getLogger(__name__)
    try:
        graph = get_company_graph()
        logger.info("Loaded company hiring graph: %d companies", len(graph.list_companies()))
        counts = seed_company_graph(graph)
        if any(counts.values()):
            logger.info("Seeded company graph rows: %s", counts)
    except Exception as exc:  # pragma: no cover - startup logs only
        logger.exception("Company hiring graph startup failed: %s", exc)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
