"""Phase D: shared target context and learning collections.

Revision ID: 20260907_0006
Revises: 20260907_0005
Create Date: 2026-09-07 19:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0006"
down_revision = "20260907_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0. Round assistance marking (nullable: legacy rounds read as unassisted).
    op.add_column("rounds", sa.Column("assisted", sa.Boolean(), nullable=True))
    op.add_column("rounds", sa.Column("assistance_kinds", sa.JSON(), nullable=True))

    # 1. Shared target context (one row per user).
    op.create_table(
        "target_contexts",
        sa.Column("user_id", sa.String(length=64), primary_key=True),
        sa.Column("company_id", sa.String(length=64), nullable=True),
        sa.Column("role_id", sa.String(length=64), nullable=True),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("jd_source", sa.String(length=16), nullable=True),
        sa.Column("jd_text", sa.Text(), nullable=True),
        sa.Column("resume_ref", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. Retry sets (persisted practice sets from missed topics).
    op.create_table(
        "retry_sets",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_retry_sets_user_id", "retry_sets", ["user_id"])

    # 3. Bookmarks (user + item identity).
    op.create_table(
        "bookmarks",
        sa.Column("user_id", sa.String(length=64), primary_key=True),
        sa.Column("item_type", sa.String(length=16), primary_key=True),
        sa.Column("item_id", sa.String(length=64), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 4. Assistance events (append-only hint/solution-use metadata).
    op.create_table(
        "assistance_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("item_type", sa.String(length=16), nullable=False),
        sa.Column("item_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("round", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistance_events_user_id", "assistance_events", ["user_id"]
    )
    op.create_index(
        "ix_assistance_events_item_id", "assistance_events", ["item_id"]
    )


def downgrade() -> None:
    op.drop_column("rounds", "assistance_kinds")
    op.drop_column("rounds", "assisted")
    op.drop_index("ix_assistance_events_item_id",
                  table_name="assistance_events")
    op.drop_index("ix_assistance_events_user_id",
                  table_name="assistance_events")
    op.drop_table("assistance_events")
    op.drop_table("bookmarks")
    op.drop_index("ix_retry_sets_user_id", table_name="retry_sets")
    op.drop_table("retry_sets")
    op.drop_table("target_contexts")
