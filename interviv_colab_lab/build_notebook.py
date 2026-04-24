from __future__ import annotations

import base64
import io
import json
import textwrap
import zipfile
from pathlib import Path


def _clean(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


def markdown(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": _clean(text),
    }


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _clean(text),
    }


BUNDLE_RELATIVE_FILES = [
    "requirements.txt",
    "retrain_ml_model.py",
    "modules/__init__.py",
    "modules/c4_feedback.py",
    "modules/knowledge_graph.py",
    "modules/ner_scorer.py",
    "modules/nlp_scorer.py",
    "modules/nlp_scorer_patch.py",
    "modules/question_bank.py",
    "modules/resume_parser.py",
    "modules/skill_taxonomy_v2.csv",
    "modules/svm_model.joblib",
    "data/ml_training_data.csv",
    "data/interview_dataset_v6.csv",
    "backend/__init__.py",
    "backend/config.py",
    "backend/integrations.py",
    "backend/scoring/__init__.py",
    "backend/scoring/pipeline.py",
]


def _bundle_base64() -> str:
    source_root = Path(__file__).resolve().parents[1] / "interViv_best"
    if not source_root.exists():
        raise FileNotFoundError(f"Missing project folder: {source_root}")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for rel_path in BUNDLE_RELATIVE_FILES:
            source = source_root / rel_path
            if not source.exists():
                raise FileNotFoundError(f"Missing bundle file: {source}")
            bundle.write(source, f"interViv_best/{rel_path}")

        # Makes backend/config.py import cleanly even when python-dotenv is not installed.
        bundle.writestr(
            "interViv_best/dotenv.py",
            "def load_dotenv(*args, **kwargs):\n"
            "    return False\n",
        )

    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _write_required_files_zip() -> Path:
    source_root = Path(__file__).resolve().parents[1] / "interViv_best"
    out_path = Path(__file__).with_name("interViv_best_required_files.zip")
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for rel_path in BUNDLE_RELATIVE_FILES:
            source = source_root / rel_path
            if not source.exists():
                raise FileNotFoundError(f"Missing required file: {source}")
            bundle.write(source, f"interViv_best/{rel_path}")

        bundle.writestr(
            "interViv_best/dotenv.py",
            "def load_dotenv(*args, **kwargs):\n"
            "    return False\n",
        )
    return out_path


def _upload_setup_cell() -> dict:
    return code(
        r'''from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys
import warnings
import zipfile

warnings.filterwarnings("ignore")
IN_COLAB = "google.colab" in sys.modules
mpl_cache = Path("/tmp/matplotlib")
mpl_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))

runtime_base = Path("/content/interviv_model_lab_runtime") if Path("/content").exists() else Path.cwd() / ".interviv_model_lab_runtime"
runtime_base.mkdir(parents=True, exist_ok=True)

def looks_like_interviv(path: Path) -> bool:
    return (
        (path / "modules" / "nlp_scorer.py").exists()
        and (path / "modules" / "svm_model.joblib").exists()
        and (path / "data" / "ml_training_data.csv").exists()
    )

def add_python_paths(project_root: Path) -> None:
    for path in [project_root, project_root / "modules", project_root / "backend"]:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

def copy_zip_project(zip_path: Path, target_root: Path) -> Path | None:
    with zipfile.ZipFile(zip_path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        prefixes = [""]
        for name in names:
            marker = "/modules/nlp_scorer.py"
            if name.endswith(marker):
                prefixes.append(name[: -len(marker)])
        prefixes = sorted(set(prefixes), key=len, reverse=True)

        for prefix in prefixes:
            def member(rel_path: str) -> str:
                return f"{prefix}/{rel_path}" if prefix else rel_path

            required = [
                member("modules/nlp_scorer.py"),
                member("modules/svm_model.joblib"),
                member("data/ml_training_data.csv"),
            ]
            if not all(item in names for item in required):
                continue

            if target_root.exists():
                shutil.rmtree(target_root)
            target_root.mkdir(parents=True, exist_ok=True)

            allowed_roots = ("modules/", "data/", "backend/")
            allowed_files = {"requirements.txt", "retrain_ml_model.py", "dotenv.py"}
            for name in names:
                rel = name[len(prefix) + 1 :] if prefix and name.startswith(prefix + "/") else name
                if rel.startswith(allowed_roots) or rel in allowed_files:
                    destination = target_root / rel
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(name))

            (target_root / "modules").mkdir(exist_ok=True)
            (target_root / "backend" / "scoring").mkdir(parents=True, exist_ok=True)
            (target_root / "modules" / "__init__.py").touch()
            (target_root / "backend" / "__init__.py").touch()
            (target_root / "backend" / "scoring" / "__init__.py").touch()
            (target_root / "dotenv.py").write_text("def load_dotenv(*args, **kwargs):\n    return False\n", encoding="utf-8")
            return target_root.resolve()
    return None

def find_existing_project() -> Path | None:
    candidates = [
        Path.cwd(),
        Path.cwd() / "interViv_best",
        Path.cwd().parent / "interViv_best",
        runtime_base / "interViv_best",
        Path("/content/interViv_best"),
        Path("/content/drive/MyDrive/interViv_best"),
        Path("/content/drive/MyDrive/mega 2 copy/interViv_best"),
    ]
    return next((path.resolve() for path in candidates if looks_like_interviv(path)), None)

def find_zip_files() -> list[Path]:
    search_dirs = [Path.cwd(), Path("/content"), Path("/content/drive/MyDrive")]
    seen = set()
    zips = []
    for base in search_dirs:
        if not base.exists():
            continue
        for pattern in ("*.zip", "*/*.zip"):
            for zip_path in base.glob(pattern):
                resolved = zip_path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    zips.append(resolved)
    return zips

PROJECT_ROOT = find_existing_project()

if PROJECT_ROOT is None:
    for zip_path in find_zip_files():
        extracted = copy_zip_project(zip_path, runtime_base / "interViv_best")
        if extracted is not None:
            PROJECT_ROOT = extracted
            print(f"Extracted project from: {zip_path}")
            break

if PROJECT_ROOT is None and IN_COLAB:
    print("Upload interViv_best_required_files.zip or an interViv_best project zip.")
    from google.colab import files
    uploaded = files.upload()
    for uploaded_name in uploaded:
        if uploaded_name.lower().endswith(".zip"):
            extracted = copy_zip_project(Path(uploaded_name), runtime_base / "interViv_best")
            if extracted is not None:
                PROJECT_ROOT = extracted
                print(f"Extracted project from uploaded file: {uploaded_name}")
                break

if PROJECT_ROOT is None:
    raise FileNotFoundError(
        "Could not find or extract interViv_best. Upload interViv_best_required_files.zip, "
        "or upload an interViv_best folder to /content/interViv_best."
    )

required_packages = [
    ("joblib", "joblib"),
    ("scikit-learn", "sklearn"),
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("matplotlib", "matplotlib"),
    ("networkx", "networkx"),
]
missing = [pip_name for pip_name, import_name in required_packages if importlib.util.find_spec(import_name) is None]
if missing:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *missing])

add_python_paths(PROJECT_ROOT)
print(f"Using project: {PROJECT_ROOT}")
print(f"Running in Colab: {IN_COLAB}")'''
    )


def _standalone_setup_cell(bundle_b64: str) -> dict:
    chunk_size = 8000
    chunks = "\n".join(
        f'"{bundle_b64[index:index + chunk_size]}"'
        for index in range(0, len(bundle_b64), chunk_size)
    )
    return code(
        f'''from pathlib import Path
import base64
import importlib.util
import io
import os
import subprocess
import sys
import warnings
import zipfile

warnings.filterwarnings("ignore")
IN_COLAB = "google.colab" in sys.modules
mpl_cache = Path("/tmp/matplotlib")
mpl_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))

BUNDLE_B64 = (
{chunks}
)

runtime_base = Path("/content/interviv_model_lab_runtime") if Path("/content").exists() else Path.cwd() / ".interviv_model_lab_runtime"
runtime_base.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(io.BytesIO(base64.b64decode(BUNDLE_B64))) as bundle:
    bundle.extractall(runtime_base)

PROJECT_ROOT = (runtime_base / "interViv_best").resolve()

required_packages = [
    ("joblib", "joblib"),
    ("scikit-learn", "sklearn"),
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("matplotlib", "matplotlib"),
    ("networkx", "networkx"),
]
missing = [pip_name for pip_name, import_name in required_packages if importlib.util.find_spec(import_name) is None]
if missing:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *missing])

for path in [PROJECT_ROOT, PROJECT_ROOT / "modules", PROJECT_ROOT / "backend"]:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

print(f"Standalone runtime extracted to: {{PROJECT_ROOT}}")
print(f"Running in Colab: {{IN_COLAB}}")'''
    )


cells = [
    markdown(
        """
        # interViv Model Lab

        This Colab notebook is a hands-on test bench for the model and scoring stack in
        `interViv_best`.

        It covers:
        - `svm_model.joblib`: the trained scikit-learn model used for Good/Average/Poor labels.
        - `PatchedNLPScorer`: the 3-layer answer scorer with the empty-ideal fallback.
        - `KnowledgeGraphScorer`: concept coverage and missing-key analysis.
        - `NERScorer`: technical entity extraction.
        - `generate_feedback`: C4-style feedback.
        - `run_scoring_pipeline`: the backend scoring pipeline.

        Run the notebook top to bottom for the sample demos, then use the custom-answer
        and interactive cells to test your own answers.
        """
    ),
    markdown(
        """
        ## 1. Locate the project and install dependencies

        Keep the `interViv_best` folder next to this notebook folder when running locally.
        In Google Colab, upload or mount the project so the notebook can find `interViv_best`.
        """
    ),
    code(
        """
        from pathlib import Path
        import importlib.util
        import os
        import subprocess
        import sys
        import warnings

        warnings.filterwarnings("ignore")
        IN_COLAB = "google.colab" in sys.modules
        mpl_cache = Path("/tmp/matplotlib")
        mpl_cache.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))

        def looks_like_interviv(path: Path) -> bool:
            return (
                (path / "modules" / "nlp_scorer.py").exists()
                and (path / "modules" / "svm_model.joblib").exists()
                and (path / "data" / "ml_training_data.csv").exists()
            )

        candidates = [
            Path.cwd(),
            Path.cwd() / "interViv_best",
            Path.cwd().parent / "interViv_best",
            Path("/content/interViv_best"),
            Path("/content/drive/MyDrive/interViv_best"),
            Path("/content/drive/MyDrive/mega 2 copy/interViv_best"),
        ]

        PROJECT_ROOT = next((p.resolve() for p in candidates if looks_like_interviv(p)), None)

        if PROJECT_ROOT is None:
            raise FileNotFoundError(
                "Could not find interViv_best. Put that folder next to this notebook, "
                "or set PROJECT_ROOT manually to the interViv_best path."
            )

        if IN_COLAB:
            req = PROJECT_ROOT / "requirements.txt"
            if req.exists():
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)])
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "matplotlib", "ipywidgets"])

        for path in [PROJECT_ROOT, PROJECT_ROOT / "modules", PROJECT_ROOT / "backend"]:
            path_str = str(path)
            if path_str not in sys.path:
                sys.path.insert(0, path_str)

        print(f"Using project: {PROJECT_ROOT}")
        print(f"Running in Colab: {IN_COLAB}")
        """
    ),
    markdown(
        """
        ## 2. Load datasets, models, and scorers
        """
    ),
    code(
        """
        import json
        import math
        from typing import Any

        import joblib
        import matplotlib.pyplot as plt
        import networkx as nx
        import numpy as np
        import pandas as pd
        from IPython.display import Markdown, clear_output, display
        from sklearn.metrics import classification_report, confusion_matrix

        from c4_feedback import generate_feedback
        from knowledge_graph import KnowledgeGraphScorer
        from ner_scorer import NERScorer
        from nlp_scorer_patch import PatchedNLPScorer
        from backend.scoring.pipeline import run_scoring_pipeline

        try:
            plt.style.use("seaborn-v0_8-whitegrid")
        except OSError:
            plt.style.use("ggplot")

        MODEL_PATH = PROJECT_ROOT / "modules" / "svm_model.joblib"
        TRAIN_PATH = PROJECT_ROOT / "data" / "ml_training_data.csv"
        QUESTIONS_PATH = PROJECT_ROOT / "data" / "interview_dataset_v6.csv"

        train_df = pd.read_csv(TRAIN_PATH)
        questions_df = pd.read_csv(QUESTIONS_PATH)
        model = joblib.load(MODEL_PATH)

        nlp_scorer = PatchedNLPScorer(model_path=str(MODEL_PATH))
        kg_scorer = KnowledgeGraphScorer()
        ner_scorer = NERScorer()

        print("Loaded:")
        print(f"  model: {MODEL_PATH.name} ({type(model).__name__})")
        print(f"  training rows: {len(train_df):,}")
        print(f"  question rows: {len(questions_df):,}")
        print(f"  KG skills: {', '.join(sorted(kg_scorer.graphs))}")
        """
    ),
    markdown(
        """
        ## 3. Dataset overview visuals
        """
    ),
    code(
        """
        overview = pd.DataFrame(
            [
                {"file": "ml_training_data.csv", "rows": len(train_df), "columns": len(train_df.columns)},
                {"file": "interview_dataset_v6.csv", "rows": len(questions_df), "columns": len(questions_df.columns)},
            ]
        )
        display(overview)
        display(train_df.head(3))

        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        plot_specs = [
            (train_df, "skill", "Training rows by skill"),
            (train_df, "label", "Training labels"),
            (questions_df, "skill", "Question rows by skill"),
            (questions_df, "difficulty", "Question difficulty"),
        ]

        for ax, (df, column, title) in zip(axes.ravel(), plot_specs):
            counts = df[column].fillna("missing").value_counts().head(12)
            labels = [str(item) for item in counts.index]
            ax.barh(labels, counts.values, color="#4c78a8")
            ax.invert_yaxis()
            ax.set_title(title)
            ax.set_xlabel("rows")
            ax.set_ylabel("")

        plt.tight_layout()
        plt.show()
        """
    ),
    markdown(
        """
        ## 4. Trained model inventory and feature visual
        """
    ),
    code(
        """
        FEATURE_NAMES = [
            "cos_similarity",
            "length_ratio",
            "keyword_coverage",
            "word_count",
            "concept_coverage",
        ]

        clf = model.named_steps.get("clf") if hasattr(model, "named_steps") else model
        print(f"Model object: {type(model)}")
        print(f"Classifier: {type(clf)}")
        print(f"Feature count: {getattr(model, 'n_features_in_', getattr(clf, 'n_features_in_', 'unknown'))}")
        print(f"Classes: {list(getattr(model, 'classes_', getattr(clf, 'classes_', [])))}")
        if hasattr(model, "named_steps"):
            print(f"Pipeline steps: {list(model.named_steps.keys())}")

        if hasattr(clf, "feature_importances_"):
            importance = pd.DataFrame(
                {"feature": FEATURE_NAMES[: len(clf.feature_importances_)], "importance": clf.feature_importances_}
            ).sort_values("importance", ascending=False)
            display(importance)

            fig, ax = plt.subplots(figsize=(10, 4))
            ordered = importance.sort_values("importance")
            ax.barh(ordered["feature"], ordered["importance"], color="#59a14f")
            ax.set_title("Model feature importance")
            ax.set_xlabel("importance")
            ax.set_ylabel("")
            plt.tight_layout()
            plt.show()
        else:
            print("This classifier does not expose feature_importances_.")
        """
    ),
    markdown(
        """
        ## 5. Scoring helpers

        These helpers run the same pieces the backend uses, then package the result into
        tables and charts.
        """
    ),
    code(
        """
        def clean_text(value: Any) -> str:
            if value is None:
                return ""
            try:
                if pd.isna(value):
                    return ""
            except TypeError:
                pass
            return str(value)


        def answer_length_ratio(answer: str, ideal_answer: str) -> float:
            answer_words = len(clean_text(answer).split())
            ideal_words = max(len(clean_text(ideal_answer).split()), 1)
            return min(answer_words / ideal_words, 3.0)


        def standalone_model_label(nlp_payload: dict[str, Any], answer: str, ideal_answer: str) -> tuple[str, list[float]]:
            feature_count = int(getattr(model, "n_features_in_", 4) or 4)
            features = [
                float(nlp_payload.get("cosine_similarity", 0.0)),
                answer_length_ratio(answer, ideal_answer),
                float(nlp_payload.get("keyword_coverage", 0.5)),
                len(clean_text(answer).split()),
                float(nlp_payload.get("concept_coverage", 0.5)),
            ]
            usable = features[:feature_count]
            label = str(model.predict([usable])[0])
            return label, usable


        def score_answer(
            *,
            question: str,
            answer: str,
            ideal_answer: str = "",
            ideal_keywords: str = "",
            skill: str = "Python",
            sub_domain: str = "",
            difficulty: str = "medium",
            use_pipeline: bool = True,
        ) -> dict[str, Any]:
            question = clean_text(question)
            answer = clean_text(answer)
            ideal_answer = clean_text(ideal_answer)
            ideal_keywords = clean_text(ideal_keywords)
            skill = clean_text(skill) or "Python"
            sub_domain = clean_text(sub_domain)
            difficulty = clean_text(difficulty) or "medium"

            nlp_payload = nlp_scorer.compute_overall_score(
                answer_text=answer,
                question=question,
                ideal_answer=ideal_answer,
                ideal_keywords=ideal_keywords,
                difficulty=difficulty,
            )

            model_label, model_features = standalone_model_label(nlp_payload, answer, ideal_answer)

            kg_payload = kg_scorer.score_answer(skill, answer)
            kg_score_100 = float(kg_payload.get("score", 0.0)) * 100.0
            ner_payload = ner_scorer.extract(answer)
            ner_entities = [name for name, _category in ner_payload.get("entities", [])]

            final_score = round((0.85 * float(nlp_payload.get("overall_score", 0.0))) + (0.15 * kg_score_100), 2)
            feedback = generate_feedback(
                answer_text=answer,
                question=question,
                ideal_answer=ideal_answer,
                skill=skill,
                sub_domain=sub_domain,
                nlp_score=float(nlp_payload.get("overall_score", 0.0)),
                svm_label=model_label,
                kg_score=kg_score_100,
                final_score=final_score,
                ner_entities=ner_entities,
            )

            pipeline_payload = None
            if use_pipeline:
                try:
                    pipeline_payload = run_scoring_pipeline(
                        answer_text=answer,
                        cos_similarity=float(nlp_payload.get("cosine_similarity", 0.0)),
                        length_ratio=model_features[1] if len(model_features) > 1 else answer_length_ratio(answer, ideal_answer),
                        aligned_score=float(nlp_payload.get("keyword_coverage", 0.0)),
                        word_count=len(answer.split()),
                        question_context={
                            "question": question,
                            "ideal_answer": ideal_answer,
                            "ideal_keywords": ideal_keywords,
                            "skill": skill,
                            "sub_domain": sub_domain,
                        },
                        difficulty=difficulty,
                    )
                except Exception as exc:
                    pipeline_payload = {"error": str(exc)}

            return {
                "question": question,
                "answer": answer,
                "ideal_answer": ideal_answer,
                "ideal_keywords": ideal_keywords,
                "skill": skill,
                "sub_domain": sub_domain,
                "difficulty": difficulty,
                "nlp": nlp_payload,
                "model_label": model_label,
                "model_features": model_features,
                "kg": kg_payload,
                "ner": ner_payload,
                "feedback": feedback,
                "final_score": final_score,
                "pipeline": pipeline_payload,
            }


        def summarize_results(named_results: list[tuple[str, dict[str, Any]]]) -> pd.DataFrame:
            rows = []
            for name, result in named_results:
                nlp = result["nlp"]
                rows.append(
                    {
                        "case": name,
                        "skill": result["skill"],
                        "difficulty": result["difficulty"],
                        "final_score": result["final_score"],
                        "nlp_score": nlp.get("overall_score", 0.0),
                        "kg_score": round(float(result["kg"].get("score", 0.0)) * 100, 2),
                        "model_label": result["model_label"],
                        "ner_label": result["ner"].get("label"),
                        "layer1": nlp.get("layer1_score", 0.0),
                        "layer2": nlp.get("layer2_score", 0.0),
                        "layer3": nlp.get("layer3_score", 0.0),
                    }
                )
            return pd.DataFrame(rows)


        def plot_result(result: dict[str, Any], title: str = "Score breakdown") -> None:
            nlp = result["nlp"]
            values = pd.DataFrame(
                [
                    {"metric": "final", "score": result["final_score"]},
                    {"metric": "nlp", "score": nlp.get("overall_score", 0.0)},
                    {"metric": "kg", "score": float(result["kg"].get("score", 0.0)) * 100},
                    {"metric": "layer1", "score": nlp.get("layer1_score", 0.0)},
                    {"metric": "layer2", "score": nlp.get("layer2_score", 0.0)},
                    {"metric": "layer3", "score": nlp.get("layer3_score", 0.0)},
                ]
            )
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.bar(values["metric"], values["score"], color=["#4c78a8", "#59a14f", "#f28e2b", "#e15759", "#76b7b2", "#edc948"])
            ax.set_ylim(0, 100)
            ax.set_title(title)
            ax.set_ylabel("score")
            ax.set_xlabel("")
            plt.tight_layout()
            plt.show()


        def plot_feature_radar(result: dict[str, Any], title: str = "NLP feature radar") -> None:
            nlp = result["nlp"]
            labels = [
                "cosine_similarity",
                "keyword_coverage",
                "concept_coverage",
                "depth_score",
                "structure_score",
                "accuracy_score",
                "clarity_score",
            ]
            values = [float(nlp.get(label, 0.0)) for label in labels]
            angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
            values += values[:1]
            angles += angles[:1]

            fig = plt.figure(figsize=(7, 7))
            ax = plt.subplot(111, polar=True)
            ax.plot(angles, values, linewidth=2)
            ax.fill(angles, values, alpha=0.25)
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(labels, fontsize=9)
            ax.set_ylim(0, 1)
            ax.set_title(title, y=1.08)
            plt.show()

        print("Helpers ready.")
        """
    ),
    markdown(
        """
        ## 6. Compare Good, Average, and Poor answers from your dataset
        """
    ),
    code(
        """
        complete_groups = train_df.groupby(["skill", "question"]).filter(
            lambda group: {"Good", "Average", "Poor"}.issubset(set(group["label"]))
        )
        seed = complete_groups.iloc[0]
        sample_rows = train_df[
            (train_df["skill"] == seed["skill"]) & (train_df["question"] == seed["question"])
        ].drop_duplicates("label")

        sample_results = []
        for wanted_label in ["Good", "Average", "Poor"]:
            row = sample_rows[sample_rows["label"] == wanted_label].iloc[0]
            result = score_answer(
                question=row["question"],
                answer=row["answer"],
                ideal_answer=row["ideal_answer"],
                ideal_keywords=row.get("ideal_keywords", ""),
                skill=row["skill"],
                sub_domain=row.get("sub_domain", ""),
                difficulty=row.get("difficulty", "medium"),
            )
            sample_results.append((wanted_label, result))

        display(Markdown(f"### Question: {clean_text(seed['question'])}"))
        display(summarize_results(sample_results))

        comparison = summarize_results(sample_results).melt(
            id_vars=["case"], value_vars=["final_score", "nlp_score", "kg_score", "layer1", "layer2", "layer3"]
        )
        pivot = comparison.pivot(index="variable", columns="case", values="value")
        ax = pivot.plot(kind="bar", figsize=(13, 5), color=["#59a14f", "#4c78a8", "#e15759"])
        ax.set_ylim(0, 100)
        ax.set_title("Score comparison across labelled answers")
        ax.set_xlabel("")
        ax.set_ylabel("score")
        ax.legend(title="dataset label")
        plt.tight_layout()
        plt.show()
        """
    ),
    markdown(
        """
        ## 7. Test one custom answer

        Edit `CUSTOM` and rerun this cell.
        """
    ),
    code(
        '''
        CUSTOM = {
            "skill": "Python",
            "sub_domain": "python_core",
            "difficulty": "Medium",
            "question": "What is a Python decorator and how do you use it?",
            "ideal_answer": (
                "A decorator is a function that wraps another function to extend or modify its "
                "behaviour without changing its source code. You apply it with the @ syntax above "
                "the function definition. Decorators are commonly used for logging, authentication, "
                "caching, and timing."
            ),
            "ideal_keywords": "decorator,function,wrapper,@ syntax,logging,caching,authentication",
            "answer": """
        A decorator is a higher-order function that takes another function and returns a wrapped
        version of it. In Python the @ syntax applies the decorator above a function definition,
        which is the same as assigning func = decorator(func). For example, I would use one for
        logging, permission checks, caching, or timing without changing the original function body.
        The trade-off is that decorators can hide control flow, so using functools.wraps helps keep
        names and docstrings readable in production.
        """,
        }

        custom_result = score_answer(**CUSTOM)
        display(summarize_results([("custom", custom_result)]))
        display(Markdown("### Feedback"))
        display(custom_result["feedback"])
        display(Markdown("### NER entities"))
        display(custom_result["ner"])
        display(Markdown("### Knowledge graph"))
        display(custom_result["kg"])

        if isinstance(custom_result["pipeline"], dict) and "error" in custom_result["pipeline"]:
            print("Pipeline note:", custom_result["pipeline"]["error"])
        else:
            display(Markdown("### Backend pipeline output"))
            display(custom_result["pipeline"])

        plot_result(custom_result, "Custom answer score breakdown")
        plot_feature_radar(custom_result, "Custom answer NLP feature radar")
        '''
    ),
    markdown(
        """
        ## 8. Interactive answer tester

        Choose a skill/question from the dataset, edit the answer, and click Run scoring.
        """
    ),
    code(
        """
        try:
            import ipywidgets as widgets

            skills = sorted(questions_df["skill"].dropna().astype(str).unique())
            skill_picker = widgets.Dropdown(options=skills, value="Python" if "Python" in skills else skills[0], description="Skill")
            difficulty_picker = widgets.Dropdown(options=["Easy", "Medium", "Hard"], value="Medium", description="Difficulty")
            question_picker = widgets.Dropdown(description="Question", layout=widgets.Layout(width="95%"))
            answer_box = widgets.Textarea(
                description="Answer",
                layout=widgets.Layout(width="95%", height="180px"),
            )
            run_button = widgets.Button(description="Run scoring", button_style="primary")
            output = widgets.Output()

            def rows_for_skill(skill: str) -> pd.DataFrame:
                rows = questions_df[questions_df["skill"].astype(str) == skill].drop_duplicates("question")
                return rows.head(100)

            def refresh_questions(*_args: Any) -> None:
                rows = rows_for_skill(skill_picker.value)
                question_picker.options = [
                    (f"{idx}: {clean_text(row['question'])[:110]}", idx)
                    for idx, row in rows.iterrows()
                ]
                if question_picker.options:
                    question_picker.value = question_picker.options[0][1]
                    row = questions_df.loc[question_picker.value]
                    answer_box.value = clean_text(row.get("answer", ""))

            def refresh_answer(*_args: Any) -> None:
                if question_picker.value is not None:
                    row = questions_df.loc[question_picker.value]
                    answer_box.value = clean_text(row.get("answer", ""))

            def run_interactive(_button: Any) -> None:
                with output:
                    clear_output(wait=True)
                    row = questions_df.loc[question_picker.value]
                    result = score_answer(
                        question=row["question"],
                        answer=answer_box.value,
                        ideal_answer=row.get("ideal_answer", ""),
                        ideal_keywords=row.get("ideal_keywords", ""),
                        skill=row.get("skill", skill_picker.value),
                        sub_domain=row.get("sub_domain", ""),
                        difficulty=difficulty_picker.value,
                    )
                    display(summarize_results([("interactive", result)]))
                    display(Markdown("### Feedback"))
                    display(result["feedback"])
                    display(Markdown("### Entities"))
                    display(result["ner"])
                    plot_result(result, "Interactive answer score breakdown")
                    plot_feature_radar(result, "Interactive answer NLP feature radar")

            skill_picker.observe(refresh_questions, names="value")
            question_picker.observe(refresh_answer, names="value")
            run_button.on_click(run_interactive)
            refresh_questions()

            display(widgets.VBox([skill_picker, difficulty_picker, question_picker, answer_box, run_button, output]))
        except Exception as exc:
            print("Interactive widgets are not available in this runtime.")
            print(exc)
        """
    ),
    markdown(
        """
        ## 9. Knowledge graph visual

        Highlighted nodes are concepts found in the answer.
        """
    ),
    code(
        """
        def plot_knowledge_graph(skill: str, answer_text: str) -> None:
            graph = kg_scorer.graphs.get(skill)
            if graph is None:
                print(f"No graph found for skill: {skill}")
                return

            kg_payload = kg_scorer.score_answer(skill, answer_text)
            found = set(kg_payload.get("found_nodes", []))
            colors = ["#2ca02c" if node in found else "#d9d9d9" for node in graph.nodes()]
            sizes = [900 if node in found else 450 for node in graph.nodes()]

            plt.figure(figsize=(13, 9))
            pos = nx.spring_layout(graph, seed=42, k=0.95)
            nx.draw_networkx_edges(graph, pos, alpha=0.25, arrows=True, arrowsize=12)
            nx.draw_networkx_nodes(graph, pos, node_color=colors, node_size=sizes, edgecolors="#333333")
            nx.draw_networkx_labels(
                graph,
                pos,
                labels={node: str(node).replace("_", " ") for node in graph.nodes()},
                font_size=8,
            )
            plt.title(f"{skill} knowledge graph coverage")
            plt.axis("off")
            plt.show()

            display(pd.DataFrame([kg_payload]))

        plot_knowledge_graph(custom_result["skill"], custom_result["answer"])
        """
    ),
    markdown(
        """
        ## 10. Batch model check with a confusion matrix

        This samples your labelled training CSV and compares the standalone joblib model
        prediction with the dataset label.
        """
    ),
    code(
        """
        EVAL_SAMPLE_SIZE = 120
        eval_df = train_df.sample(min(EVAL_SAMPLE_SIZE, len(train_df)), random_state=7).copy()

        rows = []
        errors = []
        for idx, row in eval_df.iterrows():
            try:
                result = score_answer(
                    question=row["question"],
                    answer=row["answer"],
                    ideal_answer=row.get("ideal_answer", ""),
                    ideal_keywords=row.get("ideal_keywords", ""),
                    skill=row.get("skill", "Python"),
                    sub_domain=row.get("sub_domain", ""),
                    difficulty=row.get("difficulty", "medium"),
                    use_pipeline=False,
                )
                rows.append(
                    {
                        "idx": idx,
                        "true_label": row["label"],
                        "pred_label": result["model_label"],
                        "final_score": result["final_score"],
                        "nlp_score": result["nlp"].get("overall_score", 0.0),
                        "skill": row.get("skill", ""),
                    }
                )
            except Exception as exc:
                errors.append({"idx": idx, "error": str(exc)})

        eval_results = pd.DataFrame(rows)
        display(eval_results.head())
        print(f"Scored {len(eval_results)} rows. Errors: {len(errors)}")

        labels = ["Good", "Average", "Poor"]
        matrix = confusion_matrix(eval_results["true_label"], eval_results["pred_label"], labels=labels)
        fig, ax = plt.subplots(figsize=(7, 5))
        image = ax.imshow(matrix, cmap="Blues")
        ax.set_xticks(range(len(labels)), labels=labels)
        ax.set_yticks(range(len(labels)), labels=labels)
        for row_idx in range(matrix.shape[0]):
            for col_idx in range(matrix.shape[1]):
                ax.text(col_idx, row_idx, matrix[row_idx, col_idx], ha="center", va="center", color="#111111")
        ax.set_title("Standalone model confusion matrix")
        ax.set_xlabel("predicted")
        ax.set_ylabel("true")
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        plt.tight_layout()
        plt.show()

        print(classification_report(eval_results["true_label"], eval_results["pred_label"], labels=labels, zero_division=0))
        """
    ),
    markdown(
        """
        ## 11. Optional retraining sandbox

        Set `RUN_RETRAIN = True` when you want to build a fresh local model in the notebook.
        This does not overwrite your existing `svm_model.joblib`.
        """
    ),
    code(
        """
        RUN_RETRAIN = False

        if RUN_RETRAIN:
            from sklearn.metrics import ConfusionMatrixDisplay
            from sklearn.model_selection import train_test_split
            from retrain_ml_model import build_features, make_pipeline

            X, y = build_features(train_df)
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.25, random_state=42, stratify=y
            )
            fresh_model = make_pipeline("rf")
            fresh_model.fit(X_train, y_train)
            y_pred = fresh_model.predict(X_test)

            print(classification_report(y_test, y_pred, zero_division=0))
            ConfusionMatrixDisplay.from_predictions(y_test, y_pred, cmap="Greens")
            plt.title("Fresh retrained RF confusion matrix")
            plt.show()
        else:
            print("Retraining skipped. Change RUN_RETRAIN to True to run this sandbox.")
        """
    ),
    markdown(
        """
        ## Done

        You now have a repeatable notebook for testing individual answers, comparing dataset
        examples, inspecting model behavior, and generating visuals for the scoring stack.
        """
    ),
]


notebook = {
    "cells": cells,
    "metadata": {
        "colab": {"provenance": []},
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.x",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


out_path = Path(__file__).with_name("interviv_model_lab.ipynb")
out_path.write_text(json.dumps(notebook, indent=2), encoding="utf-8")
print(f"Wrote {out_path}")

upload_cells = list(cells)
upload_cells[1] = markdown(
    """
    ## 1. Find Or Extract Uploaded Project Files

    Upload `interViv_best_required_files.zip` to Colab's Files panel, then run this
    notebook. The setup cell will find the zip in `/content`, extract it, and use
    the extracted model/data/code for all outputs.

    It also works if you upload an already-extracted `interViv_best` folder.
    """
)
upload_cells[2] = _upload_setup_cell()

upload_notebook = dict(notebook)
upload_notebook["cells"] = upload_cells

upload_out_path = Path(__file__).with_name("interviv_model_lab_upload.ipynb")
upload_out_path.write_text(json.dumps(upload_notebook, indent=2), encoding="utf-8")
print(f"Wrote {upload_out_path}")

required_zip_path = _write_required_files_zip()
print(f"Wrote {required_zip_path}")

standalone_cells = list(cells)
standalone_cells[1] = markdown(
    """
    ## 1. Unpack the built-in standalone runtime

    This standalone notebook already contains the required interViv modules, datasets,
    and `svm_model.joblib`. Upload this single `.ipynb` to Google Colab and run all cells.
    """
)
standalone_cells[2] = _standalone_setup_cell(_bundle_base64())

standalone_notebook = dict(notebook)
standalone_notebook["cells"] = standalone_cells

standalone_out_path = Path(__file__).with_name("interviv_model_lab_standalone.ipynb")
standalone_out_path.write_text(json.dumps(standalone_notebook, indent=2), encoding="utf-8")
print(f"Wrote {standalone_out_path}")
