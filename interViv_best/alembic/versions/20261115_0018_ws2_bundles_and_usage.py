"""WS2: extend bundle statuses and add usage, role skill cache, and bundle generation jobs.

Revision ID: 20261115_0018
Revises: 20261103_0017
Create Date: 2026-11-15 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261115_0018"
down_revision = "20261103_0017"
branch_labels = None
depends_on = None

_OLD_BUNDLE_STATUS_CHECK = "status IN ('draft','in_review','reviewed','rejected','retired')"
_NEW_BUNDLE_STATUS_CHECK = (
    "status IN ('draft','generated','auto_checked','in_review','reviewed','rejected','retired')"
)


def upgrade() -> None:
    with op.batch_alter_table("question_bundle_versions") as batch_op:
        batch_op.drop_constraint("ck_bundle_versions_status", type_="check")
        batch_op.create_check_constraint(
            "ck_bundle_versions_status",
            _NEW_BUNDLE_STATUS_CHECK,
        )

    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bundle_id", sa.String(length=128), nullable=True),
        sa.Column("role", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ok"),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_llm_usage_events_created_at", "llm_usage_events", ["created_at"])
    op.create_index("ix_llm_usage_events_purpose", "llm_usage_events", ["purpose"])

    op.create_table(
        "role_skill_cache",
        sa.Column("cache_key", sa.String(length=128), primary_key=True),
        sa.Column("role", sa.String(length=256), nullable=False),
        sa.Column("jd_hash", sa.String(length=64), nullable=False),
        sa.Column("skills_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "bundle_generation_jobs",
        sa.Column("id", sa.String(length=160), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("role", sa.String(length=256), nullable=True),
        sa.Column("skill", sa.String(length=128), nullable=False),
        sa.Column("topic", sa.String(length=128), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bundle_id", sa.String(length=128), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("claim_token", sa.String(length=64), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','processing','done','failed','skipped')",
            name="ck_bundle_generation_jobs_status",
        ),
    )
    op.create_index(
        "ix_bundle_generation_jobs_session_id",
        "bundle_generation_jobs",
        ["session_id"],
    )
    op.create_index(
        "ix_bundle_generation_jobs_status",
        "bundle_generation_jobs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_bundle_generation_jobs_status", table_name="bundle_generation_jobs")
    op.drop_index("ix_bundle_generation_jobs_session_id", table_name="bundle_generation_jobs")
    op.drop_table("bundle_generation_jobs")

    op.drop_table("role_skill_cache")

    op.drop_index("ix_llm_usage_events_purpose", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_created_at", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")

    with op.batch_alter_table("question_bundle_versions") as batch_op:
        batch_op.drop_constraint("ck_bundle_versions_status", type_="check")
        batch_op.create_check_constraint(
            "ck_bundle_versions_status",
            _OLD_BUNDLE_STATUS_CHECK,
        )
