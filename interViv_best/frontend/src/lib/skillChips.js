/**
 * Skill chip editing (overhaul Phase 6). Pure.
 *
 * Replaces comma-separated text fields, which re-split on every keystroke
 * and swallowed typed commas and spaces (so "System Design" or a second
 * skill could not be typed).
 */

export const COMMON_SKILLS = Object.freeze([
  'DSA', 'DBMS', 'SQL', 'OOP', 'Operating Systems', 'Computer Networks', 'System Design',
  'Python', 'Java', 'JavaScript', 'Machine Learning', 'Verbal Ability', 'HR',
]);

const MAX_SKILL_LENGTH = 60;

function clean(raw) {
  return String(raw ?? '').replace(/\s+/g, ' ').trim().slice(0, MAX_SKILL_LENGTH);
}

/** Use the suggestion's spelling when the typed text matches it case-insensitively. */
export function canonicalSkill(raw, suggestions = []) {
  const text = clean(raw);
  const match = suggestions.find((s) => String(s).toLowerCase() === text.toLowerCase());
  return match ? String(match) : text;
}

/** Add one or more skills (pasted text may contain commas or new lines). */
export function addSkills(list, raw, suggestions = [], max = 20) {
  const current = Array.isArray(list) ? [...list] : [];
  const seen = new Set(current.map((s) => String(s).toLowerCase()));
  for (const part of String(raw ?? '').split(/[,\n]/)) {
    const skill = canonicalSkill(part, suggestions);
    if (!skill || seen.has(skill.toLowerCase()) || current.length >= max) continue;
    seen.add(skill.toLowerCase());
    current.push(skill);
  }
  return current;
}

export function removeSkill(list, skill) {
  const key = String(skill).toLowerCase();
  return (Array.isArray(list) ? list : []).filter((s) => String(s).toLowerCase() !== key);
}

/** Suggestions matching the query, excluding chosen skills; prefix matches first. */
export function matchSuggestions(suggestions, query, selected = [], limit = 8) {
  const q = clean(query).toLowerCase();
  const chosen = new Set((selected || []).map((s) => String(s).toLowerCase()));
  const unique = [...new Set((suggestions || []).map((s) => String(s)).filter(Boolean))]
    .filter((s) => !chosen.has(s.toLowerCase()));
  if (!q) return unique.slice(0, limit);
  const starts = unique.filter((s) => s.toLowerCase().startsWith(q));
  const contains = unique.filter((s) => !s.toLowerCase().startsWith(q) && s.toLowerCase().includes(q));
  return [...starts, ...contains].slice(0, limit);
}
