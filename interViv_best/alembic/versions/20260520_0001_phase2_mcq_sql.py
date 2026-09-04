"""Phase 2 round engine: MCQ questions, SQL problems, test cases, and round lifecycle columns.

Revision ID: 20260520_0001
Revises: 20260519_0001
Create Date: 2026-09-04 08:50:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260520_0001"
down_revision = "20260519_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 1. mcq_questions table
    op.create_table(
        "mcq_questions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("sub_domain", sa.String(length=100), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("options_json", sa.JSON(), nullable=False),
        sa.Column("correct_option_ids", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("negative_marking", sa.Float(), nullable=False, server_default="0.0"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.UniqueConstraint("stem", name="uq_mcq_questions_stem"),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_mcq_questions_difficulty",
        ),
        sa.CheckConstraint(
            "negative_marking >= 0.0 AND negative_marking <= 1.0",
            name="ck_mcq_questions_negative_marking",
        ),
    )
    op.create_index("ix_mcq_questions_skill_id", "mcq_questions", ["skill_id"])
    op.create_index("ix_mcq_questions_difficulty", "mcq_questions", ["difficulty"])
    op.create_index("ix_mcq_questions_sub_domain", "mcq_questions", ["sub_domain"])

    # 2. sql_problems table
    op.create_table(
        "sql_problems",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("schema_ddl", sa.Text(), nullable=False),
        sa.Column("reference_query", sa.Text(), nullable=False),
        sa.Column("checks_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("prompt", name="uq_sql_problems_prompt"),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_sql_problems_difficulty",
        ),
    )
    op.create_index("ix_sql_problems_difficulty", "sql_problems", ["difficulty"])

    # 3. sql_problem_cases table
    op.create_table(
        "sql_problem_cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("problem_id", sa.String(length=64), nullable=False),
        sa.Column("case_type", sa.String(length=30), nullable=False),
        sa.Column("seed_data", sa.Text(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["problem_id"], ["sql_problems.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("problem_id", "sort_order", name="uq_sql_problem_cases_order"),
        sa.CheckConstraint(
            "case_type IN ('visible_sample', 'hidden_case')",
            name="ck_sql_problem_cases_type",
        ),
    )
    op.create_index("ix_sql_problem_cases_problem_id", "sql_problem_cases", ["problem_id"])

    # 4. Lifecycle columns on rounds table (SQLite batch compatible)
    with op.batch_alter_table("rounds") as batch_op:
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default="submitted",
            )
        )
        batch_op.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))

    # Backfill lifecycle on historical rounds:
    # A. If already answered or scored: status='submitted', started_at=created_at, submitted_at=created_at
    op.execute(
        """
        UPDATE rounds
        SET started_at = created_at,
            submitted_at = created_at,
            status = 'submitted'
        WHERE (answer_text IS NOT NULL AND answer_text != '') OR final_score IS NOT NULL
        """
    )

    # B. If unanswered and parent session is completed: status='expired', started_at=created_at
    op.execute(
        """
        UPDATE rounds
        SET started_at = created_at,
            status = 'expired'
        WHERE (answer_text IS NULL OR answer_text = '')
          AND final_score IS NULL
          AND session_id IN (SELECT id FROM sessions WHERE status = 'completed')
        """
    )

    # C. If unanswered and parent session is active: status='in_progress', started_at=created_at
    op.execute(
        """
        UPDATE rounds
        SET started_at = created_at,
            status = 'in_progress'
        WHERE (answer_text IS NULL OR answer_text = '')
          AND final_score IS NULL
          AND session_id IN (SELECT id FROM sessions WHERE status != 'completed')
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("rounds") as batch_op:
        batch_op.drop_column("submitted_at")
        batch_op.drop_column("status")
        batch_op.drop_column("expires_at")
        batch_op.drop_column("started_at")

    op.drop_index("ix_sql_problem_cases_problem_id", table_name="sql_problem_cases")
    op.drop_table("sql_problem_cases")

    op.drop_index("ix_sql_problems_difficulty", table_name="sql_problems")
    op.drop_table("sql_problems")

    op.drop_index("ix_mcq_questions_sub_domain", table_name="mcq_questions")
    op.drop_index("ix_mcq_questions_difficulty", table_name="mcq_questions")
    op.drop_index("ix_mcq_questions_skill_id", table_name="mcq_questions")
    op.drop_table("mcq_questions")
