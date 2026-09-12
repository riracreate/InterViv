import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { LogOut, User } from 'lucide-react';
import { isNavActive, navDestinations } from '../lib/appNav';
import { clearAuthToken, clearInterviewState, fetchMe } from '../lib/api';

/**
 * Brand + animated hamburger (translucent destinations bar) + profile.
 * Profile is not inside the sliding bar.
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
  const navigate = useNavigate();
  const [profile, setProfile] = useState({
    userId,
    roleId,
    userName,
    userEmail,
  });
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const rootRef = useRef(null);

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

  useEffect(() => {
    if (!menuOpen && !profileOpen) return undefined;
    function onPointerDown(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setMenuOpen(false);
        setProfileOpen(false);
      }
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        setProfileOpen(false);
      }
    }
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [menuOpen, profileOpen]);

  useEffect(() => {
    setMenuOpen(false);
    setProfileOpen(false);
  }, [location.pathname, location.hash]);

  function handleSignOut() {
    setProfileOpen(false);
    setMenuOpen(false);
    clearAuthToken();
    clearInterviewState();
    navigate('/login', { replace: true });
  }

  const initial = (profile.userName || '').trim().charAt(0).toUpperCase();
  const needsTarget = !profile.roleId;

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

        <div className="flex items-center gap-2">
          {trailing}
          <button
            type="button"
            onClick={() => {
              setMenuOpen((v) => !v);
              setProfileOpen(false);
            }}
            aria-haspopup="true"
            aria-expanded={menuOpen}
            aria-controls="app-nav-slide-panel"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            data-testid="app-nav-menu-button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-card)]/80 backdrop-blur-sm transition hover:border-slate-300"
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

          <div className="relative">
            <button
              type="button"
              onClick={() => {
                setProfileOpen((v) => !v);
                setMenuOpen(false);
              }}
              aria-haspopup="menu"
              aria-expanded={profileOpen}
              aria-label="Profile menu"
              data-testid="app-nav-profile-button"
              title={profile.userName || profile.userEmail || 'Profile'}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--color-ink)] text-sm font-semibold text-white transition hover:opacity-90"
            >
              {initial ? initial : <User size={18} aria-hidden="true" />}
            </button>
            {profileOpen && (
              <div
                role="menu"
                aria-label="Profile"
                data-testid="app-nav-profile-menu"
                className="absolute right-0 z-50 mt-2 w-60 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)]/95 p-1.5 shadow-lg backdrop-blur-md"
              >
                {(profile.userName || profile.userEmail) && (
                  <div className="border-b border-[var(--color-border)] px-3 py-2.5">
                    {profile.userName && (
                      <p className="truncate text-sm font-semibold text-[var(--color-ink)]">
                        {profile.userName}
                      </p>
                    )}
                    {profile.userEmail && (
                      <p className="truncate text-xs text-[var(--color-ink-muted)]">
                        {profile.userEmail}
                      </p>
                    )}
                  </div>
                )}
                <button
                  type="button"
                  role="menuitem"
                  onClick={handleSignOut}
                  className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-[var(--color-ink-muted)] hover:bg-[var(--color-surface)] hover:text-[var(--color-ink)]"
                >
                  <LogOut size={15} aria-hidden="true" />
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <div
        id="app-nav-slide-panel"
        data-testid="app-nav-menu"
        className={`overflow-hidden transition-[max-height,opacity,transform] duration-300 ease-out ${
          menuOpen
            ? 'mt-3 max-h-[28rem] translate-y-0 opacity-100'
            : 'pointer-events-none max-h-0 -translate-y-1 opacity-0'
        }`}
        aria-hidden={!menuOpen}
      >
        <div className="rounded-[var(--radius-card)] border border-white/40 bg-white/55 px-3 py-3 shadow-[0_12px_40px_rgba(15,23,42,0.08)] backdrop-blur-xl supports-[backdrop-filter]:bg-white/45">
          <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-muted)]">
            Navigate
          </p>
          <div className="flex flex-wrap gap-1.5" role="menu" aria-label="Site sections">
            {items.map((item, index) => {
              const active = isNavActive(location.pathname, item.to);
              const isTargetPrompt = item.to.includes('#target');
              return (
                <Link
                  key={`${item.label}:${item.to}`}
                  to={item.to}
                  role="menuitem"
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
