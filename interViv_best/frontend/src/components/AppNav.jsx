import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { DESKTOP_NAV_ITEMS, isNavActive, moreNavItems, navDestinations } from '../lib/appNav';
import { fetchMe } from '../lib/api';

/**
 * Brand + desktop destinations (Home, Practice, Progress, Jobs, More).
 * Smaller screens keep the hamburger menu with every destination.
 * Sign-out lives on Account / Settings, not in the primary nav.
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
  const [profile, setProfile] = useState({
    userId,
    roleId,
    userName,
    userEmail,
  });
  const [menuOpen, setMenuOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const rootRef = useRef(null);
  const menuButtonRef = useRef(null);
  const moreButtonRef = useRef(null);

  useEffect(() => {
    setProfile((prev) => ({
      userId: userId || prev.userId,
      roleId: roleId || prev.roleId,
      userName: userName || prev.userName,
      userEmail: userEmail || prev.userEmail,
    }));
  }, [userId, roleId, userName, userEmail]);

  useEffect(() => {
    if (userId && (roleId || userName || userEmail)) return undefined;
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

  const items = navDestinations({
    userId: profile.userId,
    roleId: profile.roleId,
  });
  const moreItems = moreNavItems({
    userId: profile.userId,
    roleId: profile.roleId,
  });
  const moreActive = moreItems.some((item) => isNavActive(location.pathname, item.to));

  useEffect(() => {
    if (!menuOpen && !moreOpen) return undefined;
    function onPointerDown(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setMenuOpen(false);
        setMoreOpen(false);
      }
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') {
        if (moreOpen) {
          setMoreOpen(false);
          moreButtonRef.current?.focus();
        }
        if (menuOpen) {
          setMenuOpen(false);
          menuButtonRef.current?.focus();
        }
      }
    }
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [menuOpen, moreOpen]);

  useEffect(() => {
    setMenuOpen(false);
    setMoreOpen(false);
  }, [location.pathname, location.hash]);

  const needsTarget = !profile.roleId;

  function navLinkClass(active) {
    return `rounded-[var(--radius-pill)] px-3.5 py-2 text-sm transition-colors ${
      active
        ? 'bg-[var(--color-ink)] font-semibold text-white shadow-sm'
        : 'font-medium text-[var(--color-ink)] hover:bg-white/80'
    }`;
  }

  function renderNavLink(item, onNavigate) {
    const active = isNavActive(location.pathname, item.to);
    const isTargetPrompt = item.to.includes('#target');
    return (
      <Link
        key={`${item.label}:${item.to}`}
        to={item.to}
        data-nav={item.label}
        onClick={onNavigate}
        title={
          isTargetPrompt
            ? 'Choose a company and role on Home first'
            : item.label
        }
        className={navLinkClass(active)}
        aria-current={active ? 'page' : undefined}
      >
        {item.label}
        {isTargetPrompt && needsTarget ? (
          <span className="ml-1 text-[10px] font-normal opacity-70">· set target</span>
        ) : null}
      </Link>
    );
  }

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

        {/* Desktop destinations */}
        <div className="hidden items-center gap-1.5 md:flex" data-testid="app-nav-desktop">
          {DESKTOP_NAV_ITEMS.map((item) => renderNavLink(item))}
          <div className="relative">
            <button
              ref={moreButtonRef}
              type="button"
              onClick={() => setMoreOpen((v) => !v)}
              aria-haspopup="true"
              aria-expanded={moreOpen}
              aria-controls="app-nav-more-panel"
              data-testid="app-nav-more-button"
              className={`inline-flex min-h-10 items-center gap-1.5 rounded-[var(--radius-pill)] px-3.5 py-2 text-sm transition-colors ${
                moreActive && !moreOpen
                  ? 'bg-[var(--color-ink)] font-semibold text-white shadow-sm'
                  : 'font-medium text-[var(--color-ink)] hover:bg-white/80'
              }`}
            >
              More
              <span aria-hidden="true" className={`text-[10px] transition-transform ${moreOpen ? 'rotate-180' : ''}`}>▾</span>
            </button>
            <div
              id="app-nav-more-panel"
              data-testid="app-nav-more-menu"
              hidden={!moreOpen}
              className="absolute right-0 top-full z-50 mt-2 w-56 rounded-[var(--radius-card)] border border-white/40 bg-white/90 p-2 shadow-[0_12px_40px_rgba(15,23,42,0.12)] backdrop-blur-xl supports-[backdrop-filter]:bg-white/85"
            >
              <div className="flex flex-col gap-0.5">
                {moreItems.map((item) => renderNavLink(item, () => setMoreOpen(false)))}
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {trailing}
          <button
            ref={menuButtonRef}
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
            aria-controls="app-nav-slide-panel"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            data-testid="app-nav-menu-button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-card)]/80 backdrop-blur-sm transition hover:border-slate-300 md:hidden"
          >
            <span className="relative block h-3.5 w-4" aria-hidden="true">
              <span
                className={`absolute left-0 top-0 h-0.5 w-4 rounded-full bg-[var(--color-ink)] transition-all duration-300 ease-out ${
                  menuOpen ? 'translate-y-[6px] rotate-45' : ''
                }`}
              />
              <span
                className={`absolute left-0 top-[6px] h-0.5 w-4 rounded-full bg-[var(--color-ink)] transition-all duration-300 ease-out ${
                  menuOpen ? 'scale-x-0 opacity-0' : ''
                }`}
              />
              <span
                className={`absolute left-0 top-[12px] h-0.5 w-4 rounded-full bg-[var(--color-ink)] transition-all duration-300 ease-out ${
                  menuOpen ? 'translate-y-[-6px] -rotate-45' : ''
                }`}
              />
            </span>
          </button>
        </div>
      </div>

      {/* Small-screen menu with every destination */}
      <div
        id="app-nav-slide-panel"
        data-testid="app-nav-menu"
        className={`overflow-hidden transition-[max-height,opacity,transform] duration-300 ease-out md:hidden ${
          menuOpen
            ? 'mt-3 max-h-[28rem] translate-y-0 opacity-100'
            : 'pointer-events-none max-h-0 -translate-y-1 opacity-0'
        }`}
        aria-hidden={!menuOpen}
        hidden={!menuOpen}
      >
        <div className="rounded-[var(--radius-card)] border border-white/40 bg-white/55 px-3 py-3 shadow-[0_12px_40px_rgba(15,23,42,0.08)] backdrop-blur-xl supports-[backdrop-filter]:bg-white/45">
          <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-muted)]">
            Navigate
          </p>
          <div className="flex flex-wrap gap-1.5">
            {items.map((item, index) => {
              const active = isNavActive(location.pathname, item.to);
              const isTargetPrompt = item.to.includes('#target');
              return (
                <Link
                  key={`${item.label}:${item.to}`}
                  to={item.to}
                  data-nav={item.label}
                  onClick={() => setMenuOpen(false)}
                  title={
                    isTargetPrompt
                      ? 'Choose a company and role on Home first'
                      : item.label
                  }
                  style={{
                    transitionDelay: menuOpen ? `${40 + index * 24}ms` : '0ms',
                  }}
                  className={`rounded-[var(--radius-pill)] px-3.5 py-2 text-sm transition-all duration-300 ease-out ${
                    menuOpen ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'
                  } ${
                    active
                      ? 'bg-[var(--color-ink)] font-semibold text-white shadow-sm'
                      : 'bg-white/50 font-medium text-[var(--color-ink)] hover:bg-white/80'
                  }`}
                  aria-current={active ? 'page' : undefined}
                >
                  {item.label}
                  {isTargetPrompt && needsTarget ? (
                    <span className="ml-1 text-[10px] font-normal opacity-70">· set target</span>
                  ) : null}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
