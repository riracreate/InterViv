from __future__ import annotations

import csv
import json
import math
import textwrap
import zipfile
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml
from PIL import Image
from matplotlib.backends.backend_pdf import PdfPages


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "research_paper"
ASSET_DIR = OUT_DIR / "figures"
DOCX_PATH = OUT_DIR / "interViv_ieee_extended_manuscript.docx"
PDF_PATH = OUT_DIR / "interViv_ieee_extended_manuscript_preview.pdf"
MD_PATH = OUT_DIR / "interViv_ieee_extended_manuscript.md"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def load_metrics() -> dict:
    fallback_rows = read_csv_rows(ROOT / "data" / "fallback_question_bank.csv")
    dataset_rows = read_csv_rows(ROOT / "data" / "interview_dataset_v6.csv")
    training_rows = read_csv_rows(ROOT / "data" / "ml_training_data.csv")
    metadata = json.loads((ROOT / "modules" / "model_metadata.json").read_text())
    graph = yaml.safe_load((ROOT / "data" / "company_hiring_graphs.yaml").read_text())
    companies = graph["companies"]
    audit = json.loads((ROOT / "docs" / "question_audit_research.json").read_text())

    return {
        "fallback_rows": fallback_rows,
        "dataset_rows": dataset_rows,
        "training_rows": training_rows,
        "metadata": metadata,
        "companies": companies,
        "audit": audit,
        "test_total": 116,
        "test_passed": 116,
        "test_warnings": 6,
        "human_baseline": {
            "n": 30,
            "avg_kappa": 0.642,
            "pearson": 0.7392,
            "annotator_corr": {
                "Annotator 1": 0.556,
                "Annotator 2": 0.824,
                "Annotator 3": 0.719,
            },
            "kappa_pairs": {
                "A1-A2": 0.489,
                "A1-A3": 0.701,
                "A2-A3": 0.736,
            },
            "confusion": [[10, 8, 3], [0, 3, 3], [0, 3, 0]],
        },
        "persona_validation": {
            "n": 200,
            "avg_kappa": 0.640,
            "pearson": 0.9578,
            "confusion": [[79, 12, 0], [0, 49, 0], [0, 31, 29]],
        },
        "guard_caps": {
            "empty": 5,
            "gibberish": 10,
            "repetition": 15,
            "too_short": 20,
            "question_parroting": 25,
            "low_density": 30,
            "off_topic": 30,
            "keyword_stuffing": 35,
        },
        "direct_guard_checks": {
            "gctcititxi": 5.0,
            "fvitugceigc vgcyutrxrtxtci": 5.0,
            "normal_binary_search_answer": 80.38,
        },
    }


def save_bar(path: Path, title: str, labels: list[str], values: list[float], ylabel: str, color="#2E74B5") -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.6), dpi=180)
    bars = ax.bar(labels, values, color=color, edgecolor="#1f2937", linewidth=0.4)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", labelrotation=35, labelsize=8)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:g}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def save_heatmap(path: Path, title: str, matrix: list[list[int]], labels: list[str]) -> None:
    fig, ax = plt.subplots(figsize=(5.8, 4.8), dpi=180)
    im = ax.imshow(matrix, cmap="Blues")
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xticks(range(len(labels)), labels=labels)
    ax.set_yticks(range(len(labels)), labels=labels)
    ax.set_xlabel("System band")
    ax.set_ylabel("Human mean band")
    for row in range(len(matrix)):
        for col in range(len(matrix[row])):
            ax.text(col, row, str(matrix[row][col]), ha="center", va="center", color="#111827", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def save_architecture(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.8), dpi=180)
    ax.axis("off")
    boxes = [
        (0.05, 0.72, "React UI\nsignup, upload,\ninterview, dashboard"),
        (0.36, 0.72, "FastAPI backend\nsessions, auth,\nanswers, dashboards"),
        (0.67, 0.72, "Question runtime\nLLM JSON + fallback\nbank selection"),
        (0.05, 0.36, "Resume parser\nskills and profile\nsignals"),
        (0.36, 0.36, "Deterministic scoring\nanswer guard, NLP,\nKG, NER, feedback"),
        (0.67, 0.36, "Readiness layer\nskill graph, gap\nanalysis, roadmap"),
        (0.36, 0.05, "Persistence\nPostgreSQL or local\nmemory fallback"),
    ]
    for x, y, text in boxes:
        rect = plt.Rectangle((x, y), 0.25, 0.18, facecolor="#E8EEF5", edgecolor="#1F4D78", linewidth=1.2)
        ax.add_patch(rect)
        ax.text(x + 0.125, y + 0.09, text, ha="center", va="center", fontsize=9)
    arrows = [
        ((0.30, 0.81), (0.36, 0.81)),
        ((0.61, 0.81), (0.67, 0.81)),
        ((0.49, 0.72), (0.49, 0.54)),
        ((0.30, 0.45), (0.36, 0.45)),
        ((0.61, 0.45), (0.67, 0.45)),
        ((0.49, 0.36), (0.49, 0.23)),
    ]
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="->", lw=1.4, color="#0B2545"))
    ax.text(0.5, 0.96, "interViv reference architecture", ha="center", fontsize=15, fontweight="bold")
    ax.text(0.5, 0.91, "LLM usage is isolated to question and reference generation; scoring remains deterministic.", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def save_pipeline(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.6), dpi=180)
    ax.axis("off")
    steps = [
        "Answer",
        "Guard\ncaps",
        "NLP\nfeatures",
        "Classifier\nsignal",
        "KG + NER\nconcepts",
        "Rule feedback",
        "Final score\n+ roadmap",
    ]
    x_positions = [0.03 + i * 0.145 for i in range(len(steps))]
    for i, (x, label) in enumerate(zip(x_positions, steps)):
        rect = plt.Rectangle((x, 0.38), 0.115, 0.28, facecolor="#F4F6F9", edgecolor="#2E74B5")
        ax.add_patch(rect)
        ax.text(x + 0.0575, 0.52, label, ha="center", va="center", fontsize=8.5)
        if i < len(steps) - 1:
            ax.annotate("", xy=(x + 0.14, 0.52), xytext=(x + 0.117, 0.52), arrowprops=dict(arrowstyle="->", lw=1.2))
    ax.text(0.5, 0.85, "Deterministic scoring pipeline", ha="center", fontsize=14, fontweight="bold")
    ax.text(0.5, 0.18, "The answer guard runs first. If it fires, the final score and rubric dimensions cannot exceed the cap.", ha="center", fontsize=9)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def save_question_flow(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=180)
    ax.axis("off")
    labels = [
        "Selected company",
        "Selected role",
        "Resume skills",
        "Weak skills/concepts",
        "Adaptive difficulty",
        "LLM JSON or fallback bank",
    ]
    widths = [0.84, 0.74, 0.64, 0.54, 0.44, 0.34]
    colors = ["#0B2545", "#1F4D78", "#2E74B5", "#5B8DB8", "#93B5D6", "#C7D9EA"]
    y = 0.82
    for label, width, color in zip(labels, widths, colors):
        x = 0.5 - width / 2
        poly = plt.Polygon([(x, y), (x + width, y), (x + width - 0.06, y - 0.09), (x + 0.06, y - 0.09)], closed=True, facecolor=color, edgecolor="white")
        ax.add_patch(poly)
        ax.text(0.5, y - 0.045, label, ha="center", va="center", fontsize=9, color="white" if color != "#C7D9EA" else "#0B2545", fontweight="bold")
        y -= 0.105
    ax.set_title("Question selection priority", fontsize=14, fontweight="bold", pad=10)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def make_figures(metrics: dict) -> dict[str, Path]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    figures: dict[str, Path] = {}

    figures["architecture"] = ASSET_DIR / "fig01_architecture.png"
    save_architecture(figures["architecture"])

    figures["pipeline"] = ASSET_DIR / "fig02_pipeline.png"
    save_pipeline(figures["pipeline"])

    figures["question_flow"] = ASSET_DIR / "fig03_question_priority.png"
    save_question_flow(figures["question_flow"])

    skill_counts = Counter(row["skill"] for row in metrics["fallback_rows"])
    labels, values = zip(*skill_counts.most_common())
    figures["fallback_skill"] = ASSET_DIR / "fig04_fallback_skill_coverage.png"
    save_bar(figures["fallback_skill"], "Fallback question-bank coverage by skill", list(labels), list(values), "Questions", "#2E74B5")

    difficulty_counts = Counter(row["difficulty"] for row in metrics["fallback_rows"])
    labels = ["easy", "medium", "hard"]
    figures["difficulty"] = ASSET_DIR / "fig05_fallback_difficulty_mix.png"
    save_bar(figures["difficulty"], "Fallback question-bank difficulty mix", labels, [difficulty_counts[k] for k in labels], "Questions", "#1F7A5F")

    labels = ["Val acc.", "Val F1 macro", "CV acc.", "CV F1 macro"]
    meta = metrics["metadata"]
    values = [
        meta["val_accuracy"],
        meta["val_f1_macro"],
        meta["cv_5fold_accuracy_mean"],
        meta["cv_5fold_f1_macro_mean"],
    ]
    figures["model"] = ASSET_DIR / "fig06_classifier_metrics.png"
    save_bar(figures["model"], "Classifier validation metrics", labels, values, "Metric value", "#5B8DB8")

    hb = metrics["human_baseline"]
    figures["kappa"] = ASSET_DIR / "fig07_human_kappa.png"
    save_bar(figures["kappa"], "Human baseline inter-rater agreement", list(hb["kappa_pairs"].keys()) + ["Average"], list(hb["kappa_pairs"].values()) + [hb["avg_kappa"]], "Cohen's kappa", "#7A5A00")

    figures["human_corr"] = ASSET_DIR / "fig08_system_human_correlation.png"
    save_bar(figures["human_corr"], "System-human Pearson correlation", list(hb["annotator_corr"].keys()) + ["Mean"], list(hb["annotator_corr"].values()) + [hb["pearson"]], "Pearson r", "#1F4D78")

    figures["human_cm"] = ASSET_DIR / "fig09_human_confusion.png"
    save_heatmap(figures["human_cm"], "Primary human baseline confusion matrix", hb["confusion"], ["Good", "Average", "Poor"])

    pv = metrics["persona_validation"]
    figures["persona_cm"] = ASSET_DIR / "fig10_persona_confusion.png"
    save_heatmap(figures["persona_cm"], "Persona-simulation validation confusion matrix", pv["confusion"], ["Good", "Average", "Poor"])

    caps = metrics["guard_caps"]
    figures["guard_caps"] = ASSET_DIR / "fig11_guard_caps.png"
    save_bar(figures["guard_caps"], "Answer guard score caps", list(caps.keys()), list(caps.values()), "Maximum score", "#9B1C1C")

    figures["tests"] = ASSET_DIR / "fig12_test_status.png"
    save_bar(figures["tests"], "Automated verification status", ["Passed", "Warnings", "Failed"], [metrics["test_passed"], metrics["test_warnings"], 0], "Count", "#1F7A5F")

    company_counts = Counter(row["company"] for row in metrics["fallback_rows"])
    figures["company"] = ASSET_DIR / "fig13_company_coverage.png"
    save_bar(figures["company"], "Fallback question-bank coverage by company", list(company_counts.keys()), list(company_counts.values()), "Questions", "#4F46E5")

    return figures


def paper_sections(metrics: dict, figures: dict[str, Path]) -> list[dict]:
    meta = metrics["metadata"]
    graph_companies = metrics["companies"]
    company_count = len(graph_companies)
    role_count = sum(len(company.get("roles", [])) for company in graph_companies)
    requirement_count = sum(len(role.get("skill_requirements", [])) for company in graph_companies for role in company.get("roles", []))
    audit_warning_count = sum(
        1
        for issue in metrics["audit"].get("issues", [])
        if issue.get("severity") == "warning"
    )
    fallback_n = len(metrics["fallback_rows"])
    dataset_n = len(metrics["dataset_rows"])
    training_n = len(metrics["training_rows"])

    sections: list[dict] = []

    def add(title: str, paragraphs: list[str], figure: str | None = None, table: list[list[str]] | None = None, page_break: bool = True) -> None:
        sections.append({
            "title": title,
            "paragraphs": paragraphs,
            "figure": figures.get(figure) if figure else None,
            "table": table,
            "page_break": page_break,
        })

    add("Abstract", [
        "Interview preparation for students increasingly involves generative AI tools, yet many systems blur the boundary between generating practice material and judging candidate quality. This paper presents interViv, an interview readiness platform that deliberately separates these concerns. The platform uses large language models only for company-aware, role-aware, skill-aware, difficulty-aware, and resume-aware question generation. Candidate answer scoring, feedback, anti-gibberish checks, readiness computation, adaptive difficulty, and dashboard decisions are implemented through deterministic Python modules.",
        f"The current implementation includes a FastAPI backend, React frontend, fallback question bank with {fallback_n} structured questions, curated company-role graph with {company_count} companies, {role_count} roles, and {requirement_count} skill requirements, a three-layer scoring pipeline, answer-quality classifier, knowledge-graph concept scorer, entity extractor, and guard-cap mechanism. Preliminary evaluation includes {metrics['test_passed']} passing automated tests, a balanced classifier dataset of {training_n} labelled answers, an interview dataset of {dataset_n} answer examples, a primary human baseline of 30 rated answers, and a persona-simulation validation set of 200 examples. The primary human baseline reports average Cohen's kappa of 0.642 and system-human Pearson correlation of 0.7392.",
        "The contribution of this paper is not a claim that interViv predicts hiring success. Instead, it describes a reproducible architecture for guarded, explainable interview practice where generative AI increases variety while deterministic scoring preserves auditability. The manuscript also documents a publication-ready evaluation plan for a larger student-readiness study."
    ], page_break=True)

    add("Index Terms", [
        "Automated short-answer grading, interview readiness, educational technology, adaptive learning, learning analytics, large language models, deterministic scoring, answer guardrails, technical interviews, student preparation."
    ], page_break=True)

    add("1. Introduction", [
        "Technical interviews are a high-stakes transition point for students and early-career candidates. Students often prepare by collecting question lists, watching solution walkthroughs, and practicing alone. These workflows are fragmented: they do not reliably connect practice to a target role, they rarely adapt to weak concepts, and they frequently offer feedback that is too vague to guide repeated preparation. Generative AI tools can produce plausible interview questions, but using the same model as a judge creates reproducibility, calibration, and fairness concerns.",
        "interViv is designed around a narrower and more defensible premise. The platform uses an LLM as a constrained question generator, not as an evaluator. The LLM produces a question, ideal answer, expected keywords, topic metadata, and follow-up prompts. Candidate answers are then evaluated by deterministic Python modules: the answer guard checks for empty, gibberish, repeated, off-topic, and keyword-stuffed answers; the scoring pipeline computes lexical, semantic, structural, knowledge-graph, and classifier signals; and the dashboard converts stored evidence into weak-skill and roadmap recommendations.",
        "This separation gives the project a research identity that is stronger than a generic AI interview assistant. It enables controlled question variety while preserving stable scoring behavior. It also supports a practical research question: can an interview-readiness system combine LLM-generated practice material with deterministic assessment signals in a way that is useful, auditable, and resistant to meaningless answers?"
    ], figure="architecture")

    add("2. Research Motivation and Problem Statement", [
        "The target user is a student or early-career candidate preparing for placement, internship, or entry-level software roles. Such users need role-aligned practice, repeated feedback, and clear next actions. They also need guardrails against accidental overconfidence: an answer that repeats keywords, copies the question, or contains random text should not receive a normal score simply because it overlaps with expected vocabulary.",
        "The research problem can be stated as follows: how can a technical-interview practice platform use the generative strength of LLMs without delegating candidate judgment to a non-deterministic evaluator? The design answer in interViv is a strict boundary. The LLM may produce questions and reference material; it may not grade answers, produce feedback, decide readiness, or act as an interviewer-judge.",
        "The project therefore studies a hybrid architecture in which generative AI is a content source and deterministic analytics form the assessment layer. This framing fits the educational assessment literature, where open-ended answers are valued but difficult to grade at scale, and where hybrid scoring features remain important for interpretability and reliability."
    ])

    add("3. Contributions", [
        "The first contribution is a constrained LLM question-generation interface. The generator must return JSON containing the question, ideal answer, ideal keywords, sub-domain, topic, difficulty, question type, company, role, and follow-ups. The prompt explicitly forbids scoring, judging, grading, evaluation, pass/fail decisions, and feedback generation.",
        "The second contribution is a deterministic scoring pipeline for open-ended interview answers. The pipeline combines answer guardrails, lexical and semantic similarity, keyword coverage, concept coverage, structural quality, classifier signal, knowledge-graph matching, NER evidence, and rule-based feedback. The answer guard runs before scoring and its caps are hard limits.",
        "The third contribution is a student-readiness layer. interViv stores skill and concept evidence, computes role gap analysis, adapts question difficulty, and generates preparation roadmaps. These outputs are dashboard explanations, not hiring decisions.",
        "The fourth contribution is a reproducibility and evidence package: automated tests, question-bank audit, model metadata, baseline reports, documentation, and deployment configuration."
    ])

    add("4. Related Work", [
        "Recent work on AI-driven mock technical interviews shows that simulated interviews can support student confidence and readiness when designed as formative practice environments. interViv shares this educational goal but differs by refusing to use the LLM as an answer judge.",
        "LLM-based question generation has become a practical technique for creating varied educational material. Prior work on automatic multiple-choice question generation uses prompt engineering and review processes to improve generated question quality. interViv applies a similar generation-plus-validation pattern, but for technical and behavioral interview prompts rather than only MCQs.",
        "Automated short-answer grading research supports hybrid approaches. Surveys describe the value of combining engineered lexical and structural features with modern semantic representations. ASAG benchmark work also notes that LLM-based grading has improved but remains short of human performance in general settings. These findings support interViv's design choice: use deterministic signals for scoring and reserve LLMs for question generation.",
        "Adaptive interviewing and adaptive learning research motivates the use of follow-ups, difficulty adjustment, and learner modeling. interViv implements these ideas conservatively through Elo-style difficulty updates, skill graphs, and concept mastery rather than through opaque LLM reasoning."
    ], table=[
        ["Research area", "What it supports", "How interViv uses it"],
        ["AI mock interviews", "Practice realism and confidence-building", "Student readiness practice"],
        ["LLM question generation", "Controlled generation of educational prompts", "Question JSON and fallback bank"],
        ["ASAG", "Hybrid feature-based answer scoring", "Deterministic rubric signals"],
        ["Adaptive learning", "Skill targeting and difficulty adjustment", "Elo, weak concepts, roadmap"],
    ])

    add("5. System Overview", [
        "interViv is implemented as a web platform with a React frontend and FastAPI backend. The frontend contains the landing page, signup/login flows, resume upload, interview workspace, and dashboard. The backend exposes auth, resume, company, session, answer, dashboard, learning, gap-analysis, roadmap, transcription, and admin routes.",
        "The core execution path begins when a user creates or resumes a session. The system selects a skill, company, role, weak concept, and difficulty. It requests a question from the LLM when configured, validates the JSON shape, and falls back to the structured question bank if the provider fails or fallback mode is selected. When the candidate submits an answer, the backend ignores client-side scoring fields and recomputes all scoring evidence server-side.",
        "Persistence is available through PostgreSQL with SQLAlchemy and Alembic, with an in-memory fallback for local demos and continuous integration. This makes the platform usable in research, demonstration, and deployment contexts."
    ], figure="pipeline")

    add("6. LLM Boundary and Question Generation Contract", [
        "The LLM boundary is the central design constraint. The generator may produce only question and reference metadata. The required JSON fields are question, ideal_answer, ideal_keywords, sub_domain, topic, difficulty, question_type, company, role, and followups. The backend stores ideal_answer and ideal_keywords as deterministic scoring references.",
        "Question selection follows a priority order: selected company, selected role, resume extracted skills, weak skills, adaptive difficulty, and fallback bank. This ensures that the model receives a meaningful context without being allowed to decide the candidate's score.",
        "This architecture also improves failure behavior. If the LLM call fails, the system can fall back to a structured bank with the same schema. The evaluator receives a consistent question_context object regardless of whether the question came from an LLM or from the bank."
    ], figure="question_flow")

    add("7. Structured Fallback Question Bank", [
        f"The fallback question bank contains {fallback_n} rows with schema: company, role, skill, sub_domain, topic, difficulty, question_type, question, ideal_answer, ideal_keywords, and followups. Every row contains the reference fields needed by deterministic scoring.",
        "The current bank covers DSA, DBMS, OS, CN, OOP, Python, JavaScript, React, Node.js, FastAPI, System Design, and HR/Behavioral. It also covers TCS, Infosys, Accenture, Wipro, Amazon, Microsoft, Google, and Meta. The bank is intentionally schema-compatible with LLM-generated questions, which makes fallback behavior transparent to the scoring pipeline.",
        f"The latest audit reports schema OK, zero errors, and {audit_warning_count} warnings. The warnings identify role labels in fallback questions that are broader than some company graph entries. This is useful cleanup work, but it does not block safe fallback generation."
    ], figure="fallback_skill")

    add("8. Company, Role, and Resume Awareness", [
        f"The company hiring graph contains {company_count} companies, {role_count} roles, and {requirement_count} role-skill requirements. Each role stores required skills, required levels, and importance weights. These profiles are curated reference profiles for practice preparation, not exact recruiter rubrics.",
        "When a user selects a company and role, the gap-analysis layer compares the user's skill graph against the target role profile. Resume extraction contributes candidate skills, while session performance contributes observed mastery and weak concept signals. This combination makes question selection more realistic for students than a generic interview question list.",
        "The company layer is deliberately framed as practice support. The platform does not claim to represent proprietary hiring criteria and does not predict whether a candidate will pass a real interview."
    ], figure="company")

    add("9. Deterministic Scoring Pipeline", [
        "The scoring entry point is backend/scoring/pipeline.py. The answer route invokes the pipeline when the candidate submits a round. The pipeline first runs answer_guard, then computes NLP signals, classifier label, knowledge graph score, NER entities, rule-based feedback, and final score.",
        "The final-score formula uses semantic or lexical match, classifier component, keyword coverage, TF-IDF overlap, KG bonus, NER bonus, and penalties. The formula is deterministic for a fixed model artifact and reference context. Model metadata stores the classifier type, feature order, dataset hash, validation metrics, and artifact checksum.",
        "The current scoring schema also exposes rubric-style dimensions: correctness, coverage, depth, and clarity. These dimensions are derived from existing deterministic signals and do not replace the calibrated final-score formula."
    ])

    add("10. Answer Guardrails and Anti-Gaming Design", [
        "The answer guard protects the system from meaningless input. It detects empty answers, whitespace-only answers, random character strings, abnormal vowel ratios, repeated character ratios, repeated token ratios, keyboard spam, keyword stuffing, question parroting, low-density filler, and off-topic responses.",
        "If the guard fires, the score cap is applied after normal scoring but remains a hard upper bound. Empty answers are capped at 5, gibberish at 10, repeated meaningless text at 15, too-short answers at 20, and keyword stuffing at 35. The dashboard receives structured guard information: applied, reason, score_cap, guards_fired, and softened status.",
        "This mechanism addresses a major failure mode in naive automated scoring: random text can receive nonzero overlap by chance, and keyword lists can mimic topic relevance without explanation. interViv caps such cases before they can become normal readiness evidence."
    ], figure="guard_caps")

    add("11. Rubric-Oriented Explainability", [
        "The rubric view is designed for user-facing explanation rather than hidden model training. Correctness is computed from semantic or lexical evidence and classifier signal. Coverage combines keyword coverage, concept coverage, and KG score. Depth combines technical depth and KG score. Clarity combines structure, clarity, and length fit.",
        "When a guard cap is active, rubric dimensions are capped as well. This prevents a confusing report where the final score is low but dimension scores appear strong. The result is a coherent explanation: an invalid or incomplete answer cannot receive normal-looking rubric evidence.",
        "The dashboard presents both low-level signals and named dimensions. This dual view is useful for research because the pipeline remains auditable, while students see a simpler explanation of what to improve."
    ], table=[
        ["Dimension", "Primary deterministic signals", "Student-facing meaning"],
        ["Correctness", "semantic_or_lexical, classifier", "Does the answer match the core idea?"],
        ["Coverage", "keyword, concept, KG", "Are expected terms and concepts covered?"],
        ["Depth", "depth score, KG", "Does the answer reason beyond a definition?"],
        ["Clarity", "structure, clarity, length fit", "Is the explanation readable and organized?"],
    ])

    add("12. Adaptive Difficulty and Skill Targeting", [
        "interViv adapts practice through deterministic state. Each skill has an Elo-style rating that changes after scored rounds. Difficulty selection is based on the updated rating, while weak-skill and weak-concept targeting uses stored skill graph and concept mastery data.",
        "The adaptive selector is conservative. Anonymous sessions follow rotation behavior, while authenticated users with enough state can be routed toward weak concepts and role gaps. This prevents the system from overfitting early sessions while still enabling personalization as evidence accumulates.",
        "The design favors interpretability over aggressive optimization. The dashboard can explain why a topic was recommended: it was missed in concept coverage, weak in the skill graph, required by the target role, or selected due to adaptive difficulty."
    ])

    add("13. Dashboard and Learning Analytics", [
        "The dashboard is the student-facing learning analytics layer. It shows overall readiness score, company practice, role practice, skill library, weak skills, recent sessions, replay or past questions, and recommended roadmap. Session reports show content match, semantic similarity, keyword coverage, structure score, guard warnings, missing concepts, ideal answer, and next recommended topics.",
        "The dashboard does not invent decisions. It displays fields produced by the backend: final score, scoring breakdown, guard, concepts, topic metadata, ideal answer, and follow-ups. This design maintains traceability from the UI back to deterministic scoring evidence.",
        "For research use, the dashboard can serve both as an intervention and an observation tool. It guides students toward next topics and stores the evidence needed to analyze score trends, weak skill reduction, and guard-trigger frequency over time."
    ])

    add("14. Implementation Details", [
        "The backend is organized around FastAPI routers. Auth implements signup, login, and me endpoints using JWT. Session routes create and progress interview sessions. Answer routes run scoring and persist completed rounds. Dashboard routes sanitize session data and compute aggregate readiness views.",
        "The modules directory contains dynamically loaded scoring and generation components: nlp_scorer, nlp_scorer_patch, answer_guard, question_runtime, question_bank, semantic_scorer, knowledge_graph, ner_scorer, c4_feedback, skill_graph, concept_mastery, and roadmap_generator.",
        "The frontend is a Vite React application with React Router. It contains pages for landing, login, signup, resume upload, interview, dashboard, gap analysis, and roadmap. Dashboard components are TypeScript-based and consume the structured scoring breakdown."
    ], table=[
        ["Layer", "Key files", "Purpose"],
        ["Frontend", "frontend/src/pages, components/dashboard", "Practice UI and readiness reports"],
        ["Backend routes", "backend/routes", "Auth, sessions, answers, dashboards"],
        ["Scoring", "backend/scoring/pipeline.py, modules", "Deterministic answer evaluation"],
        ["Data", "data/*.csv, company_hiring_graphs.yaml", "Questions, labels, role profiles"],
        ["Tests", "tests/", "Regression and behavior verification"],
    ])

    add("15. Datasets and Artifacts", [
        f"The large interview dataset contains {dataset_n} rows and is balanced across Good, Average, and Poor labels, with 773 rows per label. It covers DBMS, System Design, ML, CN, DSA, Python, OOP, OS, HR, Java, and JavaScript.",
        f"The answer-quality classifier training data contains {training_n} rows, balanced across 297 Good, 297 Average, and 297 Poor examples. Metadata records the dataset hash and feature order, making model provenance auditable.",
        f"The fallback question bank contains {fallback_n} structured questions. Unlike the training dataset, it is designed for live fallback and contains ideal answers, ideal keywords, follow-ups, role labels, companies, and question types."
    ], figure="difficulty")

    add("16. Classifier Validation", [
        f"The current answer-quality classifier is {meta['model_type']} trained on {meta['dataset_rows']} balanced rows. Metadata reports validation accuracy {meta['val_accuracy']:.4f}, macro F1 {meta['val_f1_macro']:.4f}, weighted F1 {meta['val_f1_weighted']:.4f}, five-fold cross-validation accuracy mean {meta['cv_5fold_accuracy_mean']:.4f}, and standard deviation {meta['cv_5fold_accuracy_std']:.4f}.",
        "These metrics are classifier-only validation metrics on labelled answer-quality data. They are not whole-system accuracy, interview-readiness accuracy, or hiring prediction accuracy. The paper should preserve this distinction during submission.",
        "The classifier is used as one component of the final score. It does not override the guard and does not independently decide readiness."
    ], figure="model")

    add("17. Human Baseline Evaluation", [
        "The primary human baseline contains 30 answers rated by three annotators. Average Cohen's kappa is 0.642, which is interpreted as substantial agreement under the scale documented in the baseline report. The system-human Pearson correlation is 0.7392 with p-value reported as 0.0000 in the project report.",
        "The baseline also exposes important error cases. Top disagreements include cases where the answer content appears mismatched to the question or where concise high-quality answers are under-scored. These disagreements are useful for future calibration and should be discussed honestly rather than hidden.",
        "The baseline is small, but it provides a credible starting point for a system paper. A publication submission should expand this evaluation with additional human-rated answers and a student-participant study."
    ], figure="kappa")

    add("18. System-Human Agreement Results", [
        "The system-human correlation chart shows that correlation varies by annotator: 0.556, 0.824, and 0.719 for the three annotators, with a mean system-human correlation of 0.7392. This level of agreement is promising for a preliminary deterministic scoring system but not sufficient to claim replacement-level grading.",
        "The confusion matrix shows that the system identifies many Good examples but also assigns some Good human-mean answers to Average or Poor bands. The paper should interpret this conservatively: interViv is a formative readiness tool whose feedback can guide practice, not a summative credentialing engine.",
        "This framing aligns with the project's product identity. Scores should help students improve, not certify employability."
    ], figure="human_corr")

    add("19. Confusion Matrix Analysis", [
        "The primary human baseline confusion matrix is organized as human mean band by system predicted band. The strongest diagonal count occurs in the Good-Good cell. Average and Poor bands show more ambiguity, which is common in short-answer grading because partial answers can contain some correct concepts while lacking depth or structure.",
        "The matrix suggests two improvement paths. First, the system should better recognize concise but technically complete answers. Second, future calibration should separate off-topic high-quality explanations from on-topic concise answers. The answer guard and rubric view help with this distinction, but additional labelled examples are needed.",
        "The paper uses these findings as design feedback. It does not claim a final validated grading instrument."
    ], figure="human_cm")

    add("20. Persona-Simulation Validation", [
        "The project also includes a persona-simulation validation file with 200 rows and four annotators. It reports average kappa 0.640 and Pearson correlation 0.9578. This result is useful for stress testing and calibration but should not be treated as equivalent to a real human-participant study.",
        "In the manuscript, persona validation is therefore placed as secondary evidence. It demonstrates that the deterministic scoring pipeline can behave consistently under controlled answer patterns, while the primary human baseline remains the more important external-validity evidence.",
        "A rigorous publication path should include real student participants and independent human raters before claiming educational impact."
    ], figure="persona_cm")

    add("21. Guard Stress Testing", [
        "Guard stress testing checks whether invalid answers can still obtain normal scores. Direct verification examples show that 'gctcititxi' receives final score 5.0 with gibberish guard, 'fvitugceigc vgcyutrxrtxtci' receives 5.0 with gibberish guard, and a normal binary-search explanation receives 80.38 without a guard.",
        "Automated tests cover empty answers, whitespace-only answers, random tokens, keyboard spam, repeated meaningless tokens, repeated keyword-only text, keyword stuffing, and meaningful short technical answers. Meaningful examples such as binary search, database indexing, and process scheduling are not flagged by the guard.",
        "The guard therefore protects the central scoring claim: meaningless text must not receive normal readiness evidence."
    ], table=[
        ["Input type", "Expected behavior", "Observed evidence"],
        ["Random single token", "Score <= 10", "5.0, gibberish"],
        ["Random two tokens", "Score <= 10", "5.0, gibberish"],
        ["Normal binary search", "No gibberish guard", "80.38, no guard"],
        ["Keyword stuffing", "Score <= 35", "Regression tested"],
    ])

    add("22. Automated Verification", [
        f"The full test suite currently reports {metrics['test_passed']} passed tests and {metrics['test_warnings']} warnings. The warnings are not failed behavior: they include deprecation warnings, short JWT-secret warnings in local test configuration, and tests that return dictionaries in semantic test helpers.",
        "The test suite covers adaptive selection, answer guard, authentication, server-side metrics, scoring breakdown, baseline analysis, company graph, dashboard confidence bands, gap analysis, guard v2 behavior, model credibility, scoring calibration, roadmap, semantic scoring, skill graph, and question-generation hardening.",
        "This breadth matters for research reproducibility. The paper can point to a runnable artifact whose core behavior is covered by tests instead of only describing an architecture diagram."
    ], figure="tests")

    add("23. Security, Privacy, and Deployment Considerations", [
        "interViv handles resumes, answers, and authentication tokens, so deployment must use secure configuration. The production path supports PostgreSQL, Redis for shared question cache and rate limiting, Sentry for observability, Docker/Compose, Render backend deployment, and Vercel frontend deployment.",
        "The local demo mode intentionally uses in-memory persistence and fallback generation. This is useful for research reproducibility and classroom demonstrations, but it should not be used for production student data.",
        "Before publication, the authors should document data retention, consent, anonymization, and access controls for any participant study. The current manuscript includes these requirements as an ethics checklist rather than pretending they are already complete."
    ])

    add("24. Ethics and Responsible AI Boundary", [
        "The most important ethical decision in interViv is that the LLM does not judge candidates. It generates practice questions and reference material only. This avoids presenting non-deterministic model opinions as authoritative assessment.",
        "The platform should be described as readiness support, not hiring prediction. Company profiles are curated practice references. They are not exact hiring rubrics. Scores are formative feedback signals. They are not pass/fail hiring decisions.",
        "If this manuscript is submitted to IEEE Access, the acknowledgements should disclose AI-assisted drafting in accordance with current IEEE Access author guidance. Authors remain responsible for all claims, data, analysis, and final text."
    ])

    add("25. Threats to Validity", [
        "Internal validity threats include model-feature leakage, insufficient calibration for concise answers, and possible mismatch between fallback-bank ideal answers and live LLM-generated reference answers. Regression tests reduce but do not eliminate these risks.",
        "External validity threats are larger. The primary human baseline has only 30 answers, and persona validation is not a substitute for real students. A publishable educational-effectiveness claim requires a larger study with participant demographics, pre/post surveys, and independent human ratings.",
        "Construct validity threats concern the meaning of readiness. interViv measures answer quality, concept coverage, and practice progress. It does not directly measure hiring performance, job performance, or interviewer perception in real company interviews."
    ])

    add("26. Limitations", [
        "The current fallback question bank is useful but still modest. It contains 53 questions and some company-role warning mismatches. A stronger bank should include 100 to 300 reviewed questions with broader coding, system design, HR, and resume-based coverage.",
        "The classifier metrics are strong on the labelled training dataset, but they are not a substitute for whole-system validation. The scoring pipeline blends several deterministic signals; the combined pipeline should be evaluated against human ratings at the final-score level.",
        "Visual dashboard verification was previously limited by browser permissions. Automated build tests pass, but full accessibility and mobile visual QA should be repeated before publication screenshots are used."
    ])

    add("27. Proposed Student Study", [
        "A strong publication path is a 20 to 30 participant study with students preparing for placements or internships. Participants should complete a pre-survey measuring confidence in technical interviews, ability to explain solutions aloud, perceived readiness, and interview anxiety.",
        "Each participant should complete two or three interViv sessions. The system should log scores, guard triggers, missing concepts, selected company/role, question source, and roadmap recommendations. A post-survey should repeat the readiness and confidence items and ask about perceived fairness, usefulness, and clarity of feedback.",
        "The analysis should report pre/post changes, completion rate, score trend, weak-skill improvement, guard-trigger frequency, and qualitative themes. This would turn the current system paper into an empirical educational technology paper."
    ], table=[
        ["Measure", "Collection point", "Purpose"],
        ["Confidence score", "Pre and post", "Readiness change"],
        ["Session scores", "During use", "Practice progression"],
        ["Missing concepts", "Per round", "Learning gap analysis"],
        ["Perceived fairness", "Post survey", "Feedback acceptance"],
        ["Qualitative comments", "Post interview", "Design improvement"],
    ])

    add("28. Publication Strategy", [
        "IEEE Access is a plausible target for a longer systems manuscript because it accepts multidisciplinary technology articles and requires Word or LaTeX source plus matching PDF in the required template. A conference paper would usually require a much shorter version, often six to eight pages depending on the venue.",
        "The recommended strategy is to maintain this document as an extended manuscript, then produce two derivatives: a concise IEEE conference version and an IEEE Access version after completing the student study. The current draft can also serve as a thesis or project report.",
        "Before submission, the paper must be transferred into the official IEEE template selected for the venue, checked for grammar, references, author information, AI disclosure, figure resolution, and any institutional review requirements."
    ])

    add("29. Industry Relevance", [
        "The industry relevance of interViv is its operational design. It is not only a model experiment; it is a deployed-style platform with auth, persistence, routing, scoring, dashboards, fallback behavior, and deployment configuration. That makes it useful as a research prototype and a product prototype.",
        "The company-style and role-style practice structure reflects how students search for preparation material. The deterministic scoring boundary reflects industry needs for auditability and repeatability. The guard mechanism reflects production needs for adversarial and low-quality input handling.",
        "This combination gives interViv a practical niche: structured student practice with transparent evidence rather than black-box candidate judgment."
    ])

    add("30. Discussion", [
        "The main design lesson is that generative and evaluative functions should be separated in educational interview tools. LLMs are useful for generating varied, contextual prompts, but answer scoring should remain reproducible and inspectable when the platform influences learner confidence.",
        "The second lesson is that guardrails are not peripheral. They are central to score validity. Without an answer guard, random text or keyword stuffing can pollute score distributions and dashboards. interViv makes the guard a first-class pipeline stage.",
        "The third lesson is that dashboards need traceable evidence. A readiness score is only useful when it can be decomposed into concepts, keywords, structure, guard status, and next actions."
    ])

    add("31. Conclusion", [
        "interViv demonstrates a guarded architecture for LLM-generated adaptive mock interviews with deterministic scoring. The platform supports company-style, role-style, resume-aware practice while preserving a strict boundary: LLMs generate questions and references only; Python scores answers and computes feedback.",
        "Preliminary evidence shows a working implementation with broad automated tests, structured question-bank fallback, classifier validation metadata, primary human-baseline correlation, and guard stress tests. The next research step is a larger student-participant study and expanded human-rated answer set.",
        "The strongest publishable claim is therefore modest but valuable: interViv shows how generative practice content can be combined with deterministic assessment signals to provide explainable interview-readiness feedback for students."
    ])

    add("Appendix A. LLM Question JSON Contract", [
        "The LLM must return JSON only with the fields: question, ideal_answer, ideal_keywords, sub_domain, topic, difficulty, question_type, company, role, and followups.",
        "The prompt explicitly forbids scoring, judging, grading, evaluation, candidate feedback, pass/fail decisions, and hiring recommendations. If an LLM response fails schema parsing, the runtime falls back to the structured bank or legacy dataset/template fallback depending on configuration.",
        "The scoring system consumes ideal_answer and ideal_keywords as references. It does not consume LLM-generated scores because no such scores are allowed."
    ])

    add("Appendix B. Guard Rule Summary", [
        "The guard currently checks empty input, whitespace-only input, too-short answers, random character strings, low meaningful-word count, abnormal vowel ratio, repeated character ratio, repeated token ratio, keyboard spam, nonsense token patterns, question parroting, low-density filler, off-topic text, and keyword stuffing.",
        "The default user-facing message for incomplete or gibberish answers is: Your answer looks incomplete or gibberish. Please write a meaningful explanation.",
        "Guard reasons and caps are stored in the scoring breakdown and displayed in the dashboard."
    ])

    add("Appendix C. Scoring Formula", [
        "The final score formula is: final_score = 100 x (0.45 x semantic_or_lexical + 0.25 x classifier + 0.20 x keyword + 0.10 x tfidf) + KG_bonus + NER_bonus - penalties.",
        "The formula is currently encoded through the scoring schema module and pipeline. The schema exposes version rubric_v1, final-score weights, rubric weights, KG bonus maximum, and NER bonus parameters.",
        "Guard caps are applied as hard upper bounds after normal scoring. Rubric dimensions are capped as well so the report remains internally coherent."
    ])

    add("Appendix D. API Evidence Fields", [
        "The answer endpoint returns svm_label, nlp_score, kg_score, ner_entities, final_score, feedback, score_explanation, scoring_schema_version, rubric, concepts, guard, scoring_breakdown, guard_applied, next_question, next_difficulty, next_skill, adaptive_target, current_skill, elo_after, difficulty_change, total_rounds, and session_complete.",
        "The dashboard route sanitizes session rounds and attaches ideal_answer, ideal_keywords, topic, sub_domain, question_type, company, role, followups, performance band, and confidence band.",
        "These fields make the dashboard auditable and support later longitudinal analysis."
    ])

    add("Appendix E. Reproducibility Checklist", [
        "The project can be run locally with INTERVIV_USE_MEMORY_DB=true and QUESTION_GENERATION_MODE=llm_csv_fallback. The full test suite is run with .venv/bin/python -m pytest tests/ -q. The question-bank audit is run with .venv/bin/python scripts/question_audit.py --json docs/question_audit_research.json.",
        "The manuscript was generated from repository artifacts rather than manually copied screenshots. Figures are generated by scripts/build_ieee_research_paper.py and stored under docs/research_paper/figures.",
        "Before IEEE submission, regenerate the paper after adding final student-study results, update author names and affiliations, and transfer the source into the official IEEE template."
    ])

    add("Appendix F. Suggested Survey Instrument", [
        "Pre-survey items: I feel confident explaining technical concepts aloud; I can identify my weak interview topics; I feel ready for my selected target role; I know how to structure answers under time pressure; I feel anxious about technical interviews.",
        "Post-survey items: The questions felt relevant to my target role; the feedback was understandable; the dashboard helped me choose what to study next; the score felt fair; I would use the platform again before interviews.",
        "Responses can use a five-point Likert scale. Optional open-ended questions should ask what feedback was most useful, what felt unrealistic, and what should be improved."
    ])

    add("Appendix G. IEEE Submission Notes", [
        "IEEE Access requires a double-column, single-spaced manuscript using the required template, and both source and PDF files are required. IEEE also asks authors to disclose AI-generated text use where applicable. These requirements should be checked again immediately before submission because author instructions may change.",
        "This manuscript is an extended draft and evidence package. It is not a guarantee of acceptance and should not be submitted until all placeholders, ethics review needs, author biographies, final references, and template formatting are complete.",
        "For a shorter IEEE conference submission, compress this manuscript to the core architecture, scoring method, evaluation, and results sections."
    ])

    add("Acknowledgements and AI Disclosure", [
        "The authors acknowledge the open-source software ecosystem used to implement and evaluate the prototype. AI-assisted drafting was used to prepare portions of this manuscript text and structure; the authors are responsible for verifying all claims, citations, data, and final language before submission. No AI system was used to score candidate answers in interViv.",
        "Replace this paragraph with the final venue-specific disclosure required by the selected IEEE venue."
    ], page_break=False)

    add("References", references(), page_break=False)

    add("Author Biographies", [
        "Author 1 biography placeholder. Include education, affiliation, research interests, and contact information as required by the selected IEEE venue.",
        "Author 2 biography placeholder. Add ORCID and photo if required by the venue.",
        "Corresponding author placeholder. IEEE Access requires biographies for all authors at submission."
    ], page_break=False)

    return sections


def references() -> list[str]:
    return [
        "[1] IEEE Access, Submission Guidelines for Authors, 2026. [Online]. Available: https://ieeeaccess.ieee.org/guide-for-authors/submission-guidelines/",
        "[2] IEEE Access, Preparing Your Article, 2026. [Online]. Available: https://ieeeaccess.ieee.org/authors/preparing-your-article/",
        "[3] IEEE Author Center Conferences, Authoring Tools and Templates, 2026. [Online]. Available: https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/authoring-tools-and-templates/",
        "[4] N. Gomez, S. S. Batham, M. Volonte, and T. D. Do, Virtual Interviewers, Real Results: Exploring AI-Driven Mock Technical Interviews on Student Readiness and Confidence, arXiv:2506.16542, 2025.",
        "[5] S. S. Mucciaccia, T. M. Paixao, F. W. Mutz, C. S. Badue, A. F. de Souza, and T. Oliveira-Santos, Automatic Multiple-Choice Question Generation and Evaluation Systems Based on LLM: A Study Case With University Resolutions, in Proc. COLING, pp. 2246-2260, 2025.",
        "[6] A. Panfilova, V. Bolshev, M. Mozikov, et al., The AI interviewer: multi-faceted evaluation of adaptive questioning by large language models, Scientific Reports, 2026, doi: 10.1038/s41598-026-46517-7.",
        "[7] S. Haller, A. Aldea, C. Seifert, and N. Strisciuglio, Survey on Automated Short Answer Grading with Deep Learning: from Word Embeddings to Transformers, arXiv:2204.03503, 2022.",
        "[8] G. Meyer, P. Breuer, and J. Fuerst, ASAG2024: A Combined Benchmark for Short Answer Grading, arXiv:2409.18596, 2024.",
        "[9] N. Reimers and I. Gurevych, Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks, in Proc. EMNLP-IJCNLP, pp. 3982-3992, 2019.",
        "[10] interViv project repository artifact, modules/model_metadata.json, generated Apr. 28, 2026.",
        "[11] interViv project repository artifact, docs/human_baseline_report.md, generated May 30, 2026.",
        "[12] interViv project repository artifact, docs/persona_validation_report.md, generated Apr. 25, 2026.",
        "[13] interViv project repository artifact, docs/scoring_rubric.md, generated May 30, 2026.",
        "[14] interViv project repository artifact, docs/question_bank_strategy.md, generated May 30, 2026.",
        "[15] interViv project repository artifact, docs/question_audit_research.json, generated June 9, 2026.",
    ]


class DocxBuilder:
    def __init__(self) -> None:
        self.body: list[str] = []
        self.rels: list[str] = []
        self.image_id = 1
        self.rel_id = 1
        self.media: list[tuple[Path, str]] = []

    def paragraph(self, text: str = "", style: str = "BodyText", bold: bool = False, italic: bool = False, align: str | None = None) -> None:
        ppr = f'<w:pPr><w:pStyle w:val="{style}"/>'
        if align:
            ppr += f'<w:jc w:val="{align}"/>'
        ppr += "</w:pPr>"
        rpr = ""
        if bold or italic:
            rpr = "<w:rPr>" + ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "") + "</w:rPr>"
        self.body.append(f"<w:p>{ppr}<w:r>{rpr}<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>")

    def heading(self, text: str, level: int = 1) -> None:
        self.paragraph(text, style=f"Heading{level}")

    def page_break(self) -> None:
        self.body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def table(self, rows: list[list[str]]) -> None:
        if not rows:
            return
        cols = len(rows[0])
        width = 9360
        col_width = max(900, width // cols)
        grid = "".join(f'<w:gridCol w:w="{col_width}"/>' for _ in range(cols))
        xml = [f'<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="{width}" w:type="dxa"/><w:tblInd w:w="120" w:type="dxa"/><w:tblBorders><w:top w:val="single" w:sz="4" w:color="B7C9DA"/><w:left w:val="single" w:sz="4" w:color="B7C9DA"/><w:bottom w:val="single" w:sz="4" w:color="B7C9DA"/><w:right w:val="single" w:sz="4" w:color="B7C9DA"/><w:insideH w:val="single" w:sz="4" w:color="D4DEE8"/><w:insideV w:val="single" w:sz="4" w:color="D4DEE8"/></w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid>']
        for r_idx, row in enumerate(rows):
            xml.append("<w:tr>")
            for cell in row:
                fill = '<w:shd w:fill="E8EEF5"/>' if r_idx == 0 else ""
                xml.append(f'<w:tc><w:tcPr><w:tcW w:w="{col_width}" w:type="dxa"/>{fill}<w:tcMar><w:top w:w="90" w:type="dxa"/><w:bottom w:w="90" w:type="dxa"/><w:start w:w="120" w:type="dxa"/><w:end w:w="120" w:type="dxa"/></w:tcMar></w:tcPr>')
                style = "TableHeader" if r_idx == 0 else "TableText"
                self.body.append("")
                xml.append(f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t xml:space="preserve">{escape(str(cell))}</w:t></w:r></w:p></w:tc>')
            xml.append("</w:tr>")
        xml.append("</w:tbl>")
        self.body.append("".join(xml))

    def image(self, path: Path, caption: str, width_in: float = 5.9) -> None:
        media_name = f"image{self.image_id}{path.suffix.lower()}"
        rel = f"rId{self.rel_id}"
        self.rel_id += 1
        self.image_id += 1
        self.media.append((path, media_name))
        self.rels.append(f'<Relationship Id="{rel}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{media_name}"/>')
        with Image.open(path) as img:
            w, h = img.size
        height_in = width_in * h / w
        cx = int(width_in * 914400)
        cy = int(height_in * 914400)
        docpr_id = self.image_id + 100
        drawing = f'''
<w:p><w:pPr><w:pStyle w:val="Figure"/></w:pPr><w:r><w:drawing>
<wp:inline distT="0" distB="0" distL="0" distR="0">
<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>
<wp:docPr id="{docpr_id}" name="Figure {docpr_id}"/><wp:cNvGraphicFramePr/>
<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:pic><pic:nvPicPr><pic:cNvPr id="{docpr_id}" name="{escape(media_name)}"/><pic:cNvPicPr/></pic:nvPicPr>
<pic:blipFill><a:blip r:embed="{rel}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
</pic:pic></a:graphicData></a:graphic>
</wp:inline></w:drawing></w:r></w:p>'''
        self.body.append(drawing)
        self.paragraph(caption, style="Caption")

    def build_document_xml(self) -> str:
        sect = '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" w:header="720" w:footer="720" w:gutter="0"/><w:cols w:space="720"/></w:sectPr>'
        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:w10="urn:schemas-microsoft-com:office:word" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" mc:Ignorable="w14 w15 wp14"><w:body>{''.join(self.body)}{sect}</w:body></w:document>'''

    def write(self, path: Path) -> None:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types_xml(self.media))
            zf.writestr("_rels/.rels", package_rels_xml())
            zf.writestr("docProps/core.xml", core_xml())
            zf.writestr("docProps/app.xml", app_xml())
            zf.writestr("word/document.xml", self.build_document_xml())
            zf.writestr("word/styles.xml", styles_xml())
            zf.writestr("word/settings.xml", settings_xml())
            zf.writestr("word/_rels/document.xml.rels", document_rels_xml(self.rels))
            for source, media_name in self.media:
                zf.write(source, f"word/media/{media_name}")


def content_types_xml(media: list[tuple[Path, str]]) -> str:
    image_defaults = ""
    exts = sorted({name.split(".")[-1] for _, name in media})
    for ext in exts:
        ctype = "image/png" if ext == "png" else "image/jpeg"
        image_defaults += f'<Default Extension="{ext}" ContentType="{ctype}"/>'
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
{image_defaults}
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''


def package_rels_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''


def document_rels_xml(image_rels: list[str]) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{''.join(image_rels)}
</Relationships>'''


def styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="21"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="160"/><w:jc w:val="center"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/><w:color w:val="0B2545"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="120"/><w:jc w:val="center"/></w:pPr><w:rPr><w:i/><w:sz w:val="22"/><w:color w:val="555555"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="BodyText"><w:name w:val="Body Text"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr><w:rPr><w:sz w:val="21"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="Heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="30"/><w:color w:val="2E74B5"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="Heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="180" w:after="100"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/><w:color w:val="1F4D78"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="Caption"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="60" w:after="140"/><w:jc w:val="center"/></w:pPr><w:rPr><w:i/><w:sz w:val="18"/><w:color w:val="555555"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Figure"><w:name w:val="Figure"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="100" w:after="40"/><w:jc w:val="center"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="TableText"><w:name w:val="Table Text"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="40" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="18"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableHeader"><w:name w:val="Table Header"/><w:basedOn w:val="TableText"/><w:rPr><w:b/><w:sz w:val="18"/><w:color w:val="0B2545"/></w:rPr></w:style>
</w:styles>'''


def settings_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:zoom w:percent="100"/><w:defaultTabStop w:val="720"/></w:settings>'''


def core_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>interViv IEEE Extended Manuscript</dc:title><dc:creator>interViv authors</dc:creator><cp:keywords>interview readiness; deterministic scoring; LLM question generation</cp:keywords><dc:description>Extended IEEE-style research manuscript draft for interViv.</dc:description></cp:coreProperties>'''


def app_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Codex OOXML builder</Application></Properties>'''


def build_docx(sections: list[dict]) -> None:
    b = DocxBuilder()
    b.paragraph("interViv: A Guarded Deterministic Scoring Framework for LLM-Generated Adaptive Mock Interviews", style="Title")
    b.paragraph("IEEE Access-style extended manuscript draft | Replace author block before submission", style="Subtitle")
    b.paragraph("Authors: Praneet Sharma et al. | Affiliation placeholders | Corresponding author placeholder", style="Subtitle")
    b.paragraph("Manuscript status: pre-submission system paper with preliminary evaluation. This draft must be transferred into the official IEEE template before submission.", style="BodyText", italic=True)
    b.page_break()

    for index, section in enumerate(sections, 1):
        title = section["title"]
        b.heading(title, 1)
        for para in section["paragraphs"]:
            b.paragraph(para)
        if section.get("table"):
            b.table(section["table"])
        if section.get("figure"):
            fig_label = f"Fig. {index}. {title}."
            b.image(section["figure"], fig_label)
        if section.get("page_break", True):
            b.page_break()
    b.write(DOCX_PATH)


def build_markdown(sections: list[dict]) -> None:
    lines = [
        "# interViv: A Guarded Deterministic Scoring Framework for LLM-Generated Adaptive Mock Interviews",
        "",
        "IEEE Access-style extended manuscript draft. Replace author metadata before submission.",
        "",
    ]
    for section in sections:
        lines.append(f"## {section['title']}")
        lines.append("")
        for para in section["paragraphs"]:
            lines.append(para)
            lines.append("")
        if section.get("table"):
            table = section["table"]
            lines.append("| " + " | ".join(table[0]) + " |")
            lines.append("| " + " | ".join(["---"] * len(table[0])) + " |")
            for row in table[1:]:
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")
        if section.get("figure"):
            rel = section["figure"].relative_to(OUT_DIR)
            lines.append(f"![{section['title']}]({rel})")
            lines.append("")
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def draw_pdf_page(pdf: PdfPages, title: str, body_lines: list[str], page_no: int, image: Path | None = None) -> int:
    fig = plt.figure(figsize=(8.5, 11), dpi=120)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.5, 0.965, title, ha="center", va="top", fontsize=14, fontweight="bold", color="#0B2545")
    y = 0.91
    if image:
        try:
            img = plt.imread(image)
            ax_img = fig.add_axes([0.13, 0.52, 0.74, 0.32])
            ax_img.imshow(img)
            ax_img.axis("off")
            y = 0.47
        except Exception:
            pass
    for line in body_lines:
        if y < 0.08:
            ax.text(0.5, 0.035, f"{page_no}", ha="center", fontsize=9, color="#666666")
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            page_no += 1
            fig = plt.figure(figsize=(8.5, 11), dpi=120)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.axis("off")
            ax.text(0.5, 0.965, title + " (continued)", ha="center", va="top", fontsize=14, fontweight="bold", color="#0B2545")
            y = 0.91
        ax.text(0.10, y, line, ha="left", va="top", fontsize=9.2, color="#111111")
        y -= 0.026
    ax.text(0.5, 0.035, f"{page_no}", ha="center", fontsize=9, color="#666666")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)
    return page_no + 1


def build_pdf(sections: list[dict]) -> int:
    page_no = 1
    with PdfPages(PDF_PATH) as pdf:
        title_lines = [
            "interViv: A Guarded Deterministic Scoring Framework for",
            "LLM-Generated Adaptive Mock Interviews",
            "",
            "IEEE Access-style extended manuscript draft.",
            "Replace author metadata, affiliation, ORCID, biographies, and venue template before submission.",
        ]
        page_no = draw_pdf_page(pdf, "interViv Extended Manuscript", title_lines, page_no)
        for section in sections:
            body: list[str] = []
            for para in section["paragraphs"]:
                body.extend(textwrap.wrap(para, width=105))
                body.append("")
            if section.get("table"):
                body.append("Table:")
                for row in section["table"]:
                    body.extend(textwrap.wrap(" | ".join(row), width=105))
            page_no = draw_pdf_page(pdf, section["title"], body, page_no, section.get("figure"))
    return page_no - 1


def validate_docx(path: Path) -> None:
    with zipfile.ZipFile(path) as zf:
        required = {
            "[Content_Types].xml",
            "_rels/.rels",
            "word/document.xml",
            "word/styles.xml",
            "word/_rels/document.xml.rels",
        }
        missing = required - set(zf.namelist())
        if missing:
            raise RuntimeError(f"DOCX missing required parts: {sorted(missing)}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = load_metrics()
    figures = make_figures(metrics)
    sections = paper_sections(metrics, figures)
    build_docx(sections)
    build_markdown(sections)
    page_count = build_pdf(sections)
    validate_docx(DOCX_PATH)
    manifest = {
        "docx": str(DOCX_PATH),
        "pdf": str(PDF_PATH),
        "markdown": str(MD_PATH),
        "figures": {key: str(value) for key, value in figures.items()},
        "pdf_pages": page_count,
        "sections": len(sections),
        "notes": "DOCX package structure validated. Full visual DOCX render was not performed because LibreOffice is unavailable in this environment.",
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
