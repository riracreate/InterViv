import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, BriefcaseBusiness, Download, FileUp, Plus, Trash2, UserRound } from 'lucide-react';
import AppNav from '../components/AppNav';
import AccountGate from '../components/AccountGate';
import { fetchMe } from '../lib/api';
import { readScoped, writeScoped } from '../lib/accountStorage';
import { addSkills, removeSkill } from '../lib/skillChips';
import { emptyCareerProfile, mergeCareerProfile, parseCareerImport } from '../lib/careerProfile';
import { useAccountRetry } from '../lib/useAccountRetry';

const STORAGE_KEY = 'career-profile';
const MAX_IMPORT_BYTES = 2 * 1024 * 1024;

export default function CareerProfile() {
  const navigate = useNavigate();
  const { accountError, accountAttempt, retryAccount, onAccountError } = useAccountRetry();
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(emptyCareerProfile());
  const [pending, setPending] = useState(null);
  const [skillInput, setSkillInput] = useState('');
  const [paste, setPaste] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchMe().then(me => {
      if (cancelled) return;
      const account = me.user || me;
      const id = account.id || account.user_id;
      const saved = readScoped('local', id, STORAGE_KEY);
      setUser({ ...account, id });
      setProfile(saved && typeof saved === 'object' ? {
        name: typeof saved.name === 'string' ? saved.name : '', headline: typeof saved.headline === 'string' ? saved.headline : '',
        skills: Array.isArray(saved.skills) ? saved.skills.filter(item => typeof item === 'string') : [],
        roles: Array.isArray(saved.roles) ? saved.roles.filter(item => item && typeof item === 'object') : [],
      } : emptyCareerProfile(account.name));
    }).catch(err => { if (!cancelled) onAccountError(err); });
    return () => { cancelled = true; };
  }, [accountAttempt]);

  function save(next = profile) {
    if (!writeScoped('local', user?.id, STORAGE_KEY, next)) {
      setError('Could not save on this device. Your edits are still visible until you leave this page.');
      return false;
    }
    setError('');
    setNotice('Profile saved on this device.');
    return true;
  }
  function update(field, value) { setProfile(current => ({ ...current, [field]: value })); setNotice(''); }
  function updateRole(index, field, value) {
    setProfile(current => ({ ...current, roles: current.roles.map((role, i) => i === index ? { ...role, [field]: value } : role) }));
    setNotice('');
  }
  async function importFile(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setPending(null);
    if (!/\.(txt|json|csv)$/i.test(file.name)) { setError('Choose a TXT, JSON, or CSV file.'); return; }
    if (file.size > MAX_IMPORT_BYTES) { setError('This file is too large. Choose one under 2 MB.'); return; }
    try { setPending(parseCareerImport(await file.text(), file.name)); setError(''); setNotice(''); }
    catch (err) { setError(err.message || 'This file could not be read.'); }
  }
  function importPastedText() {
    setPending(null);
    try { setPending(parseCareerImport(paste, 'pasted.txt')); setError(''); setNotice(''); }
    catch (err) { setError(err.message || 'This text could not be read.'); }
  }
  function exportProfile() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(profile, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'interviv-career-profile.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  if (!user) return <main className="min-h-screen bg-[var(--color-surface)] grid place-items-center"><AccountGate error={accountError} onRetry={retryAccount} /></main>;

  return <main className="min-h-screen bg-[var(--color-surface)] text-[var(--color-ink)]"><div className="app-container">
    <AppNav userId={user.id} roleId={user.target_role_id} userName={user.name || ''} userEmail={user.email || ''} />
    <header className="app-page-hero"><p className="iv-page-kicker">Career / Your profile</p><h1>Your experience, in one place.</h1>
      <p className="mt-3 text-sm leading-6 text-[var(--color-ink-muted)]">Bring together your skills and experience, then use them to start focused practice.</p></header>
    <div className="iv-career-notice">This profile is saved only on this device for your account. It does not update your account, resume check, or measured skills.</div>
    {error && <p role="alert" className="iv-career-error">{error}</p>}{notice && <p role="status" className="iv-career-notice">{notice}</p>}
    <div className="iv-profile-grid">
      <div className="iv-profile-main">
        <section className="iv-profile-card"><div className="iv-profile-heading"><span className="iv-quick-icon"><UserRound size={20} /></span><div><h2>About you</h2><p>Details you can review and edit.</p></div></div>
          <div className="iv-profile-fields"><label>Name<input value={profile.name} onChange={event => update('name', event.target.value)} maxLength={200} /></label>
          <label>Headline<input value={profile.headline} onChange={event => update('headline', event.target.value)} placeholder="For example, aspiring backend engineer" maxLength={200} /></label></div>
        </section>
        <section className="iv-profile-card"><div className="iv-profile-heading"><span className="iv-quick-icon"><Plus size={20} /></span><div><h2>Skills</h2><p>These are self-reported, not measured scores.</p></div></div>
          <div className="iv-profile-skills">{profile.skills.length ? profile.skills.map(skill => <span key={skill}>{skill}<button type="button" aria-label={`Remove ${skill}`} onClick={() => update('skills', removeSkill(profile.skills, skill))}>×</button></span>) : <p>No skills added yet.</p>}</div>
          <form className="iv-profile-add" onSubmit={event => { event.preventDefault(); update('skills', addSkills(profile.skills, skillInput, [], 100)); setSkillInput(''); }}>
            <label className="sr-only" htmlFor="career-skill">Add skills</label><input id="career-skill" value={skillInput} onChange={event => setSkillInput(event.target.value)} placeholder="Add a skill, or paste a comma-separated list" />
            <button className="app-button" type="submit" disabled={!skillInput.trim()}>Add</button>
          </form>
        </section>
        <section className="iv-profile-card"><div className="iv-profile-heading"><span className="iv-quick-icon"><BriefcaseBusiness size={20} /></span><div><h2>Experience</h2><p>Add roles, internships, or projects you want to remember.</p></div></div>
          {profile.roles.map((role, index) => <div className="iv-role-editor" key={index}>
            <div className="iv-role-title"><strong>Experience {index + 1}</strong><button type="button" aria-label={`Remove experience ${index + 1}`} onClick={() => update('roles', profile.roles.filter((_, i) => i !== index))}><Trash2 size={16} /></button></div>
            <div className="iv-profile-fields"><label>Role<input value={role.title || ''} onChange={event => updateRole(index, 'title', event.target.value)} maxLength={200} /></label>
              <label>Company or project<input value={role.company || ''} onChange={event => updateRole(index, 'company', event.target.value)} maxLength={200} /></label>
              <label>From<input value={role.start || ''} onChange={event => updateRole(index, 'start', event.target.value)} placeholder="Month / year" maxLength={50} /></label>
              <label>To<input value={role.end || ''} onChange={event => updateRole(index, 'end', event.target.value)} placeholder="Present" maxLength={50} /></label></div>
          </div>)}
          <button type="button" className="app-button" onClick={() => update('roles', [...profile.roles, { title: '', company: '', start: '', end: '' }])}><Plus size={15} /> Add experience</button>
        </section>
        <div className="iv-profile-actions"><button type="button" className="hub-button hub-button-primary iv-profile-save" onClick={() => save()}>Save profile</button>
          <button type="button" className="app-button" onClick={() => { if (save()) navigate('/practice?mode=full', { state: { prefilledSkills: profile.skills, prefillSource: 'career profile' } }); }} disabled={!profile.skills.length}>Practice these skills <ArrowRight size={16} /></button>
          <button type="button" className="app-button" onClick={exportProfile}><Download size={15} /> Export JSON</button>
        </div>
        <p className="iv-insight-note">Practicing saves this profile on your device and starts with up to the first five skills; you can edit them before starting.</p>
        <div className="iv-profile-clear">{confirmClear ? <><span>Clear your saved profile on this device?</span><button type="button" onClick={() => { const blank = emptyCareerProfile(); if (save(blank)) { setProfile(blank); setConfirmClear(false); setNotice('Profile cleared on this device.'); } }}>Yes, clear it</button><button type="button" onClick={() => setConfirmClear(false)}>Cancel</button></> : <button type="button" onClick={() => setConfirmClear(true)}>Clear profile on this device</button>}</div>
      </div>
      <aside className="iv-profile-card iv-profile-import"><span className="iv-quick-icon"><FileUp size={20} /></span><h2>Bring in your details</h2>
        <p>Import a profile JSON or a LinkedIn profile, positions, or skills CSV. TXT and pasted text can suggest common skills. Review everything before adding it.</p>
        <label className="iv-file-upload"><input type="file" accept=".txt,.json,.csv,text/plain,text/csv,application/json" className="sr-only" onChange={importFile} /><strong>Choose a file</strong><span>TXT, JSON, or CSV · up to 2 MB</span></label>
        <label className="iv-paste-label">Or paste text<textarea value={paste} onChange={event => setPaste(event.target.value)} placeholder="Paste a summary of your experience…" rows={4} /></label>
        <button type="button" className="app-button" disabled={!paste.trim()} onClick={importPastedText}>Find skills in text</button>
        <p className="iv-insight-note">For a PDF, use <Link to="/ats">Resume check</Link> or <Link to="/upload">Interview setup</Link>.</p>
        {pending && <div className="iv-import-review" role="region" aria-label="Review imported details"><h3>Review import</h3>
          {pending.name && <p><strong>Name:</strong> {pending.name}</p>}{pending.headline && <p><strong>Headline:</strong> {pending.headline}</p>}
          {pending.skills.length > 0 && <p><strong>Skills:</strong> {pending.skills.join(', ')}</p>}
          {pending.roles.map((role, index) => <p key={index}><strong>Experience:</strong> {[role.title, role.company, role.start, role.end].filter(Boolean).join(' · ')}</p>)}
          <p>Adding an import updates the form. Save the profile to keep it on this device.</p>
          <div><button type="button" className="app-button" onClick={() => { setProfile(current => mergeCareerProfile(current, pending)); setPending(null); setNotice('Import added. Review and save your profile.'); }}>Add to profile</button>
          <button type="button" className="app-button" onClick={() => setPending(null)}>Discard</button></div>
        </div>}
      </aside>
    </div>
  </div></main>;
}
