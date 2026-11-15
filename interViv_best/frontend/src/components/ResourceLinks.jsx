import React, { useEffect, useState } from "react";
import { buildResourceListModel, groupResourcesByLevel } from "../lib/resourceList";
import { fetchResources } from "../lib/api";
import { readScoped, writeScoped } from "../lib/accountStorage";

const LEVEL_LABEL = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};
const SOURCE_LABEL = { youtube: 'YouTube', docs: 'Guide / course', other: 'Practice / tool' };

/**
 * Compact curated links for a skill or bank question.
 * Always shows loading, error, or a one-line empty state.
 */
export default function ResourceLinks({
  skillId = null,
  questionId = null,
  heading = "Learn more",
  maxPerLevel = 3,
  variant = "light",
  emptyMessage = "No curated resources for this skill yet.",
  trackProgress = false,
  userId = null,
}) {
  const [items, setItems] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [source, setSource] = useState('');
  const [completed, setCompleted] = useState({});
  const [storageNotice, setStorageNotice] = useState('');

  useEffect(() => {
    if (trackProgress && userId) setCompleted(readScoped('local', userId, 'studied-resources') || {});
  }, [trackProgress, userId]);

  useEffect(() => {
    if (!skillId && !questionId) {
      setItems([]);
      setLoaded(true);
      return undefined;
    }
    let cancelled = false;
    setLoaded(false);
    setError('');
    fetchResources({ skillId, questionId, limitPerLevel: maxPerLevel })
      .then((data) => {
        if (cancelled) return;
        setItems(buildResourceListModel(data, { limitPerLevel: maxPerLevel }));
        setLoaded(true);
      })
      .catch((err) => {
        if (cancelled) return;
        setItems([]);
        setError(err.message || 'Resources are not available right now.');
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [skillId, questionId, maxPerLevel]);

  if (!loaded) return <p role="status">Loading resources…</p>;
  if (error) return <p role="alert">{error}</p>;
  if (items.length === 0) return <p>{emptyMessage}</p>;

  const visible = items.filter(row => (!query.trim() || row.title.toLowerCase().includes(query.trim().toLowerCase())) && (!source || row.source === source));
  const groups = groupResourcesByLevel(visible);
  const isDark = variant === "dark";
  const wrap = isDark
    ? "mt-3 rounded-2xl border border-white/10 bg-white/[0.03] p-3"
    : "mt-3 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-3";
  const titleCls = isDark
    ? "text-xs font-semibold uppercase tracking-[0.12em] text-cyan-200/80"
    : "text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-accent)]";
  const linkCls = isDark
    ? "text-sm text-cyan-100/90 underline-offset-2 hover:underline"
    : "text-sm text-[var(--color-ink)] underline-offset-2 hover:underline";
  const muted = isDark ? "text-white/45" : "text-[var(--color-ink-muted)]";

  return (
    <div className={wrap} data-testid="resource-links">
      <p className={titleCls}>{heading}</p>
      {trackProgress && <>
        <div className="iv-resource-filters">
          <label><span className="sr-only">Search resources</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search these resources" /></label>
          <label><span className="sr-only">Resource format</span><select value={source} onChange={event => setSource(event.target.value)}><option value="">All formats</option><option value="youtube">Videos</option><option value="docs">Guides & courses</option><option value="other">Practice & tools</option></select></label>
        </div>
        <p className="iv-resource-note">Studied markers are saved on this device for your account.</p>
        {storageNotice && <p role="status" className="iv-resource-note">{storageNotice}</p>}
        {!visible.length && <p className="iv-resource-note">No resources match these filters.</p>}
      </>}
      {Object.entries(groups).map(([level, rows]) =>
        rows.length === 0 ? null : (
          <div key={level} className="mt-2">
            <p className={`text-[10px] uppercase tracking-[0.14em] ${muted}`}>{LEVEL_LABEL[level]}</p>
            <ul className="mt-1 space-y-1">
              {rows.map((row) => (
                <li key={`${row.url}-${row.title}`} className={trackProgress ? 'iv-resource-row' : undefined}>
                  <span>
                  <a
                    href={row.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className={linkCls}
                  >
                    {row.title}
                  </a>
                  <span className={`ml-2 text-[10px] ${muted}`}>{SOURCE_LABEL[row.source] || row.source}</span>
                  </span>
                  {trackProgress && <button type="button" className="iv-resource-mark" aria-pressed={Boolean(completed[row.url])}
                    onClick={() => {
                      const next = { ...completed };
                      if (next[row.url]) delete next[row.url]; else next[row.url] = true;
                      setCompleted(next);
                      setStorageNotice(writeScoped('local', userId, 'studied-resources', next) ? '' : 'Could not save to this device. This change lasts only until you leave the page.');
                    }}>{completed[row.url] ? 'Studied ✓' : 'Mark studied'}</button>}
                </li>
              ))}
            </ul>
          </div>
        )
      )}
    </div>
  );
}

/** Test/helper export: render model to plain objects (titles + urls). */
export function resourceListFromMock(payload) {
  return buildResourceListModel(payload);
}
