"""Ticket B: learning_resources curated lecture/solution links.

Revision ID: 20260907_0001
Revises: 20260906_0001
Create Date: 2026-09-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0001"
down_revision = "20260906_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_resources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("skill_id", "url", name="uq_learning_resources_skill_url"),
        sa.CheckConstraint(
            "level IN ('beginner', 'intermediate', 'advanced')",
            name="ck_learning_resources_level",
        ),
        sa.CheckConstraint(
            "source IN ('youtube', 'docs', 'other')",
            name="ck_learning_resources_source",
        ),
    )
    op.create_index("ix_learning_resources_skill_id", "learning_resources", ["skill_id"])
    op.create_index("ix_learning_resources_question_id", "learning_resources", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_learning_resources_question_id", table_name="learning_resources")
    op.drop_index("ix_learning_resources_skill_id", table_name="learning_resources")
    op.drop_table("learning_resources")
