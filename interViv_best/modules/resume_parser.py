import hashlib
import re


TECH_SKILLS = [
    # Languages
    ("python", "Python"), ("javascript", "JavaScript"), ("java", "Java"),
    ("c++", "C++"), ("cpp", "C++"), ("c#", "C#"), ("c sharp", "C#"),
    ("go", "Go"), ("golang", "Go"), ("rust", "Rust"), ("ruby", "Ruby"),
    ("php", "PHP"), ("typescript", "TypeScript"), ("scala", "Scala"),
    ("kotlin", "Kotlin"), ("swift", "Swift"), ("objective-c", "Objective-C"),
    ("perl", "Perl"), ("r programming", "R"), ("r language", "R"),
    ("rstudio", "R"),

    # Web technologies
    ("html", "HTML"), ("css", "CSS"), ("react", "React"), ("react.js", "React"),
    ("reactjs", "React"), ("vue", "Vue"), ("vue.js", "Vue"), ("vuejs", "Vue"),
    ("angular", "Angular"), ("node.js", "Node.js"), ("nodejs", "Node.js"),
    ("express", "Express"), ("django", "Django"), ("flask", "Flask"),
    ("fastapi", "FastAPI"), ("spring", "Spring"), ("spring boot", "Spring"),
    ("asp.net", "ASP.NET"), ("rails", "Rails"),

    # Databases
    ("sql", "SQL"), ("mongodb", "MongoDB"), ("mongo db", "MongoDB"),
    ("postgresql", "PostgreSQL"), ("postgres", "PostgreSQL"), ("mysql", "MySQL"),
    ("redis", "Redis"), ("elasticsearch", "Elasticsearch"),
    ("cassandra", "Cassandra"), ("dynamodb", "DynamoDB"), ("oracle", "Oracle"),
    ("firebase", "Firebase"),
    ("dbms", "DBMS"), ("database", "DBMS"),

    # Cloud and DevOps
    ("aws", "AWS"), ("azure", "Azure"), ("gcp", "GCP"),
    ("google cloud", "GCP"), ("docker", "Docker"), ("kubernetes", "Kubernetes"),
    ("k8s", "k8s"), ("jenkins", "Jenkins"), ("gitlab", "GitLab"),
    ("github actions", "GitHub Actions"), ("github", "GitHub"),
    ("terraform", "Terraform"), ("ansible", "Ansible"), ("ci/cd", "CI/CD"),
    ("cicd", "CI/CD"),

    # Data and AI
    ("machine learning", "Machine Learning"), ("deep learning", "Deep Learning"),
    ("tensorflow", "TensorFlow"), ("pytorch", "PyTorch"),
    ("scikit-learn", "scikit-learn"), ("sklearn", "scikit-learn"),
    ("pandas", "Pandas"), ("numpy", "NumPy"), ("spark", "Spark"),
    ("hadoop", "Hadoop"), ("nlp", "NLP"), ("computer vision", "Computer Vision"),
    ("opencv", "OpenCV"),

    # CS fundamentals (Phase 2 / role graph)
    ("dsa", "DSA"), ("data structures", "DSA"), ("algorithms", "DSA"),
    ("oop", "OOP"), ("object oriented", "OOP"), ("object-oriented", "OOP"),
    ("operating systems", "Operating Systems"), ("operating system", "Operating Systems"),
    ("computer networks", "Computer Networks"), ("computer network", "Computer Networks"),
    ("system design", "System Design"),
    ("hr", "HR/Professional Judgment"), ("behavioral", "HR/Professional Judgment"),

    # Other
    ("git", "Git"), ("linux", "Linux"), ("windows", "Windows"),
    ("macos", "macOS"), ("rest api", "REST"), ("rest", "REST"),
    ("graphql", "GraphQL"), ("soap", "SOAP"), ("microservices", "Microservices"),
    ("agile", "Agile"), ("scrum", "Scrum"),
    ("jira", "Jira"),
]

SECTION_PATTERNS = {
    "contact": re.compile(
        r"(?im)^(?:contact|email|phone|linkedin|github)\b|(?:[\w.+-]+@[\w.-]+\.\w{2,})"
    ),
    "experience": re.compile(
        r"(?im)^(?:experience|work experience|employment|professional experience)\b"
    ),
    "education": re.compile(r"(?im)^(?:education|academics|academic background)\b"),
    "skills": re.compile(
        r"(?im)^(?:skills|technical skills|technologies|tech stack)\b"
    ),
}

SECTION_HEADER_ORDER = ("contact", "experience", "education", "skills")
BULLET_RE = re.compile(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+(.+)$")

# Header lines that start a block, used to tell where a skill is evidenced.
# Kept separate from SECTION_PATTERNS so the section-completeness payload is unchanged.
BLOCK_HEADER_RE = re.compile(
    r"(?im)^\s*(?P<name>work experience|professional experience|experience|employment|internships?|"
    r"personal projects|academic projects|key projects|projects|technical skills|skills|technologies|"
    r"tech stack|education|academics|certifications?|achievements|awards|summary|profile|objective|"
    r"publications|leadership|activities|interests|languages)\s*:?\s*$"
)
EVIDENCE_BLOCKS = ("experience", "employment", "internship", "project")

# Two-column detection (pdfplumber word boxes). A vertical gap counts as a
# column gutter when it sits in the middle of the page, is wide enough, is
# crossed by few text lines, and has text on both sides over a tall region.
GUTTER_SEARCH = (0.28, 0.72)
GUTTER_MIN_WIDTH = 0.02
GUTTER_MAX_CROSSING_LINES = 0.05
GUTTER_MIN_SIDE_HEIGHT = 0.45
GUTTER_MIN_WORDS = 40
GUTTER_MIN_SIDE_CHARS = 0.15
GUTTER_HEADER_ZONE = 0.15


def _extract_with_pymupdf(pdf_path):
    try:
        import fitz
    except ImportError:
        return ""

    try:
        text_parts = []
        with fitz.open(pdf_path) as document:
            for page in document:
                text_parts.append(page.get_text("text") or "")
        return "\n".join(text_parts)
    except Exception:
        return ""


def _text_lines(words):
    """Group pdfplumber words into lines by their top coordinate."""
    lines = []
    for word in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - word["top"]) <= 3:
            lines[-1].append(word)
        else:
            lines.append([word])
    return lines


def find_column_split(words, width, height):
    """Return (split_x, columns_top) for a two-column page, or None.

    columns_top is where the side-by-side region starts; text above it (a
    centred name or contact line) is read full width.
    """
    if len(words) < GUTTER_MIN_WORDS or width <= 0:
        return None
    lines = _text_lines(words)
    body_top = min(w["top"] for w in words)
    body_height = max(w["bottom"] for w in words) - body_top
    if body_height <= 0:
        return None
    # A centred name / contact header may cross the gutter; don't let it veto.
    body_lines = [line for line in lines if line[0]["top"] >= body_top + body_height * GUTTER_HEADER_ZONE]
    lo, hi = int(width * GUTTER_SEARCH[0]), int(width * GUTTER_SEARCH[1])
    allowed = max(1, int(len(body_lines) * GUTTER_MAX_CROSSING_LINES))
    open_x = [
        x for x in range(lo, hi + 1)
        if sum(1 for line in body_lines if any(w["x0"] <= x <= w["x1"] for w in line)) <= allowed
    ]
    best = None
    run_start = prev = None
    for x in open_x + [None]:
        if x is not None and prev is not None and x == prev + 1:
            prev = x
            continue
        if run_start is not None and (best is None or prev - run_start > best[1] - best[0]):
            best = (run_start, prev)
        run_start = prev = x
    if best is None or (best[1] - best[0]) < width * GUTTER_MIN_WIDTH:
        return None
    split = (best[0] + best[1]) / 2.0
    left = [w for w in words if w["x1"] <= split]
    right = [w for w in words if w["x0"] >= split]
    if not left or not right:
        return None
    total_chars = sum(len(w["text"]) for w in words)
    for side in (left, right):
        span = max(w["bottom"] for w in side) - min(w["top"] for w in side)
        if span < body_height * GUTTER_MIN_SIDE_HEIGHT:
            return None
        if sum(len(w["text"]) for w in side) < total_chars * GUTTER_MIN_SIDE_CHARS:
            return None
    # A column is left-aligned: its lines share a left edge and end raggedly.
    # Right-aligned dates in a single-column resume ("Engineer, Acme ... Jan
    # 2020") share a right edge instead, so they are not a column.
    segments = [[w for w in line if w["x0"] >= split] for line in body_lines]
    segments = [seg for seg in segments if seg]
    starts = [min(w["x0"] for w in seg) for seg in segments]
    ends = [max(w["x1"] for w in seg) for seg in segments]
    if len(segments) < 3 or (max(ends) - min(ends)) <= (max(starts) - min(starts)):
        return None
    two_sided = [
        line for line in lines
        if any(w["x1"] <= split for w in line) and any(w["x0"] >= split for w in line)
    ]
    columns_top = min(line[0]["top"] for line in two_sided) - 1 if two_sided else body_top
    return split, max(0.0, columns_top)


def _page_text_and_layout(page):
    words = page.extract_words() or []
    found = find_column_split(words, float(page.width), float(page.height))
    if found is None:
        return page.extract_text() or "", "single_column"
    split, top = found
    parts = []
    if top > 0:
        parts.append(page.crop((0, 0, page.width, top)).extract_text() or "")
    parts.append(page.crop((0, top, split, page.height)).extract_text() or "")
    parts.append(page.crop((split, top, page.width, page.height)).extract_text() or "")
    return "\n".join(part for part in parts if part.strip()), "two_column"


def _extract_with_pdfplumber_layout(pdf_path):
    """Return (text, layout); layout is two_column if any page is."""
    try:
        import pdfplumber
    except ImportError:
        return "", None

    try:
        text_parts = []
        layouts = set()
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text, layout = _page_text_and_layout(page)
                text_parts.append(text)
                layouts.add(layout)
        layout = "two_column" if "two_column" in layouts else ("single_column" if layouts else None)
        return "\n".join(text_parts), layout
    except Exception:
        return "", None


def _extract_with_pdfplumber(pdf_path):
    """Text only (kept for callers that don't need layout)."""
    return _extract_with_pdfplumber_layout(pdf_path)[0]


def _extract_text_and_layout(pdf_path):
    text, layout = _extract_with_pdfplumber_layout(pdf_path)
    if text.strip():
        return text, layout

    # PyMuPDF fallback reads in content order without a layout check.
    text = _extract_with_pymupdf(pdf_path)
    if text.strip():
        return text, None

    # PDF container bytes are not extracted resume text. Returning them can
    # invent skills from metadata or accept a corrupt/image-only document.
    return "", None


def _extract_text(pdf_path):
    return _extract_text_and_layout(pdf_path)[0]


_HYPHEN_SENSITIVE_ALIASES = frozenset({"go", "c", "r", "os", "ai", "ml", "ui", "cn", "hr"})


def _find_skills(text):
    text_lower = text.lower()
    skills = []

    for skill, canonical in TECH_SKILLS:
        alias = skill.lower()
        if len(alias) <= 2 or alias in _HYPHEN_SENSITIVE_ALIASES:
            # Avoid false positives on hyphenated/underscored words like "go-to-market" or "go-live".
            pattern = r"(?<![a-z0-9_-])" + re.escape(alias) + r"(?![a-z0-9_-])"
        else:
            pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        if re.search(pattern, text_lower):
            skills.append(canonical)

    return sorted(set(skills))


def extract_skills_from_text(text: str) -> list[str]:
    """Public deterministic skill extract (resume + JD). Same lexicon as parse_resume."""
    return _find_skills(text or "")


def _detect_sections(text: str) -> dict[str, bool]:
    return {name: bool(pat.search(text or "")) for name, pat in SECTION_PATTERNS.items()}


def _section_order_ok(text: str) -> bool | None:
    """Return False if headers appear in a clearly inverted order; None if too few headers."""
    positions = []
    for name in SECTION_HEADER_ORDER:
        match = SECTION_PATTERNS[name].search(text or "")
        if match:
            positions.append((match.start(), name))
    if len(positions) < 2:
        return None
    names = [n for _, n in sorted(positions)]
    expected = [n for n in SECTION_HEADER_ORDER if n in names]
    return names == expected


def _experience_bullets(text: str) -> list[str]:
    lines = (text or "").splitlines()
    # Prefer bullets after an experience header when present
    start = 0
    for i, line in enumerate(lines):
        if SECTION_PATTERNS["experience"].search(line):
            start = i + 1
            break
    chunk = "\n".join(lines[start : start + 80] if start else lines[:120])
    bullets = [m.group(1).strip() for m in BULLET_RE.finditer(chunk)]
    return [b for b in bullets if len(b) >= 8][:40]


def _evidence_text(text: str) -> str | None:
    """Text of Experience / Projects blocks, or None if no such header exists."""
    headers = list(BLOCK_HEADER_RE.finditer(text or ""))
    blocks = []
    for i, match in enumerate(headers):
        name = match.group("name").lower()
        if any(key in name for key in EVIDENCE_BLOCKS):
            end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            blocks.append(text[match.end():end])
    return "\n".join(blocks) if blocks else None


def _likely_garbage(text: str) -> bool:
    if not text or not text.strip():
        return True
    sample = text[:4000]
    printable = sum(1 for ch in sample if ch.isprintable() or ch in "\n\t")
    return (printable / max(len(sample), 1)) < 0.7


def analyze_resume_text(text: str, layout: str | None = None) -> dict:
    """Rich ATS-oriented analysis from plain text.

    ``layout`` comes from PDF extraction ("single_column" | "two_column"); it is
    None for pasted text or the PyMuPDF fallback, where layout was not checked.
    """
    text = text or ""
    extract_ok = bool(text.strip()) and not _likely_garbage(text)
    skills = _find_skills(text) if extract_ok else []
    sections = _detect_sections(text) if extract_ok else {
        "contact": False,
        "experience": False,
        "education": False,
        "skills": False,
    }
    order = _section_order_ok(text) if extract_ok else None
    bullets = _experience_bullets(text) if extract_ok else []
    evidence = _evidence_text(text) if extract_ok else None
    text_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    return {
        "skills": skills,
        "sections": sections,
        "section_order_ok": order,
        "experience_bullets": bullets,
        "extract_ok": extract_ok,
        "likely_garbage": _likely_garbage(text),
        # Layout is only known for pdfplumber extraction; tables are not classified.
        "layout_checked": layout is not None,
        "layout": layout,
        # Skills mentioned inside Experience / Projects blocks; None when the
        # resume has no such header, so "unsubstantiated" can't be judged.
        "evidence_skills": _find_skills(evidence) if evidence is not None else None,
        "evidence_sections_found": evidence is not None,
        "text_hash": text_hash,
        "char_count": len(text),
    }


def analyze_resume(pdf_path) -> dict:
    text, layout = _extract_text_and_layout(pdf_path)
    return analyze_resume_text(text, layout=layout)


def parse_resume(pdf_path):
    """
    Parse a PDF resume and extract skills.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        List of skills extracted from the resume
    """
    try:
        analysis = analyze_resume(pdf_path)
        skills = analysis.get("skills") or []
        return skills
    except Exception as exc:
        print(f"Error parsing PDF: {exc}")
        return []
