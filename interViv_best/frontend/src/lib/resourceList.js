/**
 * Pure helpers for curated learning-resource lists (Ticket B).
 * Cap at `limitPerLevel` (default 3) per beginner|intermediate|advanced.
 */

export const RESOURCE_LEVELS = ["beginner", "intermediate", "advanced"];

/**
 * Build a flat display list of {level, title, url, source} from an API payload
 * or a mock `{ resources: [...] }` / `{ by_level: {...} }` object.
 */
export function buildResourceListModel(payload, { limitPerLevel = 3 } = {}) {
  if (!payload) return [];
  const out = [];
  if (payload.by_level && typeof payload.by_level === "object") {
    for (const level of RESOURCE_LEVELS) {
      const rows = Array.isArray(payload.by_level[level]) ? payload.by_level[level] : [];
      for (const row of rows.slice(0, limitPerLevel)) {
        if (!row?.title || !row?.url) continue;
        out.push({
          level,
          title: String(row.title),
          url: String(row.url),
          source: row.source || "other",
        });
      }
    }
    return out;
  }
  const resources = Array.isArray(payload.resources) ? payload.resources : [];
  const counts = { beginner: 0, intermediate: 0, advanced: 0 };
  for (const row of resources) {
    const level = RESOURCE_LEVELS.includes(row.level) ? row.level : "beginner";
    if (counts[level] >= limitPerLevel) continue;
    if (!row?.title || !row?.url) continue;
    counts[level] += 1;
    out.push({
      level,
      title: String(row.title),
      url: String(row.url),
      source: row.source || "other",
    });
  }
  return out;
}

/** Group flat model by level for UI sections. */
export function groupResourcesByLevel(items) {
  const groups = { beginner: [], intermediate: [], advanced: [] };
  for (const item of items || []) {
    if (groups[item.level]) groups[item.level].push(item);
  }
  return groups;
}
