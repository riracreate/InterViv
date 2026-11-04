import React, { useId, useState } from 'react';
import { addSkills, matchSuggestions, removeSkill } from '../lib/skillChips';

/**
 * Searchable skill chips. Enter, Tab or a comma adds the typed skill;
 * Backspace on an empty field removes the last chip; suggestions are
 * clickable. Pasting "A, B, C" adds three chips.
 */
export default function SkillChipInput({
  label,
  value = [],
  onChange,
  suggestions = [],
  placeholder = 'Type a skill and press Enter',
  max = 20,
  testId,
}) {
  const id = useId();
  const listId = `${id}-suggestions`;
  const [text, setText] = useState('');
  const [focused, setFocused] = useState(false);
  const matches = matchSuggestions(suggestions, text, value, 8);

  const commit = (raw) => {
    const next = addSkills(value, raw, suggestions, max);
    if (next.length !== value.length) onChange?.(next);
    setText('');
  };

  return (
    <div className="mt-1" data-testid={testId}>
      {label && <label htmlFor={id} className="block text-sm text-[var(--color-ink-muted)]">{label}</label>}
      <div className="mt-1 flex flex-wrap items-center gap-1.5 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-white px-2 py-1.5 focus-within:border-[var(--color-accent)]">
        {value.map((skill) => (
          <span key={skill} className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] bg-[var(--color-surface)] px-2.5 py-1 text-sm text-[var(--color-ink)]">
            {skill}
            <button type="button" aria-label={`Remove ${skill}`} className="text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
              onClick={() => onChange?.(removeSkill(value, skill))}>×</button>
          </span>
        ))}
        <input
          id={id}
          value={text}
          role="combobox"
          aria-expanded={focused && matches.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          placeholder={value.length ? '' : placeholder}
          className="min-w-[8rem] flex-1 border-0 bg-transparent px-1 py-1 text-sm text-[var(--color-ink)] outline-none"
          onFocus={() => setFocused(true)}
          onBlur={() => { setFocused(false); if (text.trim()) commit(text); }}
          onChange={(e) => {
            const next = e.target.value;
            if (next.includes(',')) commit(next);
            else setText(next);
          }}
          onPaste={(e) => {
            const pasted = e.clipboardData?.getData('text') || '';
            if (/[,\n]/.test(pasted)) { e.preventDefault(); commit(pasted); }
          }}
          onKeyDown={(e) => {
            if ((e.key === 'Enter' || e.key === 'Tab') && text.trim()) {
              e.preventDefault();
              commit(text);
            } else if (e.key === 'Backspace' && !text && value.length) {
              onChange?.(value.slice(0, -1));
            }
          }}
        />
      </div>
      {focused && matches.length > 0 && (
        <ul id={listId} role="listbox" className="mt-1 flex flex-wrap gap-1.5">
          {matches.map((skill) => (
            <li key={skill} role="option" aria-selected="false">
              <button type="button" className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-2.5 py-1 text-xs text-[var(--color-ink)] hover:border-[var(--color-accent)]"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => commit(skill)}>
                + {skill}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
