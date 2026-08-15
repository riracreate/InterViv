"""Dataset registry and SemEval XML-to-JSONL normalization."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .schema import Concept, Example, SCHEMA_VERSION, load_jsonl, write_jsonl

LAB_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = LAB_ROOT / "data"
SEMEVAL_SOURCE_COMMIT = "5157c69f914e8c581045c03e98f96398d40a91b8"
SEMEVAL_DATASET_VERSION = (
    f"semeval-2013-task7-5way@{SEMEVAL_SOURCE_COMMIT};Core/test"
)
INTERNAL_DATASET_VERSION = "grader-lab-perturbations-v1"
SEMEVAL_DATASET_SOURCE = (
    "https://github.com/myrosia/semeval-2013-task7/tree/"
    + SEMEVAL_SOURCE_COMMIT
)
DATASET_PROVENANCE: dict[str, dict[str, str]] = {
    "scientsbank": {
        "source": SEMEVAL_DATASET_SOURCE,
        "license_status": "CC BY-SA 3.0; commercial use permitted with attribution/share-alike",
    },
    "beetle": {
        "source": SEMEVAL_DATASET_SOURCE,
        "license_status": "CC BY-SA 3.0; commercial use permitted with attribution/share-alike",
    },
    "internal_perturbation": {
        "source": "repository-local synthetic fixtures",
        "license_status": "interViv project material",
    },
    "ricechem": {
        "source": "not supplied",
        "license_status": "pending_access_and_license_review",
    },
}

_CONTENT_STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "answer",
    "because",
    "before",
    "being",
    "between",
    "could",
    "does",
    "from",
    "have",
    "into",
    "more",
    "other",
    "same",
    "than",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "through",
    "using",
    "water",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
}


@dataclass(frozen=True)
class DatasetLoadResult:
    name: str
    status: str
    version: str
    path: Path
    examples: tuple[Example, ...] = ()
    note: str = ""


def load_registered_datasets(
    data_dir: str | Path = DEFAULT_DATA_DIR,
) -> dict[str, DatasetLoadResult]:
    root = Path(data_dir)
    registry = {
        "scientsbank": (
            root / "sem_eval_2013_task_7" / "scientsbank.jsonl",
            SEMEVAL_DATASET_VERSION,
        ),
        "beetle": (
            root / "sem_eval_2013_task_7" / "beetle.jsonl",
            SEMEVAL_DATASET_VERSION,
        ),
        "internal_perturbation": (
            root / "internal_perturbations.jsonl",
            INTERNAL_DATASET_VERSION,
        ),
        "ricechem": (
            root / "ricechem" / "ricechem.jsonl",
            "pending_access",
        ),
    }

    results: dict[str, DatasetLoadResult] = {}
    for name, (path, expected_version) in registry.items():
        if not path.exists():
            if name == "ricechem":
                results[name] = DatasetLoadResult(
                    name=name,
                    status="pending_access",
                    version="pending_access",
                    path=path,
                    note="RiceChem files are absent; access and license review are pending.",
                )
            else:
                results[name] = DatasetLoadResult(
                    name=name,
                    status="missing",
                    version=expected_version,
                    path=path,
                    note="Expected JSONL file is absent.",
                )
            continue

        examples = tuple(load_jsonl(path))
        versions = {item.dataset_version for item in examples}
        if versions != {expected_version}:
            raise ValueError(
                f"{path}: expected dataset version {expected_version!r}, got {sorted(versions)!r}"
            )
        if any(item.dataset != name for item in examples):
            raise ValueError(f"{path}: contains records for another dataset")
        results[name] = DatasetLoadResult(
            name=name,
            status="loaded",
            version=expected_version,
            path=path,
            examples=examples,
            note=f"{len(examples)} validated examples",
        )
    return results


def import_semeval_5way(source_root: str | Path, output_dir: str | Path) -> dict[str, int]:
    """Normalize the organizer's extracted 5-way `Core` test XML files.

    `source_root` must contain the extracted `beetle/` and `sciEntsBank/`
    directories. Training data and `Extra` facet annotations are intentionally
    excluded so reports evaluate only the official held-out Core partitions.
    """

    source = Path(source_root)
    output = Path(output_dir)
    dataset_dirs = {
        "beetle": source / "beetle",
        "scientsbank": source / "sciEntsBank",
    }
    counts: dict[str, int] = {}
    for dataset_name, dataset_dir in dataset_dirs.items():
        if not dataset_dir.is_dir():
            raise FileNotFoundError(f"Expected extracted dataset directory: {dataset_dir}")
        examples = list(_iter_semeval_examples(dataset_name, dataset_dir))
        write_jsonl(output / f"{dataset_name}.jsonl", examples)
        counts[dataset_name] = len(examples)
    return counts


def _iter_semeval_examples(
    dataset_name: str, dataset_dir: Path
) -> Iterable[Example]:
    paths = sorted(dataset_dir.glob("test-*/Core/*.xml"))
    if not paths:
        raise FileNotFoundError(f"No test-*/Core/*.xml files found under {dataset_dir}")
    for xml_path in paths:
        root = ET.parse(xml_path).getroot()
        question_id = root.attrib.get("id", xml_path.stem)
        question = _element_text(root.find("questionText"))
        references = tuple(
            text
            for text in (_element_text(item) for item in root.findall("./referenceAnswers/referenceAnswer"))
            if text
        )
        if not question or not references:
            raise ValueError(f"{xml_path}: question or reference answer missing")
        concepts = _concepts_from_references(dataset_name, question_id, references)
        split = xml_path.parents[1].name
        source_file = str(xml_path.relative_to(dataset_dir))

        for index, node in enumerate(root.findall("./studentAnswers/studentAnswer")):
            answer = _element_text(node) or node.attrib.get("answerText", "").strip()
            label = node.attrib.get("accuracy", "").strip().lower()
            student_id = node.attrib.get("id", f"{question_id}-{index}")
            yield Example.from_dict(
                {
                    "schema_version": SCHEMA_VERSION,
                    "example_id": f"{dataset_name}:{student_id}",
                    "dataset": dataset_name,
                    "dataset_version": SEMEVAL_DATASET_VERSION,
                    "split": split,
                    "question_id": question_id,
                    "question": question,
                    "reference_answers": list(references),
                    "answer": answer,
                    "gold_label": label,
                    "concepts": [item.to_dict() for item in concepts],
                    "pilot_synthetic": False,
                    "metadata": {
                        "module": root.attrib.get("module", ""),
                        "test_set": root.attrib.get("testSet", split),
                        "source_file": source_file,
                        "source_commit": SEMEVAL_SOURCE_COMMIT,
                    },
                },
                location=str(xml_path),
            )


def _element_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def _concepts_from_references(
    dataset_name: str, question_id: str, references: tuple[str, ...]
) -> tuple[Concept, ...]:
    tokens: list[str] = []
    for text in references:
        for token in re.findall(r"[a-z][a-z0-9-]+", text.lower()):
            if len(token) >= 4 and token not in _CONTENT_STOPWORDS and token not in tokens:
                tokens.append(token)
    if not tokens:
        tokens = ["reference-answer"]
    question_slug = re.sub(r"[^a-z0-9]+", "-", question_id.lower()).strip("-")
    return tuple(
        Concept(
            id=f"concept.{dataset_name}.{question_slug}.{token}",
            description=token.replace("-", " "),
        )
        for token in tokens[:8]
    )


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()
