import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { isNavActive, navDestinations } from '../lib/appNav';

/**
 * Shared primary nav for demo path pages.
 * flex-wrap keeps mobile widths from overflowing (Track 3 visual bar).
 */
export default function AppNav({
  brandTo = '/home',
  userId = null,
  roleId = null,
  trailing = null,
}) {
  const location = useLocation();
  const items = navDestinations({ userId, roleId });

  return (
    <nav
      className="app-primary-nav flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] pb-5"
      data-testid="app-primary-nav"
      aria-label="Primary"
    >
      <Link
        to={brandTo}
        className="text-[length:var(--text-3xl)] text-[var(--color-ink)]"
        style={{ fontFamily: 'var(--font-display)' }}
      >
        interViv
      </Link>
      <div className="flex max-w-full flex-wrap items-center gap-1 sm:gap-2">
        {items.map((item) => {
          const active = isNavActive(location.pathname, item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              data-nav={item.label}
              className={
                active
                  ? 'rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-3 py-1.5 text-sm font-semibold text-white'
                  : 'rounded-[var(--radius-pill)] px-3 py-1.5 text-sm text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]'
              }
              aria-current={active ? 'page' : undefined}
            >
              {item.label}
            </Link>
          );
        })}
        {trailing}
      </div>
    </nav>
  );
}
