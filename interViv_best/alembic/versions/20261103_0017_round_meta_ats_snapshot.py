"""Overhaul: persist ATS snapshots, private round metadata and ML results.

Additive only. Existing rows keep NULL in every new column; reads fall back
to legacy ``config_json`` keys where they were written before this revision.
ATS snapshots discarded before this revision cannot be reconstructed.

Revision ID: 20261103_0017
Revises: 20260918_0016
Create Date: 2026-11-03 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261103_0017"
down_revision = "20260918_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("ats_snapshot", sa.JSON(), nullable=True))
    op.add_column("rounds", sa.Column("private_meta_json", sa.JSON(), nullable=True))
    op.add_column("ml_primitives_attempts", sa.Column("score", sa.Float(), nullable=True))
    op.add_column("ml_primitives_attempts", sa.Column("result_json", sa.JSON(), nullable=True))
    op.add_column(
        "ml_primitives_attempts",
        sa.Column("grader_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "ml_primitives_attempts",
        sa.Column("execution_status", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    # Plain drop_column (not batch): a batch rebuild of ``candidates`` would
    # DROP TABLE under live foreign keys on SQLite.
    op.drop_column("ml_primitives_attempts", "execution_status")
    op.drop_column("ml_primitives_attempts", "grader_version")
    op.drop_column("ml_primitives_attempts", "result_json")
    op.drop_column("ml_primitives_attempts", "score")
    op.drop_column("rounds", "private_meta_json")
    op.drop_column("candidates", "ats_snapshot")
