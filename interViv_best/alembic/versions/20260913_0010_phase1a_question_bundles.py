"""Phase 1A: immutable question bundles, review decisions, status audit.

Revision ID: 20260913_0010
Revises: 20260908_0009

Additive only: four new tables, no changes to existing tables, rounds, or
reports. Existing question flows do not read these tables unless
``REVIEWED_BUNDLES_ONLY=1`` (default off).

Rollback: ``alembic downgrade 20260908_0009`` drops the four tables. That
discards imported bundle content (recoverable from the canonical YAML under
``data/question_bundles/``) and any recorded review decisions / audit rows
(NOT recoverable — they are human evidence, so export
``bundle_review_decisions`` and ``bundle_status_audit`` before downgrading a
database that holds real reviews). No existing row is touched either way.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260913_0010"
down_revision = "20260908_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "question_bundles",
        sa.Column("bundle_id", sa.String(128), primary_key=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("skill", sa.String(64), nullable=False),
        sa.Column("topic", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_question_bundles_skill", "question_bundles", ["skill"])

    op.create_table(
        "question_bundle_versions",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("bundle_id", sa.String(128), sa.ForeignKey("question_bundles.bundle_id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.String(16), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("attribution_json", sa.JSON(), nullable=False),
        sa.Column("author_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("bundle_id", "version", name="uq_bundle_versions_bundle_version"),
        sa.UniqueConstraint("bundle_id", "content_hash", name="uq_bundle_versions_bundle_hash"),
        sa.CheckConstraint("version >= 1", name="ck_bundle_versions_version_positive"),
        sa.CheckConstraint(
            "status IN ('draft','in_review','reviewed','rejected','retired')",
            name="ck_bundle_versions_status",
        ),
    )
    op.create_index("ix_question_bundle_versions_bundle_id", "question_bundle_versions", ["bundle_id"])

    op.create_table(
        "bundle_review_decisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("version_id", sa.String(160), sa.ForeignKey("question_bundle_versions.id"), nullable=False),
        sa.Column("bundle_id", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("reviewer_id", sa.String(128), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("checklist_json", sa.JSON(), nullable=False),
        sa.Column("reasons", sa.Text(), nullable=False),
        sa.Column("calibration_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("version_id", "reviewer_id", name="uq_bundle_review_version_reviewer"),
        sa.CheckConstraint(
            "decision IN ('approve','reject','adjudicate_approve','adjudicate_reject')",
            name="ck_bundle_review_decision",
        ),
    )
    op.create_index("ix_bundle_review_decisions_version_id", "bundle_review_decisions", ["version_id"])

    op.create_table(
        "bundle_status_audit",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("version_id", sa.String(160), sa.ForeignKey("question_bundle_versions.id"), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=True),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bundle_status_audit_version_id", "bundle_status_audit", ["version_id"])


def downgrade():
    op.drop_index("ix_bundle_status_audit_version_id", table_name="bundle_status_audit")
    op.drop_table("bundle_status_audit")
    op.drop_index("ix_bundle_review_decisions_version_id", table_name="bundle_review_decisions")
    op.drop_table("bundle_review_decisions")
    op.drop_index("ix_question_bundle_versions_bundle_id", table_name="question_bundle_versions")
    op.drop_table("question_bundle_versions")
    op.drop_index("ix_question_bundles_skill", table_name="question_bundles")
    op.drop_table("question_bundles")
