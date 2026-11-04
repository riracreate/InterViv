"""Phase 3A: narration-jobs outbox.

Revision ID: 20260914_0012
Revises: 20260914_0011
"""

from alembic import op
import sqlalchemy as sa


revision = "20260914_0012"
down_revision = "20260914_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "narration_jobs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("feedback_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_digest", sa.String(64), nullable=True),
        sa.Column("skill", sa.String(255), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("artifact_json", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("claim_token", sa.String(64), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','processing','done','failed','skipped')",
            name="ck_narration_jobs_status",
        ),
    )
    for column in ("user_id", "session_id", "status"):
        op.create_index(f"ix_narration_jobs_{column}", "narration_jobs", [column])


def downgrade() -> None:
    for column in ("status", "session_id", "user_id"):
        op.drop_index(f"ix_narration_jobs_{column}", table_name="narration_jobs")
    op.drop_table("narration_jobs")
