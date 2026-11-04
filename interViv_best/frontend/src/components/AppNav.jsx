import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  PRIMARY_NAV,
  isGroupActive,
  isNavActive,
  mobileNavSections,
  secondaryNavItems,
} from '../lib/appNav';
import { fetchMe } from '../lib/api';
import AccountMenu from './AccountMenu';

const linkClass = (active) =>
  `rounded-[var(--radius-pill)] px-3.5 py-2 text-sm transition-colors ${
    active
      ? 'bg-[var(--color-ink)] font-semibold text-white shadow-sm'
      : 'font-medium text-[var(--color-ink)] hover:bg-[var(--color-card)]'
  }`;

/** Dropdown for a group of destinations (Career & Resume, More). */
function NavDropdown({ id, label, items, active, testIdPrefix }) {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const buttonRef = useRef(null);

  useEffect(() => { setOpen(false); }, [location.pathname, location.hash]);

  useEffect(() => {
    if (!open) return undefined;
    function onPointerDown(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false);
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    }
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={`app-nav-${id}-panel`}
        data-testid={`${testIdPrefix}-button`}
        className={`inline-flex min-h-10 items-center gap-1.5 ${linkClass(active && !open)}`}
      >
        {label}
        <span aria-hidden="true" className={`text-[10px] transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>
      <div
        id={`app-nav-${id}-panel`}
        data-testid={`${testIdPrefix}-menu`}
        hidden={!open}
        className="absolute left-0 top-full z-50 mt-2 w-56 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-white p-2 shadow-[0_12px_40px_rgba(15,23,42,0.12)]"
      >
        <div className="flex flex-col gap-0.5">
          {items.map((item) => {
            const itemActive = isNavActive(location.pathname, item.to);
            return (
              <Link
                key={`${item.label}:${item.to}`}
                to={item.to}
                data-nav={item.label}
                onClick={() => setOpen(false)}
                className={linkClass(itemActive)}
                aria-current={itemActive ? 'page' : undefined}
                title={item.to.includes('#target') ? 'Choose a company and role on Home first' : item.label}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/**
 * Signed-in navigation: Home · Practice · Coding Arena · Career & Resume ▾ ·
 * Progress, a "More" menu for secondary pages, and the account menu with
 * Sign out. Small screens get one menu with every destination.
 */
export default function AppNav({
  brandTo = '/home',
  userId = null,
  roleId = null,
  userName = '',
  userEmail = '',
  trailing = null,
}) {
  const location = useLocation();
  const [profile, setProfile] = useState({ userId, roleId, userName, userEmail });
  const [menuOpen, setMenuOpen] = useState(false);
  const rootRef = useRef(null);
  const menuButtonRef = useRef(null);

  useEffect(() => {
    setProfile((prev) => ({
      userId: userId || prev.userId,
      roleId: roleId || prev.roleId,
      userName: userName || prev.userName,
      userEmail: userEmail || prev.userEmail,
    }));
  }, [userId, roleId, userName, userEmail]);

  useEffect(() => {
    if (userId && (userName || userEmail)) return undefined;
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        const u = me.user || me;
        setProfile({
          userId: u.id || u.user_id || null,
          roleId: u.target_role_id || null,
          userName: u.name || '',
          userEmail: u.email || '',
        });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [userId, roleId, userName, userEmail]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    function onPointerDown(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) setMenuOpen(false);
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        menuButtonRef.current?.focus();
      }
    }
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [menuOpen]);

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname, location.hash]);

  const secondary = secondaryNavItems({ userId: profile.userId, roleId: profile.roleId });
  const sections = mobileNavSections({ userId: profile.userId, roleId: profile.roleId });
  const moreActive = secondary.some((item) => isNavActive(location.pathname, item.to));

  return (
    <nav
      ref={rootRef}
      className="app-primary-nav relative z-40 border-b border-[var(--color-border)] pb-5"
      data-testid="app-primary-nav"
      aria-label="Primary"
    >
      <div className="flex items-center justify-between gap-3">
        <Link
          to={brandTo}
          className="text-[length:var(--text-3xl)] text-[var(--color-ink)]"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          interViv
        </Link>

        {/* Desktop: five primary destinations plus More */}
        <div className="hidden items-center gap-1.5 md:flex" data-testid="app-nav-desktop">
          {PRIMARY_NAV.map((item) => {
            if (item.children) {
              return (
                <NavDropdown
                  key={item.id}
                  id={item.id}
                  label={item.label}
                  items={item.children}
                  active={isGroupActive(location.pathname, item)}
                  testIdPrefix={`app-nav-${item.id}`}
                />
              );
            }
            const active = isNavActive(location.pathname, item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                data-nav={item.label}
                className={linkClass(active)}
                aria-current={active ? 'page' : undefined}
              >
                {item.label}
              </Link>
            );
          })}
          <NavDropdown id="more" label="More" items={secondary} active={moreActive} testIdPrefix="app-nav-more" />
        </div>

        <div className="flex items-center gap-2">
          {trailing}
          <AccountMenu userName={profile.userName} userEmail={profile.userEmail} fetchProfile={false} />
          <button
            ref={menuButtonRef}
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
            aria-controls="app-nav-slide-panel"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            data-testid="app-nav-menu-button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-card)] transition hover:border-slate-300 md:hidden"
          >
            <span aria-hidden="true" className="text-lg leading-none text-[var(--color-ink)]">{menuOpen ? '×' : '≡'}</span>
          </button>
        </div>
      </div>

      {/* Small screens: one menu with every destination, grouped */}
      <div
        id="app-nav-slide-panel"
        data-testid="app-nav-menu"
        className="md:hidden"
        hidden={!menuOpen}
      >
        <div className="mt-3 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-3">
          {sections.map((section) => (
            <div key={section.title} className="mb-2 last:mb-0">
              <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-muted)]">
                {section.title}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {section.items.map((item) => {
                  const active = isNavActive(location.pathname, item.to);
                  return (
                    <Link
                      key={`${item.label}:${item.to}`}
                      to={item.to}
                      data-nav={item.label}
                      onClick={() => setMenuOpen(false)}
                      className={linkClass(active)}
                      aria-current={active ? 'page' : undefined}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </nav>
  );
}
