import React from 'react';
import { Link } from 'react-router-dom';
import AccountPage, { useAccountOverview } from '../components/AccountPage';
import { displayScore, sessionLabel } from '../lib/accountOverview';

function fraction(value) {
  return typeof value === 'number' && Number.isFinite(value) ? `${Math.round(value * 100)}%` : 'Not available';
}

export function ProgressContent({ data }) {
  const measured = data.skills.filter(skill => skill.attempts > 0);
  const skills = [...data.skills];
  for (const requirement of data.target?.per_skill_gap || []) {
    if (!skills.some(skill => skill.name === requirement.skill)) skills.push({ name: requirement.skill, attempts: 0 });
  }
  const signals = data.learning_signals;
  return <>
    <header className="hub-progress-hero">
      <div><p className="hub-eyebrow">Progress{data.target ? ` · ${data.target.company_name} · ${data.target.role_title}` : ''}</p><h1>Readiness<br /><em>{displayScore(data.readiness)}</em></h1>
        <p>{data.readiness == null ? 'Readiness is measured against a target role after you practice its required skills.' : `Based on ${data.target.tested_skill_count} of ${data.target.required_skill_count} required skills. Untested skills are excluded from this score.`}</p>
      </div>
      <dl className="hub-stats"><div><dt>Scored sessions</dt><dd>{data.scored_session_count}</dd></div><div><dt>Skills measured</dt><dd>{measured.length}</dd></div></dl>
    </header>

    <section className="hub-section" aria-labelledby="mastery-heading">
      <div className="hub-section-heading"><span>01</span><h2 id="mastery-heading">Skill mastery</h2><p>Recent scored rounds, by skill.</p></div>
      {skills.length === 0 ? <p className="hub-empty">Not measured. Your skills will appear after practice or when you select a target.</p> : <ul className="hub-skill-list">{skills.map(skill => <li key={skill.name}>
        <strong>{skill.name}</strong><div>{skill.attempts > 0 ? <meter min="0" max="100" value={skill.current_score} aria-label={`${skill.name} score`} /> : <span className="hub-unmeasured-track" />}</div>
        <span>{skill.attempts > 0 ? displayScore(skill.current_score) : 'Not measured'}</span><span className="hub-caption">{skill.attempts > 0 ? `${skill.attempts} rounds · ${Math.round(skill.current_elo)} Elo` : 'No scored rounds'}</span>
      </li>)}</ul>}
    </section>

    <section className="hub-section" aria-labelledby="history-heading">
      <div className="hub-section-heading"><span>02</span><h2 id="history-heading">Session history</h2><p>Open a report to review your answers and feedback.</p></div>
      {data.history.length === 0 ? <div className="hub-empty"><h3>No scored sessions yet.</h3><p>Once a round is scored, its session report will appear here.</p></div> : <div className="hub-table-scroll"><table className="hub-history"><caption className="sr-only">Most recent scored practice sessions</caption><thead><tr><th>Date</th><th>Session</th><th>Skill focus</th><th>Score</th><th><span className="sr-only">Report</span></th></tr></thead><tbody>{data.history.map(session => <tr key={session.session_id}>
        <td>{session.created_at ? new Date(session.created_at).toLocaleDateString('en', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Not available'}</td>
        <td><strong>{sessionLabel(session.round_types)}</strong><small>{session.completed_rounds}/{session.total_rounds} rounds scored{session.status === 'completed' ? ' · Complete' : ' · In progress'}{(session.unscored_rounds || []).length > 0 ? ` · ${session.unscored_rounds.length} unscored (${[...new Set(session.unscored_rounds.map((u) => u.reason === 'execution_unavailable' ? 'coding unavailable' : u.reason))].join(', ')})` : ''}</small></td>
        <td>{session.skills.join(', ')}</td><td className="hub-history-score">{displayScore(session.average_score)}</td><td><Link className="hub-button" to={`/dashboard/${encodeURIComponent(session.session_id)}`} aria-label={`View ${sessionLabel(session.round_types)} report from ${session.created_at ? new Date(session.created_at).toLocaleDateString() : 'this session'}`}>View report →</Link></td>
      </tr>)}</tbody></table></div>}
      {data.scored_session_count > data.history.length && <p className="hub-caption">Showing the latest {data.history.length} of {data.scored_session_count} scored sessions.</p>}
    </section>

    <section className="hub-section" aria-labelledby="signals-heading">
      <div className="hub-section-heading"><span>03</span><h2 id="signals-heading">Learning signals</h2><p>Your recorded practice activity.</p></div>
      <div className="hub-columns hub-columns-three">
        <div className="hub-detail"><h3>Elo changes</h3>{!signals?.elo_deltas?.length ? <p>Not available. Score a round to record an Elo change.</p> : <ul className="hub-signal-list">{Object.entries(Object.fromEntries(signals.elo_deltas.map(row => [row.skill, row.cumulative_delta]))).map(([skill, delta]) => <li key={skill}><span>{skill}</span><strong>{delta >= 0 ? '+' : ''}{delta}</strong></li>)}</ul>}<p className="hub-caption">Cumulative recorded change per skill.</p></div>
        <div className="hub-detail"><h3>Revisit rate</h3>{!signals?.revisit_rates?.length ? <p>Not available. Revisit a skill across sessions to track practice repetition.</p> : <ul className="hub-signal-list">{signals.revisit_rates.map(row => <li key={row.skill}><span>{row.skill}</span><strong>{fraction(row.rate)}</strong></li>)}</ul>}<p className="hub-caption">Repeat sessions divided by all sessions for each skill. This describes activity, not learning effectiveness.</p></div>
        <div className="hub-detail"><h3>Roadmap completion</h3><ul className="hub-signal-list">{[7, 14, 30].map(days => <li key={days}><span>{days} day plan</span><strong>{fraction(signals?.roadmap_completion?.[String(days)])}</strong></li>)}</ul><p className="hub-caption">Completion records reflect marked roadmap steps.</p></div>
      </div>
    </section>
    <footer className="hub-footer"><p>Choose your next practice, target or resume check on Home.</p><Link className="hub-button hub-button-primary" to="/home">Back to Home →</Link></footer>
  </>;
}

export default function Progress() {
  const overview = useAccountOverview();
  return <AccountPage {...overview}>{overview.data && <ProgressContent data={overview.data} />}</AccountPage>;
}
