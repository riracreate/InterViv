from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260518_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("public_info", sa.JSON(), nullable=True),
        sa.UniqueConstraint("name", name="uq_companies_name"),
    )

    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("sub_domain", sa.String(length=255), nullable=True),
        sa.Column("parent_skill_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["parent_skill_id"], ["skills.id"]),
        sa.UniqueConstraint("canonical_name", name="uq_skills_canonical_name"),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("level", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.UniqueConstraint("company_id", "title", "level", name="uq_roles_company_title_level"),
    )
    op.create_index("ix_roles_company_id", "roles", ["company_id"])

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("target_company_id", sa.Integer(), nullable=True),
        sa.Column("target_role_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["target_company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["target_role_id"], ["roles.id"]),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "company_role_requirements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("required_level", sa.Float(), nullable=False),
        sa.Column("importance_weight", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.UniqueConstraint("role_id", "skill_id", name="uq_company_role_requirements_role_skill"),
    )
    op.create_index("ix_company_role_requirements_role_id", "company_role_requirements", ["role_id"])
    op.create_index("ix_company_role_requirements_skill_id", "company_role_requirements", ["skill_id"])

    op.create_table(
        "student_skill_graph",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("current_score", sa.Float(), nullable=False),
        sa.Column("current_elo", sa.Float(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_practiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.UniqueConstraint("user_id", "skill_id", name="uq_student_skill_graph_user_skill"),
    )
    op.create_index("ix_student_skill_graph_user_id", "student_skill_graph", ["user_id"])
    op.create_index("ix_student_skill_graph_skill_id", "student_skill_graph", ["skill_id"])

    op.create_table(
        "student_concept_mastery",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("concept_name", sa.String(length=255), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("demonstrated", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.UniqueConstraint("user_id", "skill_id", "concept_name", name="uq_concept_mastery_user_skill_concept"),
    )
    op.create_index("ix_student_concept_mastery_user_id", "student_concept_mastery", ["user_id"])
    op.create_index("ix_student_concept_mastery_skill_id", "student_concept_mastery", ["skill_id"])

    op.create_table(
        "candidates",
        sa.Column("candidate_id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("resume_skills", sa.JSON(), nullable=False),
        sa.Column("sub_domain_profile", sa.JSON(), nullable=False),
        sa.Column("elo_ratings", sa.JSON(), nullable=False),
        sa.Column("session_history", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_candidates_user_id", "candidates", ["user_id"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("candidate_id", sa.String(length=64), nullable=True),
        sa.Column("target_company_id", sa.Integer(), nullable=True),
        sa.Column("target_role_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overall_readiness_score", sa.Float(), nullable=True),
        sa.Column("skill", sa.String(length=255), nullable=True),
        sa.Column("sub_domain", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("current_difficulty", sa.String(length=50), nullable=True),
        sa.Column("current_skill", sa.String(length=255), nullable=True),
        sa.Column("last_round", sa.Integer(), nullable=False),
        sa.Column("skills_json", sa.JSON(), nullable=False),
        sa.Column("rounds_per_skill", sa.Integer(), nullable=False),
        sa.Column("total_rounds", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"]),
        sa.ForeignKeyConstraint(["target_company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["target_role_id"], ["roles.id"]),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_candidate_id", "sessions", ["candidate_id"])

    op.create_table(
        "rounds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=True),
        sa.Column("question_id", sa.String(length=255), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("scoring_breakdown_json", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("guard_applied", sa.String(length=255), nullable=True),
        sa.Column("feedback_json", sa.JSON(), nullable=True),
        sa.Column("engagement_label", sa.String(length=80), nullable=True),
        sa.Column("engagement_delta", sa.Integer(), nullable=True),
        sa.Column("skill_text", sa.String(length=255), nullable=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=50), nullable=True),
        sa.Column("difficulty_change", sa.String(length=50), nullable=True),
        sa.Column("nlp_score", sa.Float(), nullable=True),
        sa.Column("svm_label", sa.String(length=80), nullable=True),
        sa.Column("kg_score", sa.Float(), nullable=True),
        sa.Column("kg_label", sa.String(length=255), nullable=True),
        sa.Column("covered_concepts", sa.JSON(), nullable=False),
        sa.Column("missing_concepts", sa.JSON(), nullable=False),
        sa.Column("ner_entities", sa.JSON(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("elo_before", sa.Float(), nullable=True),
        sa.Column("elo_after", sa.Float(), nullable=True),
        sa.Column("question_context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.UniqueConstraint("session_id", "round_number", name="uq_rounds_session_round"),
    )
    op.create_index("ix_rounds_session_id", "rounds", ["session_id"])
    op.create_index("ix_rounds_skill_id", "rounds", ["skill_id"])

    op.create_table(
        "question_rubrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("question_id", sa.String(length=255), nullable=False),
        sa.Column("required_concept", sa.String(length=255), nullable=False),
        sa.Column("importance_weight", sa.Float(), nullable=False),
    )
    op.create_index("ix_question_rubrics_question_id", "question_rubrics", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_question_rubrics_question_id", table_name="question_rubrics")
    op.drop_table("question_rubrics")
    op.drop_index("ix_rounds_skill_id", table_name="rounds")
    op.drop_index("ix_rounds_session_id", table_name="rounds")
    op.drop_table("rounds")
    op.drop_index("ix_sessions_candidate_id", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_candidates_user_id", table_name="candidates")
    op.drop_table("candidates")
    op.drop_index("ix_student_concept_mastery_skill_id", table_name="student_concept_mastery")
    op.drop_index("ix_student_concept_mastery_user_id", table_name="student_concept_mastery")
    op.drop_table("student_concept_mastery")
    op.drop_index("ix_student_skill_graph_skill_id", table_name="student_skill_graph")
    op.drop_index("ix_student_skill_graph_user_id", table_name="student_skill_graph")
    op.drop_table("student_skill_graph")
    op.drop_index("ix_company_role_requirements_skill_id", table_name="company_role_requirements")
    op.drop_index("ix_company_role_requirements_role_id", table_name="company_role_requirements")
    op.drop_table("company_role_requirements")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_roles_company_id", table_name="roles")
    op.drop_table("roles")
    op.drop_table("skills")
    op.drop_table("companies")
