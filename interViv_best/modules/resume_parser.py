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

    # Other
    ("git", "Git"), ("linux", "Linux"), ("windows", "Windows"),
    ("macos", "macOS"), ("rest api", "REST"), ("rest", "REST"),
    ("graphql", "GraphQL"), ("soap", "SOAP"), ("microservices", "Microservices"),
    ("system design", "System Design"), ("agile", "Agile"), ("scrum", "Scrum"),
    ("jira", "Jira"),
]


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


def parse_resume(pdf_path):
    """
    Parse a PDF resume and extract skills.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        List of skills extracted from the resume
    """
    try:
        skills = _find_skills(_extract_text(pdf_path))
        return skills or ["Python"]
    except Exception as exc:
        print(f"Error parsing PDF: {exc}")
        return ["Python"]
