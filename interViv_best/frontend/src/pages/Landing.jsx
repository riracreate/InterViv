import React, { useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

/* ═══════════════════════════════════════════════════════════
   VIDEO BACKGROUND with custom fade-in / fade-out loop
   ═══════════════════════════════════════════════════════════ */
function VideoBackground() {
  const videoRef = useRef(null);
  const rafRef = useRef(null);

  const FADE_DURATION = 0.5; // seconds

  const monitorPlayback = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.paused) return;

    const { currentTime, duration } = video;

    if (duration && duration > 0) {
      // Fade in at start
      if (currentTime < FADE_DURATION) {
        video.style.opacity = String(currentTime / FADE_DURATION);
      }
      // Fade out near end
      else if (currentTime > duration - FADE_DURATION) {
        const remaining = duration - currentTime;
        video.style.opacity = String(Math.max(0, remaining / FADE_DURATION));
      }
      // Full opacity mid-playback
      else {
        video.style.opacity = '1';
      }
    }

    rafRef.current = requestAnimationFrame(monitorPlayback);
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // Start with opacity 0
    video.style.opacity = '0';
    video.style.transition = 'none';

    const handlePlay = () => {
      rafRef.current = requestAnimationFrame(monitorPlayback);
    };

    const handleEnded = () => {
      // Cancel animation frame
      if (rafRef.current) cancelAnimationFrame(rafRef.current);

      // Snap to transparent
      video.style.opacity = '0';

      // Brief pause, then restart
      setTimeout(() => {
        video.currentTime = 0;
        video.play().catch(() => {});
      }, 100);
    };

    video.addEventListener('play', handlePlay);
    video.addEventListener('ended', handleEnded);

    // Initial play
    video.play().catch(() => {});

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('ended', handleEnded);
    };
  }, [monitorPlayback]);

  return (
    <div
      className="absolute z-0"
      style={{ top: '300px', inset: 'auto 0 0 0', position: 'absolute' }}
    >
      <video
        ref={videoRef}
        muted
        playsInline
        preload="auto"
        className="w-full h-full object-cover"
        style={{ opacity: 0 }}
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260328_083109_283f3553-e28f-428b-a723-d639c617eb2b.mp4"
      />
      {/* Gradient overlays over video */}
      <div className="absolute inset-0 bg-gradient-to-b from-white via-transparent to-white pointer-events-none" />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   NAVIGATION BAR
   ═══════════════════════════════════════════════════════════ */
function Navbar() {
  const navigate = useNavigate();

  const menuItems = [
    { label: 'Home', active: true },
    { label: 'Practice', active: false, action: () => navigate('/upload') },
    { label: 'Dashboard', active: false, action: () => navigate('/dashboard') },
  ];

  return (
    <nav className="relative z-10 w-full">
      <div className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
        {/* Logo */}
        <a
          href="/"
          onClick={(e) => { e.preventDefault(); navigate('/'); }}
          className="text-3xl tracking-tight text-black"
          style={{ fontFamily: "'Instrument Serif', serif" }}
        >
          interViv<sup className="text-sm align-super">©</sup>
        </a>

        {/* Menu Items */}
        <ul className="hidden md:flex items-center gap-8">
          {menuItems.map((item) => (
            <li key={item.label}>
              <a
                href="#"
                onClick={(e) => { e.preventDefault(); item.action && item.action(); }}
                className="text-sm transition-colors duration-200 hover:text-black"
                style={{
                  fontFamily: "'Inter', sans-serif",
                  color: item.active ? '#000000' : '#6F6F6F',
                }}
              >
                {item.label}
              </a>
            </li>
          ))}
        </ul>

        {/* CTA Button */}
        <button
          onClick={() => navigate('/upload')}
          className="rounded-full px-6 py-2.5 text-sm text-white cursor-pointer transition-transform duration-200 hover:scale-[1.03]"
          style={{
            backgroundColor: '#000000',
            fontFamily: "'Inter', sans-serif",
          }}
        >
          Begin Interview
        </button>
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
          fontFamily: "'Instrument Serif', serif",
          lineHeight: 0.95,
          letterSpacing: '-2.46px',
          color: '#000000',
        }}
      >
        Beyond{' '}
        <em style={{ color: '#6F6F6F', fontStyle: 'italic' }}>preparation,</em>
        <br />
        we build{' '}
        <em style={{ color: '#6F6F6F', fontStyle: 'italic' }}>confidence.</em>
      </h1>

      {/* Description */}
      <p
        className="animate-fade-rise-delay text-base sm:text-lg max-w-2xl mt-8 leading-relaxed"
        style={{
          fontFamily: "'Inter', sans-serif",
          color: '#6F6F6F',
        }}
      >
        AI-powered mock interviews that adapt to your skill level in real time.
        Upload your resume, speak your answers, and get instant feedback from
        an intelligent scoring engine.
      </p>

      {/* CTA Button */}
      <button
        onClick={() => navigate('/upload')}
        className="animate-fade-rise-delay-2 rounded-full px-14 py-5 text-base mt-12 text-white cursor-pointer transition-transform duration-200 hover:scale-[1.03]"
        style={{
          backgroundColor: '#000000',
          fontFamily: "'Inter', sans-serif",
        }}
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
      {/* Video background layer */}
      <VideoBackground />

      {/* Navigation */}
      <Navbar />

      {/* Hero */}
      <HeroSection />
    </div>
  );
}
