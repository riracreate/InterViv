"""Two-column resume reconstruction and skill-evidence flags (ATS, advisory)."""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF, already a dependency
import pytest

from modules.ats_scorer import score_ats, unsubstantiated_skills
from modules.resume_parser import analyze_resume, analyze_resume_text

PAGE_W, PAGE_H = 612, 792

LEFT = [
    "SKILLS", "Python, Java, SQL", "Docker, Kubernetes", "React, Git", "",
    "EDUCATION", "B.Tech Computer Science", "Example University", "2019 - 2023", "",
    "CERTIFICATIONS", "Cloud Practitioner", "", "LANGUAGES", "English, Hindi",
]
RIGHT = [
    "EXPERIENCE", "Software Engineer, Acme Corp", "- Built REST services in Python",
    "- Cut query latency 40% with SQL indexes", "- Shipped React dashboards",
    "- Led migration of 12 services", "- Mentored 3 interns on Git workflow", "",
    "PROJECTS", "Interview Coach", "- Python backend with Docker deploy",
    "- Added caching that halved p95 latency", "- Wrote 200 unit tests",
    "", "Job Tracker", "- React frontend and Java API", "- Deployed for 50 users",
]


def _write(path: Path, place) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    place(page)
    doc.save(str(path))
    doc.close()
    return path


def _two_column(page) -> None:
    page.insert_text((230, 50), "JANE DOE", fontsize=16)
    page.insert_text((200, 68), "jane@example.com  |  github.com/jane", fontsize=9)
    for i, line in enumerate(LEFT):
        page.insert_text((40, 110 + i * 16), line, fontsize=10)
    for i, line in enumerate(RIGHT):
        page.insert_text((330, 110 + i * 16), line, fontsize=10)


def _single_with_dates(page) -> None:
    y = 50
    page.insert_text((40, y), "JANE DOE  jane@example.com", fontsize=14)
    y += 30
    rows = [
        ("EXPERIENCE", None),
        ("Software Engineer, Acme Corp", "Jan 2022 - Present"),
        ("- Built REST services in Python that handle payments for merchants", None),
        ("- Cut query latency 40% with SQL indexes across the reporting stack", None),
        ("Intern, Beta Labs", "May 2021 - Aug 2021"),
        ("- Shipped React dashboards used by the operations team every day", None),
        ("Teaching Assistant, Example University", "Aug 2020 - May 2021"),
        ("- Ran weekly Java lab sessions for forty second-year students", None),
        ("EDUCATION", None),
        ("B.Tech Computer Science, Example University", "2019 - 2023"),
        ("SKILLS", None),
        ("Python, Java, SQL, Docker, Kubernetes, React, Git", None),
    ]
    for left, date in rows * 2:
        page.insert_text((40, y), left, fontsize=10)
        if date:
            page.insert_text((470 + (90 - len(date) * 4.5), y), date, fontsize=10)
        y += 16


def _single_plain(page) -> None:
    lines = ["JANE DOE jane@example.com", "EXPERIENCE"] + [
        f"- Built and operated Python services that processed {n} thousand requests per day" for n in range(1, 16)
    ] + ["EDUCATION", "B.Tech Computer Science, Example University", "SKILLS", "Python, SQL, Docker"]
    for i, line in enumerate(lines):
        page.insert_text((40, 50 + i * 16), line, fontsize=10)


def test_two_column_resume_is_reconstructed_column_by_column(tmp_path: Path) -> None:
    analysis = analyze_resume(_write(tmp_path / "two.pdf", _two_column))
    assert analysis["layout"] == "two_column"
    assert analysis["layout_checked"] is True
    assert analysis["sections"]["experience"] and analysis["sections"]["skills"]
    # Experience bullets come out whole, not interleaved with the left column.
    assert "Cut query latency 40% with SQL indexes" in analysis["experience_bullets"]


def test_two_column_text_order(tmp_path: Path) -> None:
    from modules.resume_parser import _extract_text_and_layout

    text, layout = _extract_text_and_layout(str(_write(tmp_path / "two.pdf", _two_column)))
    assert layout == "two_column"
    assert text.index("JANE DOE") < text.index("SKILLS") < text.index("EDUCATION") < text.index("EXPERIENCE")
    assert "Python, Java, SQL" in text and "Docker, Kubernetes" in text
    assert text.index("EXPERIENCE") < text.index("PROJECTS")


@pytest.mark.parametrize("builder", [_single_with_dates, _single_plain])
def test_single_column_resumes_are_not_split(tmp_path: Path, builder) -> None:
    analysis = analyze_resume(_write(tmp_path / "one.pdf", builder))
    assert analysis["layout"] == "single_column"
    assert analysis["layout_checked"] is True


def test_pasted_text_layout_stays_unchecked() -> None:
    analysis = analyze_resume_text("EXPERIENCE\n- Built Python services\nSKILLS\nPython")
    assert analysis["layout_checked"] is False
    assert analysis["layout"] is None
    result = score_ats(analysis=analysis, must_have=["Python"])
    assert "extract_layout_unchecked" in result["flags"]


def test_unsubstantiated_skill_is_flagged_without_changing_score(tmp_path: Path) -> None:
    analysis = analyze_resume(_write(tmp_path / "two.pdf", _two_column))
    # Kubernetes appears only in the Skills column; Python, Docker, React, Java, SQL, Git are used.
    assert set(analysis["evidence_skills"]) >= {"Python", "Docker", "React", "Java", "SQL", "Git"}
    assert "Kubernetes" not in analysis["evidence_skills"]
    result = score_ats(analysis=analysis, must_have=["Python", "Kubernetes", "Docker"])
    assert result["unsubstantiated_skills"] == ["Kubernetes"]
    assert "two_column_reconstructed" in result["flags"]
    without_evidence = {**analysis, "evidence_sections_found": False, "evidence_skills": None}
    assert score_ats(analysis=without_evidence, must_have=["Python", "Kubernetes", "Docker"])["total"] == result["total"]


def test_unsubstantiated_is_unknown_without_experience_or_projects() -> None:
    analysis = analyze_resume_text("SKILLS\nPython, Kubernetes\nEDUCATION\nB.Tech")
    assert analysis["evidence_sections_found"] is False
    assert unsubstantiated_skills(analysis, ["Python"]) is None
