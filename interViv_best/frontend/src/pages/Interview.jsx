import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { loadInterviewState, submitAnswer as apiSubmitAnswer, buildAnswerMetrics, clearInterviewState } from '../lib/api';

export default function Interview() {
  const { sessionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const videoRef = useRef(null);
  const recognitionRef = useRef(null);
  const streamRef = useRef(null);

  const initState = location.state || loadInterviewState() || {};

  const [question, setQuestion] = useState(initState.question || '');
  const [difficulty, setDifficulty] = useState(initState.difficulty || 'medium');
  const [currentSkill, setCurrentSkill] = useState(initState.skill || '');
  const [allSkills] = useState(initState.allSkills || [initState.skill || 'General']);
  const [round, setRound] = useState(initState.round || 1);
  const [totalRounds] = useState(initState.totalRounds || 5);
  const [elo, setElo] = useState(initState.elo || 1200);

  const [timer, setTimer] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [interimText, setInterimText] = useState('');
  const [isScoring, setIsScoring] = useState(false);
  const [isVideoOn, setIsVideoOn] = useState(true);
  const [sessionComplete, setSessionComplete] = useState(false);

  const [currentScore, setCurrentScore] = useState(null);
  const [currentFeedback, setCurrentFeedback] = useState('');
  const [scores, setScores] = useState([]);

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = 'en-US';
    rec.onresult = (e) => {
      let final = '', interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) final += t + ' ';
        else interim += t;
      }
      if (final) { setTranscript(p => p + final); setInterimText(''); }
      else setInterimText(interim);
    };
    rec.onerror = (e) => {
      if (e.error === 'not-allowed') alert('Microphone access denied.');
      setIsRecording(false);
    };
    rec.onend = () => { setIsRecording(false); setInterimText(''); };
    recognitionRef.current = rec;
  }, []);

  useEffect(() => {
    if (isVideoOn && navigator.mediaDevices?.getUserMedia) {
      navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        .then(stream => {
          streamRef.current = stream;
          if (videoRef.current) videoRef.current.srcObject = stream;
        })
        .catch(() => setIsVideoOn(false));
    } else {
      streamRef.current?.getTracks().forEach(t => t.stop());
      streamRef.current = null;
      if (videoRef.current) videoRef.current.srcObject = null;
    }
    return () => streamRef.current?.getTracks().forEach(t => t.stop());
  }, [isVideoOn]);

  useEffect(() => {
    if (sessionComplete) return;
    const id = setInterval(() => setTimer(t => t + 1), 1000);
    return () => clearInterval(id);
  }, [sessionComplete]);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      recognitionRef.current?.stop();
      setIsRecording(false);
    } else {
      if (!recognitionRef.current) {
        alert('Speech Recognition is not supported. Please use Chrome or Edge.');
        return;
      }
      try { recognitionRef.current.start(); setIsRecording(true); }
      catch { /* already started */ }
    }
  }, [isRecording]);

  const submitAnswer = async () => {
    if (!transcript.trim() || isScoring) return;
    if (isRecording) { recognitionRef.current?.stop(); setIsRecording(false); }
    setIsScoring(true);
    try {
      const metrics = buildAnswerMetrics(transcript.trim());
      const resp = await apiSubmitAnswer({
        session_id: sessionId,
        round,
        answer_text: transcript.trim(),
        ...metrics,
      });

      const score = resp.final_score ?? 50;
      const feedbackRaw = resp.feedback?.next_step || resp.feedback?.content?.[0] || '';
      const feedback = typeof feedbackRaw === 'string' ? feedbackRaw : '';
      setCurrentScore(score);
      setCurrentFeedback(feedback);
      setElo(resp.elo_after ?? elo);
      setScores(p => [...p, { round, skill: currentSkill, score, question, feedback }]);

      if (resp.session_complete) {
        setSessionComplete(true);
      } else if (resp.next_question) {
        setQuestion(resp.next_question);
        setDifficulty(resp.difficulty || 'medium');
        setCurrentSkill(resp.current_skill || resp.next_skill || currentSkill);
        setRound(round + 1);
      }
    } catch (err) {
      setCurrentFeedback('Scoring failed — ' + err.message);
    } finally {
      setIsScoring(false);
    }
  };

  const handleNext = () => {
    if (sessionComplete) {
      clearInterviewState();
      navigate(`/dashboard/${sessionId}`);
      return;
    }
    setTranscript(''); setInterimText('');
    setCurrentScore(null); setCurrentFeedback('');
    setIsRecording(false);
  };

  const resetAnswer = () => {
    if (isRecording) recognitionRef.current?.stop();
    setTranscript(''); setInterimText('');
    setCurrentScore(null); setCurrentFeedback('');
    setIsRecording(false);
  };

  const fmt = (s) => `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;
  const scoreColor = (score) => score >= 75 ? '#16A34A' : score >= 50 ? '#D97706' : '#DC2626';
  const progress = totalRounds ? ((round - 1 + (currentScore !== null ? 1 : 0)) / totalRounds) * 100 : 0;
  const answerWordCount = transcript.trim().split(/\s+/).filter(Boolean).length;
  const canSubmit = transcript.trim().length > 0 && !isScoring && currentScore === null;

  if (sessionComplete) {
    const avg = scores.length ? Math.round(scores.reduce((a, b) => a + b.score, 0) / scores.length) : 0;
    return (
      <div className="min-h-screen bg-white flex flex-col">
        <nav className="border-b border-black/5">
          <div className="flex items-center justify-between px-8 py-5 max-w-7xl mx-auto">
            <a href="/" onClick={(e) => { e.preventDefault(); navigate('/'); }}
              className="text-2xl tracking-tight text-black" style={{ fontFamily: "'Instrument Serif', serif" }}>
              interViv<sup className="text-xs align-super">©</sup>
            </a>
          </div>
        </nav>
        <div className="flex-1 flex items-start justify-center px-6 pt-12 pb-20">
          <div className="max-w-2xl w-full">
            <div className="text-center mb-10">
              <h1 className="text-5xl tracking-tight mb-3" style={{ fontFamily: "'Instrument Serif', serif", letterSpacing: '-1.5px' }}>
                Session Complete
              </h1>
              <p className="text-base" style={{ fontFamily: "'Inter', sans-serif", color: '#6F6F6F' }}>
                {scores.length} rounds · {fmt(timer)} · Average{' '}
                <span style={{ color: scoreColor(avg), fontWeight: 600 }}>{avg}%</span>
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4 mb-8">
              {[{ v: elo, l: 'Final Elo' }, { v: `${avg}%`, l: 'Average Score' }].map(s => (
                <div key={s.l} className="rounded-2xl border border-black/8 py-5 text-center">
                  <div className="text-2xl font-normal text-black mb-1" style={{ fontFamily: "'Instrument Serif', serif" }}>{s.v}</div>
                  <div className="text-[10px] font-medium uppercase tracking-wider text-[#6F6F6F]" style={{ fontFamily: "'Inter', sans-serif" }}>{s.l}</div>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-center gap-3">
              <button onClick={() => { clearInterviewState(); navigate(`/dashboard/${sessionId}`); }}
                className="rounded-full px-8 py-3 text-sm font-medium text-white cursor-pointer hover:scale-[1.02] transition-transform"
                style={{ backgroundColor: '#000', fontFamily: "'Inter', sans-serif" }}>
                View Dashboard
              </button>
              <button onClick={() => navigate('/upload')}
                className="rounded-full px-8 py-3 text-sm font-medium text-[#6F6F6F] cursor-pointer hover:text-black transition-colors border border-black/10"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                New Session
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-white flex flex-col overflow-hidden">
      <header className="h-14 px-6 flex items-center justify-between border-b border-black/5 shrink-0">
        <div className="flex items-center gap-4">
          <button onClick={() => { if (confirm('Exit? Progress will be lost.')) { clearInterviewState(); navigate('/'); } }}
            className="text-[#6F6F6F] hover:text-black transition-colors cursor-pointer text-sm"
            style={{ fontFamily: "'Inter', sans-serif" }}>
            ← Exit
          </button>
          <div className="h-4 w-px bg-black/10" />
          <span className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F]"
            style={{ fontFamily: "'Inter', sans-serif" }}>{currentSkill || 'Live Session'}</span>
        </div>
        <div className="flex items-center gap-5">
          <div className="hidden sm:flex items-center gap-2">
            <div className="w-24 h-1.5 bg-black/5 rounded-full overflow-hidden">
              <div className="h-full bg-black rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
            </div>
            <span className="text-xs text-[#6F6F6F]" style={{ fontFamily: "'Inter', sans-serif" }}>{round}/{totalRounds}</span>
          </div>
          <span className="text-sm font-mono text-[#6F6F6F]">{fmt(timer)}</span>
          <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-black/[0.03] text-[#6F6F6F]"
            style={{ fontFamily: "'Inter', sans-serif" }}>Elo {elo}</span>
          <div className="hidden md:flex gap-1">
            {allSkills.map(s => (
              <span key={s} className="text-[10px] px-2 py-1 rounded-full border"
                style={{
                  fontFamily: "'Inter', sans-serif",
                  borderColor: s === currentSkill ? '#000' : '#E0E0E0',
                  backgroundColor: s === currentSkill ? '#000' : 'transparent',
                  color: s === currentSkill ? '#fff' : '#6F6F6F',
                }}>
                {s}
              </span>
            ))}
          </div>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[7fr_3fr] gap-4 p-4 overflow-hidden">
        <div className="relative flex-1 bg-black/[0.02] rounded-2xl overflow-hidden border border-black/8">
          {isVideoOn
            ? <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
            : (
              <div className="w-full h-full flex flex-col items-center justify-center">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#6F6F6F" strokeWidth="1">
                  <path d="M16 16v1a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2m5.66 0H14a2 2 0 0 1 2 2v3.34l1 1L23 7v10"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
                <span className="text-sm mt-4 text-[#6F6F6F]" style={{ fontFamily: "'Inter', sans-serif" }}>Camera Off</span>
              </div>
            )
          }

          <div className="absolute top-4 left-4 flex items-center gap-2 bg-white/90 backdrop-blur-sm px-3 py-1.5 rounded-full border border-black/8">
            <div className={`w-2 h-2 rounded-full ${isRecording ? 'bg-red-500 animate-pulse' : 'bg-[#6F6F6F]/30'}`} />
            <span className="text-[10px] font-medium uppercase tracking-wider text-[#6F6F6F]"
              style={{ fontFamily: "'Inter', sans-serif" }}>
              {isRecording ? 'Recording' : 'Standby'}
            </span>
          </div>

          <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm px-3 py-1.5 rounded-full border border-black/8">
            <span className="text-[10px] font-medium uppercase tracking-wider text-[#6F6F6F]"
              style={{ fontFamily: "'Inter', sans-serif" }}>
              {currentSkill} · {difficulty}
            </span>
          </div>

          <div className="absolute bottom-4 left-4 right-4 bg-white/95 backdrop-blur-sm rounded-xl p-5 border border-black/8 shadow-sm">
            <span className="text-[10px] font-medium uppercase tracking-wider text-[#6F6F6F] mb-2 block"
              style={{ fontFamily: "'Inter', sans-serif" }}>
              Question {String(round).padStart(2, '0')} / {String(totalRounds).padStart(2, '0')}
            </span>
            <p className="text-base font-normal text-black leading-relaxed" style={{ fontFamily: "'Inter', sans-serif" }}>
              {question || 'Loading...'}
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-3 overflow-hidden min-h-0">
          <div className="rounded-2xl border border-black/8 p-5 flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[10px] font-medium uppercase tracking-wider text-[#6F6F6F]"
                style={{ fontFamily: "'Inter', sans-serif" }}>Answer Draft</h3>
              {answerWordCount > 0 && (
                <span className="text-[10px] text-[#6F6F6F]/60" style={{ fontFamily: "'Inter', sans-serif" }}>
                  {answerWordCount} words
                </span>
              )}
            </div>
            <textarea
              aria-label="Answer draft"
              value={transcript}
              onChange={(e) => {
                setTranscript(e.target.value);
                setCurrentFeedback('');
              }}
              disabled={isScoring || currentScore !== null}
              placeholder={isRecording ? 'Listening...' : 'Type your answer here or use the microphone.'}
              className="flex-1 min-h-[180px] w-full resize-none rounded-xl border border-transparent bg-transparent text-sm leading-relaxed text-[#333] outline-none transition-colors placeholder:text-[#6F6F6F]/40 focus:border-black/10 focus:bg-black/[0.015] disabled:cursor-default"
              style={{ fontFamily: "'Inter', sans-serif" }}
            />
            {interimText && currentScore === null && (
              <p className="mt-3 rounded-xl bg-black/[0.03] px-3 py-2 text-xs italic text-[#6F6F6F]/70"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                {interimText}
              </p>
            )}
          </div>

          {currentScore !== null && (
            <div className="rounded-2xl border border-black/8 p-5">
              <div className="text-3xl font-normal mb-1 text-center"
                style={{ fontFamily: "'Instrument Serif', serif", color: scoreColor(currentScore) }}>
                {Math.round(currentScore)}%
              </div>
              {currentFeedback && (
                <p className="text-xs text-[#6F6F6F] text-center mt-1 leading-relaxed"
                  style={{ fontFamily: "'Inter', sans-serif" }}>
                  {currentFeedback}
                </p>
              )}
            </div>
          )}

          <div className="flex items-center gap-2">
            <button onClick={() => setIsVideoOn(p => !p)}
              className={`w-11 h-11 rounded-full flex items-center justify-center cursor-pointer transition-all border ${!isVideoOn ? 'bg-red-50 border-red-200 text-red-500' : 'bg-white border-black/10 text-[#6F6F6F]'}`}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                {isVideoOn
                  ? <><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></>
                  : <><path d="M16 16v1a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2m5.66 0H14a2 2 0 0 1 2 2v3.34l1 1L23 7v10"/><line x1="1" y1="1" x2="23" y2="23"/></>
                }
              </svg>
            </button>

            <button onClick={toggleRecording}
              className={`w-11 h-11 rounded-full flex items-center justify-center cursor-pointer transition-all border ${isRecording ? 'bg-red-50 border-red-200 text-red-500' : 'bg-white border-black/10 text-[#6F6F6F]'}`}>
              {isRecording
                ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/></svg>
                : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
              }
            </button>

            {currentScore === null && (
              <button onClick={submitAnswer} disabled={!canSubmit}
                className="flex-1 rounded-full py-3 text-sm font-medium text-white cursor-pointer hover:scale-[1.01] transition-transform disabled:cursor-not-allowed disabled:opacity-35"
                style={{ backgroundColor: '#000', fontFamily: "'Inter', sans-serif" }}>
                {isScoring
                  ? <span className="flex items-center justify-center gap-2">
                      <span className="w-3 h-3 border border-white/30 border-t-white rounded-full animate-spin"/>Scoring...
                    </span>
                  : 'Submit Answer'
                }
              </button>
            )}

            {currentScore !== null && (
              <button onClick={handleNext}
                className="flex-1 rounded-full py-3 text-sm font-medium text-white cursor-pointer hover:scale-[1.01] transition-transform"
                style={{ backgroundColor: '#000', fontFamily: "'Inter', sans-serif" }}>
                {sessionComplete ? 'View Dashboard →' : 'Next Question →'}
              </button>
            )}

            <button onClick={resetAnswer}
              className="w-9 h-9 rounded-full flex items-center justify-center border border-black/10 text-[#6F6F6F] cursor-pointer">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
