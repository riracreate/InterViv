"""One-shot transcription of the 12 starter roles. No model calls."""
from __future__ import annotations

import certifi
import json
import re
import ssl
import urllib.request
from pathlib import Path

import yaml

from modules.role_blueprints import RESEARCH_PATH, ROOT

OUT = ROOT / "data" / "role_blueprints"
ACCESS = "2026-11-17"
FAMILIES = {
    "backend-engineer": "engineering",
    "frontend-engineer": "engineering",
    "fullstack-engineer": "engineering",
    "devops-cloud-engineer": "engineering",
    "qa-test-engineer": "engineering",
    "data-analyst": "data",
    "data-scientist-ml": "data",
    "business-analyst": "business",
    "associate-product-manager": "product",
    "product-marketing": "business",
    "ui-ux-designer": "design",
    "operations-project-coordinator": "business",
}
TYPE_MAP = {"technical": "technical", "role scenario": "role_scenario", "behavioural": "behavioural"}
KIND_MAP = {
    "resume / project opener": "opener",
    "core technical — fundamentals": "fundamentals",
    "core technical — deep / trade-off": "tradeoff",
    "role scenario": "scenario",
    "behavioural (star)": "behavioural",
    "practical round": "practical",
}


def slug(text: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return token or "competency"


def fetch(url: str) -> tuple[str, str]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "interviv-blueprint-check"})
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(request, timeout=20, context=context) as response:
            body = response.read(250_000).decode("utf-8", "replace")
            final = response.geturl()
    except Exception as exc:
        return "unverified", str(exc.__class__.__name__)
    title = ""
    match = re.search(r"<title>(.*?)</title>", body, re.I | re.S)
    if match:
        title = re.sub(r"\s+", " ", match.group(1)).strip()
    if body.lstrip().startswith("{") or '"title"' in body[:500]:
        try:
            payload = json.loads(body)
            title = str(payload.get("title") or payload.get("preferredLabel") or title)
        except json.JSONDecodeError:
            labelled = re.search(r'"preferredLabel"\s*:\s*"([^"]+)"', body) or re.search(r'"title"\s*:\s*"([^"]+)"', body)
            if labelled:
                title = labelled.group(1)
    return ("verified" if title else "unverified", title or final)


def aliases_from(text: str) -> dict[str, list[str]]:
    found = {}
    for line in text.splitlines():
        match = re.search(r"\(`([a-z0-9-]+)`\)\s*\|\s*[^|]+\|\s*([^|]+)\|", line)
        if not match:
            continue
        found[match.group(1)] = [part.strip() for part in match.group(2).split(",") if part.strip()]
    return found


def competencies(table: str) -> list[dict]:
    rows = []
    seen = set()
    for line in table.splitlines():
        if not line.startswith("| **"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        name = re.sub(r"\*+", "", cells[0]).strip()
        kind = TYPE_MAP.get(cells[1].strip().lower())
        if kind is None:
            continue
        weight = float(cells[2])
        linked = cells[3]
        head = re.split(r"\s*\(", linked, maxsplit=1)[0]
        skills = re.findall(r"`([^`]+)`", head)
        topic = re.sub(r"`[^`]+`", "", linked)
        topic = re.sub(r"\*+", "", topic).strip(" ()")
        cid = slug(name)
        if cid in seen:
            cid = f"{cid}-2"
        seen.add(cid)
        item = {
            "id": cid,
            "name": name,
            "type": kind,
            "weight": weight,
            "skills": skills if kind == "technical" else [],
            "scenario_topics": [] if kind == "technical" else [topic or name],
        }
        rows.append(item)
    return rows


def questions(section: str) -> list[dict]:
    seeds = []
    for match in re.finditer(r"- \*\*([^*]+)\*\*: \"([^\"]+)\"", section):
        label = match.group(1).strip().lower()
        kind = KIND_MAP.get(label, slug(label))
        seeds.append({"kind": kind, "text": match.group(2).strip()})
    return seeds


def expectations(section: str) -> dict[str, str]:
    start = section.find("**Level Expectations**")
    end = section.find("| Competency")
    chunk = section[start:end] if start != -1 and end != -1 else ""
    junior = mid = ""
    for match in re.finditer(r"- \*\*([^*]+)\*\*: (.+)", chunk):
        label, text = match.group(1).lower(), " ".join(match.group(2).split())
        if "intern" in label or "junior" in label:
            junior = text
        elif label.strip() == "mid":
            mid = text
    return {"intern": junior, "junior": junior, "mid": mid}


def provenance(section: str, role_id: str) -> dict:
    links = re.findall(r"\[([^\]]+)\]\((https?://[^)]+)\)", section.split("**Representative")[0])
    onet = next(((label, url) for label, url in links if "onetonline.org" in url), ("", ""))
    esco = next(((label, url) for label, url in links if "esco" in url), ("", ""))
    if role_id == "devops-cloud-engineer":
        onet = (
            "15-1299.08 Computer Systems Engineers/Architects",
            "https://www.onetonline.org/link/summary/15-1299.08",
        )
    if role_id == "associate-product-manager":
        onet = ("", "")
    records = {}
    if role_id == "associate-product-manager":
        records["onet"] = {
            "code": "",
            "title": "",
            "url": "",
            "accessed": ACCESS,
            "status": "none",
            "page_title": "",
            "note": "Owner decision: no O*NET product-manager occupation. ESCO ICT product manager is the primary mapping.",
        }
    for key, (label, url) in (("onet", onet), ("esco", esco)):
        if key in records:
            continue
        if not url:
            records[key] = {"code": "", "title": label, "url": "", "accessed": ACCESS, "status": "unverified", "page_title": "", "note": "no url in the research file"}
            continue
        status, detail = fetch(url)
        code_match = re.search(r"(\d{2}-\d{4}\.\d{2})", label) or re.search(r"(\d{2}-\d{4}\.\d{2})", url)
        if key == "esco":
            code_match = re.search(r"(\d{4}\.\d+(?:\.\d+)?)", label)
        code = code_match.group(1) if code_match else ""
        note = "" if status == "verified" else detail
        if role_id == "devops-cloud-engineer" and key == "onet":
            note = "Owner decision: use Computer Systems Engineers/Architects instead of the network-administrator mapping. " + note
        if role_id == "devops-cloud-engineer" and key == "esco":
            note = "Page was read. Owner did not replace this ESCO code; it remains ICT system administrator, a weak fit for DevOps. " + note
        records[key] = {
            "code": code,
            "title": label,
            "url": url,
            "accessed": ACCESS,
            "status": status,
            "page_title": detail if status == "verified" else "",
            "note": note,
        }
    records["source"] = "docs/research/role_catalog_research.md"
    return records


def main() -> None:
    text = RESEARCH_PATH.read_text()
    alias_map = aliases_from(text)
    parts = re.split(r"\n### \d+\. ", text)
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for part in parts[1:]:
        heading, _, body = part.partition("\n")
        match = re.search(r"\(`([a-z0-9-]+)`\)", heading)
        if not match or match.group(1) not in FAMILIES:
            continue
        role_id = match.group(1)
        title = heading.split("(`")[0].strip()
        track_match = re.search(r"Practical Track: \*\*(Coding|SQL|None)\*\*", body)
        track = {"Coding": "coding", "SQL": "sql", "None": "none"}[track_match.group(1)]
        doc = {
            "id": role_id,
            "title": title,
            "aliases": alias_map.get(role_id, []),
            "family": FAMILIES[role_id],
            "levels": ["intern", "junior", "mid"],
            "practical_track": track,
            "status": "draft",
            "version": 1,
            "level_expectations": expectations(body),
            "level_expectation_review": {"junior": "needs owner edit"},
            "competencies": competencies(body),
            "draft_seeds": questions(body),
            "provenance": provenance(body, role_id),
        }
        path = OUT / f"{role_id}.yaml"
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
        written.append(role_id)
        print(role_id, "weights", round(sum(item["weight"] for item in doc["competencies"]), 3),
              "seeds", len(doc["draft_seeds"]), "onet", doc["provenance"]["onet"]["status"])
    print("wrote", len(written))


if __name__ == "__main__":
    main()
