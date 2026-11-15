import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ArrowUpRight, BarChart3, BookOpen, BriefcaseBusiness, CalendarDays,
  Code2, Compass, FileSearch, GraduationCap, Home, Menu, MessageCircle,
  Moon, Search, Sparkles, Sun, Target, UserRound, X,
} from 'lucide-react';
import { contextualNavItems, isNavActive } from '../lib/appNav';
import { fetchMe } from '../lib/api';
import { readTheme, setTheme } from '../lib/theme';
import AccountMenu from './AccountMenu';

const ICONS = {
  Home, Practice: Compass, 'Coding Arena': Code2, 'Learning hub': GraduationCap,
  Resources: BookOpen, Coach: MessageCircle, 'Resume check': FileSearch,
  Jobs: BriefcaseBusiness, 'Gap analysis': Target, 'Study plan': CalendarDays,
  Progress: BarChart3, 'Interview setup': Sparkles, 'Career profile': UserRound,
};

/** The same destinations power the sidebar and keyboard search. */
export function workspaceSections({ userId, roleId } = {}) {
  const [gap, roadmap] = contextualNavItems({ userId, roleId });
  return [
    { title: 'Workspace', items: [
      { label: 'Home', to: '/home', description: 'Your preparation overview' },
      { label: 'Progress', to: '/dashboard', description: 'Your practice history and skills' },
    ] },
    { title: 'Practice', items: [
      { label: 'Practice', to: '/practice', description: 'Choose an interview or assessment' },
      { label: 'Coding Arena', to: '/problems', description: 'Browse coding problems' },
      { label: 'Interview setup', to: '/upload', description: 'Choose a resume and skills' },
    ] },
    { title: 'Improve', items: [
      { label: 'Learning hub', to: '/learn', description: 'Reviews, mistakes and saved questions' },
      { label: 'Resources', to: '/resources', description: 'Guides and courses by skill' },
      { label: 'Coach', to: '/coach', description: 'Get a preparation plan' },
    ] },
    { title: 'Career', items: [
      { label: 'Career profile', to: '/career', description: 'Review your skills and experience' },
      { label: 'Resume check', to: '/ats', description: 'Review your resume against a role' },
      { label: 'Jobs', to: '/jobs', description: 'Explore opportunities' },
      { ...gap, description: 'Compare your skills with a target role' },
      { ...roadmap, label: 'Study plan', description: 'Plan your next steps' },
    ] },
  ];
}

function CommandSearch({ open, onClose, sections }) {
  const dialogRef = useRef(null);
  const inputRef = useRef(null);
  const [query, setQuery] = useState('');
  const items = useMemo(() => {
    const term = query.trim().toLowerCase();
    return sections.flatMap(section => section.items.map(item => ({ ...item, section: section.title })))
      .filter(item => !term || `${item.label} ${item.description} ${item.section}`.toLowerCase().includes(term));
  }, [sections, query]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return undefined;
    if (open && !dialog.open) {
      dialog.showModal();
      inputRef.current?.focus();
    } else if (!open && dialog.open) dialog.close();
    return undefined;
  }, [open]);

  function close() {
    setQuery('');
    onClose();
  }

  return <dialog ref={dialogRef} className="iv-command" aria-labelledby="command-title"
    onClose={close} onCancel={close} onClick={event => { if (event.target === event.currentTarget) close(); }}>
    <div className="iv-command-heading">
      <Search size={19} aria-hidden="true" />
      <label className="sr-only" htmlFor="iv-command-search" id="command-title">Search InterViv pages</label>
      <input id="iv-command-search" ref={inputRef} value={query} onChange={event => setQuery(event.target.value)} placeholder="Where would you like to go?" autoComplete="off" />
      <button type="button" className="iv-icon-button" aria-label="Close search" onClick={close}><X size={18} /></button>
    </div>
    <div className="iv-command-results">
      <p className="iv-nav-label">{query ? 'Search results' : 'Go to'}</p>
      {items.length ? <ul>{items.map(item => {
        const Icon = ICONS[item.label] || ArrowUpRight;
        return <li key={`${item.label}:${item.to}`}><Link to={item.to} onClick={close} className="iv-command-result">
          <span className="iv-command-icon"><Icon size={17} aria-hidden="true" /></span>
          <span><strong>{item.label}</strong><small>{item.description}</small></span>
          <ArrowUpRight size={16} aria-hidden="true" />
        </Link></li>;
      })}</ul> : <p className="iv-command-empty">No pages found. Try “coding”, “resume”, or “resources”.</p>}
    </div>
    <p className="iv-command-hint">Search pages and tools · Press Esc to close</p>
  </dialog>;
}

export default function AppNav({ brandTo = '/home', userId = null, roleId = null, userName = '', userEmail = '', trailing = null }) {
  const location = useLocation();
  const [profile, setProfile] = useState({ userId, roleId, userName, userEmail });
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [theme, updateTheme] = useState(readTheme);
  const menuButtonRef = useRef(null);
  const sidebarRef = useRef(null);

  useEffect(() => {
    setProfile(prev => ({ userId: userId || prev.userId, roleId: roleId || prev.roleId,
      userName: userName || prev.userName, userEmail: userEmail || prev.userEmail }));
  }, [userId, roleId, userName, userEmail]);

  useEffect(() => {
    if (userId && (userName || userEmail)) return undefined;
    let cancelled = false;
    fetchMe().then(me => {
      if (cancelled) return;
      const u = me.user || me;
      setProfile({ userId: u.id || u.user_id || null, roleId: u.target_role_id || null,
        userName: u.name || '', userEmail: u.email || '' });
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [userId, roleId, userName, userEmail]);

  useEffect(() => {
    function onKeyDown(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setSearchOpen(true);
      }
      if (event.key === 'Escape' && menuOpen && !searchOpen) {
        setMenuOpen(false);
        menuButtonRef.current?.focus();
      }
      if (event.key === 'Tab' && menuOpen && !searchOpen && window.matchMedia('(max-width: 850px)').matches) {
        const controls = [...(sidebarRef.current?.querySelectorAll('a[href], button:not([disabled])') || [])]
          .filter(element => element.getClientRects().length);
        if (!controls.length) return;
        const first = controls[0], last = controls[controls.length - 1];
        if (!sidebarRef.current.contains(document.activeElement)) { event.preventDefault(); (event.shiftKey ? last : first).focus(); }
        else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [menuOpen, searchOpen]);

  useEffect(() => { setMenuOpen(false); setSearchOpen(false); }, [location.pathname, location.hash]);

  const sections = useMemo(() => workspaceSections(profile), [profile.userId, profile.roleId]);
  const name = profile.userName || 'Your account';
  const toggleTheme = () => updateTheme(setTheme(theme === 'dark' ? 'light' : 'dark'));

  return <div className="iv-nav-root" data-testid="app-primary-nav">
    <div className="iv-mobile-bar">
      <Link className="iv-brand" to={brandTo}><span className="iv-brand-mark">i</span><span>inter<span>Viv</span></span></Link>
      <div className="iv-mobile-actions">{trailing}
        <button type="button" className="iv-icon-button" onClick={() => setSearchOpen(true)} aria-label="Search pages"><Search size={19} /></button>
        <button ref={menuButtonRef} type="button" className="iv-icon-button" onClick={() => setMenuOpen(value => !value)}
          aria-expanded={menuOpen} aria-controls="iv-sidebar" aria-label={menuOpen ? 'Close menu' : 'Open menu'} data-testid="app-nav-menu-button">
          {menuOpen ? <X size={21} /> : <Menu size={21} />}
        </button>
      </div>
    </div>
    {menuOpen && <button className="iv-nav-backdrop" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
    <aside ref={sidebarRef} id="iv-sidebar" className={`iv-sidebar ${menuOpen ? 'is-open' : ''}`} aria-label="Workspace navigation">
      <div className="iv-sidebar-top">
        <Link className="iv-brand" to={brandTo}><span className="iv-brand-mark">i</span><span>inter<span>Viv</span></span></Link>
        <button type="button" className="iv-sidebar-close iv-icon-button" onClick={() => { setMenuOpen(false); menuButtonRef.current?.focus(); }} aria-label="Close menu"><X size={19} /></button>
      </div>
      <button type="button" className="iv-search-button" onClick={() => setSearchOpen(true)}>
        <Search size={17} aria-hidden="true" /><span>Search anything</span><kbd>⌘ K</kbd>
      </button>
      <nav className="iv-sidebar-scroll" aria-label="Primary">
        {sections.map(section => <div className="iv-nav-section" key={section.title}>
          <p className="iv-nav-label">{section.title}</p>
          {section.items.map(item => {
            const Icon = ICONS[item.label] || ArrowUpRight;
            const active = isNavActive(location.pathname, item.to);
            return <Link key={`${item.label}:${item.to}`} to={item.to} data-nav={item.label}
              onClick={() => setMenuOpen(false)} aria-current={active ? 'page' : undefined}
              title={item.to.includes('#target') ? 'Choose a company and role on Home first' : item.description}
              className={`iv-nav-link ${active ? 'is-active' : ''}`}>
              <Icon size={18} aria-hidden="true" /><span>{item.label}</span>{active && <span className="iv-nav-dot" />}
            </Link>;
          })}
        </div>)}
      </nav>
      <div className="iv-sidebar-footer">
        <button type="button" className="iv-theme-toggle" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}<span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
        </button>
        <div className="iv-account-row">
          <AccountMenu userName={profile.userName} userEmail={profile.userEmail} fetchProfile={false} />
          <span className="iv-account-copy"><strong>{name}</strong><small>{profile.userEmail || 'Your workspace'}</small></span>
        </div>
      </div>
    </aside>
    <CommandSearch open={searchOpen} sections={sections} onClose={() => { setSearchOpen(false); }} />
  </div>;
}
