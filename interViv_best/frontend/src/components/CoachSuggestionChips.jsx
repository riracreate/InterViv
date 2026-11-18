import React from 'react';

export default function CoachSuggestionChips({ chips = [], busy = false, onChip }) {
  if (!chips.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2" data-testid="coach-chips">
      {chips.map((chip) => (
        <button
          key={`${chip.type}-${chip.label}`}
          type="button"
          disabled={busy}
          className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold"
          onClick={() => onChip?.(chip)}
        >
          {chip.label}
        </button>
      ))}
    </div>
  );
}
