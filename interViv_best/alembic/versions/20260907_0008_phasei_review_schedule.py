"""Phase I: spaced-review schedule state over notebook misses.

Revision ID: 20260907_0008
Revises: 20260907_0007
Create Date: 2026-09-07 21:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0008"
down_revision = "20260907_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_schedules",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("item_type", sa.String(length=16), nullable=False),
        sa.Column("item_id", sa.String(length=64), nullable=False),
        sa.Column("skill", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("source_session_id", sa.String(length=64), nullable=True),
        sa.Column("source_round", sa.Integer(), nullable=True),
        sa.Column("originating_assisted", sa.Boolean(), nullable=True),
        sa.Column("miss_reason", sa.String(length=120), nullable=True),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("interval_index", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_outcome", sa.String(length=16), nullable=True),
        sa.Column("last_review_assisted", sa.Boolean(), nullable=True),
        sa.Column("review_available", sa.Boolean(), nullable=False),
        sa.Column("unavailable_reason", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "item_type", "item_id",
            name="uq_review_schedules_user_item",
        ),
    )
    op.create_index(
        "ix_review_schedules_user_id",
        "review_schedules",
        ["user_id"],
    )
    op.create_index(
        "ix_review_schedules_user_due",
        "review_schedules",
        ["user_id", "due_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_schedules_user_due", table_name="review_schedules")
    op.drop_index("ix_review_schedules_user_id", table_name="review_schedules")
    op.drop_table("review_schedules")
