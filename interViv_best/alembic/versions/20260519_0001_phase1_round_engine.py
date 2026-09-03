"""Phase 1 round engine: typed rounds, artifacts, and interview templates."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260519_0001"
down_revision = "20260518_0001"
branch_labels = None
depends_on = None

TECHNICAL_SHORT_ANSWER = "technical_short_answer"


def upgrade() -> None:
    op.create_table(
        "interview_templates",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "template_rounds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("template_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("round_type", sa.String(length=50), nullable=False,
                  server_default=TECHNICAL_SHORT_ANSWER),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["template_id"], ["interview_templates.id"]),
        sa.UniqueConstraint("template_id", "position",
                            name="uq_template_rounds_template_position"),
    )
    op.create_index("ix_template_rounds_template_id", "template_rounds", ["template_id"])

    # NOT NULL with a server default fills pre-existing rows on both
    # PostgreSQL and SQLite, so no separate nullable-then-alter dance.
    op.add_column("rounds", sa.Column(
        "round_type", sa.String(length=50), nullable=False,
        server_default=TECHNICAL_SHORT_ANSWER,
    ))
    op.add_column("rounds", sa.Column(
        "artifact_json", sa.JSON(), nullable=False, server_default="{}",
    ))
    op.add_column("rounds", sa.Column(
        "config_json", sa.JSON(), nullable=False, server_default="{}",
    ))
    # SQLite cannot add a constraint of any kind to an existing table, so the
    # FK ships only where the dialect supports it. SQLite deployments rely on
    # the ORM relationship, not DDL enforcement (FK pragma is off by default).
    if op.get_bind().dialect.name == "sqlite":
        op.add_column("sessions", sa.Column(
            "template_id", sa.String(length=64), nullable=True,
        ))
    else:
        op.add_column("sessions", sa.Column(
            "template_id", sa.String(length=64),
            sa.ForeignKey("interview_templates.id"), nullable=True,
        ))

    # Explicit backfill: belt and braces behind the server defaults, and the
    # thing the standalone null-count check verifies.
    op.execute(
        "UPDATE rounds SET round_type = '%s' WHERE round_type IS NULL"
        % TECHNICAL_SHORT_ANSWER
    )
    op.execute("UPDATE rounds SET artifact_json = '{}' WHERE artifact_json IS NULL")
    op.execute("UPDATE rounds SET config_json = '{}' WHERE config_json IS NULL")


def downgrade() -> None:
    op.drop_column("sessions", "template_id")
    op.drop_column("rounds", "config_json")
    op.drop_column("rounds", "artifact_json")
    op.drop_column("rounds", "round_type")
    op.drop_index("ix_template_rounds_template_id", table_name="template_rounds")
    op.drop_table("template_rounds")
    op.drop_table("interview_templates")
