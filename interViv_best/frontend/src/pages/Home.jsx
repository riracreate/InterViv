import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, BookOpen, BriefcaseBusiness, Code2, FileSearch, Layers3, MessageCircle, Sparkles, Target, UserRound } from 'lucide-react';
import AccountPage, { useAccountOverview } from '../components/AccountPage';
import CompanySelector from '../components/CompanySelector';
import RoleSelector from '../components/RoleSelector';
import { fetchTargetContext } from '../lib/api';
import { ROLE_ONLY_TARGETS, roleTargetFromContext, roleTargetLabel } from '../lib/roleTargets';

const QUICK_LINKS = [
  { to: '/practice?mode=full', title: 'Interview practice', text: 'Build confidence one answer at a time.', icon: MessageCircle, label: 'Text & voice' },
  { to: '/problems', title: 'Coding Arena', text: 'Work through problems with real feedback.', icon: Code2, label: 'Coding' },
  { to: '/practice?mode=sql', title: 'SQL practice', text: 'Turn queries into practical experience.', icon: Layers3, label: 'SQL' },
  { to: '/practice?mode=custom', title: 'Custom interview', text: 'Build a session around your goals.', icon: Sparkles, label: 'Your mix' },
];

function QuickLink({ to, title, text, icon: Icon, label }) {
  return <Link className="iv-quick-card" to={to}>
    <span className="iv-quick-icon"><Icon size={20} aria-hidden="true" /></span><span className="iv-quick-label">{label}</span>
    <h3>{title}</h3><p>{text}</p><span className="iv-quick-action">Get started <ArrowUpRight size={16} aria-hidden="true" /></span>
  </Link>;
}

/** Role-only Home target (ROLE_ONLY_TARGETS): one role and a level, no company. */
function RoleTargetPanel({ roleTarget, onSaved }) {
  const navigate = useNavigate();
  return <section className="iv-target-panel" id="target" aria-labelledby="target-picker-heading">
    <div><p className="iv-kicker">Your direction</p><h2 id="target-picker-heading">Choose your role</h2><p>Save a role and level to plan role interviews. You can practice without one.</p>
      {roleTarget && <p className="iv-home-note">Current target: {roleTargetLabel(roleTarget)}</p>}
    </div>
    <RoleSelector isAuthenticated onSaved={onSaved}
      onStarted={started => navigate(`/interview/${encodeURIComponent(started.session_id)}`)} />
  </section>;
}

function useRoleTarget(enabled) {
  const [roleTarget, setRoleTarget] = useState(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    fetchTargetContext().then(data => { if (!cancelled) setRoleTarget(roleTargetFromContext(data)); }).catch(() => {});
    return () => { cancelled = true; };
  }, [enabled, version]);
  return [roleTarget, () => setVersion(v => v + 1)];
}

export function HomeContent({ data, reload }) {
  const user = data.user;
  const [roleTarget, refreshRoleTarget] = useRoleTarget(ROLE_ONLY_TARGETS);
  const target = ROLE_ONLY_TARGETS ? null : data.target;
  const resume = data.resumable_session;
  const firstName = user.name?.trim().split(/\s+/)[0] || 'there';
  const targetPath = target ? `/gap-analysis/${encodeURIComponent(user.id)}/${encodeURIComponent(target.role_id)}` : null;
  return <div className="iv-home">
    <section className="iv-home-hero" aria-labelledby="welcome-heading">
      <div className="iv-welcome">
        <p className="iv-kicker"><span /> Your preparation space</p>
        <h1 id="welcome-heading">Hello, <em>{firstName}.</em><br />Let's make progress.</h1>
        <p>A little preparation goes a long way. Pick up where you left off, or find something new to practice.</p>
        <div className="iv-home-actions">
          <Link className="hub-button hub-button-primary" to={resume ? `/interview/${encodeURIComponent(resume.session_id)}` : '/practice'}>{resume ? 'Continue practice' : 'Start practicing'} <ArrowUpRight size={17} aria-hidden="true" /></Link>
          <Link className="hub-button" to="/coach">Help me choose a path</Link>
        </div>
        {resume && <p className="iv-home-note">Timed assessments keep their original deadline.</p>}
      </div>
      <div className="iv-next-card">
        <div className="iv-card-top"><span className="iv-kicker">Your next step</span><span className="iv-next-icon"><Sparkles size={18} aria-hidden="true" /></span></div>
        {ROLE_ONLY_TARGETS ? <>
          <h2>{resume ? 'Ready when you are.' : roleTarget ? 'Practice with purpose.' : 'Make a plan that fits.'}</h2>
          <p>{resume ? 'Your active session is ready to continue.' : roleTarget ? `Prepare for the ${roleTargetLabel(roleTarget)} role, one interview at a time.` : 'Choose a target role, or jump straight into practice. Both are a great place to start.'}</p>
          <div className="iv-next-meta"><Target size={17} aria-hidden="true" /><span><small>YOUR TARGET</small><strong>{roleTarget ? roleTargetLabel(roleTarget) : 'Choose a role & level'}</strong></span></div>
          <a href="#target" className="iv-inline-link">{roleTarget ? 'View or change target' : 'Set your target'} <ArrowRight size={16} aria-hidden="true" /></a>
        </> : <>
        <h2>{resume ? 'Ready when you are.' : target ? 'Practice with purpose.' : 'Make a plan that fits.'}</h2>
        <p>{resume ? 'Your active session is ready to continue.' : target ? `Prepare for ${target.role_title} at ${target.company_name}, one skill at a time.` : 'Choose a target role, or jump straight into practice. Both are a great place to start.'}</p>
        <div className="iv-next-meta"><Target size={17} aria-hidden="true" /><span><small>YOUR TARGET</small><strong>{target ? `${target.company_name} · ${target.role_title}` : 'Choose a company & role'}</strong></span></div>
        <a href="#target" className="iv-inline-link">{target ? 'View or change target' : 'Set your target'} <ArrowRight size={16} aria-hidden="true" /></a>
        </>}
      </div>
    </section>

    <div className="iv-journey" aria-label="Your preparation journey"><span><b>01</b> Choose a goal</span><ArrowRight aria-hidden="true" /><span><b>02</b> Practice</span><ArrowRight aria-hidden="true" /><span><b>03</b> Get feedback</span><ArrowRight aria-hidden="true" /><span><b>04</b> Keep improving</span></div>

    <section className="iv-home-section" aria-labelledby="practice-heading">
      <div className="iv-section-head"><div><p className="iv-kicker">Make it a habit</p><h2 id="practice-heading">Practice your way</h2><p>Choose a focused session or put together your own.</p></div><Link to="/practice" className="iv-inline-link">Explore all practice <ArrowRight size={16} aria-hidden="true" /></Link></div>
      <div className="iv-quick-grid">{QUICK_LINKS.map(item => <QuickLink key={item.title} {...item} />)}</div>
      <div className="iv-more-practice">More ways to practice <span>•</span> <Link to="/practice?mode=oa">Technical MCQs</Link><Link to="/practice?mode=verbal">Verbal ability</Link><Link to="/practice?mode=system_design">System design</Link><Link to="/practice?mode=ml_primitives">ML primitives</Link></div>
    </section>

    <section className="iv-home-section" aria-labelledby="apply-heading">
      <div className="iv-section-head"><div><p className="iv-kicker">Prepare for what's next</p><h2 id="apply-heading">Apply with clarity</h2><p>Your preparation and career tools, together.</p></div></div>
      <div className="iv-career-grid">
        <Link className="iv-career-card" to="/career"><span className="iv-quick-icon"><UserRound size={20} /></span><div><h3>Career profile</h3><p>Bring your skills and experience together.</p></div><ArrowUpRight size={18} /></Link>
        <Link className="iv-career-card" to="/ats"><span className="iv-quick-icon"><FileSearch size={20} /></span><div><h3>Resume check</h3><p>See how your resume aligns with a role or job description.</p></div><ArrowUpRight size={18} /></Link>
        <Link className="iv-career-card" to="/jobs"><span className="iv-quick-icon"><BriefcaseBusiness size={20} /></span><div><h3>Explore jobs</h3><p>Find opportunities and prepare for the skills they need.</p></div><ArrowUpRight size={18} /></Link>
        <Link className="iv-career-card" to="/resources"><span className="iv-quick-icon"><BookOpen size={20} /></span><div><h3>Learning resources</h3><p>Find useful guides and courses for your next step.</p></div><ArrowUpRight size={18} /></Link>
      </div>
    </section>

    {ROLE_ONLY_TARGETS ? <RoleTargetPanel roleTarget={roleTarget} onSaved={() => { refreshRoleTarget(); reload?.(); }} /> : <section className="iv-target-panel" id="target" aria-labelledby="target-picker-heading">
      <div><p className="iv-kicker">Your direction</p><h2 id="target-picker-heading">Choose company &amp; role</h2><p>Save a target to unlock gap analysis and a study plan. You can practice without one.</p>
        {target && <div className="hub-target-links">{targetPath && <Link className="iv-inline-link" to={targetPath}>See your gaps →</Link>}<Link className="iv-inline-link" to={`/roadmap/${encodeURIComponent(user.id)}/${encodeURIComponent(target.role_id)}?days=30`}>Open your study plan →</Link></div>}
      </div>
      <CompanySelector key={`${user.target_company_id}-${user.target_role_id}`} isAuthenticated initialCompanyId={user.target_company_id} initialRoleId={user.target_role_id} onSaved={reload} />
    </section>}

    <section className="iv-coach-banner" aria-labelledby="guide-heading"><div><p className="iv-kicker">Your Guide</p><h2 id="guide-heading">Not sure where to start?</h2><p>Tell your coach what you're working toward and get a practical next step.</p></div><Link className="hub-button" to="/coach">Talk to your coach <ArrowRight size={16} /></Link></section>
    <footer className="iv-home-footer"><span>Made for the next step in your journey.</span><Link to="/dashboard">View your progress →</Link></footer>
  </div>;
}

export default function Home() {
  const overview = useAccountOverview();
  return <AccountPage {...overview}>{overview.data && <HomeContent data={overview.data} reload={overview.reload} />}</AccountPage>;
}
