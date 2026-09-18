"""Phase 4A: teaching exposures and assessment-eligibility fields.

Revision ID: 20260917_0014
Revises: 20260915_0013
Create Date: 2026-09-17 23:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260917_0014"
down_revision = "20260915_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teaching_exposures",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("delivery_id", sa.String(length=64), nullable=False),
        sa.Column("content_id", sa.String(length=64), nullable=False),
        sa.Column("owner_key", sa.String(length=96), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("block_id", sa.String(length=64), nullable=True),
        sa.Column("round", sa.Integer(), nullable=True),
        sa.Column("item_type", sa.String(length=32), nullable=True),
        sa.Column("item_id", sa.String(length=255), nullable=True),
        sa.Column("content_kind", sa.String(length=32), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=True),
        sa.Column("concept_topic_scope_json", sa.JSON(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivery_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("delivery_id", name="uq_teaching_exposures_delivery_id"),
    )
    op.create_index("ix_teaching_exposures_owner_key", "teaching_exposures", ["owner_key"])
    op.create_index("ix_teaching_exposures_user_id", "teaching_exposures", ["user_id"])
    op.create_index("ix_teaching_exposures_session_id", "teaching_exposures", ["session_id"])
    op.create_index("ix_teaching_exposures_item_id", "teaching_exposures", ["item_id"])

    op.add_column(
        "rounds",
        sa.Column("assessment_eligibility", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "rounds",
        sa.Column("eligibility_policy_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "rounds",
        sa.Column("eligibility_exclusion_reasons", sa.JSON(), nullable=True),
    )
    op.add_column(
        "rounds",
        sa.Column("eligibility_exposure_ids", sa.JSON(), nullable=True),
    )
    op.add_column("rounds", sa.Column("is_follow_up", sa.Boolean(), nullable=True))
    op.add_column(
        "rounds",
        sa.Column("follow_up_parent_round", sa.Integer(), nullable=True),
    )
    op.add_column(
        "rounds",
        sa.Column("follow_up_identity", sa.String(length=96), nullable=True),
    )

    op.add_column(
        "sessions",
        sa.Column("practice_mode", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("allow_optional_follow_ups", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    # Downgrade drops Phase 4A eligibility/exposure data. Historical
    # assistance_events remain; teaching_exposures and frozen eligibility
    # columns are removed (data loss for 4A-only fields).
    op.drop_column("sessions", "allow_optional_follow_ups")
    op.drop_column("sessions", "practice_mode")
    op.drop_column("rounds", "follow_up_identity")
    op.drop_column("rounds", "follow_up_parent_round")
    op.drop_column("rounds", "is_follow_up")
    op.drop_column("rounds", "eligibility_exposure_ids")
    op.drop_column("rounds", "eligibility_exclusion_reasons")
    op.drop_column("rounds", "eligibility_policy_version")
    op.drop_column("rounds", "assessment_eligibility")
    op.drop_index("ix_teaching_exposures_item_id", table_name="teaching_exposures")
    op.drop_index("ix_teaching_exposures_session_id", table_name="teaching_exposures")
    op.drop_index("ix_teaching_exposures_user_id", table_name="teaching_exposures")
    op.drop_index("ix_teaching_exposures_owner_key", table_name="teaching_exposures")
    op.drop_table("teaching_exposures")
