"""Offline audit for interViv's curated fallback question bank.

This script does not call an LLM. It validates the structured CSV fallback
used when live question generation is unavailable and prints coverage by
company, role, skill, difficulty, and question type.

Run:
    python scripts/question_audit.py
    python scripts/question_audit.py --json docs/question_audit_report.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.company_graph import get_company_graph  # noqa: E402


REQUIRED_COLUMNS = [
    "company",
    "role",
    "skill",
    "sub_domain",
    "topic",
    "difficulty",
    "question_type",
    "question",
    "ideal_answer",
    "ideal_keywords",
    "followups",
]

VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_QUESTION_TYPES = {
    "conceptual",
    "coding",
    "system_design",
    "behavioral",
    "resume_based",
}


@dataclass
class AuditIssue:
    row: int | None
    severity: str
    message: str


@dataclass
class AuditReport:
    bank_path: str
    total_questions: int
    minimum_expected_questions: int
    schema_ok: bool
    counts: dict[str, dict[str, int]]
    issues: list[AuditIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[AuditIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[AuditIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]


def _split_multi(value: str) -> list[str]:
    raw = str(value or "").replace(",", "|")
    return [item.strip() for item in raw.split("|") if item.strip()]


def _word_count(value: str) -> int:
    return len(str(value or "").split())


def _load_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _company_role_index() -> tuple[set[str], dict[str, set[str]]]:
    graph = get_company_graph()
    company_names = {company.name.lower() for company in graph.list_companies()}
    roles_by_company: dict[str, set[str]] = defaultdict(set)
    for company in graph.list_companies():
        for role in company.roles:
            roles_by_company[company.name.lower()].add(role.title.lower())
    return company_names, roles_by_company


def audit_question_bank(path: Path, minimum_questions: int = 50) -> AuditReport:
    issues: list[AuditIssue] = []
    if not path.exists():
        return AuditReport(
            bank_path=str(path),
            total_questions=0,
            minimum_expected_questions=minimum_questions,
            schema_ok=False,
            counts={},
            issues=[AuditIssue(None, "error", f"Question bank not found: {path}")],
        )

    rows, columns = _load_rows(path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns]
    extra_columns = [column for column in columns if column not in REQUIRED_COLUMNS]
    if missing_columns:
        issues.append(
            AuditIssue(None, "error", f"Missing required columns: {', '.join(missing_columns)}")
        )
    if extra_columns:
        issues.append(
            AuditIssue(None, "warning", f"Unexpected columns present: {', '.join(extra_columns)}")
        )
    if len(rows) < minimum_questions:
        issues.append(
            AuditIssue(
                None,
                "error",
                f"Only {len(rows)} questions found; expected at least {minimum_questions}.",
            )
        )

    company_names, roles_by_company = _company_role_index()
    seen_questions: dict[str, int] = {}
    counters = {
        "company": Counter(),
        "role": Counter(),
        "skill": Counter(),
        "difficulty": Counter(),
        "question_type": Counter(),
        "company_skill": Counter(),
    }

    for index, row in enumerate(rows, start=2):
        normalized = {key: str(row.get(key, "") or "").strip() for key in REQUIRED_COLUMNS}

        for column, value in normalized.items():
            if not value:
                issues.append(AuditIssue(index, "error", f"Blank value for {column}."))

        question_key = normalized["question"].lower()
        if question_key:
            if question_key in seen_questions:
                issues.append(
                    AuditIssue(
                        index,
                        "error",
                        f"Duplicate question also appears on row {seen_questions[question_key]}.",
                    )
                )
            else:
                seen_questions[question_key] = index

        difficulty = normalized["difficulty"].lower()
        if difficulty and difficulty not in VALID_DIFFICULTIES:
            issues.append(AuditIssue(index, "error", f"Invalid difficulty: {difficulty}"))

        question_type = normalized["question_type"].lower()
        if question_type and question_type not in VALID_QUESTION_TYPES:
            issues.append(AuditIssue(index, "error", f"Invalid question_type: {question_type}"))

        keywords = _split_multi(normalized["ideal_keywords"])
        if len(keywords) < 4:
            issues.append(
                AuditIssue(index, "warning", "Fewer than 4 ideal keywords; scoring may be thin.")
            )

        followups = _split_multi(normalized["followups"])
        if len(followups) < 2:
            issues.append(AuditIssue(index, "warning", "Fewer than 2 follow-up prompts."))

        if _word_count(normalized["ideal_answer"]) < 20:
            issues.append(
                AuditIssue(index, "warning", "Ideal answer is under 20 words; reference may be weak.")
            )

        company = normalized["company"]
        role = normalized["role"]
        skill = normalized["skill"]
        if company.lower() not in company_names:
            issues.append(AuditIssue(index, "warning", f"Company not in company graph: {company}"))
        elif role.lower() not in roles_by_company.get(company.lower(), set()):
            issues.append(
                AuditIssue(
                    index,
                    "warning",
                    f"Role '{role}' is not listed under company graph entry '{company}'.",
                )
            )

        counters["company"][company] += 1
        counters["role"][role] += 1
        counters["skill"][skill] += 1
        counters["difficulty"][difficulty] += 1
        counters["question_type"][question_type] += 1
        counters["company_skill"][f"{company} / {skill}"] += 1

    counts = {
        name: dict(sorted(counter.items()))
        for name, counter in counters.items()
    }
    return AuditReport(
        bank_path=str(path),
        total_questions=len(rows),
        minimum_expected_questions=minimum_questions,
        schema_ok=not missing_columns,
        counts=counts,
        issues=issues,
    )


def _print_report(report: AuditReport) -> None:
    print("Question bank audit")
    print(f"Bank: {report.bank_path}")
    print(f"Questions: {report.total_questions}")
    print(f"Schema OK: {report.schema_ok}")
    print(f"Errors: {len(report.errors)}")
    print(f"Warnings: {len(report.warnings)}")
    print()

    for section in ("company", "skill", "difficulty", "question_type"):
        print(section.replace("_", " ").title())
        for key, value in report.counts.get(section, {}).items():
            print(f"  {key}: {value}")
        print()

    if report.issues:
        print("Issues")
        for issue in report.issues[:80]:
            row = f"row {issue.row}: " if issue.row is not None else ""
            print(f"  [{issue.severity}] {row}{issue.message}")
        if len(report.issues) > 80:
            print(f"  ... {len(report.issues) - 80} more issues")


def _json_ready(report: AuditReport) -> dict[str, Any]:
    payload = asdict(report)
    payload["errors"] = [asdict(issue) for issue in report.errors]
    payload["warnings"] = [asdict(issue) for issue in report.warnings]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bank",
        type=Path,
        default=PROJECT_ROOT / "data" / "fallback_question_bank.csv",
        help="Path to the structured fallback question CSV.",
    )
    parser.add_argument(
        "--min-questions",
        type=int,
        default=50,
        help="Minimum expected curated fallback questions.",
    )
    parser.add_argument("--json", type=Path, help="Optional path to write JSON report.")
    args = parser.parse_args()

    report = audit_question_bank(args.bank, args.min_questions)
    _print_report(report)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(_json_ready(report), indent=2), encoding="utf-8")
        print(f"\nWrote JSON report: {args.json}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
