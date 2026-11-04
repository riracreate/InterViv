"""Track 4: learning_events and roadmap_progress tables.

Revision ID: 20260906_0001
Revises: 20260520_0001
Create Date: 2026-09-06 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260906_0001"
down_revision = "20260520_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("skill", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_learning_events_user_id", "learning_events", ["user_id"])
    op.create_index("ix_learning_events_session_id", "learning_events", ["session_id"])
    op.create_index("ix_learning_events_skill", "learning_events", ["skill"])
    op.create_index("ix_learning_events_event_type", "learning_events", ["event_type"])

    op.create_table(
        "roadmap_progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("role_id", sa.String(length=64), nullable=False),
        sa.Column("plan_days", sa.Integer(), nullable=False),
        sa.Column("completed_blocks", sa.JSON(), nullable=False),
        sa.Column("blocks_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "role_id", "plan_days", name="uq_roadmap_progress_user_role_days"
        ),
        sa.CheckConstraint("plan_days IN (7, 14, 30)", name="ck_roadmap_progress_plan_days"),
    )
    op.create_index("ix_roadmap_progress_user_id", "roadmap_progress", ["user_id"])
    op.create_index("ix_roadmap_progress_role_id", "roadmap_progress", ["role_id"])


def downgrade() -> None:
    op.drop_index("ix_roadmap_progress_role_id", table_name="roadmap_progress")
    op.drop_index("ix_roadmap_progress_user_id", table_name="roadmap_progress")
    op.drop_table("roadmap_progress")
    op.drop_index("ix_learning_events_event_type", table_name="learning_events")
    op.drop_index("ix_learning_events_skill", table_name="learning_events")
    op.drop_index("ix_learning_events_session_id", table_name="learning_events")
    op.drop_index("ix_learning_events_user_id", table_name="learning_events")
    op.drop_table("learning_events")
