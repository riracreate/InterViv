import React from 'react';
import { useNavigate } from 'react-router-dom';
import { hasAuthToken } from '../lib/api';

/* ═══════════════════════════════════════════════════════════
   PREMIUM NON-NATURE BACKGROUND
   ═══════════════════════════════════════════════════════════ */
function PremiumBackground() {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-0 overflow-hidden" style={{ top: '92px' }} aria-hidden="true">
      <div
        className="absolute inset-0"
        style={{
          background: 'linear-gradient(180deg, #FFFFFF 0%, #F5F7FA 32%, #DDE5ED 100%)',
        }}
      />

      <div
        className="absolute inset-x-0 top-0 h-[560px]"
        style={{
          background: 'linear-gradient(180deg, rgba(255,255,255,1) 0%, rgba(255,255,255,0.98) 58%, rgba(255,255,255,0.24) 100%)',
        }}
      />

      <div
        className="absolute left-1/2 top-[455px] h-[380px] w-[88vw] max-w-[1180px] -translate-x-1/2 overflow-hidden rounded-[34px] border border-white/70"
        style={{
          background: 'linear-gradient(135deg, rgba(7,18,32,0.96) 0%, rgba(18,34,50,0.92) 52%, rgba(99,110,118,0.78) 100%)',
          boxShadow: '0 44px 130px rgba(9, 22, 39, 0.28), inset 0 1px 0 rgba(255,255,255,0.35)',
        }}
      >
        <div
          className="absolute inset-0 opacity-50"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.10) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px)',
            backgroundSize: '76px 76px',
          }}
        />

        <div className="absolute left-[7%] top-[17%] h-[34%] w-[22%] rounded-[22px] border border-white/20 bg-white/10 shadow-2xl backdrop-blur-md" />
        <div className="absolute left-[33%] top-[10%] h-[46%] w-[34%] rounded-[26px] border border-white/20 bg-white/10 shadow-2xl backdrop-blur-md" />
        <div className="absolute right-[7%] top-[18%] h-[34%] w-[22%] rounded-[22px] border border-white/20 bg-white/10 shadow-2xl backdrop-blur-md" />

        <div className="absolute left-[11%] top-[25%] h-2 w-[13%] rounded-full bg-white/40" />
        <div className="absolute left-[11%] top-[33%] h-2 w-[18%] rounded-full bg-cyan-100/20" />
        <div className="absolute left-[11%] top-[41%] h-2 w-[10%] rounded-full bg-white/20" />

        <div className="absolute left-[39%] top-[23%] h-2 w-[20%] rounded-full bg-white/40" />
        <div className="absolute left-[39%] top-[32%] h-2 w-[16%] rounded-full bg-cyan-100/25" />
        <div className="absolute left-[39%] top-[41%] h-2 w-[23%] rounded-full bg-white/20" />

        <div className="absolute right-[11%] top-[26%] h-2 w-[13%] rounded-full bg-white/30" />
        <div className="absolute right-[11%] top-[35%] h-2 w-[18%] rounded-full bg-cyan-100/20" />
        <div className="absolute right-[11%] top-[44%] h-2 w-[10%] rounded-full bg-white/20" />

        <div className="absolute inset-x-[9%] bottom-[88px] h-px bg-white/30" />
        <div className="absolute inset-x-[18%] bottom-[56px] h-px bg-white/20" />
        <div className="absolute bottom-0 left-1/2 h-[130px] w-[72%] -translate-x-1/2 bg-black/40" style={{ clipPath: 'polygon(11% 0, 89% 0, 100% 100%, 0 100%)' }} />
      </div>

      <div
        className="absolute left-1/2 bottom-[82px] h-[120px] w-[76vw] max-w-[940px] -translate-x-1/2"
        style={{
          background: 'linear-gradient(180deg, rgba(255,255,255,0.78) 0%, rgba(9,18,31,0.18) 100%)',
          clipPath: 'polygon(14% 0, 86% 0, 100% 100%, 0 100%)',
          filter: 'blur(0.2px)',
        }}
      />

      <div
        className="absolute inset-x-0 bottom-0 h-[310px]"
        style={{
          background: 'linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.48) 44%, rgba(255,255,255,0.96) 100%)',
        }}
      />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   NAVIGATION BAR
   ═══════════════════════════════════════════════════════════ */
function Navbar() {
  const navigate = useNavigate();
  const signedIn = hasAuthToken();

  const menuItems = [
    { label: 'Home', to: '/home' },
    { label: 'Practice', to: '/practice' },
    { label: 'Progress', to: '/dashboard' },
  ];

  return (
    <nav className="relative z-10 w-full">
      <div className="flex flex-wrap items-center justify-between gap-4 px-5 py-6 sm:px-8 max-w-7xl mx-auto">
        {/* Logo */}
        <a
          href="/"
          onClick={(e) => { e.preventDefault(); navigate('/'); }}
          className="text-3xl tracking-tight text-black"
          style={{ fontFamily: "var(--font-display)" }}
        >
          interViv<sup className="text-sm align-super">©</sup>
        </a>

        {/* Menu Items */}
        <ul className="hidden md:flex items-center gap-8">
          {menuItems.map((item) => (
            <li key={item.label}>
              <a
                href={item.to}
                onClick={(e) => { e.preventDefault(); navigate(item.to); }}
                className="text-sm transition-colors duration-200 hover:!text-black"
                style={{
                  fontFamily: "var(--font-body)",
                  color: 'var(--color-muted)',
                }}
              >
                {item.label}
              </a>
            </li>
          ))}
        </ul>

        {/* Account actions: one way back in when signed in */}
        <div className="flex items-center gap-3">
          {signedIn ? (
            <button type="button" onClick={() => navigate('/home')} className="app-button app-button-primary">
              Go to Home
            </button>
          ) : (
            <>
              <button type="button" onClick={() => navigate('/login')} className="app-button">
                Login
              </button>
              <button type="button" onClick={() => navigate('/signup')} className="app-button app-button-primary">
                Sign up
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}

/* ═══════════════════════════════════════════════════════════
   HERO SECTION
   ═══════════════════════════════════════════════════════════ */
function HeroSection() {
  const navigate = useNavigate();

  return (
    <section
      className="relative z-10 flex flex-col items-center justify-center text-center px-6 pb-40"
      style={{ paddingTop: 'calc(8rem - 75px)' }}
    >
      {/* Headline */}
      <h1
        className="animate-fade-rise text-5xl sm:text-7xl md:text-8xl max-w-7xl font-normal"
        style={{
          fontFamily: "var(--font-display)",
          lineHeight: 0.95,
          letterSpacing: 0,
          color: 'var(--color-foreground)',
        }}
      >
        Beyond{' '}
        <em style={{ color: 'var(--color-muted)', fontStyle: 'italic' }}>preparation,</em>
        <br />
        we build{' '}
        <em style={{ color: 'var(--color-muted)', fontStyle: 'italic' }}>confidence.</em>
      </h1>

      {/* Description */}
      <p
        className="animate-fade-rise-delay text-base sm:text-lg max-w-2xl mt-8 leading-relaxed"
        style={{
          fontFamily: "var(--font-body)",
          color: '#334155',
          textShadow: '0 1px 18px rgba(255,255,255,0.96)',
        }}
      >
        Interview readiness practice that adapts to your skill level in real time.
        Upload your resume, speak your answers, and get deterministic feedback
        from the scoring engine.
      </p>

      {/* CTA Button */}
      <button
        type="button"
        onClick={() => navigate('/upload')}
        className="animate-fade-rise-delay-2 app-button app-button-primary mt-20"
        style={{ padding: '20px 56px', fontSize: 'var(--text-base)' }}
      >
        Start Interview
      </button>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════
   LANDING PAGE ASSEMBLY
   ═══════════════════════════════════════════════════════════ */
export default function Landing() {
  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-white">
      {/* Premium background layer */}
      <PremiumBackground />

      {/* Navigation */}
      <Navbar />

      {/* Hero */}
      <HeroSection />
    </div>
  );
}
