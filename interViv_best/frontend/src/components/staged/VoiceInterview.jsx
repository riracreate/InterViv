import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import AppNav from '../AppNav';
import { fetchAvCapabilities, transcribeAudio } from '../../lib/api';
import { createStagedSessionController, stagedSessionState } from '../../lib/stagedSession';
import { deliveryReport } from '../../lib/speech/deliveryReport';
import { CLOSING_LINE, attachInterviewSpeech, interviewerLines } from '../../lib/speech/interviewerScript';
import { createPresenceSampler, detectFaceCount } from '../../lib/speech/presence';
import { createRecognitionController, recognitionClass } from '../../lib/speech/stt';
import { createSpeaker } from '../../lib/speech/tts';
import { pickEnglishVoice, rankEnglishVoices, readStoredVoiceName, writeStoredVoiceName } from '../../lib/speech/voiceChoice';
import { speechInputMode } from '../../lib/speech/voiceSession';

const RAIL = [['warm_up', 'Warm-up'], ['core', 'Core'], ['follow_up', 'Follow-up'], ['wrap_up', 'Wrap-up']];

function railKey(stage, phase) {
  if (phase === 'completed' || stage === 'behavioural') return 'wrap_up';
  if (stage === 'follow_up') return 'follow_up';
  if (stage === 'core') return 'core';
  return 'warm_up';
}

function formatSeconds(ms) {
  return `${(Math.max(0, Number(ms) || 0) / 1000).toFixed(1)} s`;
}

function answerLabel(item) {
  const stage = { warm_up: 'Warm-up', core: 'Core', follow_up: 'Follow-up', behavioural: 'Behavioural' }[item.stage] || '';
  if (item.stage === 'follow_up') return [item.skill, 'Follow-up'].filter(Boolean).join(' · ');
  if (item.skill && item.stage !== 'warm_up') return item.skill;
  return stage || item.skill || `Question ${item.round}`;
}

export default function VoiceInterview({ session }) {
  const [view, setView] = useState(() => stagedSessionState(session));
  const [answer, setAnswer] = useState('');
  const [draftReady, setDraftReady] = useState(false);
  const [draftNotice, setDraftNotice] = useState('Loading saved answer…');
  const [caption, setCaption] = useState('');
  const [speaking, setSpeaking] = useState(false);
  const [muted, setMuted] = useState(false);
  const [voices, setVoices] = useState([]);
  const [voiceName, setVoiceName] = useState(() => readStoredVoiceName());
  const [listenState, setListenState] = useState('idle');
  const [serverTranscription, setServerTranscription] = useState(false);
  const [serverBusy, setServerBusy] = useState(false);
  const [speechNotice, setSpeechNotice] = useState('');
  const [cameraNote, setCameraNote] = useState('');
  const [reports, setReports] = useState([]);
  const controller = useRef(null);
  const dirty = useRef(false);
  const committed = useRef('');
  const spokenMs = useRef(0);
  const listenStartedAt = useRef(0);
  const speechRef = useRef(null);
  const speakerRef = useRef(null);
  const recognitionRef = useRef(null);
  const videoRef = useRef(null);
  const samplerRef = useRef(null);
  const voiceNameRef = useRef(voiceName);
  const mutedRef = useRef(false);
  const greetedRef = useRef(false);
  const spokenKey = useRef('');
  const lastLines = useRef([]);
  const attempted = useRef(null);
  const chunks = useRef([]);
  const mediaRecorderRef = useRef(null);
  const audioStreamRef = useRef(null);
  const discardServer = useRef(false);
  const unmounted = useRef(false);
  voiceNameRef.current = voiceName;
  mutedRef.current = muted;

  const mode = speechInputMode({
    recognitionAvailable: Boolean(recognitionClass()),
    transcriptionAvailable: serverTranscription,
  });

  function markListenStart() {
    if (!listenStartedAt.current) listenStartedAt.current = Date.now();
  }
  function markListenStop() {
    if (!listenStartedAt.current) return;
    spokenMs.current += Date.now() - listenStartedAt.current;
    listenStartedAt.current = 0;
  }
  function releaseServerAudio(discard) {
    discardServer.current = discard;
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    else audioStreamRef.current?.getTracks().forEach(track => track.stop());
  }

  useEffect(() => {
    const speaker = createSpeaker({
      chooseVoice: available => pickEnglishVoice(available, voiceNameRef.current),
      onEnd: () => speechRef.current?.ended(),
    });
    const Recognition = recognitionClass();
    const recognition = Recognition ? createRecognitionController({
      Recognition,
      onResult: (finalText, interim) => {
        if (finalText) committed.current = `${committed.current} ${finalText}`.trim();
        dirty.current = true;
        setAnswer(`${committed.current} ${interim}`.trim());
      },
        onState: state => {
          setListenState(state);
          if (state === 'error') setSpeechNotice('Speech input unavailable; please type.');
        },
    }) : null;
    speakerRef.current = speaker;
    recognitionRef.current = recognition;
    speechRef.current = attachInterviewSpeech({
      speaker, recognition, onSpeaking: setSpeaking, onCaption: setCaption,
    });
    return () => {
      unmounted.current = true;
      speechRef.current?.cancel();
      speaker.cancel();
      recognition?.abort();
      releaseServerAudio(true);
    };
  }, []);

  useEffect(() => {
    const current = createStagedSessionController({ session, onChange: setView });
    controller.current = current;
    setView(current.snapshot());
    return () => { current.dispose(); controller.current = null; };
  }, [session]);

  useEffect(() => {
    const video = videoRef.current;
    let stream = null;
    let cancelled = false;
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraNote('Camera unavailable. You can still answer by voice or typing.');
      return undefined;
    }
    navigator.mediaDevices.getUserMedia({ video: true, audio: false }).then(next => {
      if (cancelled) { next.getTracks().forEach(track => track.stop()); return; }
      stream = next;
      if (video) video.srcObject = next;
    }).catch(() => {
      if (!cancelled) setCameraNote('Camera unavailable. You can still answer by voice or typing.');
    });
    return () => {
      cancelled = true;
      stream?.getTracks().forEach(track => track.stop());
      if (video) video.srcObject = null;
    };
  }, []);

  const round = view.active?.round;
  useEffect(() => {
    spokenMs.current = 0;
    listenStartedAt.current = 0;
    const sampler = createPresenceSampler({ detectFaces: detectFaceCount });
    samplerRef.current = sampler;
    sampler.attach(videoRef.current);
    sampler.start();
    return () => sampler.stop();
  }, [round]);

  useEffect(() => {
    let cancelled = false;
    fetchAvCapabilities().then(report => {
      if (!cancelled) setServerTranscription(Boolean(report?.transcription?.available));
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const synth = window.speechSynthesis;
    if (!synth) return undefined;
    const load = () => setVoices(rankEnglishVoices(synth.getVoices?.() || []));
    load();
    synth.addEventListener?.('voiceschanged', load);
    return () => synth.removeEventListener?.('voiceschanged', load);
  }, []);

  useEffect(() => {
    if (view.phase !== 'ready' || view.busy || view.needsRefresh || view.error) return;
    const pending = view.pending?.round;
    if (!pending || attempted.current === pending) return;
    attempted.current = pending;
    controller.current?.advance();
  }, [view.phase, view.busy, view.needsRefresh, view.error, view.pending?.round]);

  useEffect(() => {
    if (view.phase === 'completed') {
      if (spokenKey.current === 'completed') return;
      spokenKey.current = 'completed';
      lastLines.current = [CLOSING_LINE];
      if (mutedRef.current) setCaption(CLOSING_LINE);
      else speechRef.current?.play([CLOSING_LINE]);
      return;
    }
    const active = view.active;
    if (view.phase !== 'answering' || !active?.question) return;
    const key = `${active.round}|${active.isFollowUp ? 1 : 0}|${active.question}`;
    if (spokenKey.current === key) return;
    spokenKey.current = key;
    const lines = interviewerLines({
      stage: active.stage, skill: active.skill, question: active.question,
      isFollowUp: active.isFollowUp, greeted: greetedRef.current,
    });
    if (active.stage === 'warm_up') greetedRef.current = true;
    lastLines.current = lines;
    if (mutedRef.current) setCaption(lines.at(-1) || active.question);
    else speechRef.current?.play(lines);
    return () => { spokenKey.current = ''; };
  }, [view.phase, view.active?.round, view.active?.question, view.active?.isFollowUp, view.active?.stage, view.active?.skill]);

  useEffect(() => {
    let cancelled = false;
    dirty.current = false;
    committed.current = '';
    setAnswer('');
    setDraftReady(false);
    if (view.phase !== 'answering' || view.active?.type !== 'technical_short_answer') return undefined;
    setDraftNotice('Loading saved answer…');
    controller.current.readDraft(round).then(saved => {
      if (cancelled || dirty.current) return;
      const text = saved || '';
      committed.current = text;
      setAnswer(text);
      setDraftNotice(saved ? 'Saved answer restored.' : 'Your answer saves as you type.');
    }).catch(() => {
      if (!cancelled) setDraftNotice('The saved answer could not be loaded. You can type an answer and retry saving.');
    }).finally(() => { if (!cancelled) setDraftReady(true); });
    return () => { cancelled = true; };
  }, [session.session_id, round, view.phase, view.active?.type]);

  useEffect(() => {
    if (!draftReady || !dirty.current || view.phase !== 'answering' || view.busy) return undefined;
    let cancelled = false;
    const timer = setTimeout(() => {
      setDraftNotice('Saving answer…');
      controller.current.saveDraft(round, answer).then(saved => {
        if (!cancelled && saved) setDraftNotice('Answer saved.');
      }).catch(() => { if (!cancelled) setDraftNotice('Answer could not be saved. Your text is still here; submit it or retry saving.'); });
    }, 600);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [answer, draftReady, round, view.phase, view.busy]);

  function rememberReport() {
    const active = view.active;
    if (!active?.round) return;
    markListenStop();
    const report = deliveryReport({
      text: answer,
      speakingMs: spokenMs.current,
      faceSamples: samplerRef.current?.samples() || [],
    });
    setReports(prev => [...prev.filter(item => item.round !== active.round), {
      round: active.round, skill: active.skill, stage: active.stage, ...report,
    }]);
  }

  async function startAnswering() {
    if (mode === 'type') {
      setSpeechNotice('Speech input unavailable; please type.');
      return;
    }
    if (mode === 'server') {
      await startServerCapture();
      return;
    }
    const recognition = recognitionRef.current;
    if (!recognition) {
      setSpeechNotice('Speech input unavailable; please type.');
      return;
    }
    setSpeechNotice('');
    markListenStart();
    recognition.start();
    if (speechRef.current?.queue.active) recognition.pause();
  }

  async function startServerCapture() {
    if (typeof MediaRecorder === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setSpeechNotice('Speech input unavailable; please type.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      if (unmounted.current) { stream.getTracks().forEach(track => track.stop()); return; }
      audioStreamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      chunks.current = [];
      recorder.ondataavailable = event => { if (event.data?.size) chunks.current.push(event.data); };
      recorder.onstop = () => { finishServerCapture(recorder); };
      mediaRecorderRef.current = recorder;
      recorder.start();
      markListenStart();
      setListenState('listening');
      setSpeechNotice('');
    } catch {
      setSpeechNotice('Speech input unavailable; please type.');
    }
  }

  async function finishServerCapture(recorder) {
    const parts = chunks.current.splice(0);
    audioStreamRef.current?.getTracks().forEach(track => track.stop());
    audioStreamRef.current = null;
    mediaRecorderRef.current = null;
    markListenStop();
    setListenState('idle');
    if (unmounted.current || discardServer.current || !parts.length) {
      discardServer.current = false;
      return;
    }
    setServerBusy(true);
    try {
      const type = recorder.mimeType || 'audio/webm';
      const blob = new Blob(parts, { type });
      const response = await transcribeAudio(blob, type.includes('wav') ? 'answer.wav' : 'answer.webm');
      const text = String(response?.text || '').trim();
      if (unmounted.current) return;
      if (!text) setSpeechNotice('No speech detected. You can type your answer.');
      else {
        dirty.current = true;
        setAnswer(prev => {
          const next = prev ? `${prev.trim()} ${text}` : text;
          committed.current = next;
          return next;
        });
      }
    } catch {
      if (!unmounted.current) setSpeechNotice('Speech input unavailable; please type.');
    } finally {
      if (!unmounted.current) setServerBusy(false);
    }
  }

  function doneAnswering() {
    markListenStop();
    recognitionRef.current?.stop();
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    else setListenState('idle');
  }

  function stopSpeech() {
    speechRef.current?.cancel();
    speakerRef.current?.cancel();
  }

  function submitAnswer(event) {
    event.preventDefault();
    if (locked || serverBusy || !answer.trim()) return;
    rememberReport();
    recognitionRef.current?.stop();
    releaseServerAudio(true);
    stopSpeech();
    controller.current.submit(answer);
  }

  const supported = view.active?.type === 'technical_short_answer';
  const locked = view.busy || view.needsRefresh || !draftReady;
  const voiceActive = listenState === 'listening' || listenState === 'paused';
  const currentRail = railKey(view.active?.stage || view.stage, view.phase);
  const question = view.active?.question || '';

  return <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-ink)]">
    <div className="app-container">
      <AppNav />
      <main className="mx-auto max-w-5xl px-4 py-8" data-testid="voice-interview">
        <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">Quick interview · voice</p>
            <h1 className="mt-2 text-3xl font-semibold">{view.phase === 'completed' ? 'Interview complete' : 'Live interview'}</h1>
          </div>
          <p className="text-sm text-[var(--color-ink-muted)]">{view.answeredCount} of {view.totalRounds} answers saved</p>
        </header>

        <ol className="mb-5 flex flex-wrap gap-2" data-testid="stage-rail">
          {RAIL.map(([key, label]) => <li key={key} aria-current={currentRail === key ? 'step' : undefined}
            className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wider ${currentRail === key ? 'border-[var(--color-ink)]' : 'border-[var(--color-border)] text-[var(--color-ink-muted)]'}`}>{label}</li>)}
        </ol>

        {view.error && <div role="alert" className="mb-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
          <p>{view.error}</p>
          <button type="button" className="app-button mt-3" disabled={view.busy} onClick={() => controller.current.refresh()}>Refresh interview</button>
          {view.phase === 'ready' && <button type="button" className="app-button mt-3" disabled={view.busy} onClick={() => { attempted.current = null; controller.current.advance(); }}>Continue interview</button>}
        </div>}

        <div className="grid gap-4 md:grid-cols-2">
          <section className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-4" data-testid="interviewer-tile" aria-label="Interviewer">
            <div className="flex items-center gap-3">
              <div className="flex h-14 w-14 items-center justify-center rounded-full border border-[var(--color-border)] text-sm font-semibold" aria-hidden="true">IV</div>
              <div>
                <p className="font-semibold">Interviewer</p>
                <p data-testid="speaking-indicator" className="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">{speaking ? 'Speaking' : 'Quiet'}</p>
              </div>
            </div>
            <p className="mt-4 min-h-16 text-base leading-7" data-testid="live-caption">{caption || question}</p>
            {question && caption && caption !== question && <h2 className="mt-2 text-lg font-medium leading-7">{question}</h2>}
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <button type="button" className="app-button" aria-pressed={muted} onClick={() => { const next = !mutedRef.current; mutedRef.current = next; setMuted(next); if (next) stopSpeech(); }}>
                {muted ? 'Unmute interviewer' : 'Mute interviewer'}
              </button>
              <button type="button" className="app-button" onClick={() => { if (lastLines.current.length) speechRef.current?.play(lastLines.current); }}>Replay</button>
              <label className="text-sm">
                <span className="sr-only">Interviewer voice</span>
                <select className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-2 py-2" value={voiceName}
                  onChange={event => { const name = event.target.value; voiceNameRef.current = name; setVoiceName(name); writeStoredVoiceName(name); }}>
                  <option value="">Automatic</option>
                  {voices.map(voice => <option key={voice.name} value={voice.name}>{voice.name}</option>)}
                </select>
              </label>
            </div>
          </section>

          <section className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-4" data-testid="camera-tile" aria-label="Your camera">
            <p className="text-sm font-semibold">You</p>
            <video ref={videoRef} data-testid="candidate-camera" autoPlay playsInline muted
              className="mt-3 h-52 w-full rounded-xl bg-black object-cover" style={{ transform: 'scaleX(-1)' }} />
            <p className="mt-3 text-xs leading-5 text-[var(--color-ink-muted)]">{cameraNote || 'Your camera stays in this browser. Nothing is recorded, and it is not part of your score.'}</p>
          </section>
        </div>

        {view.phase === 'completed' ? <section className="mt-5 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-6" data-testid="delivery-panel">
          <h2 className="text-xl font-semibold">Delivery feedback. Not part of your score.</h2>
          <p className="mt-2 text-sm text-[var(--color-ink-muted)]">These notes stay in this browser. They are not sent with your answers.</p>
          {reports.length ? <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wider text-[var(--color-ink-muted)]">
                  <th className="py-2 pr-3">Answer</th><th className="py-2 pr-3">Speaking</th><th className="py-2 pr-3">Words per minute</th><th className="py-2 pr-3">Filler words</th><th className="py-2 pr-3">Face visible</th><th className="py-2">More than one face</th>
                </tr>
              </thead>
              <tbody>
                {reports.map(item => <tr key={item.round} className="border-t border-[var(--color-border)]">
                  <td className="py-2 pr-3">{answerLabel(item)}</td>
                  <td className="py-2 pr-3">{formatSeconds(item.speakingMs)}</td>
                  <td className="py-2 pr-3">{item.wpm == null ? '—' : item.wpm}</td>
                  <td className="py-2 pr-3">{item.fillerWords}</td>
                  <td className="py-2 pr-3">{item.faceVisiblePercent == null ? '—' : `${item.faceVisiblePercent}%`}</td>
                  <td className="py-2">{item.multipleFaceSamples}</td>
                </tr>)}
              </tbody>
            </table>
          </div> : <p className="mt-4 text-sm">No delivery notes were captured for this sitting.</p>}
          <Link className="app-button app-button-primary mt-5" to={`/dashboard/${encodeURIComponent(view.sessionId)}`} onClick={stopSpeech}>View dashboard</Link>
        </section> : view.phase === 'blocked' ? <section className="mt-5 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-6" role="status">
          <h2 className="text-xl font-semibold">Answer saved; next question unavailable</h2>
          <p className="mt-3 text-sm leading-6">{view.blockedReason}</p>
          <button type="button" className="app-button mt-5" disabled={view.busy || view.needsRefresh} onClick={() => controller.current.retryBlocked()}>{view.busy ? 'Checking…' : 'Retry continuation'}</button>
        </section> : view.phase === 'ready' ? <p className="mt-5 text-sm" role="status">Opening the next question…</p>
        : view.phase === 'answering' && supported ? <form className="mt-5 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5" onSubmit={submitAnswer}>
          <label htmlFor="staged-answer" className="block text-sm font-semibold">Your answer</label>
          <textarea id="staged-answer" value={answer} disabled={locked} rows={8}
            onChange={event => { dirty.current = true; committed.current = event.target.value; setAnswer(event.target.value); }}
            className="mt-2 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] p-4 text-base leading-7 disabled:opacity-60" />
          <p className="mt-2 text-xs text-[var(--color-ink-muted)]" role="status">{draftNotice}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" className="app-button" disabled={locked || voiceActive || serverBusy || mode === 'type'} onClick={startAnswering}>Start answering</button>
            <button type="button" className="app-button" disabled={!voiceActive} onClick={doneAnswering}>Done</button>
            <button type="submit" className="app-button app-button-primary" disabled={locked || serverBusy || !answer.trim()}>{view.busy ? 'Saving answer…' : 'Submit answer'}</button>
          </div>
          {mode === 'browser' && <p className="mt-3 text-xs text-[var(--color-ink-muted)]">In Chrome, speech is processed by Google's speech service.</p>}
          {mode === 'type' && <p className="mt-3 text-xs" role="status">Speech input unavailable; please type.</p>}
          {serverBusy && <p className="mt-3 text-xs" role="status">Transcribing…</p>}
          {speechNotice && <p className="mt-3 text-xs" role="status">{speechNotice}</p>}
        </form> : <section className="mt-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
          <h2 className="text-xl font-semibold">This round is unavailable on this screen</h2>
          <p className="mt-3 text-sm">Your progress is saved. You can refresh this interview or return to practice.</p>
          <button type="button" className="app-button mt-5" disabled={view.busy} onClick={() => controller.current.refresh()}>Refresh interview</button>
        </section>}
        <Link className="mt-6 inline-block text-sm underline" to="/practice" onClick={stopSpeech}>Back to practice</Link>
      </main>
    </div>
  </div>;
}
