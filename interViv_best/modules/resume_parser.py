import hashlib
import re
from pathlib import Path


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


def _extract_with_pdfplumber(pdf_path):
    try:
        import pdfplumber
    except ImportError:
        return ""

    try:
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except Exception:
        return ""


def _extract_text(pdf_path):
    text = _extract_with_pdfplumber(pdf_path)
    if text.strip():
        return text

    text = _extract_with_pymupdf(pdf_path)
    if text.strip():
        return text

    # Last-resort fallback for simple PDFs. It keeps upload working even when
    # optional PDF extraction packages are missing from the active interpreter.
    try:
        return Path(pdf_path).read_bytes().decode("latin-1", errors="ignore")
    except Exception:
        return ""


def _find_skills(text):
    text_lower = text.lower()
    skills = []

    for skill, canonical in TECH_SKILLS:
        pattern = r"(?<![a-z0-9])" + re.escape(skill.lower()) + r"(?![a-z0-9])"
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


def _likely_garbage(text: str) -> bool:
    if not text or not text.strip():
        return True
    sample = text[:4000]
    printable = sum(1 for ch in sample if ch.isprintable() or ch in "\n\t")
    return (printable / max(len(sample), 1)) < 0.7


def analyze_resume_text(text: str) -> dict:
    """Rich ATS-oriented analysis from plain text (no layout/CV model)."""
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
    text_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    return {
        "skills": skills,
        "sections": sections,
        "section_order_ok": order,
        "experience_bullets": bullets,
        "extract_ok": extract_ok,
        "likely_garbage": _likely_garbage(text),
        # Honest: resume_parser does not classify multi-column / table layouts.
        "layout_checked": False,
        "text_hash": text_hash,
        "char_count": len(text),
    }


def analyze_resume(pdf_path) -> dict:
    text = _extract_text(pdf_path)
    return analyze_resume_text(text)


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
        return skills or ["Python"]
    except Exception as exc:
        print(f"Error parsing PDF: {exc}")
        return ["Python"]
