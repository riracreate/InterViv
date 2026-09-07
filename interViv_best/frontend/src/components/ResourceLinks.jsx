import React, { useEffect, useState } from "react";
import { buildResourceListModel, groupResourcesByLevel } from "../lib/resourceList";
import { fetchResources } from "../lib/api";

const LEVEL_LABEL = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

/**
 * Compact curated links for a skill or bank question.
 * Renders nothing when the API returns no rows (no empty-state essay).
 */
export default function ResourceLinks({
  skillId = null,
  questionId = null,
  heading = "Learn more",
  maxPerLevel = 3,
  variant = "light",
  emptyMessage = null,
}) {
  const [items, setItems] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!skillId && !questionId) {
      setItems([]);
      setLoaded(true);
      return undefined;
    }
    let cancelled = false;
    setLoaded(false);
    setError('');
    fetchResources({ skillId, questionId })
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

  if (!loaded) return emptyMessage ? <p role="status">Loading resources…</p> : null;
  if (error) return emptyMessage ? <p role="alert">{error}</p> : null;
  if (items.length === 0) return emptyMessage ? <p>{emptyMessage}</p> : null;

  const groups = groupResourcesByLevel(items);
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
      {Object.entries(groups).map(([level, rows]) =>
        rows.length === 0 ? null : (
          <div key={level} className="mt-2">
            <p className={`text-[10px] uppercase tracking-[0.14em] ${muted}`}>{LEVEL_LABEL[level]}</p>
            <ul className="mt-1 space-y-1">
              {rows.map((row) => (
                <li key={`${row.url}-${row.title}`}>
                  <a
                    href={row.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className={linkCls}
                  >
                    {row.title}
                  </a>
                  <span className={`ml-2 text-[10px] ${muted}`}>{row.source}</span>
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
