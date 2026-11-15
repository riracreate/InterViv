import { COMMON_SKILLS } from './skillChips.js';

const CATALOG = [...COMMON_SKILLS, 'React', 'TypeScript', 'Node.js', 'AWS', 'Docker', 'Kubernetes', 'PostgreSQL', 'MongoDB', 'Git', 'REST', 'HTML', 'CSS'];
const clean = value => typeof value === 'string' ? value.trim().slice(0, 1000) : '';

export function emptyCareerProfile(name = '') {
  return { name: clean(name), headline: '', skills: [], roles: [] };
}

function uniqueSkills(values) {
  const seen = new Set();
  return values.map(value => clean(typeof value === 'string' ? value : value?.name))
    .filter(value => value && !seen.has(value.toLowerCase()) && seen.add(value.toLowerCase())).slice(0, 100);
}

function extractTextSkills(text) {
  return CATALOG.filter(skill => {
    const escaped = skill.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return new RegExp(`(^|[^a-z0-9])${escaped}(?=$|[^a-z0-9])`, 'i').test(text);
  });
}

/** Handle commas, quoted values, escaped quotes and line breaks in exports. */
export function parseCsv(text) {
  const rows = [];
  let row = [], value = '', quoted = false;
  const source = String(text || '').replace(/^\uFEFF/, '');
  for (let i = 0; i < source.length; i += 1) {
    const char = source[i];
    if (char === '"') {
      if (quoted && source[i + 1] === '"') { value += '"'; i += 1; }
      else quoted = !quoted;
    } else if (char === ',' && !quoted) { row.push(value); value = ''; }
    else if ((char === '\n' || char === '\r') && !quoted) {
      if (char === '\r' && source[i + 1] === '\n') i += 1;
      row.push(value); rows.push(row); row = []; value = '';
    } else value += char;
  }
  if (quoted) throw new Error('This CSV has an unfinished quoted field.');
  if (value || row.length) { row.push(value); rows.push(row); }
  const header = (rows.shift() || []).map(column => column.trim().toLowerCase());
  return rows.filter(columns => columns.some(column => column.trim())).map(columns => Object.fromEntries(header.map((name, index) => [name, columns[index] || ''])));
}

function normalizeRole(role) {
  role = role && typeof role === 'object' ? role : {};
  return { title: clean(role.title || role.role || role.position || role['title']),
    company: clean(role.company || role.companyName || role['company name']),
    start: clean(role.start || role.startDate || role['started on']),
    end: clean(role.end || role.endDate || role['finished on']) };
}

export function parseCareerImport(text, fileName = '') {
  const source = String(text || '').trim();
  if (!source) throw new Error('There is no text to import.');
  const profile = emptyCareerProfile();
  if (/\.json$/i.test(fileName)) {
    let parsed;
    try { parsed = JSON.parse(source); } catch { throw new Error('This JSON file could not be read.'); }
    const data = parsed?.profile || parsed;
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Expected a profile object in this JSON file.');
    profile.name = clean(data.name || [data.firstName, data.lastName].filter(Boolean).join(' '));
    profile.headline = clean(data.headline);
    profile.skills = uniqueSkills(Array.isArray(data.skills) ? data.skills : []);
    profile.roles = (Array.isArray(data.roles) ? data.roles : Array.isArray(data.positions) ? data.positions : Array.isArray(data.experience) ? data.experience : []).map(normalizeRole).filter(role => role.title || role.company).slice(0, 100);
  } else if (/\.csv$/i.test(fileName)) {
    const rows = parseCsv(source);
    const first = rows[0] || {};
    if ('first name' in first || 'last name' in first || 'headline' in first) {
      profile.name = clean([first['first name'], first['last name']].filter(Boolean).join(' '));
      profile.headline = clean(first.headline);
    } else if ('company name' in first || 'title' in first) {
      profile.roles = rows.map(normalizeRole).filter(role => role.title || role.company).slice(0, 100);
    } else if ('name' in first) profile.skills = uniqueSkills(rows.map(row => row.name));
  } else profile.skills = extractTextSkills(source);
  if (!profile.name && !profile.headline && !profile.skills.length && !profile.roles.length) {
    throw new Error('No supported profile details were found. You can enter them manually.');
  }
  return profile;
}

export function mergeCareerProfile(current, imported) {
  const roles = [...(current.roles || [])];
  const seen = new Set(roles.map(role => `${role.title}|${role.company}|${role.start}|${role.end}`.toLowerCase()));
  for (const role of imported.roles || []) {
    const key = `${role.title}|${role.company}|${role.start}|${role.end}`.toLowerCase();
    if (!seen.has(key)) { seen.add(key); roles.push(role); }
  }
  return { name: imported.name || current.name || '', headline: imported.headline || current.headline || '',
    skills: uniqueSkills([...(current.skills || []), ...(imported.skills || [])]), roles: roles.slice(0, 100) };
}
