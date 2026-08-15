"""Build the anonymous six-page CINS 2026 interViv manuscript candidate.

The paper is generated only from frozen grader-lab artifacts. It does not run
benchmarks, call external services, or modify production application logic.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = ROOT / "docs" / "research_paper"
FIGURE_DIR = PAPER_DIR / "figures"
RESULTS_DIR = ROOT / "research" / "grader_lab" / "results"
DOCX_PATH = PAPER_DIR / "interViv_cins2026_anonymous.docx"
MD_PATH = PAPER_DIR / "interViv_cins2026_anonymous.md"
FIGURE_PATH = FIGURE_DIR / "cins_fig01_diagnostic_pipeline.png"

PRIMARY_RUN = "grader-lab-20260815T160016Z"
ABLATION_RUN = "grader-lab-20260815T161227Z"
ERROR_RUN = "grader-lab-20260815T161440Z"
COMMIT = "8758ecfed5171176add2d1905173aeac58ee914a"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
CLASSIFIER_VERSION = "LogisticRegression 1.1.0"
CLASSIFIER_SHA = "2897c8cc6283cbdb4815a78182188ea60c17b39876feefa2d67919f065f16dd7"


@dataclass(frozen=True)
class Section:
    title: str
    paragraphs: tuple[str, ...]
    subsections: tuple[tuple[str, tuple[str, ...]], ...] = ()


ABSTRACT = (
    "Automated interview-practice systems can produce confident scores without "
    "showing whether those scores generalize or which evidence supports their "
    "feedback. We evaluate interViv's current deterministic short-answer scorer "
    "as a diagnostic component rather than as a learner-readiness predictor. A "
    "reproducible grader lab compares lexical similarity, a pinned semantic "
    "similarity plus contradiction heuristic, and the current guarded pipeline "
    "on the five-way SciEntsBank (n=5,835) and BEETLE (n=1,258) Core test sets. "
    "interViv reaches macro-F1 0.246 and 0.161, below the semantic baseline's "
    "0.335 and 0.277. It has the lowest off-topic false-positive rates (0.009 and "
    "0.007) but also low off-topic recall (0.062 and 0.010), and it exposes no "
    "contradiction signal (0/894 detected). Feedback statements have complete "
    "structural evidence identifiers, but this does not establish citation "
    "correctness. A four-case follow-up result is reported only as a synthetic "
    "pilot. Ablations indicate domain-sensitive weighting: removing the "
    "classifier aggregation term improves macro-F1 on both benchmarks. These "
    "results reject broad superiority claims and identify calibration, "
    "contradiction handling, and human validation as prerequisites for stronger "
    "educational claims."
)

KEYWORDS = (
    "automated short-answer grading; diagnostic feedback; auditability; "
    "technical interview practice; evidence tracing; benchmark evaluation"
)

SECTIONS = (
    Section(
        "I. INTRODUCTION",
        (
            "Practice systems for technical interviews combine two tasks that "
            "should be evaluated separately: generating a useful question and "
            "judging the learner's response. A fluent prompt generator can "
            "increase variety, but a scoring component influences what the "
            "learner studies next. That component therefore needs external "
            "benchmark evidence, explicit failure modes, and a trace from each "
            "feedback statement to the scoring evidence that licensed it.",
            "interViv is an interview-practice prototype whose current scorer "
            "combines semantic, classifier, keyword, TF-IDF, knowledge-graph, "
            "entity, and anti-gaming signals. Earlier descriptions emphasized "
            "the complete application and small internal validation exercises. "
            "This paper narrows the contribution to the diagnostic scorer. We "
            "exclude learner-readiness improvement, hiring validity, and the "
            "non-blinded pilot from the empirical claim set.",
            "We ask three questions. RQ1: how does the current scorer generalize "
            "relative to lexical and semantic baselines on external five-way "
            "short-answer grading? RQ2: what safety-auditability trade-off is "
            "visible in off-topic errors, contradiction detection, and evidence "
            "citations? RQ3: can exact competency-gap resolution be measured in "
            "a deliberately limited synthetic follow-up pilot?",
            "The contributions are: (1) a shared-schema, manifest-stamped grader "
            "lab; (2) an external comparison and research-only component "
            "ablation of the current pipeline; (3) explicit evidence-citation "
            "and exact-gap-resolution metrics; and (4) a negative result showing "
            "where the present scorer is not yet competitive."
        ),
    ),
    Section(
        "II. RELATED WORK",
        (),
        (
            (
                "A. Automated short-answer grading",
                (
                    "SciEntsBank and BEETLE were consolidated in SemEval-2013 "
                    "Task 7 as five-way student-response classification data "
                    "[1]. Representation-based grading progressed from lexical "
                    "matching toward contextual encoders [2], including "
                    "Sentence-BERT [3]. ASAG2024 highlights the continued "
                    "difficulty of cross-question and cross-domain "
                    "generalization [4]. Recent response-level studies show "
                    "that aggregate metrics conceal difficulty-dependent "
                    "collapse [5] and mid-range degradation [6]. We therefore "
                    "report accuracy and macro-F1 together with targeted safety "
                    "and evidence metrics rather than treating one score as a "
                    "complete evaluation."
                ),
            ),
            (
                "B. LLM grading and auditability",
                (
                    "LLM judges can scale rubric application, but reliability, "
                    "bias, prompt dependence, and interpretability remain open "
                    "problems [7], [8]. A 2026 rubric-guided study found gains "
                    "for a larger model but degradation for a smaller model; it "
                    "also observed rationales containing hallucinated rubric "
                    "elements [7]. Cross-disciplinary ChatGPT grading similarly "
                    "showed consistency alongside leniency and compressed grade "
                    "distributions [9]. These findings motivate explicit "
                    "evidence identifiers, but identifiers alone cannot prove "
                    "that a feedback claim is warranted."
                ),
            ),
            (
                "C. Adaptive interview systems",
                (
                    "AI interviewer research has begun to evaluate adaptive "
                    "questioning at scale. Panfilova et al. compare six models "
                    "using 2,900 human annotations [10], while recent technical "
                    "mock-interview work studies readiness and confidence [11]. "
                    "Those studies focus on interviewing behavior or learner "
                    "experience. Our narrower unit is the diagnostic judgment "
                    "attached to one answer and, synthetically, the resolution "
                    "of one identified competency gap."
                ),
            ),
        ),
    ),
    Section(
        "III. DIAGNOSTIC SCORING AND EVIDENCE",
        (),
        (
            (
                "A. Scoring boundary",
                (
                    "The research adapter calls the existing production scorer "
                    "without changing application logic. For an answer a and "
                    "reference r, the pipeline computes a bounded semantic "
                    "component, a saved logistic-regression component, keyword "
                    "coverage, and TF-IDF similarity. Knowledge-graph and entity "
                    "bonuses are added, penalties are subtracted, and any "
                    "anti-gaming cap is applied last. The saved classifier also "
                    "consumes a semantic-derived feature; consequently, the "
                    "component ablations are sensitivity tests rather than "
                    "causal isolation."
                ),
            ),
            (
                "B. Feedback evidence contract",
                (
                    "Every emitted feedback statement can list evidence IDs "
                    "from an available set. Rubric evidence uses rubric.* and "
                    "concept evidence uses concept.*. Evidence-citation "
                    "completeness is the fraction of feedback statements citing "
                    "at least one valid rubric or concept ID. Unsupported-"
                    "feedback rate is computed separately from whether the "
                    "citation is explicit. Both are structural checks; human "
                    "adjudication is required to establish substantive support "
                    "or pedagogical usefulness."
                ),
            ),
            (
                "C. Follow-up resolution",
                (
                    "A follow-up record names the exact trigger gap and whether "
                    "the second answer resolves it. Resolved-evidence rate is "
                    "the accuracy of that exact-gap judgment. SciEntsBank and "
                    "BEETLE are single-turn data, so this metric is never "
                    "reported as benchmark validation; all corresponding rows "
                    "carry pilot_synthetic=true."
                ),
            ),
        ),
    ),
    Section(
        "IV. EVALUATION",
        (),
        (
            (
                "A. Data and labels",
                (
                    "We normalize the official SemEval five-way Core test "
                    "partitions to a shared JSONL schema: correct, partially "
                    "correct/incomplete, contradictory, irrelevant, and "
                    "non-domain. SciEntsBank contributes 5,835 examples and "
                    "BEETLE 1,258. Their organizer package is CC BY-SA 3.0. An "
                    "internal 17-example set covers off-topic, vague, keyword-"
                    "stuffed, contradictory, partial, clean-control, and four "
                    "follow-up cases. RiceChem is absent and recorded as "
                    "pending_access rather than silently omitted."
                ),
            ),
            (
                "B. Baselines",
                (
                    "Lexical similarity uses content-token F1. The semantic "
                    "baseline uses the pinned all-MiniLM-L6-v2 checkpoint plus "
                    "an inspectable negation/antonym heuristic; it is not a "
                    "trained NLI model. The interViv baseline uses the current "
                    "scorer and guards. A structured LLM rubric-judge interface "
                    "exists only as a disabled configuration stub. It is marked "
                    "deferred, made zero API/network calls, and leaves this "
                    "comparison incomplete."
                ),
            ),
            (
                "C. Metrics and protocol",
                (
                    "We report five-way accuracy and macro-F1; off-topic recall "
                    "and false-positive rate; contradiction recall; unsupported-"
                    "feedback rate; and evidence-citation completeness. The "
                    "synthetic follow-up pilot additionally reports exact-gap "
                    "resolution. All models run offline. The clean run records "
                    "7,110 applicable interViv predictions, 7,110 semantic "
                    "function calls, and zero lexical fallbacks. No test-set "
                    "tuning was performed after inspecting the results."
                ),
            ),
            (
                "D. Reproducibility manifest",
                (
                    "The primary run is " + PRIMARY_RUN + "; ablation is "
                    + ABLATION_RUN + "; and contradiction analysis is "
                    + ERROR_RUN + ". All record commit " + COMMIT[:12] +
                    " (dirty research worktree), dataset versions and SHA-256 "
                    "digests, Python/runtime versions, embedding revision "
                    + EMBEDDING_REVISION[:12] + ", and classifier artifact "
                    + CLASSIFIER_SHA[:12] + ". The frozen CSV/Markdown hashes "
                    "are listed in the supplemental experiment-freeze file."
                ),
            ),
        ),
    ),
    Section(
        "V. RESULTS",
        (),
        (
            (
                "A. Five-way grading",
                (
                    "On SciEntsBank, interViv improves accuracy over the lexical "
                    "baseline (0.373 vs. 0.358) but is below the semantic "
                    "baseline (0.399). Its macro-F1 (0.246) is effectively the "
                    "lexical result (0.245) and below semantic (0.335). On "
                    "BEETLE, interViv is worse in both accuracy (0.170) and "
                    "macro-F1 (0.161) than lexical (0.338, 0.274) and semantic "
                    "(0.304, 0.277). RQ1 therefore has a negative answer: the "
                    "current aggregate does not generalize competitively across "
                    "the two benchmark domains."
                ),
            ),
            (
                "B. Safety and contradictions",
                (
                    "interViv produces the lowest off-topic false-positive rate "
                    "on both datasets, but this apparent safety is coupled to "
                    "very low detection recall. SciEntsBank recall/FPR is "
                    "0.062/0.009 versus lexical 0.407/0.141; BEETLE is "
                    "0.010/0.007 versus lexical 0.727/0.085. The semantic "
                    "baseline offers a less extreme trade-off. interViv detects "
                    "0/539 SciEntsBank and 0/355 BEETLE contradictions because "
                    "the current adapter exposes no contradiction output. The "
                    "semantic heuristic detects 170/539 and 148/355. Of its 576 "
                    "misses, automatic rules resolve only one as a factual "
                    "reversal; 575 require human review."
                ),
            ),
            (
                "C. Auditability and follow-up pilot",
                (
                    "interViv feedback has 100% evidence-citation completeness "
                    "and zero automatically unsupported claims in this run. "
                    "However, the semantic research baseline also reaches 100% "
                    "because its adapter emits evidence IDs, and the deferred "
                    "LLM judge prevents an opaque-judge comparison. The result "
                    "supports only a structural traceability claim. On four "
                    "internal follow-up cases, interViv and the semantic "
                    "baseline each judge exact-gap resolution correctly in "
                    "4/4 cases; lexical obtains 3/4. This is synthetic-only "
                    "pilot evidence, not a learner-outcome result."
                ),
            ),
            (
                "D. Component sensitivity",
                (
                    "Removing the classifier final-score term improves macro-F1 "
                    "from 0.246 to 0.251 on SciEntsBank and from 0.161 to 0.205 "
                    "on BEETLE. Removing semantic evidence lowers SciEntsBank "
                    "macro-F1 to 0.231 but raises BEETLE to 0.179. Removing "
                    "guards raises SciEntsBank macro-F1 to 0.258 yet lowers "
                    "BEETLE to 0.128 and eliminates the explicit off-topic flag. "
                    "The differences indicate domain-sensitive calibration and "
                    "a measurable guard trade-off, not one universally dominant "
                    "component."
                ),
            ),
        ),
    ),
    Section(
        "VI. DISCUSSION AND LIMITATIONS",
        (
            "The strongest current result is diagnostic rather than "
            "promotional. Semantic execution is verified, so the poor BEETLE "
            "result cannot be explained by a silent lexical fallback. The "
            "combination of low false positives and very low recall indicates "
            "that the guard is conservative. The classifier-term ablation and "
            "opposite semantic effect across domains identify calibration as a "
            "priority for future work. Contradiction detection is a missing "
            "capability at the scorer-output boundary, not merely a threshold "
            "problem.",
            "The evaluation has several limits. First, benchmark labels do not "
            "cleanly isolate low effort, so the off-topic result cannot be "
            "generalized to every low-effort answer. Second, the contradiction "
            "taxonomy is almost entirely unresolved without human review. "
            "Third, citation completeness checks the presence of valid IDs, not "
            "the truth, sufficiency, or pedagogical quality of a statement. "
            "Fourth, the four follow-ups are constructed examples. Fifth, the "
            "structured LLM judge is deferred and RiceChem is pending, so the "
            "comparison is explicitly incomplete.",
            "No result here establishes improved readiness, retention, fairness "
            "across learner groups, or hiring validity. Those claims require a "
            "consented longitudinal study with blinded human adjudication. The "
            "earlier non-blinded pilot is excluded from the main evidence. "
            "Future research should add an independently adjudicated "
            "contradiction set, calibrate on development data without touching "
            "the test partitions, implement the structured-judge comparison "
            "under an approved cost/privacy policy, and collect real follow-up "
            "conversations."
        ),
    ),
    Section(
        "VII. CONCLUSION",
        (
            "A reproducible evaluation of interViv's current diagnostic scorer "
            "finds complete structural evidence tracing and low off-topic false "
            "positives, but weak off-topic recall, no contradiction output, and "
            "substantial cross-domain calibration failure. The semantic "
            "baseline outperforms the current aggregate on macro-F1 in both "
            "external benchmarks. Treating these as first-class negative "
            "results converts an application description into a falsifiable "
            "research artifact. Stronger claims about LLM comparison, follow-up "
            "resolution, or learner readiness remain deferred until the missing "
            "baselines and human studies exist."
        ),
    ),
)

REFERENCES = (
    "[1] M. Dzikovska et al., “SemEval-2013 Task 7: The Joint Student Response Analysis and 8th Recognizing Textual Entailment Challenge,” in Proc. SemEval, 2013, pp. 263–274.",
    "[2] S. Haller, A. Aldea, C. Seifert, and N. Strisciuglio, “Survey on automated short answer grading with deep learning: From word embeddings to transformers,” arXiv:2204.03503, 2022.",
    "[3] N. Reimers and I. Gurevych, “Sentence-BERT: Sentence embeddings using Siamese BERT-networks,” in Proc. EMNLP-IJCNLP, 2019, pp. 3982–3992.",
    "[4] G. Meyer, P. Breuer, and J. Fürst, “ASAG2024: A combined benchmark for short answer grading,” in Proc. SIGCSE Virtual, 2024, doi:10.1145/3649409.3691083.",
    "[5] L. Cong, S. Hahn, S. Gombert, L. Camus, H. Drachsler, and U. Kroehne, “Estimating LLM grading ability and response difficulty in automatic short answer grading via item response theory,” in Proc. BEA, 2026, pp. 259–271, doi:10.18653/v1/2026.bea-1.19.",
    "[6] A. Gurin Schleifer, M. Ariely, B. Beigman Klebanov, A. Salman, and G. Alexandron, “Quality-conditioned agreement in automated short answer scoring,” in Proc. BEA, 2026, pp. 432–442, doi:10.18653/v1/2026.bea-1.29.",
    "[7] S. Haque, D. Hettiachchi, and D. Beck, “Rubric-guided prompting for automatic assessment scoring,” in Proc. L@S, 2026, pp. 428–432, doi:10.1145/3774398.3811581.",
    "[8] J. Gu et al., “A survey on LLM-as-a-judge,” The Innovation, vol. 7, no. 6, Art. 101253, 2026, doi:10.1016/j.xinn.2025.101253.",
    "[9] R. Awashreh, H. Al Ghunaimi, and S. AlGhenaimi, “Reliable but not rigorous: Evaluating ChatGPT's reliability, validity, and bias in automated academic grading,” Social Sciences & Humanities Open, Art. 102788, 2026, doi:10.1016/j.ssaho.2026.102788.",
    "[10] A. Panfilova et al., “The AI interviewer: Multi-faceted evaluation of adaptive questioning by large language models,” Scientific Reports, vol. 16, Art. 20257, 2026, doi:10.1038/s41598-026-46517-7.",
    "[11] N. Gomez, S. S. Batham, M. Volonte, and T. D. Do, “Virtual interviewers, real results: Exploring AI-driven mock technical interviews on student readiness and confidence,” arXiv:2506.16542, 2025.",
)


def _read_results() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    with (RESULTS_DIR / "grader_lab_results.csv").open(encoding="utf-8", newline="") as handle:
        primary = list(csv.DictReader(handle))
    with (RESULTS_DIR / "interviv_ablation_results.csv").open(encoding="utf-8", newline="") as handle:
        ablation = list(csv.DictReader(handle))
    if {row["run_id"] for row in primary} != {PRIMARY_RUN}:
        raise RuntimeError("Primary result run does not match the frozen manuscript run")
    if {row["run_id"] for row in ablation} != {ABLATION_RUN}:
        raise RuntimeError("Ablation result run does not match the frozen manuscript run")
    return primary, ablation


def _metric(rows: list[dict[str, str]], dataset: str, method: str, metric: str) -> str:
    key = "baseline" if "baseline" in rows[0] else "configuration"
    matches = [
        row["value"]
        for row in rows
        if row["dataset"] == dataset and row[key] == method and row["metric"] == metric
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one result for {dataset}/{method}/{metric}")
    return f"{float(matches[0]):.3f}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_figure() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (1450, 690), "white")
    draw = ImageDraw.Draw(canvas)
    font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    bold_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    font = ImageFont.truetype(font_path, 23)
    small = ImageFont.truetype(font_path, 20)
    title_font = ImageFont.truetype(bold_path, 29)

    def center_text(box: tuple[int, int, int, int], label: str, text_font) -> None:
        bounds = draw.multiline_textbbox((0, 0), label, font=text_font, align="center", spacing=4)
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        x1, y1, x2, y2 = box
        draw.multiline_text(
            ((x1 + x2 - width) / 2, (y1 + y2 - height) / 2),
            label,
            fill="#172B3A",
            font=text_font,
            align="center",
            spacing=4,
        )

    def arrow(start: tuple[int, int], end: tuple[int, int]) -> None:
        draw.line((start, end), fill="#264A68", width=4)
        ex, ey = end
        if abs(end[0] - start[0]) >= abs(end[1] - start[1]):
            direction = 1 if end[0] > start[0] else -1
            points = [(ex, ey), (ex - 14 * direction, ey - 9), (ex - 14 * direction, ey + 9)]
        else:
            direction = 1 if end[1] > start[1] else -1
            points = [(ex, ey), (ex - 9, ey - 14 * direction), (ex + 9, ey - 14 * direction)]
        draw.polygon(points, fill="#264A68")

    boxes = [
        ((35, 170, 240, 305), "Answer\n+ reference", "#E8F0F7"),
        ((300, 170, 505, 305), "Anti-gaming\nguard", "#FDECEC"),
        ((565, 170, 875, 305), "Semantic • classifier\nkeyword • TF-IDF", "#E8F0F7"),
        ((935, 170, 1140, 305), "Score +\nfeedback", "#EAF5EE"),
        ((1200, 170, 1415, 305), "Rubric /\nconcept IDs", "#FFF6D9"),
        ((935, 435, 1140, 570), "Named\ncompetency gap", "#EAF5EE"),
        ((1200, 435, 1415, 570), "Follow-up\nresolution", "#FFF6D9"),
    ]
    for box, label, color in boxes:
        draw.rounded_rectangle(box, radius=12, fill=color, outline="#264A68", width=4)
        center_text(box, label, font)
    for start, end in (
        ((240, 238), (300, 238)),
        ((505, 238), (565, 238)),
        ((875, 238), (935, 238)),
        ((1140, 238), (1200, 238)),
        ((1037, 305), (1037, 435)),
        ((1140, 502), (1200, 502)),
    ):
        arrow(start, end)
    title = "Research evaluation boundary"
    title_bounds = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((1450 - (title_bounds[2] - title_bounds[0])) / 2, 60), title, fill="#172B3A", font=title_font)
    note = "The production scorer is observed through an adapter; the grader lab adds metrics and manifests only."
    note_bounds = draw.textbbox((0, 0), note, font=small)
    draw.text(((1450 - (note_bounds[2] - note_bounds[0])) / 2, 625), note, fill="#333333", font=small)
    canvas.save(FIGURE_PATH, optimize=True)


def _set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def _set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    tc_pr.append(shading)


def _set_cell_margins(cell, value: int = 35) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for edge in ("top", "start", "bottom", "end"):
        tag = tc_mar.find(qn(f"w:{edge}"))
        if tag is None:
            tag = OxmlElement(f"w:{edge}")
            tc_mar.append(tag)
        tag.set(qn("w:w"), str(value))
        tag.set(qn("w:type"), "dxa")


def _set_run_font(run, size: float, *, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Times New Roman"
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Times New Roman")
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Times New Roman")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


def _add_body(doc: Document, text: str) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.first_line_indent = Inches(0.13)
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.paragraph_format.line_spacing = 1.0
    _set_run_font(paragraph.add_run(text), 9.2)


def _add_heading(doc: Document, text: str, *, major: bool) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if major else WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.space_before = Pt(6 if major else 4)
    paragraph.paragraph_format.space_after = Pt(2.5)
    _set_run_font(paragraph.add_run(text), 10.0 if major else 9.4, bold=True)


def _add_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(2)
    _set_run_font(p.add_run(text), 7.8, italic=True)


def _add_table(doc: Document, rows: list[list[str]], widths: list[float]) -> None:
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table_width_twips = int(sum(widths) * 1440)
    tbl_pr = table._tbl.tblPr
    tbl_width = tbl_pr.first_child_found_in("w:tblW")
    if tbl_width is None:
        tbl_width = OxmlElement("w:tblW")
        tbl_pr.append(tbl_width)
    tbl_width.set(qn("w:w"), str(table_width_twips))
    tbl_width.set(qn("w:type"), "dxa")
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)
    for grid_col, width in zip(table._tbl.tblGrid.gridCol_lst, widths):
        grid_col.set(qn("w:w"), str(int(width * 1440)))
    for row_index, row_values in enumerate(rows):
        row = table.rows[row_index]
        if row_index == 0:
            _set_repeat_table_header(row)
        for col_index, value in enumerate(row_values):
            cell = row.cells[col_index]
            cell.width = Inches(widths[col_index])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            _set_cell_margins(cell)
            if row_index == 0:
                _set_cell_shading(cell, "D9E7F3")
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(0)
            _set_run_font(p.add_run(value), 7.0, bold=row_index == 0)


def _add_page_number(section) -> None:
    footer = section.footer
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, end])
    _set_run_font(run, 7.5)


def _paragraphs(value: tuple[str, ...] | str) -> tuple[str, ...]:
    """Normalize one-paragraph subsection literals to a tuple."""
    return (value,) if isinstance(value, str) else value


def _configure_section(section, *, columns: int, add_footer: bool = False) -> None:
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(17.5)
    section.bottom_margin = Mm(17.5)
    section.left_margin = Mm(17.5)
    section.right_margin = Mm(17.5)
    section.header_distance = Mm(7)
    section.footer_distance = Mm(7)
    sect_pr = section._sectPr
    cols = sect_pr.xpath("./w:cols")
    cols_el = cols[0] if cols else OxmlElement("w:cols")
    if not cols:
        sect_pr.append(cols_el)
    cols_el.set(qn("w:num"), str(columns))
    cols_el.set(qn("w:space"), "360")
    if add_footer:
        _add_page_number(section)


def build_docx(primary: list[dict[str, str]], ablation: list[dict[str, str]]) -> None:
    doc = Document()
    doc.core_properties.title = "interViv: Auditable Diagnostic Scoring for Technical Interview Practice"
    doc.core_properties.subject = "Anonymous CINS 2026 manuscript candidate"
    doc.core_properties.author = "Anonymous"
    doc.core_properties.last_modified_by = "Anonymous"
    doc.core_properties.keywords = "automated short-answer grading; auditability; interview practice"
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    normal.font.size = Pt(9.2)

    first = doc.sections[0]
    _configure_section(first, columns=1, add_footer=True)
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(4)
    _set_run_font(title.add_run("interViv: Auditable Diagnostic Scoring for\nTechnical Interview Practice"), 16, bold=True)
    author = doc.add_paragraph()
    author.alignment = WD_ALIGN_PARAGRAPH.CENTER
    author.paragraph_format.space_after = Pt(7)
    _set_run_font(author.add_run("Anonymous submission"), 9.5, italic=True)

    abstract = doc.add_paragraph()
    abstract.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    abstract.paragraph_format.space_after = Pt(3)
    _set_run_font(abstract.add_run("Abstract—"), 8.8, bold=True)
    _set_run_font(abstract.add_run(ABSTRACT), 8.8)
    keywords = doc.add_paragraph()
    keywords.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    keywords.paragraph_format.space_after = Pt(4)
    _set_run_font(keywords.add_run("Index Terms—"), 8.6, bold=True)
    _set_run_font(keywords.add_run(KEYWORDS), 8.6, italic=True)

    body_section = doc.add_section(WD_SECTION_START.CONTINUOUS)
    _configure_section(body_section, columns=2)

    for section in SECTIONS:
        _add_heading(doc, section.title, major=True)
        for paragraph in _paragraphs(section.paragraphs):
            _add_body(doc, paragraph)
        for subtitle, paragraphs in section.subsections:
            _add_heading(doc, subtitle, major=False)
            for paragraph in _paragraphs(paragraphs):
                _add_body(doc, paragraph)

            if subtitle == "A. Scoring boundary":
                doc.add_picture(str(FIGURE_PATH), width=Inches(3.28))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                _add_caption(doc, "Fig. 1. Diagnostic scoring, evidence, and follow-up boundary.")
                equation = doc.add_paragraph()
                equation.alignment = WD_ALIGN_PARAGRAPH.CENTER
                equation.paragraph_format.space_after = Pt(3)
                _set_run_font(
                    equation.add_run(
                        "S = min(Cg, 100(0.45ssem + 0.25sclf + 0.20skw + 0.10stfidf) + bKG + bNER − p)."
                    ),
                    8.6,
                    italic=True,
                )

            if subtitle == "A. Five-way grading":
                _add_caption(doc, "TABLE I. Accuracy and macro-F1 (benchmark-validated).")
                rows = [["Data / metric", "Lex.", "Sem.", "interViv"]]
                for dataset, label in (("scientsbank", "SciEntsBank"), ("beetle", "BEETLE")):
                    for metric, short in (("grading_accuracy", "Acc."), ("macro_f1", "Macro-F1")):
                        rows.append([
                            f"{label} {short}",
                            _metric(primary, dataset, "lexical_similarity", metric),
                            _metric(primary, dataset, "semantic_nli_relevance", metric),
                            _metric(primary, dataset, "interviv_current_scorer_guard", metric),
                        ])
                _add_table(doc, rows, [1.42, 0.55, 0.55, 0.68])

            if subtitle == "B. Safety and contradictions":
                _add_caption(doc, "TABLE II. Off-topic and contradiction recall; FP is off-topic false-positive rate.")
                rows = [["Data / method", "OT rec.", "FP", "Contr."]]
                for dataset, label in (("scientsbank", "Sci"), ("beetle", "BEETLE")):
                    for method, short in (
                        ("lexical_similarity", "Lex."),
                        ("semantic_nli_relevance", "Sem."),
                        ("interviv_current_scorer_guard", "interViv"),
                    ):
                        rows.append([
                            f"{label} {short}",
                            _metric(primary, dataset, method, "off_topic_detection_rate"),
                            _metric(primary, dataset, method, "off_topic_false_positive_rate"),
                            _metric(primary, dataset, method, "contradiction_detection_rate"),
                        ])
                _add_table(doc, rows, [1.2, 0.62, 0.58, 0.7])

            if subtitle == "D. Component sensitivity":
                _add_caption(doc, "TABLE III. Research-only macro-F1 ablations.")
                rows = [["Configuration", "Sci", "BEETLE", "Synth.*"]]
                configurations = (
                    ("full_interviv", "Full"),
                    ("without_semantic", "− semantic"),
                    ("without_classifier_term", "− classifier term"),
                    ("without_keyword_term", "− keyword term"),
                    ("without_tfidf_term", "− TF-IDF term"),
                    ("without_guards", "− guards"),
                )
                for configuration, label in configurations:
                    rows.append([
                        label,
                        _metric(ablation, "scientsbank", configuration, "macro_f1"),
                        _metric(ablation, "beetle", configuration, "macro_f1"),
                        _metric(ablation, "internal_perturbation", configuration, "macro_f1"),
                    ])
                _add_table(doc, rows, [1.38, 0.55, 0.7, 0.7])
                note = doc.add_paragraph()
                note.paragraph_format.space_after = Pt(2)
                _set_run_font(note.add_run("* pilot_synthetic=true; not benchmark evidence."), 7.2, italic=True)

    _add_heading(doc, "REFERENCES", major=True)
    for reference in REFERENCES:
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.left_indent = Inches(0.15)
        paragraph.paragraph_format.first_line_indent = Inches(-0.15)
        paragraph.paragraph_format.space_after = Pt(1.5)
        _set_run_font(paragraph.add_run(reference), 7.6)

    # A terminal continuous section forces Word-compatible renderers to balance
    # the final pair of manuscript columns instead of leaving the right column
    # empty after the references.
    terminal_section = doc.add_section(WD_SECTION_START.CONTINUOUS)
    _configure_section(terminal_section, columns=1)

    DOCX_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(DOCX_PATH)


def build_markdown(primary: list[dict[str, str]], ablation: list[dict[str, str]]) -> None:
    lines = [
        "# interViv: Auditable Diagnostic Scoring for Technical Interview Practice",
        "",
        "*Anonymous submission*",
        "",
        "## Abstract",
        "",
        ABSTRACT,
        "",
        f"**Index Terms—** {KEYWORDS}",
        "",
    ]
    for section in SECTIONS:
        lines.extend([f"## {section.title}", ""])
        for paragraph in _paragraphs(section.paragraphs):
            lines.extend([paragraph, ""])
        for subtitle, paragraphs in section.subsections:
            lines.extend([f"### {subtitle}", ""])
            for paragraph in _paragraphs(paragraphs):
                lines.extend([paragraph, ""])
            if subtitle == "A. Scoring boundary":
                lines.extend([
                    "![Diagnostic scoring, evidence, and follow-up boundary.](figures/cins_fig01_diagnostic_pipeline.png)",
                    "",
                    "S = min(Cg, 100(0.45ssem + 0.25sclf + 0.20skw + 0.10stfidf) + bKG + bNER − p).",
                    "",
                ])
            if subtitle == "A. Five-way grading":
                lines.extend(["**Table I. Accuracy and macro-F1 (benchmark-validated).**", ""])
                lines.extend(_markdown_primary_table(primary))
            if subtitle == "D. Component sensitivity":
                lines.extend(["**Table III. Research-only macro-F1 ablations.**", ""])
                lines.extend(_markdown_ablation_table(ablation))
    lines.extend(["## REFERENCES", ""])
    for reference in REFERENCES:
        lines.extend([reference, ""])
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def _markdown_primary_table(rows: list[dict[str, str]]) -> list[str]:
    output = [
        "| Dataset / metric | Lexical | Semantic | interViv |",
        "| --- | ---: | ---: | ---: |",
    ]
    for dataset, label in (("scientsbank", "SciEntsBank"), ("beetle", "BEETLE")):
        for metric, short in (("grading_accuracy", "Accuracy"), ("macro_f1", "Macro-F1")):
            output.append(
                "| " + " | ".join([
                    f"{label} {short}",
                    _metric(rows, dataset, "lexical_similarity", metric),
                    _metric(rows, dataset, "semantic_nli_relevance", metric),
                    _metric(rows, dataset, "interviv_current_scorer_guard", metric),
                ]) + " |"
            )
    return output + [""]


def _markdown_ablation_table(rows: list[dict[str, str]]) -> list[str]:
    output = [
        "| Configuration | SciEntsBank | BEETLE | Synthetic pilot* |",
        "| --- | ---: | ---: | ---: |",
    ]
    for configuration, label in (
        ("full_interviv", "Full"),
        ("without_semantic", "− semantic"),
        ("without_classifier_term", "− classifier term"),
        ("without_keyword_term", "− keyword term"),
        ("without_tfidf_term", "− TF-IDF term"),
        ("without_guards", "− guards"),
    ):
        output.append(
            "| " + " | ".join([
                label,
                _metric(rows, "scientsbank", configuration, "macro_f1"),
                _metric(rows, "beetle", configuration, "macro_f1"),
                _metric(rows, "internal_perturbation", configuration, "macro_f1"),
            ]) + " |"
        )
    return output + ["", "* pilot_synthetic=true; not benchmark evidence.", ""]


def _anonymity_gate() -> None:
    forbidden = (
        "praneet",
        "/users/",
        "interviv authors",
        "author 1",
    )
    text = MD_PATH.read_text(encoding="utf-8").lower()
    for token in forbidden:
        if token in text:
            raise RuntimeError(f"Anonymity gate failed: {token!r}")
    if re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.IGNORECASE):
        raise RuntimeError("Anonymity gate failed: email address")
    if re.search(r"\b(?:acknowledg(?:e)?ments?|biograph(?:y|ies))\b", text):
        raise RuntimeError("Anonymous manuscript contains identity-oriented section")


def main() -> int:
    primary, ablation = _read_results()
    make_figure()
    build_markdown(primary, ablation)
    _anonymity_gate()
    build_docx(primary, ablation)
    print(json.dumps({
        "docx": str(DOCX_PATH),
        "markdown": str(MD_PATH),
        "figure": str(FIGURE_PATH),
        "docx_sha256": _sha256(DOCX_PATH),
        "primary_run": PRIMARY_RUN,
        "ablation_run": ABLATION_RUN,
        "error_analysis_run": ERROR_RUN,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
