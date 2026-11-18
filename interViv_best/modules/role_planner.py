"""Deterministic role interview plans. No model calls."""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

SCENARIO_IN_QUICK = frozenset({"business", "product", "design"})
PRACTICE_FAMILIES = SCENARIO_IN_QUICK
_BANK = Path(__file__).resolve().parents[1] / "data" / "interview_dataset_v6.csv"
_BANK_ALIASES = {
    "operating systems": "os",
    "computer networks": "cn",
    "machine learning": "ml",
    "os": "os",
    "cn": "cn",
    "ml": "ml",
}


class PlanError(ValueError):
    pass


@dataclass(frozen=True)
class PlanSlot:
    kind: str
    competency_id: str
    name: str
    skill: str
    difficulty: str
    reason: str
    practice_only: bool
    scored: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


def _diffs(level: str) -> dict[str, str]:
    if level in {"intern", "junior"}:
        return {"default": "medium", "harder": "hard", "fundamentals": "easy"}
    if level == "mid":
        return {"default": "hard", "harder": "hard", "fundamentals": "easy"}
    raise PlanError("level must be intern, junior, or mid")


def _by_weight(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda item: (-float(item["weight"]), str(item["id"])))


def _skill_of(item: dict) -> str:
    skills = item.get("skills") or []
    return str(skills[0]) if skills else str(item.get("name") or item["id"])


def _status_for(item: dict, resume: dict | None) -> str:
    if not resume:
        return ""
    wanted = {str(skill).casefold() for skill in item.get("skills") or []}
    found = []
    for name, status in (resume.get("skills") or {}).items():
        if str(name).casefold() in wanted:
            found.append(status)
    if "claimed_with_evidence" in found:
        return "claimed_with_evidence"
    if "listed_only" in found:
        return "listed_only"
    if "missing" in found:
        return "missing"
    return ""


def _pick_technical(items: list[dict], count: int, resume: dict | None) -> list[tuple[dict, str]]:
    ordered = _by_weight(items)
    chosen: list[dict] = []
    roles: dict[str, str] = {}
    if resume:
        claimed = [item for item in ordered if _status_for(item, resume) == "claimed_with_evidence"]
        missing = [item for item in ordered if _status_for(item, resume) == "missing"]
        if claimed:
            chosen.append(claimed[0])
            roles[claimed[0]["id"]] = "claimed_with_evidence"
        if missing and missing[0]["id"] not in roles:
            chosen.append(missing[0])
            roles[missing[0]["id"]] = "missing"
    for item in ordered:
        if len(chosen) >= count:
            break
        if item["id"] not in roles:
            chosen.append(item)
            roles[item["id"]] = _status_for(item, resume) or "core"
    return [(item, roles[item["id"]]) for item in chosen[:count]]


def _core_slot(item: dict, how: str, level: str) -> PlanSlot:
    band = _diffs(level)
    skill = _skill_of(item)
    if how == "claimed_with_evidence":
        difficulty, reason = band["harder"], f"{skill}: on your resume, asked one level harder"
    elif how == "missing":
        difficulty, reason = band["fundamentals"], f"{skill}: missing from your resume, asked at fundamentals"
    elif how == "listed_only":
        difficulty, reason = band["default"], f"{skill}: listed on your resume"
    else:
        difficulty, reason = band["default"], f"{skill}: core skill for this role"
    return PlanSlot("core", item["id"], item["name"], skill, difficulty, reason, False)


def _easy_bank_keys() -> set[str]:
    keys = set()
    if not _BANK.exists():
        return keys
    with _BANK.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("difficulty") or "").strip().lower() != "easy":
                continue
            skill = " ".join((row.get("skill") or "").split()).casefold()
            if skill:
                keys.add(skill)
    return keys


@lru_cache(maxsize=1)
def easy_bank_skills() -> frozenset[str]:
    return frozenset(_easy_bank_keys())


def _has_easy_bank(skill: str, extra: set[str]) -> bool:
    key = " ".join(str(skill or "").split()).casefold()
    if not key:
        return False
    if key in extra or key in easy_bank_skills():
        return True
    alias = _BANK_ALIASES.get(key)
    return bool(alias and alias in easy_bank_skills())


def _warm_up(blueprint: dict, technical: list[dict], extra_easy: set[str]) -> PlanSlot:
    ranked = _by_weight(technical)
    for item in ranked:
        for skill in item.get("skills") or []:
            if _has_easy_bank(skill, extra_easy):
                return PlanSlot(
                    "opener", item["id"], "Warm-up", str(skill), "easy",
                    f"{skill}: easy bank warm-up", False, True,
                )
    title = str(blueprint.get("title") or "this")
    text = f"Tell me a little about yourself and what draws you to the {title} role."
    return PlanSlot("opener", "", "Role opener", title, "easy", text, False, False)


def plan_role(blueprint: dict, *, level: str, length: str, resume: dict | None = None,
              jd_skills: list[str] | None = None, extra_easy_skills: set[str] | None = None) -> list[PlanSlot]:
    if length not in {"quick", "full"}:
        raise PlanError("length must be quick or full")
    technical = [item for item in blueprint["competencies"] if item["type"] == "technical"]
    scenarios = _by_weight([item for item in blueprint["competencies"] if item["type"] == "role_scenario"])
    behavioural = _by_weight([item for item in blueprint["competencies"] if item["type"] == "behavioural"])
    family = blueprint["family"]
    extra = {str(skill).casefold() for skill in (extra_easy_skills or set())}
    if resume and resume.get("projects"):
        project = str(resume["projects"][0])
        opener = PlanSlot("opener", "", "Resume opener", project, "easy", f"{project}: resume opener", False, False)
    else:
        opener = _warm_up(blueprint, technical, extra)
    slots = [opener]
    scenario_in_quick = family in SCENARIO_IN_QUICK and bool(scenarios)
    if length == "quick":
        core_count = 1 if scenario_in_quick else 2
        for item, how in _pick_technical(technical, core_count, resume):
            slots.append(_core_slot(item, how, level))
        if scenario_in_quick:
            item = scenarios[0]
            slots.append(PlanSlot(
                "scenario", item["id"], item["name"], _skill_of(item), _diffs(level)["default"],
                f"{item['name']}: role scenario", family in PRACTICE_FAMILIES,
            ))
        return slots
    for item, how in _pick_technical(technical, 3, resume):
        slots.append(_core_slot(item, how, level))
    if scenarios:
        item = scenarios[0]
        slots.append(PlanSlot(
            "scenario", item["id"], item["name"], _skill_of(item), _diffs(level)["default"],
            f"{item['name']}: role scenario", family in PRACTICE_FAMILIES,
        ))
    if behavioural:
        item = behavioural[0]
        slots.append(PlanSlot(
            "behavioural", item["id"], item["name"], _skill_of(item), "medium",
            f"{item['name']}: behavioural", False,
        ))
    track = blueprint.get("practical_track") or "none"
    if track != "none":
        slots.append(PlanSlot("practical", "", track.upper(), track, _diffs(level)["default"],
                              f"{track}: practical", False))
    if jd_skills:
        wanted = {str(skill).casefold() for skill in jd_skills}
        for index, slot in enumerate(slots):
            if slot.kind == "core" and slot.skill.casefold() in wanted and slot.reason.endswith("core skill for this role"):
                slots[index] = PlanSlot(
                    slot.kind, slot.competency_id, slot.name, slot.skill, slot.difficulty,
                    f"{slot.skill}: in the job description", slot.practice_only,
                )
    return slots
