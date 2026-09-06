"""Ticket D: jobs_cache + jobs_search_cache for Adzuna explorer.

Revision ID: 20260907_0003
Revises: 20260907_0002
Create Date: 2026-09-07 14:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0003"
down_revision = "20260907_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("redirect_url", sa.String(length=1024), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "external_id", name="uq_jobs_cache_provider_external"),
    )
    op.create_table(
        "jobs_search_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("results_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("query_hash", name="uq_jobs_search_cache_query_hash"),
    )
    op.create_index("ix_jobs_search_cache_query_hash", "jobs_search_cache", ["query_hash"])


def downgrade() -> None:
    op.drop_index("ix_jobs_search_cache_query_hash", table_name="jobs_search_cache")
    op.drop_table("jobs_search_cache")
    op.drop_table("jobs_cache")
