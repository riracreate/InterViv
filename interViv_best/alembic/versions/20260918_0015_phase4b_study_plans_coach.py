"""Phase 4B: study plans and coach conversations.

Revision ID: 20260918_0015
Revises: 20260917_0014
Create Date: 2026-09-18 08:55:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260918_0015"
down_revision = "20260917_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "study_plans",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("plan_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("scope_key", sa.String(length=96), nullable=False),
        sa.Column("role_id", sa.String(length=64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plan_id", "version", name="uq_study_plans_plan_version"),
    )
    op.create_index("ix_study_plans_plan_id", "study_plans", ["plan_id"])
    op.create_index("ix_study_plans_user_id", "study_plans", ["user_id"])
    op.create_index("ix_study_plans_scope_key", "study_plans", ["scope_key"])
    op.create_index(
        "ix_study_plans_user_scope_active",
        "study_plans",
        ["user_id", "scope_key", "is_active"],
    )

    op.create_table(
        "coach_conversations",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("owner_key", sa.String(length=96), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("conversation_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_coach_conversations_owner_key", "coach_conversations", ["owner_key"])
    op.create_index("ix_coach_conversations_user_id", "coach_conversations", ["user_id"])

    # Store-level uniqueness for follow-up parent (nullable → multiple NULLs ok).
    op.create_index(
        "uq_rounds_session_follow_up_parent",
        "rounds",
        ["session_id", "follow_up_parent_round"],
        unique=True,
        sqlite_where=sa.text("is_follow_up IS 1 AND follow_up_parent_round IS NOT NULL"),
        postgresql_where=sa.text("is_follow_up IS TRUE AND follow_up_parent_round IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_rounds_session_follow_up_parent", table_name="rounds")
    op.drop_index("ix_coach_conversations_user_id", table_name="coach_conversations")
    op.drop_index("ix_coach_conversations_owner_key", table_name="coach_conversations")
    op.drop_table("coach_conversations")
    op.drop_index("ix_study_plans_user_scope_active", table_name="study_plans")
    op.drop_index("ix_study_plans_scope_key", table_name="study_plans")
    op.drop_index("ix_study_plans_user_id", table_name="study_plans")
    op.drop_index("ix_study_plans_plan_id", table_name="study_plans")
    op.drop_table("study_plans")
