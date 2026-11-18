import React, { lazy, Suspense, useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { loadInterviewState, submitAnswer as apiSubmitAnswer, buildAnswerMetrics, clearInterviewState, transcribeAudio, saveInterviewState, fetchSession, saveAnswerDraft, fetchAnswerDraft, fetchAvCapabilities, continueSession, fetchRoundFeedback, requestFollowUp, activateRound } from '../lib/api';
import {
  MAX_NARRATION_POLLS,
  PHASES,
  TECHNICAL_ADVISORY_SECONDS,
  canRequestManualFollowUp,
  followUpOutcomeFromPayload,
  followUpOutcomeLabel,
  inputsLocked,
  isShowingResult,
  pendingRoundFromResponse,
  pendingRoundFromSession,
  phaseAfterSubmit,
  progressPercent,
  roundFieldsFromPayload,
  shouldPollNarration,
  technicalSecondsRemaining,
} from '../lib/interviewLifecycle';
import {
  applyFeedbackPollResult,
  clearFeedbackPollInterval,
  isFeedbackPollTickCurrent,
  shouldKeepPollingNarration,
} from '../lib/feedbackPoll';
import { blockedResumeFromSession } from '../lib/blockedResume';
import { classifyFrame, loadModels, modeOfLabels } from '../lib/engagement';
import { blockUsesInterviewMedia, stopMediaStream, mediaErrorMessage } from '../lib/interviewMedia';
import MCQRound from '../components/MCQRound';
import SQLRound from '../components/SQLRound';
import CodingRound from '../components/CodingRound';
import MLPrimitivesRound from '../components/MLPrimitivesRound';
import SystemDesignRound from '../components/SystemDesignRound';
import AvUnavailablePanel from '../components/AvUnavailablePanel';
import { AV_STATES, classifyMediaError, transcriptionFailureResult } from '../lib/avStates';
import StarComposer from '../components/StarComposer';
import { readDevicePreference, writeDevicePreference } from '../lib/accountStorage';
import { createSpeaker } from '../lib/speech/tts';
import { createRecognitionController, deliverySignals, recognitionClass } from '../lib/speech/stt';

const VivStage = lazy(() => import('../components/VivStage'));
const DEADLINE_TRANSCRIPTION_NOTICE =
  'Time expired. Your answer was submitted with the text captured so far. Transcription after the deadline does not extend assessment time.';

export default function Interview({ sessionState = null }) {
  const { sessionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const videoRef = useRef(null);
  const cameraStreamRef = useRef(null);
  const attachVideoEl = useCallback((node) => {
    videoRef.current = node;
    const stream = cameraStreamRef.current;
    if (node && stream && node.srcObject !== stream) {
      node.srcObject = stream;
      node.play?.().catch(() => {});
    }
  }, []);
  const recognitionRef = useRef(null);
  const micStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const mediaChunksRef = useRef([]);
  const discardServerRecordingRef = useRef(false);
  const engagementSamplesRef = useRef([]);
  const engagementBusyRef = useRef(false);
  const lastEngagementSampleAtRef = useRef(0);
  const engagementReadyRef = useRef(false);

  const hasBrowserSTT = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);

  const initState = sessionState || location.state || loadInterviewState() || {};
  const candidateId = initState.candidateId || '';

  const SUPPORTED_ROUND_TYPES = ['technical_short_answer', 'mcq', 'sql', 'coding', 'system_design', 'ml_primitives'];
  const isSupportedRoundType = (t) => SUPPORTED_ROUND_TYPES.includes(t);

  const [question, setQuestion] = useState(initState.question || '');
  const [roundType, setRoundType] = useState(initState.round_type || 'technical_short_answer');
  const [blockCategory, setBlockCategory] = useState(
    initState.block_category || initState.blockCategory || null
  );
  const usesInterviewMedia = blockUsesInterviewMedia(blockCategory, roundType);
  const [difficulty, setDifficulty] = useState(initState.difficulty || 'medium');
  const [questionContext, setQuestionContext] = useState(initState.question_context || {});
  const [configJson, setConfigJson] = useState(initState.config_json || {});
  const [expiresAt, setExpiresAt] = useState(initState.expires_at || null);
  const [startedAt, setStartedAt] = useState(initState.started_at || null);
  // Explicit lifecycle (see lib/interviewLifecycle.js): the submitted round
  // stays on screen until "Next Question" opens the prepared next round.
  const [phase, setPhase] = useState(
    initState.phase
      || ((initState.progressionBlocked || initState.status === 'content_blocked')
        ? PHASES.BLOCKED
        : PHASES.ANSWERING)
  );
  const [pendingRound, setPendingRound] = useState(initState.pendingRound || null);
  const [actionError, setActionError] = useState('');
  // Opt-in read-aloud of questions and feedback; recognition pauses meanwhile.
  const [readAloud, setReadAloud] = useState(false);
  const [showViv, setShowViv] = useState(false);
  const [vivAppearance, setVivAppearance] = useState(() => {
    const saved = readDevicePreference('viv-appearance');
    return ['fern', 'ocean', 'plum'].includes(saved) ? saved : 'fern';
  });
  const [vivSpeaking, setVivSpeaking] = useState(false);
  const speakerRef = useRef(null);
  if (speakerRef.current === null && typeof window !== 'undefined') {
    speakerRef.current = createSpeaker({
      win: window,
      onStart: () => { setVivSpeaking(true); recognitionRef.current?.pause?.(); },
      onEnd: () => { setVivSpeaking(false); recognitionRef.current?.resume?.(); },
    });
  }
  const spokenKeyRef = useRef('');
  const showingResult = isShowingResult(phase);
  const locked = inputsLocked(phase);
  const [currentArtifact, setCurrentArtifact] = useState(initState.currentArtifact || null);
  const [evaluationMode, setEvaluationMode] = useState(initState.evaluationMode || null);
  const [evaluationBoundary, setEvaluationBoundary] = useState(null);
  const [avState, setAvState] = useState(AV_STATES.PERMISSION_NOT_REQUESTED);
  const [avDetail, setAvDetail] = useState('');
  const [transcriptionAvailable, setTranscriptionAvailable] = useState(null);
  const [currentSkill, setCurrentSkill] = useState(initState.skill || '');
  const [allSkills] = useState(initState.allSkills || [initState.skill || 'General']);
  const [round, setRound] = useState(initState.round || 1);
  const [totalRounds, setTotalRounds] = useState(initState.totalRounds || 5);
  const [elo, setElo] = useState(initState.elo || 1200);

  const [nowMs, setNowMs] = useState(() => Date.now());
  // Untimed legacy rounds with no server activation time: local advisory budget.
  const [localDeadlineMs, setLocalDeadlineMs] = useState(() => Date.now() + TECHNICAL_ADVISORY_SECONDS * 1000);
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState(initState.answerText || '');
  const [draftNotice, setDraftNotice] = useState('');
  const draftTimerRef = useRef(null);
  const draftLoadedForRef = useRef('');
  const [interimText, setInterimText] = useState('');
  const [isScoring, setIsScoring] = useState(false);
  // Camera is optional and starts off; engagement stays unmeasured unless enabled.
  const [isVideoOn, setIsVideoOn] = useState(false);
  const [sessionComplete, setSessionComplete] = useState(initState.phase === PHASES.COMPLETED);
  const [cameraError, setCameraError] = useState('');
  const [micError, setMicError] = useState('');

  const restoredResult = isShowingResult(initState.phase)
    || Boolean(initState.progressionBlocked || initState.status === 'content_blocked');
  const [currentScore, setCurrentScore] = useState(
    restoredResult ? (initState.currentScore ?? null) : null
  );
  const [currentFeedback, setCurrentFeedback] = useState(
    restoredResult ? (initState.currentFeedback || '') : ''
  );
  const [feedbackSourceLabel, setFeedbackSourceLabel] = useState('');
  const [feedbackDetails, setFeedbackDetails] = useState(null);
  const [progressionBlocked, setProgressionBlocked] = useState(
    Boolean(initState.progressionBlocked || initState.status === 'content_blocked')
  );
  const [progressionBlockedReason, setProgressionBlockedReason] = useState(
    initState.progressionBlockedReason || initState.progression_blocked_reason || ''
  );
  const [continueBusy, setContinueBusy] = useState(false);
  const [eligibilityLabel, setEligibilityLabel] = useState('');
  const [followUpBusy, setFollowUpBusy] = useState(false);
  const [followUpNote, setFollowUpNote] = useState('');
  const [isFollowUp, setIsFollowUp] = useState(
    Boolean(initState.isFollowUp || initState.is_follow_up || initState.config_json?.is_follow_up)
  );
  const [followUpParentRound, setFollowUpParentRound] = useState(
    initState.followUpParentRound
    ?? initState.follow_up_parent_round
    ?? initState.config_json?.follow_up_parent_round
    ?? null
  );
  const [followUpScheduledForRound, setFollowUpScheduledForRound] = useState(
    Boolean(initState.followUpScheduled)
  );
  const [followUpOutcome, setFollowUpOutcome] = useState(
    restoredResult
      ? (initState.followUpOutcome || followUpOutcomeFromPayload({ config_json: initState.config_json }) || null)
      : null
  );
  const feedbackPollRef = useRef(null);
  const feedbackRoundRef = useRef(null);
  const [currentRubric, setCurrentRubric] = useState(restoredResult ? (initState.currentRubric || null) : null);
  const [currentConcepts, setCurrentConcepts] = useState(restoredResult ? (initState.currentConcepts || null) : null);

  const [useServerSTT, setUseServerSTT] = useState(!hasBrowserSTT);
  const [serverRecording, setServerRecording] = useState(false);
  const [serverTranscribing, setServerTranscribing] = useState(false);
  const [engagementReady, setEngagementReady] = useState(false);
  const [engagementLoadFailed, setEngagementLoadFailed] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraCollapsed, setCameraCollapsed] = useState(false);
  const [deadlineNotice, setDeadlineNotice] = useState('');

  const stopCamera = useCallback(() => {
    stopMediaStream(cameraStreamRef.current);
    cameraStreamRef.current = null;
    setCameraReady(false);
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const stopMicrophone = useCallback(() => {
    stopMediaStream(micStreamRef.current);
    micStreamRef.current = null;
  }, []);

  // Speaking-time accounting for the advisory WPM indicator.
  const recordedMsRef = useRef(0);
  const recordingSinceRef = useRef(null);
  const stopRecording = useCallback(() => {
    recognitionRef.current?.stop?.();
    if (recordingSinceRef.current != null) {
      recordedMsRef.current += Date.now() - recordingSinceRef.current;
      recordingSinceRef.current = null;
    }
    stopMicrophone();
    setIsRecording(false);
    setInterimText('');
  }, [stopMicrophone]);

  const stopServerRecording = useCallback((discard = false) => {
    discardServerRecordingRef.current = discard;
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      try { recorder.stop(); }
      catch { /* recorder was already stopped */ }
    }
  }, []);

  const clearEngagementSamples = useCallback(() => {
    engagementSamplesRef.current = [];
    lastEngagementSampleAtRef.current = 0;
  }, []);

  const ensureMicrophone = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setAvState(AV_STATES.UNSUPPORTED_BROWSER);
      setAvDetail('getUserMedia is not available in this browser.');
      throw Object.assign(new Error('media-devices-unavailable'), {
        name: 'NotSupportedError',
      });
    }
    if (micStreamRef.current?.active) {
      setAvState(AV_STATES.READY);
      return micStreamRef.current;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });
      micStreamRef.current = stream;
      stream.getAudioTracks().forEach(track => {
        track.addEventListener('ended', () => {
          setMicError('Microphone disconnected.');
          setAvState(AV_STATES.INTERRUPTED_RECOVERABLE);
          setAvDetail('Microphone track ended mid-session. Retry capture when ready.');
          setIsRecording(false);
        });
      });
      setAvState(AV_STATES.READY);
      setAvDetail('');
      setMicError('');
      return stream;
    } catch (err) {
      const state = classifyMediaError(err, {
        secureContext: Boolean(window.isSecureContext
          || ['localhost', '127.0.0.1'].includes(window.location.hostname)),
      });
      setAvState(state);
      setAvDetail(mediaErrorMessage(err, 'Microphone'));
      setMicError(mediaErrorMessage(err, 'Microphone'));
      throw err;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchAvCapabilities()
      .then((report) => {
        if (cancelled) return;
        const available = Boolean(report?.transcription?.available);
        setTranscriptionAvailable(available);
      })
      .catch(() => {
        if (cancelled) return;
        setTranscriptionAvailable(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => () => {
    feedbackPollRef.current = clearFeedbackPollInterval(feedbackPollRef.current);
    feedbackRoundRef.current = null;
  }, []);

  useEffect(() => {
    if (!usesInterviewMedia) {
      engagementReadyRef.current = false;
      setEngagementReady(false);
      setEngagementLoadFailed(false);
      return undefined;
    }
    let cancelled = false;

    loadModels().then((ok) => {
      if (cancelled) return;
      engagementReadyRef.current = ok;
      setEngagementReady(ok);
      setEngagementLoadFailed(!ok);
    });

    return () => {
      cancelled = true;
    };
  }, [usesInterviewMedia]);

  // Browser speech recognition: restarts after normal pauses while the
  // candidate keeps recording; stops on permission errors, submit, exit or
  // repeated failures. It owns the microphone (no competing getUserMedia).
  useEffect(() => {
    const Recognition = recognitionClass(window);
    if (!usesInterviewMedia || !Recognition) {
      recognitionRef.current = null;
      if (usesInterviewMedia && !Recognition) {
        setUseServerSTT(true);
        setMicError('');
      }
      return undefined;
    }
    const controller = createRecognitionController({
      Recognition,
      onResult: (finalText, interim) => {
        if (finalText) { setTranscript((prev) => prev + finalText); setInterimText(''); }
        else setInterimText(interim);
      },
      onState: (state, detail) => {
        if (state === 'listening') {
          setMicError('');
          setIsRecording(true);
          if (recordingSinceRef.current == null) recordingSinceRef.current = Date.now();
        } else if (state === 'idle' || state === 'error') {
          if (recordingSinceRef.current != null) {
            recordedMsRef.current += Date.now() - recordingSinceRef.current;
            recordingSinceRef.current = null;
          }
          setIsRecording(false);
          setInterimText('');
          if (state === 'error') {
            const name = detail === 'not-allowed' || detail === 'service-not-allowed' ? 'NotAllowedError' : detail;
            if (name === 'NotAllowedError') setAvState(AV_STATES.PERMISSION_DENIED);
            setMicError(detail === 'repeated'
              ? 'Speech recognition kept failing. You can type your answer or switch to server transcription.'
              : mediaErrorMessage({ name }, 'Microphone'));
          }
        }
      },
    });
    recognitionRef.current = controller;
    return () => {
      controller.abort();
      recognitionRef.current = null;
    };
  }, [usesInterviewMedia]);

  useEffect(() => {
    let cancelled = false;

    async function startCamera() {
      if (!usesInterviewMedia || !isVideoOn) {
        stopCamera();
        setCameraReady(false);
        return;
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        setCameraError(mediaErrorMessage(null, 'Camera'));
        setCameraReady(false);
        setIsVideoOn(false);
        return;
      }

      try {
        setCameraError('');
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'user',
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
          audio: false,
        });
        if (cancelled) {
          stopMediaStream(stream);
          return;
        }
        stopCamera();
        cameraStreamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play?.().catch(() => {});
        }
        setCameraReady(true);
        stream.getVideoTracks().forEach(track => {
          track.addEventListener('ended', () => {
            setCameraError('Camera disconnected.');
            setCameraReady(false);
            setIsVideoOn(false);
          });
        });
      } catch (err) {
        if (cancelled) return;
        setCameraError(mediaErrorMessage(err, 'Camera'));
        setCameraReady(false);
        setIsVideoOn(false);
      }
    }

    startCamera();
    return () => { cancelled = true; };
  }, [isVideoOn, stopCamera, usesInterviewMedia]);

  useEffect(() => {
    if (!isVideoOn) {
      clearEngagementSamples();
    }
  }, [clearEngagementSamples, isVideoOn]);

  useEffect(() => {
    clearEngagementSamples();
  }, [clearEngagementSamples, round]);

  // Phase B: recover owned free-text drafts once per session/round.
  useEffect(() => {
    if (roundType !== 'technical_short_answer') return undefined;
    const key = `${sessionId}:${round}`;
    if (!sessionId || locked || draftLoadedForRef.current === key) return undefined;
    draftLoadedForRef.current = key;
    setDraftNotice('');
    let cancelled = false;
    fetchAnswerDraft(sessionId, round)
      .then((data) => {
        if (cancelled) return;
        const saved = String(data?.draft?.answer_text || '').trim();
        if (saved) {
          setTranscript(saved);
          setDraftNotice('Restored your saved draft.');
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [sessionId, round, roundType, locked]);

  // Phase B: autosave free-text drafts (debounced).
  useEffect(() => {
    if (roundType !== 'technical_short_answer') return undefined;
    if (!sessionId || locked || !transcript.trim()) return undefined;
    if (draftTimerRef.current) clearTimeout(draftTimerRef.current);
    draftTimerRef.current = setTimeout(() => {
      saveAnswerDraft(sessionId, { round, answer_text: transcript }).catch(() => {});
    }, 1500);
    return () => {
      if (draftTimerRef.current) clearTimeout(draftTimerRef.current);
    };
  }, [transcript, sessionId, round, roundType, locked]);

  useEffect(() => {
    const node = videoRef.current;
    const stream = cameraStreamRef.current;
    if (node && stream && node.srcObject !== stream) {
      node.srcObject = stream;
      node.play?.().catch(() => {});
    }
  }, [isVideoOn, cameraCollapsed]);

  useEffect(() => {
    const shouldClassify =
      usesInterviewMedia &&
      isVideoOn &&
      engagementReady &&
      !locked &&
      (isRecording || serverRecording || transcript.trim().length > 0);

    if (!shouldClassify) return undefined;

    let cancelled = false;

    const sampleFrame = async () => {
      if (engagementBusyRef.current) return;
      engagementBusyRef.current = true;
      try {
        const sample = await classifyFrame(videoRef.current);
        if (cancelled) return;
        if (sample) {
          const now = Date.now();
          if (now - lastEngagementSampleAtRef.current >= 2000) {
            engagementSamplesRef.current.push(sample);
            lastEngagementSampleAtRef.current = now;
          }
        }
      } finally {
        engagementBusyRef.current = false;
      }
    };

    sampleFrame();
    const id = setInterval(sampleFrame, 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [engagementReady, isRecording, isVideoOn, locked, serverRecording, transcript, usesInterviewMedia]);

  useEffect(() => {
    return () => {
      speakerRef.current?.cancel();
      stopServerRecording(true);
      stopCamera();
      stopMicrophone();
    };
  }, [stopCamera, stopMicrophone, stopServerRecording]);

  // Read the question aloud when a round opens, and the feedback summary
  // when its result arrives; once each, only when the candidate opted in.
  useEffect(() => {
    if (!readAloud || roundType !== 'technical_short_answer') return;
    const speaker = speakerRef.current;
    if (!speaker?.supported) return;
    if (phase === PHASES.ANSWERING && question) {
      const key = `q:${round}:${question}`;
      if (spokenKeyRef.current !== key) { spokenKeyRef.current = key; speaker.speak(question); }
    } else if (showingResult && currentFeedback) {
      const key = `f:${round}`;
      if (spokenKeyRef.current !== key) { spokenKeyRef.current = key; speaker.speak(currentFeedback); }
    }
  }, [readAloud, phase, question, round, roundType, showingResult, currentFeedback]);

  useEffect(() => {
    if (!sessionId || sessionComplete) return;
    // Persist blocked resume hints even while the score card is visible.
    if (currentScore !== null && !progressionBlocked) return;
    saveInterviewState({
      candidateId,
      skill: currentSkill || allSkills[0] || 'General',
      allSkills,
      sessionId,
      question,
      difficulty,
      round,
      round_type: roundType,
      block_category: blockCategory,
      question_context: questionContext,
      config_json: configJson,
      expires_at: expiresAt,
      elo,
      totalRounds,
      isFollowUp,
      followUpParentRound,
      followUpScheduled: followUpScheduledForRound,
      followUpOutcome,
      progressionBlocked,
      progressionBlockedReason,
      status: progressionBlocked ? 'content_blocked' : undefined,
      currentScore: progressionBlocked ? currentScore : undefined,
      currentFeedback: progressionBlocked ? currentFeedback : undefined,
    });
  }, [
    allSkills,
    blockCategory,
    candidateId,
    configJson,
    currentFeedback,
    currentScore,
    currentSkill,
    difficulty,
    elo,
    expiresAt,
    followUpOutcome,
    followUpParentRound,
    followUpScheduledForRound,
    isFollowUp,
    progressionBlocked,
    progressionBlockedReason,
    question,
    questionContext,
    round,
    roundType,
    sessionComplete,
    sessionId,
    totalRounds,
  ]);

  useEffect(() => {
    if (!sessionId) return undefined;
    let cancelled = false;
    fetchSession(sessionId)
      .then((data) => {
        if (cancelled || !data) return;
        const cr = data.active_round || data.current_round;
        if (cr?.block_category) setBlockCategory(cr.block_category);
        const resume = blockedResumeFromSession(data);
        if (resume.progressionBlocked) {
          setProgressionBlocked(true);
          setProgressionBlockedReason(resume.progressionBlockedReason || '');
          if (resume.currentScore != null) setCurrentScore(resume.currentScore);
          if (resume.currentFeedback) {
            setCurrentFeedback(resume.currentFeedback);
            setFeedbackSourceLabel('Rules feedback');
          }
          if (resume.round != null) setRound(resume.round);
        } else if (data.status === 'active' && cr?.status === 'in_progress') {
          setProgressionBlocked(false);
          setProgressionBlockedReason('');
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || phase !== PHASES.ANSWERING) return;
    if (
      (roundType === 'mcq' || roundType === 'sql' || roundType === 'coding' || roundType === 'ml_primitives') &&
      (!questionContext || Object.keys(questionContext).length === 0)
    ) {
      fetchSession(sessionId)
        .then((data) => {
          const cr = data?.active_round || data?.current_round;
          if (cr) {
            if (cr.round_type) setRoundType(cr.round_type);
            if (cr.block_category !== undefined) setBlockCategory(cr.block_category || null);
            if (cr.question) setQuestion(cr.question);
            if (cr.difficulty) setDifficulty(cr.difficulty);
            if (cr.question_context) setQuestionContext(cr.question_context);
            if (cr.config_json) setConfigJson(cr.config_json);
            if (cr.expires_at) setExpiresAt(cr.expires_at);
            if (cr.round) setRound(cr.round);
            if (cr.final_score !== undefined && cr.final_score !== null) {
              setCurrentScore(cr.final_score);
            }
            if (cr.artifact_json) {
              setCurrentArtifact(cr.artifact_json);
            }
            if (cr.feedback) {
              const fb = typeof cr.feedback === 'string' ? cr.feedback : cr.feedback?.content?.[0] || '';
              setCurrentFeedback(fb);
            }
          }
        })
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, roundType]);

  const toggleRecording = useCallback(async () => {
    if (isRecording) {
      stopRecording();
      return;
    }

    if (!recognitionRef.current) {
      setMicError('Speech recognition is not supported in this browser.');
      return;
    }
    setMicError('');
    // The recognizer asks for the microphone itself.
    recognitionRef.current.start();
  }, [isRecording, stopRecording]);

  const toggleServerRecording = useCallback(async () => {
    if (serverRecording) {
      stopServerRecording(false);
      return;
    }

    if (!window.MediaRecorder) {
      setAvState(AV_STATES.UNSUPPORTED_BROWSER);
      setAvDetail('MediaRecorder is not supported.');
      setMicError('Transcription unavailable, please type your answer');
      return;
    }
    if (transcriptionAvailable === false) {
      setAvState(AV_STATES.SERVICE_UNAVAILABLE);
      setAvDetail('Server transcription is unavailable. Type your answer.');
      setMicError('Transcription unavailable, please type your answer');
      return;
    }

    try {
      setMicError('');
      setServerTranscribing(false);
      discardServerRecordingRef.current = false;
      const stream = await ensureMicrophone();
      mediaChunksRef.current = [];

      const preferredType = 'audio/webm;codecs=opus';
      const fallbackType = 'audio/webm';
      const mimeType = window.MediaRecorder.isTypeSupported?.(preferredType)
        ? preferredType
        : window.MediaRecorder.isTypeSupported?.(fallbackType)
          ? fallbackType
          : '';
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);

      recorder.ondataavailable = (event) => {
        if (event.data?.size) mediaChunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        setServerRecording(false);
        setServerTranscribing(false);
        setMicError('Transcription unavailable, please type your answer');
        stopMicrophone();
      };
      recorder.onstop = async () => {
        const chunks = mediaChunksRef.current;
        const shouldDiscard = discardServerRecordingRef.current;
        discardServerRecordingRef.current = false;
        mediaChunksRef.current = [];
        mediaRecorderRef.current = null;
        stopMicrophone();
        setServerRecording(false);

        if (shouldDiscard || !chunks.length) {
          setServerTranscribing(false);
          return;
        }

        setServerTranscribing(true);
        try {
          const type = recorder.mimeType || 'audio/webm';
          const blob = new Blob(chunks, { type });
          const filename = type.includes('wav') ? 'answer.wav' : 'answer.webm';
          const resp = await transcribeAudio(blob, filename);
          const text = (resp.text || '').trim();
          if (text) {
            setTranscript(prev => prev ? `${prev.trimEnd()} ${text}` : text);
            setAvState(AV_STATES.READY);
          } else {
            // Empty result is not a fabricated transcript; candidate types.
            setMicError('No speech detected. You can type your answer.');
            setAvState(AV_STATES.CAPTURE_FAILED);
            setAvDetail('No speech detected in the recording.');
          }
        } catch (err) {
          const failure = transcriptionFailureResult(err?.status || 503);
          setAvState(failure.state);
          setAvDetail('Transcription unavailable. No transcript or speech score recorded.');
          setMicError('Transcription unavailable, please type your answer');
        } finally {
          setServerTranscribing(false);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setServerRecording(true);
    } catch (err) {
      setMicError(mediaErrorMessage(err, 'Microphone'));
      stopMicrophone();
      setServerRecording(false);
      setServerTranscribing(false);
    }
  }, [ensureMicrophone, serverRecording, stopMicrophone, stopServerRecording]);

  const submitAnswer = async (options = {}) => {
    // Fail loudly: an unrenderable round type must never be scored, not even
    // on the timer force-submit path.
    if (!isSupportedRoundType(roundType)) {
      setCurrentFeedback(`Unsupported round type "${roundType}" — answer not submitted.`);
      return;
    }
    const force = Boolean(options.force);
    const isMcq = roundType === 'mcq';
    const isSystemDesign = roundType === 'system_design';
    const suppliedAnswer = options.answer_text ?? options.answerText ?? transcript;
    const answerText = roundType === 'coding' ? suppliedAnswer : suppliedAnswer.trim();
    const answers = options.answers;
    const rubricRatings = options.rubric_ratings;
    if (!isMcq && (!answerText && !force) || isScoring || phase !== PHASES.ANSWERING) return;
    if (force) {
      // Discard in-flight STT — deadline is authoritative; do not wait/extend.
      if (serverRecording || serverTranscribing) stopServerRecording(true);
      if (isRecording) stopRecording();
      setDeadlineNotice(DEADLINE_TRANSCRIPTION_NOTICE);
    } else {
      setDeadlineNotice('');
      if (isRecording) stopRecording();
      if (serverRecording) stopServerRecording(false);
    }
    speakerRef.current?.cancel();
    setIsScoring(true);
    setActionError('');
    setPhase(PHASES.SUBMITTING);
    try {
      const metrics = (!isMcq && !isSystemDesign) ? buildAnswerMetrics(answerText) : {};
      if (roundType === 'technical_short_answer') {
        // Delivery signals are stored with the attempt; they never change the score.
        const signals = deliverySignals(answerText, recordedMsRef.current);
        if (signals.wpm != null) metrics.wpm = signals.wpm;
        if (recognitionRef.current?.restartCount != null && recordedMsRef.current > 0) {
          metrics.pause_count = recognitionRef.current.restartCount;
        }
      }
      const engagement = isVideoOn ? modeOfLabels(engagementSamplesRef.current) : null;
      // No calibration baseline is captured, so the delta is unmeasured.
      const engagementDelta = null;
      const payload = {
        session_id: sessionId,
        round,
        engagement_label: engagement?.label ?? null,
        engagement_confidence: engagement?.confidence ?? null,
        engagement_delta: engagementDelta,
        ...metrics,
      };
      if (isMcq) {
        payload.answers = Array.isArray(answers) ? answers : [];
      } else {
        payload.answer_text = answerText;
      }
      if (isSystemDesign) {
        payload.rubric_ratings = rubricRatings || {};
      }
      if (roundType === 'coding' || roundType === 'ml_primitives') {
        if (roundType === 'coding') payload.language = options.language || configJson.language || 'python';
        delete payload.engagement_label;
        delete payload.engagement_confidence;
        delete payload.engagement_delta;
        delete payload.wpm;
        delete payload.pause_count;
      }
      const resp = await apiSubmitAnswer(payload);

      // Never invent a score when the API omits one.
      const outcome = followUpOutcomeFromPayload(resp);
      const isInlineFollowUpResp = Boolean(outcome);
      const score = isInlineFollowUpResp
        ? null
        : (typeof resp.final_score === 'number' ? resp.final_score : null);
      const feedbackRaw = isInlineFollowUpResp
        ? (resp.feedback?.content?.[0] || resp.feedback?.next_step || '')
        : (resp.feedback?.next_step || resp.feedback?.content?.[0] || resp.feedback || '');
      const feedback = typeof feedbackRaw === 'string' ? feedbackRaw : '';
      const rubric = isInlineFollowUpResp ? null : (resp.rubric || resp.scoring_breakdown?.rubric || null);
      const concepts = isInlineFollowUpResp ? null : (resp.concepts || resp.scoring_breakdown?.concepts || null);
      setFollowUpOutcome(outcome);
      setFollowUpScheduledForRound(Boolean(resp.follow_up_scheduled));
      setCurrentScore(score);
      const elig = resp.assessment_eligibility;
      if (elig === 'excluded' || resp.assisted) {
        setEligibilityLabel(
          resp.is_follow_up ? 'Follow-up · Practiced with help' : 'Practiced with help'
        );
      } else if (elig === 'eligible') {
        setEligibilityLabel('Assessment');
      } else if (elig === 'unknown' || elig === 'legacy_unknown') {
        setEligibilityLabel('Unscored practice');
      } else if (score === null) {
        setEligibilityLabel('Unscored practice');
      } else {
        setEligibilityLabel('');
      }
      let feedbackWithMode = feedback;
      if (resp.scoring_mode === 'lexical_fallback_degraded') {
        feedbackWithMode = (
          'Approximate score: the meaning-based scorer was unavailable, so this answer was '
          + 'scored by keyword matching only.'
          + (feedback ? `\n\n${feedback}` : '')
        );
      } else if (resp.scoring_mode === 'self_reported') {
        feedbackWithMode = (
          'Scoring mode: self-reported (not measured mastery).'
          + (feedback ? `\n\n${feedback}` : '')
        );
      }
      setCurrentFeedback(feedbackWithMode);
      setFeedbackSourceLabel('Rules feedback');
      setFeedbackDetails(null);
      setProgressionBlocked(Boolean(resp.progression_blocked));
      setProgressionBlockedReason(resp.progression_blocked_reason || '');
      setCurrentRubric(rubric && typeof rubric === 'object' ? rubric : null);
      setCurrentConcepts(concepts && typeof concepts === 'object' ? concepts : null);
      setCurrentArtifact(resp.artifact_json || resp);
      setEvaluationMode(resp.evaluation_mode || null);
      setEvaluationBoundary(resp.evaluation_boundary || null);
      setElo(resp.elo_after ?? elo);
      if (typeof resp.total_rounds === 'number' && resp.total_rounds > 0) {
        setTotalRounds(resp.total_rounds);
      }
      // The submitted question, component and feedback stay on screen; the
      // prepared next round opens only from "Next Question".
      setPendingRound(pendingRoundFromResponse(resp));
      setSessionComplete(Boolean(resp.session_complete));
      setPhase(phaseAfterSubmit(resp));

      // Poll narration only while the server reports a pending job.
      if (sessionId && shouldPollNarration(resp.narration_status)) {
        const pollRound = round;
        feedbackRoundRef.current = pollRound;
        feedbackPollRef.current = clearFeedbackPollInterval(feedbackPollRef.current);
        let pollState = {
          displayFeedback: feedbackWithMode,
          displaySource: 'Rules feedback',
          narrationStatus: resp.narration_status,
          polling: true,
        };
        let polls = 0;
        const tick = async () => {
          if (!isFeedbackPollTickCurrent(feedbackRoundRef.current, pollRound)) return;
          polls += 1;
          if (polls > MAX_NARRATION_POLLS) {
            feedbackPollRef.current = clearFeedbackPollInterval(feedbackPollRef.current);
            return;
          }
          try {
            const payload = await fetchRoundFeedback(sessionId, pollRound);
            pollState = applyFeedbackPollResult(pollState, payload, pollRound);
            if (pollState.ignoredStale) return;
            if (pollState.displayFeedback) setCurrentFeedback(pollState.displayFeedback);
            if (pollState.displaySource) setFeedbackSourceLabel(pollState.displaySource);
            setFeedbackDetails(pollState.narrationDetails || null);
            if (!shouldKeepPollingNarration(pollState.narrationStatus)) {
              feedbackPollRef.current = clearFeedbackPollInterval(feedbackPollRef.current);
            }
          } catch {
            /* keep rules feedback visible */
          }
        };
        tick();
        feedbackPollRef.current = setInterval(tick, 2500);
      }
    } catch (err) {
      // Nothing was recorded: reopen the answer for a retry.
      setPhase(PHASES.ANSWERING);
      setActionError(`Submission failed — ${err.message || 'please try again.'}`);
    } finally {
      setIsScoring(false);
    }
  };

  useEffect(() => {
    setLocalDeadlineMs(Date.now() + TECHNICAL_ADVISORY_SECONDS * 1000);
  }, [round]);

  useEffect(() => {
    if (phase !== PHASES.ANSWERING || roundType !== 'technical_short_answer') return undefined;
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [phase, roundType]);

  const serverSecondsLeft = technicalSecondsRemaining({ expiresAt, startedAt, nowMs });
  const timeLeft = serverSecondsLeft ?? Math.max(0, Math.ceil((localDeadlineMs - nowMs) / 1000));
  // Auto-submit only when the clock runs out while the candidate is here;
  // returning to an already-elapsed round must not submit an empty answer.
  const sawTimeLeftRef = useRef(false);
  useEffect(() => { sawTimeLeftRef.current = false; }, [round]);
  if (timeLeft > 0) sawTimeLeftRef.current = true;

  useEffect(() => {
    if (timeLeft > 0 || phase !== PHASES.ANSWERING || isScoring || roundType !== 'technical_short_answer') {
      return;
    }
    if (!sawTimeLeftRef.current) return;
    submitAnswer({ force: true });
  }, [isScoring, phase, roundType, submitAnswer, timeLeft]);

  const stopRoundActivity = () => {
    speakerRef.current?.cancel();
    feedbackPollRef.current = clearFeedbackPollInterval(feedbackPollRef.current);
    feedbackRoundRef.current = null;
    stopRecording();
    stopServerRecording(true);
  };

  // Save & Exit: the server keeps the session; a running deadline keeps
  // running (saving never pauses assessment time).
  const saveAndExit = async () => {
    if (draftTimerRef.current) clearTimeout(draftTimerRef.current);
    if (roundType === 'technical_short_answer' && phase === PHASES.ANSWERING && transcript.trim()) {
      try { await saveAnswerDraft(sessionId, { round, answer_text: transcript }); }
      catch { /* best effort; the server keeps the last autosave */ }
    }
    stopRoundActivity();
    stopCamera();
    stopMicrophone();
    navigate('/home');
  };

  const resetRoundUi = () => {
    stopRoundActivity();
    setTranscript(''); setInterimText(''); setDraftNotice('');
    setCurrentScore(null); setCurrentFeedback('');
    setFeedbackSourceLabel(''); setFeedbackDetails(null);
    setProgressionBlocked(false); setProgressionBlockedReason('');
    setDeadlineNotice('');
    setCurrentRubric(null); setCurrentConcepts(null);
    setCurrentArtifact(null);
    setEvaluationMode(null); setEvaluationBoundary(null);
    setEligibilityLabel('');
    setFollowUpNote(''); setFollowUpBusy(false);
    setIsFollowUp(false); setFollowUpParentRound(null);
    setFollowUpScheduledForRound(false); setFollowUpOutcome(null);
    setActionError('');
    recordedMsRef.current = 0;
    recordingSinceRef.current = null;
    clearEngagementSamples();
  };

  const applyOpenedRound = (fields) => {
    setQuestion(fields.question);
    setRoundType(fields.roundType);
    setBlockCategory(fields.blockCategory);
    setDifficulty(fields.difficulty);
    if (fields.skill) setCurrentSkill(fields.skill);
    setQuestionContext(fields.questionContext);
    setConfigJson(fields.configJson);
    setExpiresAt(fields.expiresAt);
    setStartedAt(fields.startedAt);
    setRound(fields.round);
    setIsFollowUp(Boolean(fields.isFollowUp));
    setFollowUpParentRound(fields.followUpParentRound ?? null);
    setFollowUpScheduledForRound(false);
    setFollowUpOutcome(null);
    setNowMs(Date.now());
  };

  const handleNext = async () => {
    if (phase === PHASES.COMPLETED || sessionComplete) {
      clearInterviewState();
      navigate(`/dashboard/${sessionId}`);
      return;
    }
    if (phase !== PHASES.REVIEWING) return; // ignores repeat clicks while opening
    setPhase(PHASES.ACTIVATING);
    setActionError('');
    try {
      let target = pendingRound;
      if (!target) {
        const fresh = await fetchSession(sessionId);
        target = pendingRoundFromSession(fresh.pending_round);
        if (!target && fresh.active_round?.status === 'in_progress') {
          resetRoundUi();
          applyOpenedRound(roundFieldsFromPayload(fresh.active_round, { skill: currentSkill }));
          setPhase(PHASES.ANSWERING);
          return;
        }
        if (!target) throw new Error('The next question is not ready yet.');
      }
      const resp = await activateRound(sessionId, target.round);
      const fields = roundFieldsFromPayload(resp.active_round, { skill: target.skill || currentSkill });
      if (typeof resp.total_rounds === 'number' && resp.total_rounds > 0) setTotalRounds(resp.total_rounds);
      resetRoundUi();
      applyOpenedRound(fields);
      setPendingRound(null);
      setPhase(PHASES.ANSWERING);
    } catch (err) {
      setActionError(err.message || 'Could not open the next question. Try again.');
      setPhase(PHASES.REVIEWING);
    }
  };

  const handleContinueBlocked = async () => {
    if (!sessionId || continueBusy) return;
    setContinueBusy(true);
    try {
      const resp = await continueSession(sessionId);
      if (!resp.continued) {
        setProgressionBlocked(true);
        setProgressionBlockedReason(
          resp.progression_blocked_reason || progressionBlockedReason || 'Content still unavailable.'
        );
        return;
      }
      const fields = roundFieldsFromPayload(resp.active_round || {
        round: resp.round,
        question: resp.question,
        round_type: resp.round_type,
        block_category: resp.block_category,
        difficulty: resp.difficulty,
        skill: resp.current_skill,
        question_context: resp.question_context,
        config_json: resp.config_json,
        expires_at: resp.expires_at,
      }, { skill: resp.current_skill || currentSkill });
      if (typeof resp.total_rounds === 'number' && resp.total_rounds > 0) setTotalRounds(resp.total_rounds);
      resetRoundUi();
      applyOpenedRound(fields);
      setPendingRound(null);
      setSessionComplete(false);
      setPhase(PHASES.ANSWERING);
    } catch (err) {
      setProgressionBlockedReason(err.message || 'Could not continue session.');
    } finally {
      setContinueBusy(false);
    }
  };

  // Clears the draft being written; never touches a submitted result.
  const resetAnswer = () => {
    if (locked) return;
    if (isRecording) stopRecording();
    if (serverRecording) stopServerRecording(true);
    setTranscript(''); setInterimText('');
    setDraftNotice('');
    setIsRecording(false);
    clearEngagementSamples();
  };

  const fmt = (s) => `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;
  const scoreColor = (score) => score >= 75 ? '#16A34A' : score >= 50 ? '#D97706' : '#DC2626';
  const progress = progressPercent({ round, totalRounds, phase });
  const delivery = deliverySignals(
    transcript,
    recordedMsRef.current + (recordingSinceRef.current != null ? nowMs - recordingSinceRef.current : 0),
  );
  const answerWordCount = delivery.words;
  const serverSttActive = useServerSTT || !hasBrowserSTT;
  const canSubmit = transcript.trim().length > 0 && !isScoring && phase === PHASES.ANSWERING && !serverRecording && !serverTranscribing && isSupportedRoundType(roundType);
  const voiceButtonBusy = serverSttActive ? (serverRecording || serverTranscribing) : isRecording;
  const voiceButtonDisabled = isScoring || locked || serverTranscribing;
  const nextLabel = phase === PHASES.COMPLETED || sessionComplete
    ? 'View report →'
    : phase === PHASES.BLOCKED
      ? (continueBusy ? 'Checking…' : 'Retry next question')
      : phase === PHASES.ACTIVATING
        ? 'Opening…'
        : 'Next Question →';
  const voiceStatus = serverTranscribing
    ? 'Transcribing'
    : serverRecording
      ? 'Recording Server'
      : isRecording
        ? 'Recording'
        : micError
          ? 'Mic Check'
          : 'Standby';
  // Typed round components share one contract: their result stays visible
  // after submission (scored or not) until Next opens the next round.
  const roundProps = {
    sessionId,
    round,
    question,
    questionContext,
    configJson,
    expiresAt,
    isScoring,
    currentScore,
    currentArtifact,
    currentFeedback,
    submitted: showingResult,
    nextBusy: phase === PHASES.ACTIVATING,
    onSubmit: (payload) => submitAnswer(payload),
    onNextRound: phase === PHASES.BLOCKED ? handleContinueBlocked : handleNext,
    sessionComplete: phase === PHASES.COMPLETED || sessionComplete,
  };
  const roundKey = `${sessionId}:${round}`;

  return (
    <div className="iv-interview-shell h-screen bg-[var(--color-surface)] flex flex-col overflow-y-auto lg:overflow-hidden">
      <header className="h-14 px-6 flex items-center justify-between border-b border-[var(--color-border)] shrink-0 sticky top-0 bg-white z-10">
        <div className="flex items-center gap-4">
          <button type="button" onClick={saveAndExit} className="app-button" style={{ minHeight: 32, padding: '6px 14px' }}
            title="Your progress is saved on the server. A running timer keeps running.">
            ← Save &amp; Exit
          </button>
          <div className="h-4 w-px bg-black/10" />
          <span className="text-xs font-medium uppercase tracking-wider text-[var(--color-ink-muted)]"
            style={{ fontFamily: "var(--font-body)" }}>{currentSkill || 'Live Session'}</span>
        </div>
        <div className="flex items-center gap-5">
          <div className="hidden sm:flex items-center gap-2">
            <div className="w-24 h-1.5 bg-black/5 rounded-full overflow-hidden">
              <div className="h-full bg-black rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
            </div>
            <span className="text-xs text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>{round}/{totalRounds}</span>
          </div>
          {usesInterviewMedia && roundType === 'technical_short_answer' && (
            <span
              className={`text-sm font-mono ${timeLeft <= 15 ? 'text-red-500' : 'text-[var(--color-ink-muted)]'}`}
              title="Time left in this round"
            >
              {fmt(timeLeft)}
            </span>
          )}
          <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-black/[0.03] text-[var(--color-ink-muted)]"
            style={{ fontFamily: "var(--font-body)" }}>Elo {elo}</span>
          <div className="hidden md:flex gap-1">
            {allSkills.map(s => (
              <span key={s} className="text-[10px] px-2 py-1 rounded-full border"
                style={{
                  fontFamily: "var(--font-body)",
                  borderColor: s === currentSkill ? 'var(--color-ink)' : 'var(--color-border)',
                  backgroundColor: s === currentSkill ? 'var(--color-ink)' : 'transparent',
                  color: s === currentSkill ? '#fff' : 'var(--color-ink-muted)',
                }}>
                {s}
              </span>
            ))}
          </div>
        </div>
      </header>

      {actionError && (
        <div role="alert" data-testid="interview-action-error"
          className="mx-4 mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">
          {actionError}
        </div>
      )}
      {phase === PHASES.BLOCKED && roundType !== 'technical_short_answer' && (
        <div role="status" className="mx-4 mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
          <span>{progressionBlockedReason || 'The next question is temporarily unavailable. Your result is saved.'}</span>
          <button type="button" className="app-button" disabled={continueBusy} onClick={handleContinueBlocked}>
            {continueBusy ? 'Checking…' : 'Retry next question'}
          </button>
        </div>
      )}

      {roundType === 'mcq' ? (
        <div className="flex-1 overflow-y-auto min-h-0">
          <MCQRound key={roundKey} {...roundProps} />
        </div>
      ) : roundType === 'sql' ? (
        <div className="flex-1 overflow-y-auto min-h-0">
          <SQLRound key={roundKey} {...roundProps} />
        </div>
      ) : roundType === 'coding' ? (
        <div className="flex-1 overflow-y-auto min-h-0">
          <CodingRound key={roundKey} {...roundProps} />
        </div>
      ) : roundType === 'ml_primitives' ? (
        <div className="flex-1 overflow-y-auto min-h-0">
          <MLPrimitivesRound key={roundKey} {...roundProps} />
        </div>
      ) : roundType === 'system_design' ? (
        <div className="flex-1 overflow-y-auto min-h-0">
          <SystemDesignRound key={roundKey} {...roundProps}
            evaluationMode={evaluationMode}
            evaluationBoundary={evaluationBoundary} />
        </div>
      ) : (
        <div className="iv-interview-grid flex-1 grid grid-cols-1 lg:grid-cols-[7fr_3fr] gap-4 p-4 overflow-hidden">
        <div className="iv-interview-question relative flex-1 rounded-2xl overflow-hidden border border-[var(--color-border)] bg-white flex flex-col min-h-0">
          {/* Live status chips */}
          <div className="flex flex-wrap items-center gap-2 px-6 pt-5">
            {/* Only after a requested mic/camera actually failed. */}
            {avState && avState !== AV_STATES.READY && avState !== AV_STATES.PERMISSION_NOT_REQUESTED ? (
              <div className="w-full">
                <AvUnavailablePanel
                  state={avState}
                  detail={avDetail}
                  onRetry={
                    avState === AV_STATES.INTERRUPTED_RECOVERABLE
                      || avState === AV_STATES.CAPTURE_FAILED
                      || avState === AV_STATES.PERMISSION_DENIED
                      || avState === AV_STATES.PERMISSION_NOT_REQUESTED
                      ? () => {
                        setMicError('');
                        setAvDetail('');
                        setAvState(AV_STATES.PERMISSION_NOT_REQUESTED);
                        ensureMicrophone().catch(() => {});
                      }
                      : null
                  }
                />
              </div>
            ) : null}
            <div className="flex items-center gap-2 bg-black/[0.03] px-3 py-1.5 rounded-full border border-[var(--color-border)]">
              <div className={`w-2 h-2 rounded-full ${isRecording || serverRecording ? 'bg-red-500 animate-pulse' : serverTranscribing ? 'bg-blue-500 animate-pulse' : micError ? 'bg-amber-500' : 'bg-slate-300'}`} />
              <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-ink-muted)]"
                style={{ fontFamily: "var(--font-body)" }}>
                {voiceStatus}
              </span>
            </div>
            <button type="button" className="iv-viv-toggle" aria-pressed={showViv} onClick={() => setShowViv(value => !value)}>
              {showViv ? 'Hide Viv' : 'Show Viv'}
            </button>
            {showViv && <label className="iv-viv-style">Viv style <select value={vivAppearance} onChange={event => { setVivAppearance(event.target.value); writeDevicePreference('viv-appearance', event.target.value); }}>
              <option value="fern">Fern</option><option value="ocean">Ocean</option><option value="plum">Plum</option>
            </select></label>}
            {isVideoOn && (
              <div className="flex items-center gap-2 bg-black/[0.03] px-3 py-1.5 rounded-full border border-[var(--color-border)]">
                <div className={`w-2 h-2 rounded-full ${engagementLoadFailed ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-ink-muted)]"
                  style={{ fontFamily: "var(--font-body)" }} title="Camera cues do not measure readiness or competence.">
                  Camera on{engagementLoadFailed ? ' · cues unavailable' : ''}
                </span>
              </div>
            )}
          </div>

          {/* Question — the primary focus of the screen */}
          <div className="flex-1 flex flex-col justify-center px-8 md:px-12 py-6 overflow-y-auto min-h-0">
            {showViv && <Suspense fallback={<p className="iv-viv-loading" role="status">Loading Viv…</p>}><VivStage speaking={vivSpeaking} listening={isRecording || serverRecording} appearance={vivAppearance} /></Suspense>}
            <div className="flex items-center gap-3 mb-5 flex-wrap">
              <span className="text-[11px] font-medium uppercase tracking-[0.15em] text-[var(--color-ink-muted)]"
                style={{ fontFamily: "var(--font-body)" }}>
                Question {String(round).padStart(2, '0')} / {String(totalRounds).padStart(2, '0')}
              </span>
              {isFollowUp && (
                <span
                  className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-800 border border-amber-500/20"
                  style={{ fontFamily: "var(--font-body)" }}
                  data-testid="followup-badge"
                >
                  Follow-up{followUpParentRound != null ? ` (Round ${followUpParentRound})` : ''}
                </span>
              )}
              <span className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-black/[0.04] text-[var(--color-ink-muted)] capitalize"
                style={{ fontFamily: "var(--font-body)" }}>
                {currentSkill} · {difficulty}
              </span>
            </div>
            <p className="text-2xl md:text-3xl lg:text-[34px] font-normal text-[var(--color-ink)] leading-[1.3] max-w-3xl"
              style={{ fontFamily: "var(--font-display)" }}>
              {question || 'Loading…'}
            </p>
          </div>

          {/* Collapsible self-view — never covers question/answer on mobile */}
          <div
            className={`absolute bottom-4 right-4 rounded-xl overflow-hidden border border-[var(--color-border)] bg-black/[0.04] shadow-md transition-all ${
              cameraCollapsed ? 'w-auto' : 'w-36 lg:w-48 aspect-video'
            }`}
            data-testid="interview-camera-panel"
          >
            {cameraCollapsed ? (
              <button
                type="button"
                className="px-3 py-2 text-[10px] uppercase tracking-wider text-[var(--color-ink-muted)]"
                style={{ fontFamily: 'var(--font-body)' }}
                onClick={() => setCameraCollapsed(false)}
                aria-expanded="false"
                aria-label="Show camera preview"
              >
                Show camera
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className="absolute top-1 left-1 z-10 rounded bg-black/50 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-white"
                  onClick={() => setCameraCollapsed(true)}
                  aria-expanded="true"
                  aria-label="Hide camera preview"
                >
                  Hide
                </button>
                {isVideoOn
                  ? <video ref={attachVideoEl} autoPlay playsInline muted className="w-full h-full object-cover" />
                  : (
                    <div className="w-full h-full flex flex-col items-center justify-center gap-1.5 px-2 text-center aspect-video">
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-ink-muted)" strokeWidth="1.2">
                        <path d="M16 16v1a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2m5.66 0H14a2 2 0 0 1 2 2v3.34l1 1L23 7v10"/>
                        <line x1="1" y1="1" x2="23" y2="23"/>
                      </svg>
                      <span className="text-[9px] text-[var(--color-ink-muted)] leading-tight" style={{ fontFamily: "var(--font-body)" }}>
                        {cameraError || 'Camera Off'}
                      </span>
                    </div>
                  )
                }
              </>
            )}
          </div>
        </div>

        <div className="iv-interview-answer flex flex-col gap-3 overflow-y-auto min-h-0 lg:overflow-hidden">
          {deadlineNotice && (
            <div
              role="status"
              data-testid="deadline-transcription-notice"
              className="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-xs text-amber-900 leading-relaxed"
              style={{ fontFamily: 'var(--font-body)' }}
            >
              {deadlineNotice}
            </div>
          )}
          {!isSupportedRoundType(roundType) ? (
            <div role="alert" data-testid="unsupported-round-type"
              className="rounded-2xl border border-red-300 bg-red-50 p-5 flex-1 flex flex-col justify-center">
              <h3 className="text-sm font-medium text-red-800"
                style={{ fontFamily: "var(--font-body)" }}>Unsupported round type</h3>
              <p className="mt-2 text-xs leading-relaxed text-red-700"
                style={{ fontFamily: "var(--font-body)" }}>
                This round uses type &ldquo;{roundType}&rdquo;, which this version cannot
                render. Nothing was submitted and nothing was scored — your progress
                is saved.
              </p>
            </div>
          ) : (
          <div className="rounded-2xl border border-[var(--color-border)] bg-white p-5 flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-ink-muted)]"
                style={{ fontFamily: "var(--font-body)" }}>
                Answer Draft
                {draftNotice && (
                  <span className="ml-2 normal-case text-blue-600" role="status"> — {draftNotice}</span>
                )}
              </h3>
              <div className="flex items-center gap-3">
                {answerWordCount > 0 && (
                  <span className="text-[10px] text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }} data-testid="delivery-words">
                    {answerWordCount} words{delivery.wpm != null ? ` · ~${delivery.wpm} wpm` : ''}
                  </span>
                )}
                {speakerRef.current?.supported && (
                  <label className="flex items-center gap-1.5 text-[10px] text-[var(--color-ink-muted)] select-none" style={{ fontFamily: "var(--font-body)" }}>
                    <input
                      type="checkbox"
                      checked={readAloud}
                      onChange={(e) => {
                        setReadAloud(e.target.checked);
                        spokenKeyRef.current = '';
                        if (!e.target.checked) speakerRef.current?.cancel();
                      }}
                      className="h-3 w-3 accent-black"
                      data-testid="read-aloud-toggle"
                    />
                    Read aloud
                  </label>
                )}
                <label className="flex items-center gap-1.5 text-[10px] text-[var(--color-ink-muted)] select-none"
                  style={{ fontFamily: "var(--font-body)" }}>
                  <input
                    type="checkbox"
                    checked={serverSttActive}
                    disabled={!hasBrowserSTT || isRecording || serverRecording || serverTranscribing || locked}
                    onChange={(e) => {
                      if (isRecording) stopRecording();
                      if (serverRecording) stopServerRecording(true);
                      setUseServerSTT(e.target.checked);
                      setMicError('');
                    }}
                    className="h-3 w-3 accent-black disabled:opacity-50"
                  />
                  Use server transcription
                </label>
              </div>
            </div>
            <textarea
              aria-label="Answer draft"
              value={transcript}
              onChange={(e) => {
                setTranscript(e.target.value);
                setCurrentFeedback('');
              }}
              disabled={locked}
              placeholder={isRecording || serverRecording ? 'Listening...' : serverTranscribing ? 'Transcribing...' : 'Type your answer here or use the microphone.'}
              className="flex-1 min-h-[180px] w-full resize-none rounded-xl border border-transparent bg-transparent text-sm leading-relaxed text-[var(--color-ink)] outline-none transition-colors placeholder:text-[var(--color-ink-muted)] focus:border-[var(--color-border)] focus:bg-black/[0.015] disabled:cursor-default"
              style={{ fontFamily: "var(--font-body)" }}
            />
            {!locked && <StarComposer onInsert={(text) => setTranscript(previous => previous.trim() ? `${previous.trim()}\n\n${text}` : text)} />}
            {!locked && answerWordCount > 0 && (
              <p className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px] text-[var(--color-ink-muted)]" data-testid="delivery-checklist"
                style={{ fontFamily: "var(--font-body)" }}>
                <span>Structure (advisory, not scored):</span>
                {[['concept', 'Concept'], ['tradeoff', 'Trade-off'], ['example', 'Example']].map(([key, label]) => (
                  <span key={key} className={`rounded-full border px-2 py-0.5 ${delivery.checklist[key] ? 'border-emerald-300 bg-emerald-50 text-emerald-800' : 'border-[var(--color-border)]'}`}>
                    {delivery.checklist[key] ? '✓ ' : ''}{label}
                  </span>
                ))}
              </p>
            )}
            {interimText && !locked && (
              <p className="mt-3 rounded-xl bg-black/[0.03] px-3 py-2 text-xs italic text-[var(--color-ink-muted)]"
                style={{ fontFamily: "var(--font-body)" }}>
                {interimText}
              </p>
            )}
            {micError && !locked && (
              <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700"
                style={{ fontFamily: "var(--font-body)" }}>
                {micError}
              </p>
            )}
          </div>
          )}

          {showingResult && (
            <div className="rounded-2xl border border-[var(--color-border)] bg-white p-5" data-testid="verbal-review">
              {followUpOutcome || (isFollowUp && currentScore == null) ? (
                <div className="text-center mb-1" data-testid="followup-concept-outcome">
                  <div
                    className="text-xl font-medium mb-1"
                    style={{
                      fontFamily: "var(--font-display)",
                      color: followUpOutcome
                        ? (followUpOutcome.demonstrated
                          ? '#16A34A'
                          : followUpOutcome.status === 'unclear'
                            ? '#D97706'
                            : '#DC2626')
                        : 'var(--color-ink)',
                    }}
                  >
                    {followUpOutcomeLabel(followUpOutcome)}
                  </div>
                  {followUpOutcome?.concept_label && (
                    <p className="text-xs font-medium text-[var(--color-ink)]" style={{ fontFamily: "var(--font-body)" }}>
                      {followUpOutcome.concept_label}
                    </p>
                  )}
                </div>
              ) : (
                <div className="text-3xl font-normal mb-1 text-center"
                  style={{ fontFamily: "var(--font-display)", color: currentScore == null ? 'var(--color-ink-muted)' : scoreColor(currentScore) }}>
                  {currentScore == null ? '—' : `${Math.round(currentScore)}%`}
                </div>
              )}
              {eligibilityLabel && (
                <p className="text-[11px] uppercase tracking-wider text-center text-[var(--color-ink-muted)] mb-2"
                  style={{ fontFamily: "var(--font-body)" }}>
                  {eligibilityLabel}
                </p>
              )}
              {currentFeedback && (
                <p className="text-xs text-[var(--color-ink-muted)] text-center mt-1 leading-relaxed"
                  style={{ fontFamily: "var(--font-body)" }}>
                  {currentFeedback}
                </p>
              )}
              {feedbackSourceLabel && (
                <p className="mt-2 text-[10px] uppercase tracking-wider text-center text-[var(--color-ink-muted)]"
                  style={{ fontFamily: "var(--font-body)" }}>
                  Source: {feedbackSourceLabel}
                </p>
              )}
              {feedbackDetails && (
                <details className="mt-2 text-[11px] text-[var(--color-ink-muted)]">
                  <summary className="cursor-pointer text-center">Feedback details</summary>
                  <ul className="mt-1 space-y-0.5 text-left px-2">
                    {feedbackDetails.validation && <li>Validation: {feedbackDetails.validation}</li>}
                    {feedbackDetails.model && <li>Model: {feedbackDetails.model}</li>}
                    {feedbackDetails.schema_version != null && (
                      <li>Schema: {feedbackDetails.schema_version}</li>
                    )}
                    {feedbackDetails.snapshot_digest && (
                      <li className="break-all">Snapshot: {String(feedbackDetails.snapshot_digest).slice(0, 16)}…</li>
                    )}
                  </ul>
                </details>
              )}
              {progressionBlocked && (
                <p className="mt-3 text-[11px] text-[#B45309] text-center leading-relaxed"
                  style={{ fontFamily: "var(--font-body)" }} role="status">
                  {progressionBlockedReason || 'Next question is temporarily unavailable. Your score is saved.'}
                </p>
              )}
              {currentRubric && (
                <div className="mt-4 space-y-2">
                  {['correctness', 'coverage', 'depth', 'clarity'].map((dim) => {
                    const val = Number(currentRubric[dim]);
                    if (!Number.isFinite(val)) return null;
                    const pct = Math.max(0, Math.min(100, val * 10));
                    return (
                      <div key={dim} className="flex items-center gap-2">
                        <span className="text-[10px] uppercase tracking-wider text-[var(--color-ink-muted)] w-[68px] shrink-0 capitalize"
                          style={{ fontFamily: "var(--font-body)" }}>{dim}</span>
                        <div className="flex-1 h-1.5 rounded-full bg-black/5 overflow-hidden">
                          <div className="h-full rounded-full transition-all duration-500"
                            style={{ width: `${pct}%`, backgroundColor: scoreColor(pct) }} />
                        </div>
                        <span className="text-[10px] text-[var(--color-ink-muted)] w-7 text-right tabular-nums"
                          style={{ fontFamily: "var(--font-body)" }}>{val.toFixed(1)}</span>
                      </div>
                    );
                  })}
                </div>
              )}
              {currentConcepts?.missing?.length > 0 && (
                <p className="mt-3 text-[11px] text-[var(--color-ink-muted)] leading-relaxed"
                  style={{ fontFamily: "var(--font-body)" }}>
                  <span className="font-medium text-[var(--color-ink)]">Review:</span> {currentConcepts.missing.slice(0, 4).join(', ')}
                </p>
              )}
              {canRequestManualFollowUp({
                roundType,
                phase,
                followUpNote,
                followUpScheduled: followUpScheduledForRound,
                isFollowUp,
              }) && (
                <button
                  type="button"
                  className="mt-4 w-full rounded-xl border border-[var(--color-border)] px-3 py-2 text-xs text-[var(--color-ink)] disabled:opacity-50"
                  style={{ fontFamily: "var(--font-body)" }}
                  disabled={followUpBusy}
                  onClick={async () => {
                    if (!window.confirm(
                      'Optional follow-ups are Practiced with help and excluded from primary assessment metrics. Continue?'
                    )) return;
                    setFollowUpBusy(true);
                    try {
                      // ``round`` is still the submitted round while reviewing.
                      const res = await requestFollowUp(sessionId, round);
                      if (res.scheduled) {
                        if (typeof res.total_rounds === 'number') setTotalRounds(res.total_rounds);
                        setFollowUpNote(
                          `Follow-up scheduled (${res.follow_up_scoring || 'unscored'}). It appears after remaining mandatory rounds.`
                        );
                      } else {
                        setFollowUpNote(`Follow-up not scheduled: ${res.reason || 'unavailable'}.`);
                      }
                    } catch (err) {
                      setFollowUpNote(err?.message || 'Follow-up request failed.');
                    } finally {
                      setFollowUpBusy(false);
                    }
                  }}
                >
                  {followUpBusy ? 'Scheduling follow-up…' : 'Request optional follow-up'}
                </button>
              )}
              {followUpNote && (
                <p className="mt-3 text-[11px] text-[var(--color-ink-muted)] text-center" style={{ fontFamily: "var(--font-body)" }}>
                  {followUpNote}
                </p>
              )}
            </div>
          )}

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsVideoOn(p => !p)}
              aria-label={isVideoOn ? 'Turn camera off' : 'Turn camera on'}
              title={isVideoOn ? 'Turn camera off' : 'Turn camera on'}
              className={`w-11 h-11 rounded-full flex items-center justify-center cursor-pointer transition-all border ${!isVideoOn ? 'bg-red-50 border-red-200 text-red-500' : 'bg-white border-[var(--color-border)] text-[var(--color-ink-muted)]'}`}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                {isVideoOn
                  ? <><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></>
                  : <><path d="M16 16v1a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2m5.66 0H14a2 2 0 0 1 2 2v3.34l1 1L23 7v10"/><line x1="1" y1="1" x2="23" y2="23"/></>
                }
              </svg>
            </button>

            <button
              onClick={serverSttActive ? toggleServerRecording : toggleRecording}
              disabled={voiceButtonDisabled}
              aria-label={serverSttActive ? (serverRecording ? 'Stop server transcription recording' : 'Record with server transcription') : (isRecording ? 'Stop microphone' : 'Start microphone')}
              title={serverSttActive ? (serverRecording ? 'Stop server transcription recording' : 'Record with server transcription') : (isRecording ? 'Stop microphone' : 'Start microphone')}
              className={`${serverSttActive ? 'h-11 min-w-[142px] px-4 gap-2' : 'w-11 h-11'} rounded-full flex items-center justify-center cursor-pointer transition-all border disabled:cursor-not-allowed disabled:opacity-40 ${voiceButtonBusy ? 'bg-red-50 border-red-200 text-red-500' : 'bg-white border-[var(--color-border)] text-[var(--color-ink-muted)]'}`}>
              {serverTranscribing
                ? <span className="w-3.5 h-3.5 border border-current/30 border-t-current rounded-full animate-spin" />
                : voiceButtonBusy
                ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/></svg>
                : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
              }
              {serverSttActive && (
                <span className="text-xs font-medium" style={{ fontFamily: "var(--font-body)" }}>
                  {serverTranscribing ? 'Transcribing' : serverRecording ? 'Stop' : 'Record (server)'}
                </span>
              )}
            </button>

            {!showingResult && (
              <button onClick={() => submitAnswer()} disabled={!canSubmit}
                className="flex-1 rounded-full py-3 text-sm font-medium text-white cursor-pointer hover:scale-[1.01] transition-transform disabled:cursor-not-allowed disabled:opacity-35"
                style={{ backgroundColor: 'var(--color-ink)', fontFamily: "var(--font-body)" }}>
                {isScoring
                  ? <span className="flex items-center justify-center gap-2">
                      <span className="w-3 h-3 border border-white/30 border-t-white rounded-full animate-spin"/>Scoring...
                    </span>
                  : 'Submit Answer'
                }
              </button>
            )}

            {showingResult && (
                <button
                onClick={phase === PHASES.BLOCKED ? handleContinueBlocked : handleNext}
                disabled={continueBusy || phase === PHASES.ACTIVATING}
                className="flex-1 rounded-full py-3 text-sm font-medium text-white cursor-pointer hover:scale-[1.01] transition-transform disabled:opacity-50"
                style={{ backgroundColor: 'var(--color-ink)', fontFamily: "var(--font-body)" }}>
                {nextLabel}
              </button>
            )}

            <button onClick={resetAnswer} disabled={locked} aria-label="Clear answer draft" title="Clear answer draft"
              className="w-9 h-9 rounded-full flex items-center justify-center border border-[var(--color-border)] text-[var(--color-ink-muted)] cursor-pointer">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}
