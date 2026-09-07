from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    target_company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    target_role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CompanyRow(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class RoleRow(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str | None] = mapped_column(String(80), nullable=True)

    __table_args__ = (UniqueConstraint("company_id", "title", "level", name="uq_roles_company_title_level"),)


class SkillRow(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    sub_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id"), nullable=True)


class CompanyRoleRequirementRow(Base):
    __tablename__ = "company_role_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False, index=True)
    required_level: Mapped[float] = mapped_column(Float, nullable=False)
    importance_weight: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (UniqueConstraint("role_id", "skill_id", name="uq_company_role_requirements_role_skill"),)


class StudentSkillGraphRow(Base):
    __tablename__ = "student_skill_graph"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False, index=True)
    current_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_elo: Mapped[float] = mapped_column(Float, default=1200.0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_student_skill_graph_user_skill"),)


class StudentConceptMasteryRow(Base):
    __tablename__ = "student_concept_mastery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False, index=True)
    concept_name: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    demonstrated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "skill_id", "concept_name", name="uq_concept_mastery_user_skill_concept"),)


class CandidateRow(Base):
    __tablename__ = "candidates"

    candidate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    resume_skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    sub_domain_profile: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    elo_ratings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    session_history: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.candidate_id"), nullable=True, index=True)
    target_company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    target_role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    overall_readiness_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    skill: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sub_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    current_difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_skill: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_round: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    skills_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    rounds_per_skill: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    total_rounds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    template_id: Mapped[str | None] = mapped_column(ForeignKey("interview_templates.id"), nullable=True)
    # Phase B block contract (nullable so legacy rows stay valid).
    round_plan_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    round_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    block_plan_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    expanded_plan_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    allow_unknown_topic_fallback: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    rounds: Mapped[list["RoundRow"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="RoundRow.round_number",
    )


class RoundRow(Base):
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id"), nullable=True)
    question_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    scoring_breakdown_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    guard_applied: Mapped[str | None] = mapped_column(String(255), nullable=True)
    feedback_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    engagement_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    engagement_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)

    skill_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    round_type: Mapped[str] = mapped_column(String(50), nullable=False, default="technical_short_answer")
    artifact_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    difficulty_change: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nlp_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    svm_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    kg_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    kg_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    covered_concepts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    missing_concepts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    ner_entities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    elo_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    elo_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    question_context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="in_progress", nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Phase B block identity (nullable so legacy rounds stay valid).
    block_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    block_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    block_category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    block_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    block_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Phase D assistance marking (nullable: legacy rounds read as unassisted).
    assisted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    assistance_kinds: Mapped[list | None] = mapped_column(JSON, nullable=True)

    session: Mapped[SessionRow] = relationship(back_populates="rounds")

    __table_args__ = (UniqueConstraint("session_id", "round_number", name="uq_rounds_session_round"),)


class InterviewTemplateRow(Base):
    __tablename__ = "interview_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    rounds: Mapped[list["TemplateRoundRow"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateRoundRow.position",
    )


class TemplateRoundRow(Base):
    __tablename__ = "template_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("interview_templates.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    round_type: Mapped[str] = mapped_column(String(50), nullable=False, default="technical_short_answer")
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    template: Mapped[InterviewTemplateRow] = relationship(back_populates="rounds")

    __table_args__ = (UniqueConstraint("template_id", "position", name="uq_template_rounds_template_position"),)


class QuestionRubricRow(Base):
    __tablename__ = "question_rubrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    required_concept: Mapped[str] = mapped_column(String(255), nullable=False)
    importance_weight: Mapped[float] = mapped_column(Float, nullable=False)


class MCQQuestionRow(Base):
    __tablename__ = "mcq_questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False, index=True)
    sub_domain: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stem: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    options_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    correct_option_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_marking: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    __table_args__ = (
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_mcq_questions_difficulty"),
        CheckConstraint("negative_marking >= 0.0 AND negative_marking <= 1.0", name="ck_mcq_questions_negative_marking"),
    )


class SQLProblemRow(Base):
    __tablename__ = "sql_problems"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    schema_ddl: Mapped[str] = mapped_column(Text, nullable=False)
    reference_query: Mapped[str] = mapped_column(Text, nullable=False)
    checks_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    cases: Mapped[list["SQLProblemCaseRow"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        order_by="SQLProblemCaseRow.sort_order",
    )

    __table_args__ = (
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_sql_problems_difficulty"),
    )


class SQLProblemCaseRow(Base):
    __tablename__ = "sql_problem_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("sql_problems.id", ondelete="CASCADE"), nullable=False, index=True)
    case_type: Mapped[str] = mapped_column(String(30), nullable=False)
    seed_data: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    problem: Mapped[SQLProblemRow] = relationship(back_populates="cases")

    __table_args__ = (
        UniqueConstraint("problem_id", "sort_order", name="uq_sql_problem_cases_order"),
        CheckConstraint("case_type IN ('visible_sample', 'hidden_case')", name="ck_sql_problem_cases_type"),
    )


class LearningEventRow(Base):
    """Persisted effectiveness signals (Elo deltas, skill attempts)."""

    __tablename__ = "learning_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    skill: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RoadmapProgressRow(Base):
    """Per-user roadmap block completion for 7/14/30 day plans."""

    __tablename__ = "roadmap_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan_days: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_blocks: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    blocks_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "plan_days", name="uq_roadmap_progress_user_role_days"),
        CheckConstraint("plan_days IN (7, 14, 30)", name="ck_roadmap_progress_plan_days"),
    )


class LearningResourceRow(Base):
    """Curated lecture/solution links for Phase 2 skills (no scrape / no API)."""

    __tablename__ = "learning_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    # Soft reference to MCQ/SQL bank item id (no single questions table).
    question_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("skill_id", "url", name="uq_learning_resources_skill_url"),
        CheckConstraint(
            "level IN ('beginner', 'intermediate', 'advanced')",
            name="ck_learning_resources_level",
        ),
        CheckConstraint(
            "source IN ('youtube', 'docs', 'other')",
            name="ck_learning_resources_source",
        ),
    )


class AtsRunRow(Base):
    """Persisted ATS checker runs (deterministic scores + flags)."""

    __tablename__ = "ats_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resume_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    jd_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parse_score: Mapped[float] = mapped_column(Float, nullable=False)
    section_score: Mapped[float] = mapped_column(Float, nullable=False)
    keyword_score: Mapped[float] = mapped_column(Float, nullable=False)
    heuristic_score: Mapped[float] = mapped_column(Float, nullable=False)
    total: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    missing_skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    present_skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class JobsCacheRow(Base):
    """Cached Adzuna (or fixture) job cards — snippet + metadata only."""

    __tablename__ = "jobs_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, default="", nullable=False)
    redirect_url: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_jobs_cache_provider_external"),
    )


class JobsSearchCacheRow(Base):
    """Query-level cache so identical searches skip Adzuna within TTL."""

    __tablename__ = "jobs_search_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    page: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    results_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class PracticePresetRow(Base):
    """User-scoped, versioned Phase B practice presets."""

    __tablename__ = "practice_presets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    blocks_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class BuilderDraftRow(Base):
    """One autosaved Phase B builder draft per user."""

    __tablename__ = "builder_drafts"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    blocks_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AnswerDraftRow(Base):
    """In-progress answers keyed by session and round (owned drafts only)."""

    __tablename__ = "answer_drafts"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    round_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    draft_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CodingSubmissionRow(Base):
    """Phase C coding submit attempts: candidate source plus outcome counts.

    One row per submit attempt (retries after an unavailable outcome
    each record their own row). Hidden inputs, expected outputs,
    reference solutions, and hidden stdout/stderr are never stored.
    """

    __tablename__ = "coding_submissions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    problem_id: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="python")
    source: Mapped[str] = mapped_column(Text, nullable=False, default="")
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    visible_passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visible_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hidden_passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hidden_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TargetContextRow(Base):
    """Phase D shared target context: one row per user.

    Carries company, role, the selected job or JD, and the relevant
    resume reference so every hop (jobs, coach, ATS, gap, roadmap,
    practice) can prefill from one server-validated source instead of
    re-prompting. Selecting a target is intent, not evidence: nothing
    here feeds mastery or readiness math.
    """

    __tablename__ = "target_contexts"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    jd_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RetrySetRow(Base):
    """Phase D retry set: a persisted practice set drawn from missed topics."""

    __tablename__ = "retry_sets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    items_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="missed-topics")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class BookmarkRow(Base):
    """Phase D bookmarked problem/question (user + item identity)."""

    __tablename__ = "bookmarks"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    item_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AssistanceEventRow(Base):
    """Phase D hint/solution-use metadata, recorded at the point of use.

    Append-only. A round is marked assisted when an event exists for one
    of its items before submit; learning surfaces keep assisted and
    unassisted populations separate. Scores are never altered.
    """

    __tablename__ = "assistance_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(16), nullable=False)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
