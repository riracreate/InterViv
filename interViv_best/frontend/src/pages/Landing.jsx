import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, BookOpen, Braces, Check, FileSearch, MessageCircle, Sparkles, Target } from 'lucide-react';
import { hasAuthToken } from '../lib/api';

function Navbar() {
  const navigate = useNavigate();
  const signedIn = hasAuthToken();
  return <nav className="iv-marketing-nav" aria-label="Main navigation">
    <a className="iv-brand" href="/" onClick={event => { event.preventDefault(); navigate('/'); }}><span className="iv-brand-mark">i</span><span>inter<span>Viv</span></span></a>
    <div className="iv-marketing-links"><a href="#how-it-works">How it works</a><a href="#features">Explore features</a></div>
    <div className="iv-marketing-actions">
      {signedIn ? (
        <button type="button" onClick={() => navigate('/home')} className="app-button app-button-primary">
          Go to Home
        </button>
      ) : <><button type="button" onClick={() => navigate('/login')} className="app-button">Log in</button><button type="button" onClick={() => navigate('/signup')} className="app-button app-button-primary">Get started <ArrowUpRight size={15} /></button></>}
    </div>
  </nav>;
}

function HeroSection() {
  const navigate = useNavigate();
  const signedIn = hasAuthToken();
  return <main>
    <section className="iv-landing-hero">
      <div><p className="iv-kicker"><span className="iv-landing-dot" /> YOUR NEXT OPPORTUNITY STARTS HERE</p>
        <h1>Prepare with purpose.<br /><em>Interview with confidence.</em></h1>
        <p className="iv-landing-intro">A more thoughtful way to practice interviews, sharpen your skills, and see where to go next.</p>
        <div className="iv-landing-actions"><button type="button" className="app-button app-button-primary" onClick={() => navigate('/upload')}>Start practicing <ArrowUpRight size={17} /></button><a className="app-button" href="#how-it-works">See how it works <ArrowRight size={16} /></a></div>
        <p className="iv-landing-footnote"><Check size={15} /> Practice at your own pace <span>·</span> Start with or without a resume</p>
      </div>
      <div className="iv-landing-visual" aria-label="Preparation tools overview"><div className="iv-landing-orbit iv-landing-orbit-one" /><div className="iv-landing-orbit iv-landing-orbit-two" />
        <div className="iv-landing-panel"><div className="iv-landing-panel-top"><span className="iv-brand-mark">i</span><span>YOUR PREPARATION SPACE</span><Sparkles size={17} /></div>
          <h2>Every step counts.</h2><p>Build a routine that moves you forward.</p>
          <div className="iv-landing-row"><span><MessageCircle size={18} /></span><div><strong>Practice interviews</strong><small>Text, voice, and custom rounds</small></div><ArrowUpRight size={16} /></div>
          <div className="iv-landing-row"><span><Braces size={18} /></span><div><strong>Sharpen your skills</strong><small>Coding, SQL, and more</small></div><ArrowUpRight size={16} /></div>
          <div className="iv-landing-row"><span><Target size={18} /></span><div><strong>Find your next step</strong><small>Feedback and focused learning</small></div><ArrowUpRight size={16} /></div>
        </div>
      </div>
    </section>
    <section className="iv-landing-journey" id="how-it-works"><p className="iv-kicker">A clearer path forward</p><h2>Progress, one step at a time.</h2>
      <div className="iv-landing-steps"><article><span>01</span><h3>Choose your focus</h3><p>Start with a role, a skill, or a practice mode that fits your goals.</p></article><article><span>02</span><h3>Put it into practice</h3><p>Work through realistic questions in the way that works for you.</p></article><article><span>03</span><h3>Learn what comes next</h3><p>Review your answers and build a plan around your progress.</p></article></div>
    </section>
    <section className="iv-landing-features" id="features"><div><p className="iv-kicker">Everything in one place</p><h2>Make room for<br /><em>better preparation.</em></h2></div>
      <div className="iv-landing-feature-grid"><article><MessageCircle /><h3>Interview practice</h3><p>Answer technical and behavioral questions with text or voice.</p></article><article><Braces /><h3>Coding &amp; SQL</h3><p>Practice problems with examples, drafts, and feedback.</p></article><article><FileSearch /><h3>Resume check</h3><p>Review your resume against a role or job description.</p></article><article><BookOpen /><h3>Learning &amp; resources</h3><p>Revisit mistakes and find the right material for your next step.</p></article></div>
    </section>
    <section className="iv-landing-cta"><div><p className="iv-kicker">Ready when you are</p><h2>Your next step starts here.</h2><p>Bring your curiosity. We’ll help you build a practice habit.</p></div><button type="button" className="app-button" onClick={() => navigate(signedIn ? '/home' : '/signup')}>{signedIn ? 'Go to your workspace' : 'Create your account'} <ArrowRight size={16} /></button></section>
    <footer className="iv-landing-footer"><span>interViv</span><span>Built for your next step.</span></footer>
  </main>;
}

export default function Landing() {
  return <div className="iv-landing"><Navbar /><HeroSection /></div>;
}
