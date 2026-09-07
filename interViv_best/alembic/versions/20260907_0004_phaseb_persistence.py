"""Phase B.1: persist block plans, round block identity, presets and drafts.

Revision ID: 20260907_0004
Revises: 20260907_0003
Create Date: 2026-09-07 15:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0004"
down_revision = "20260907_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Session-level block plans (nullable: legacy rows stay valid).
    op.add_column("sessions", sa.Column("round_plan_json", sa.JSON(), nullable=True))
    op.add_column("sessions", sa.Column("round_config_json", sa.JSON(), nullable=True))
    op.add_column("sessions", sa.Column("block_plan_json", sa.JSON(), nullable=True))
    op.add_column("sessions", sa.Column("expanded_plan_json", sa.JSON(), nullable=True))
    op.add_column(
        "sessions",
        sa.Column("allow_unknown_topic_fallback", sa.Boolean(), nullable=True),
    )

    # 2. Per-round block identity (nullable: legacy rounds stay valid).
    op.add_column("rounds", sa.Column("block_id", sa.String(length=64), nullable=True))
    op.add_column("rounds", sa.Column("block_position", sa.Integer(), nullable=True))
    op.add_column("rounds", sa.Column("block_category", sa.String(length=30), nullable=True))
    op.add_column("rounds", sa.Column("block_index", sa.Integer(), nullable=True))
    op.add_column("rounds", sa.Column("block_total", sa.Integer(), nullable=True))

    # 3. Practice presets (user-scoped, versioned).
    op.create_table(
        "practice_presets",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("blocks_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_practice_presets_user_id", "practice_presets", ["user_id"])

    # 4. Builder drafts (one autosaved draft per user).
    op.create_table(
        "builder_drafts",
        sa.Column("user_id", sa.String(length=64), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("blocks_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 5. Answer drafts (keyed by session + round).
    op.create_table(
        "answer_drafts",
        sa.Column("session_id", sa.String(length=64), primary_key=True),
        sa.Column("round_number", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("draft_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_answer_drafts_user_id", "answer_drafts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_answer_drafts_user_id", table_name="answer_drafts")
    op.drop_table("answer_drafts")
    op.drop_table("builder_drafts")
    op.drop_index("ix_practice_presets_user_id", table_name="practice_presets")
    op.drop_table("practice_presets")

    op.drop_column("rounds", "block_total")
    op.drop_column("rounds", "block_index")
    op.drop_column("rounds", "block_category")
    op.drop_column("rounds", "block_position")
    op.drop_column("rounds", "block_id")

    op.drop_column("sessions", "allow_unknown_topic_fallback")
    op.drop_column("sessions", "expanded_plan_json")
    op.drop_column("sessions", "block_plan_json")
    op.drop_column("sessions", "round_config_json")
    op.drop_column("sessions", "round_plan_json")
