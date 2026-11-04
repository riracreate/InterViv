import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { fetchMe, signOut } from '../lib/api';

/**
 * Avatar button with the account menu (name, Progress, Sign out). Used by
 * AppNav and by pages with their own header (Upload, session report), so
 * sign out is reachable from every signed-in page.
 */
export default function AccountMenu({ userName = '', userEmail = '', fetchProfile = true }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState({ userName, userEmail });
  const rootRef = useRef(null);
  const buttonRef = useRef(null);

  useEffect(() => {
    setProfile((prev) => ({
      userName: userName || prev.userName,
      userEmail: userEmail || prev.userEmail,
    }));
  }, [userName, userEmail]);

  useEffect(() => {
    if (!fetchProfile || userName || userEmail) return undefined;
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        const u = me.user || me;
        setProfile({ userName: u.name || '', userEmail: u.email || '' });
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [fetchProfile, userName, userEmail]);

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

  function handleSignOut() {
    setOpen(false);
    signOut();
    navigate('/login', { replace: true });
  }

  const initial = (profile.userName || profile.userEmail || 'I').trim().charAt(0).toUpperCase() || 'I';

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls="app-account-menu"
        aria-label="Account menu"
        data-testid="app-nav-account-button"
        className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-card)] text-sm font-semibold text-[var(--color-ink)] transition hover:border-slate-300"
      >
        <span aria-hidden="true">{initial}</span>
      </button>
      <div
        id="app-account-menu"
        data-testid="app-nav-account-menu"
        hidden={!open}
        className="absolute right-0 top-full z-50 mt-2 w-60 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-white p-2 text-left shadow-[0_12px_40px_rgba(15,23,42,0.12)]"
      >
        {(profile.userName || profile.userEmail) && (
          <div className="px-3 py-2 text-sm">
            {profile.userName && <p className="font-semibold text-[var(--color-ink)]">{profile.userName}</p>}
            {profile.userEmail && <p className="truncate text-[var(--color-ink-muted)]">{profile.userEmail}</p>}
          </div>
        )}
        <Link to="/dashboard" className="block rounded-[var(--radius-pill)] px-3 py-2 text-sm text-[var(--color-ink)] hover:bg-[var(--color-surface)]">
          Progress
        </Link>
        <button
          type="button"
          onClick={handleSignOut}
          data-testid="app-nav-sign-out"
          className="block w-full rounded-[var(--radius-pill)] px-3 py-2 text-left text-sm text-[var(--color-ink)] hover:bg-[var(--color-surface)]"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}
