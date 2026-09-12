import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, BookOpen, Code2, FileText, ListChecks } from 'lucide-react';
import AccountPage, { useAccountOverview } from '../components/AccountPage';
import CompanySelector from '../components/CompanySelector';

function FeatureLink({ to, title, children, icon }) {
  return <Link className="hub-feature" to={to}>
    <div className="hub-feature-title">{icon}<h3>{title}</h3><ArrowUpRight aria-hidden="true" size={18} /></div>
    <p>{children}</p>
  </Link>;
}

export function HomeContent({ data, reload }) {
  const user = data.user;
  const target = data.target;
  const resume = data.resumable_session;
  const firstName = user.name?.trim().split(/\s+/)[0] || 'there';
  const targetPath = target ? `/gap-analysis/${encodeURIComponent(user.id)}/${encodeURIComponent(target.role_id)}` : null;
  return <>
    <section className="hub-greeting">
      <p className="hub-eyebrow">{new Date().toLocaleDateString('en', { weekday: 'long', day: 'numeric', month: 'long' })}</p>
      <h1>Hello, <em>{firstName}.</em></h1>
      <p className="hub-intro">One focused session. A clearer next step.</p>
      <div className="hub-actions">
        <Link className="hub-button hub-button-primary" to={resume ? `/interview/${encodeURIComponent(resume.session_id)}` : '/practice'}>{resume ? 'Continue practice' : 'Start practicing'}<ArrowUpRight size={18} aria-hidden="true" /></Link>
        <Link className="hub-button" to="/coach">Help me choose a path</Link>
      </div>
      <p className="hub-caption">Practice with or without a resume or a target company.</p>
      {resume && <p className="hub-caption">Your active session is ready. Timed assessments keep their original deadline.</p>}
    </section>

    <div className="hub-target-strip">
      <div><span className="hub-eyebrow">Your target</span><strong>{target ? `${target.company_name} · ${target.role_title}` : 'Not set yet'}</strong></div>
      <a className="hub-button" href="#target">{target ? 'Change company & role' : 'Choose company & role'}</a>
    </div>

    <section className="hub-section" aria-labelledby="prepare-heading">
      <div className="hub-section-heading"><span>01</span><h2 id="prepare-heading">Prepare</h2><p>Choose a focused practice session or configure your own.</p></div>
      <div className="hub-prepare-grid">
        <div className="hub-featured">
          <BookOpen size={26} aria-hidden="true" /><h3>Interview practice</h3>
          <p>Choose your skills and answer technical or HR interview questions. Review your scores and feedback after each round.</p>
          <Link className="hub-button hub-button-primary" to="/practice?mode=full">Choose interview skills<ArrowUpRight size={17} aria-hidden="true" /></Link>
        </div>
        <div>
          <FeatureLink to="/practice?mode=oa" title="OA practice" icon={<ListChecks size={20} aria-hidden="true" />}>Timed technical MCQs only — separate from SQL and coding.</FeatureLink>
          <FeatureLink to="/problems" title="Coding platform" icon={<Code2 size={20} aria-hidden="true" />}>Python problems with the local runner, examples, and coach hints.</FeatureLink>
          <FeatureLink to="/practice?mode=sql" title="SQL practice" icon={<FileText size={20} aria-hidden="true" />}>SQL problems with schemas and execution-based evaluation.</FeatureLink>
          <FeatureLink to="/practice?mode=custom" title="Custom interview" icon={<FileText size={20} aria-hidden="true" />}>Configure interview, OA, SQL, coding and more in the block builder.</FeatureLink>
          <FeatureLink to="/resources" title="Resources" icon={<BookOpen size={20} aria-hidden="true" />}>Curated study links by category — DSA, system design, behavioral, and more.</FeatureLink>
        </div>
      </div>
    </section>

    <section className="hub-section" aria-labelledby="target-heading">
      <div className="hub-section-heading"><span>02</span><h2 id="target-heading">Target</h2><p>Focus your preparation around a company and role.</p></div>
      <div className="hub-columns hub-columns-three">
        <div className="hub-detail"><h3>Company & role</h3><p>Explore curated hiring profiles and save a target for your preparation.</p><a className="hub-text-link" href="#target">{target ? 'Review your target' : 'Select a target'} →</a></div>
        <div className="hub-detail"><h3>Gap analysis</h3><p>Compare role requirements with skills you have actually practiced.</p>{targetPath ? <Link className="hub-text-link" to={targetPath}>See your gaps →</Link> : <p className="hub-caption">Choose a target role to begin.</p>}</div>
        <div className="hub-detail"><h3>Roadmap</h3><p>Build a 7, 14 or 30 day preparation plan from your skill gaps.</p>{target ? <Link className="hub-text-link" to={`/roadmap/${encodeURIComponent(user.id)}/${encodeURIComponent(target.role_id)}?days=30`}>Open your roadmap →</Link> : <p className="hub-caption">Choose a target role to begin.</p>}</div>
      </div>
      <details className="hub-target-picker" id="target"><summary>Choose company & role</summary><CompanySelector key={`${user.target_company_id}-${user.target_role_id}`} isAuthenticated initialCompanyId={user.target_company_id} initialRoleId={user.target_role_id} onSaved={reload} /></details>
    </section>

    <section className="hub-section" aria-labelledby="apply-heading">
      <div className="hub-section-heading"><span>03</span><h2 id="apply-heading">Apply</h2><p>Connect preparation with your next opportunity.</p></div>
      <div className="hub-columns">
        <FeatureLink to="/ats" title="Resume check" icon={<FileText size={20} aria-hidden="true" />}>Check parsing, resume structure and skill coverage against a role or job description. This is not an employer ATS score or hiring probability.</FeatureLink>
        <FeatureLink to="/jobs" title="Jobs" icon={<ArrowUpRight size={20} aria-hidden="true" />}>Explore listings and practice relevant skills. The Jobs page identifies sample listings and the source of available results.</FeatureLink>
      </div>
    </section>

    <section className="hub-guide" aria-labelledby="guide-heading">
      <div><p className="hub-eyebrow">04 · Guide</p><h2 id="guide-heading">Find your next step.<br /><em>Start with the goal.</em></h2><p>Describe what you want to work toward. The coach maps your goal to supported skills and useful practice.</p></div>
      <div className="hub-guide-actions"><Link className="hub-button" to="/coach">Ask the coach<ArrowUpRight size={17} aria-hidden="true" /></Link><Link className="hub-button" to="/learn">Mistakes and retry sets</Link><Link className="hub-button" to="/resources">Resources by skill</Link></div>
    </section>
    <footer className="hub-footer"><p>Your measured readiness, skill mastery and practice history live in Progress.</p><Link className="hub-button" to="/dashboard">Open Progress →</Link></footer>
  </>;
}

export default function Home() {
  const overview = useAccountOverview();
  return <AccountPage {...overview}>{overview.data && <HomeContent data={overview.data} reload={overview.reload} />}</AccountPage>;
}
