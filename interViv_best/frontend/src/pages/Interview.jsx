import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { loadInterviewState, submitAnswer as apiSubmitAnswer, buildAnswerMetrics, clearInterviewState, transcribeAudio, saveInterviewState, fetchSession, saveAnswerDraft, fetchAnswerDraft, fetchAvCapabilities } from '../lib/api';
import { classifyFrame, computeEngagementDelta, loadModels, modeOfLabels } from '../lib/engagement';
import MCQRound from '../components/MCQRound';
import SQLRound from '../components/SQLRound';
import CodingRound from '../components/CodingRound';
import MLPrimitivesRound from '../components/MLPrimitivesRound';
import SystemDesignRound from '../components/SystemDesignRound';
import AvUnavailablePanel from '../components/AvUnavailablePanel';
import { AV_STATES, classifyMediaError, transcriptionFailureResult } from '../lib/avStates';

const ROUND_SECONDS = 120;

/** Phase L: Verbal/OA blocks never use interview camera/mic/calibration.
 *  When category is not yet known, only treat non-mcq round types as media rounds
 *  so a late-arriving verbal/oa category cannot race a getUserMedia call. */
function blockUsesInterviewMedia(category, roundType) {
  const c = String(category || '').toLowerCase();
  if (roundType === 'coding' || c === 'coding' || c === 'verbal' || c === 'oa' || c === 'ml_primitives') return false;
  if (c) return true;
  const t = String(roundType || '');
  return t === 'technical_short_answer' || t === 'sql' || t === 'system_design';
}

function stopMediaStream(stream) {
  stream?.getTracks?.().forEach(track => track.stop());
}

function mediaErrorMessage(error, device) {
  if (!navigator.mediaDevices?.getUserMedia) {
    return `${device} access is not supported in this browser.`;
  }
  if (!window.isSecureContext && !['localhost', '127.0.0.1'].includes(window.location.hostname)) {
    return `${device} access requires HTTPS or localhost.`;
  }
  if (error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError') {
    return `${device} permission was blocked. Allow access in the browser and try again.`;
  }
  if (error?.name === 'NotFoundError' || error?.name === 'DevicesNotFoundError') {
    return `No ${device.toLowerCase()} device was found.`;
  }
  if (error?.name === 'NotReadableError' || error?.name === 'TrackStartError') {
    return `${device} is already in use by another app.`;
  }
  return `${device} could not be started.`;
}

export default function Interview({ sessionState = null }) {
  const { sessionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const videoRef = useRef(null);
  const recognitionRef = useRef(null);
  const cameraStreamRef = useRef(null);
  const micStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const mediaChunksRef = useRef([]);
  const discardServerRecordingRef = useRef(false);
  const engagementSamplesRef = useRef([]);
  const baselineSamplesRef = useRef([]);
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
  const [currentArtifact, setCurrentArtifact] = useState(null);
  const [evaluationMode, setEvaluationMode] = useState(null);
  const [evaluationBoundary, setEvaluationBoundary] = useState(null);
  const [avState, setAvState] = useState(AV_STATES.PERMISSION_NOT_REQUESTED);
  const [avDetail, setAvDetail] = useState('');
  const [transcriptionAvailable, setTranscriptionAvailable] = useState(null);
  const [currentSkill, setCurrentSkill] = useState(initState.skill || '');
  const [allSkills] = useState(initState.allSkills || [initState.skill || 'General']);
  const [round, setRound] = useState(initState.round || 1);
  const [totalRounds] = useState(initState.totalRounds || 5);
  const [elo, setElo] = useState(initState.elo || 1200);

  const [timeLeft, setTimeLeft] = useState(ROUND_SECONDS);
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [draftNotice, setDraftNotice] = useState('');
  const draftTimerRef = useRef(null);
  const draftLoadedForRef = useRef('');
  const [interimText, setInterimText] = useState('');
  const [isScoring, setIsScoring] = useState(false);
  const [isVideoOn, setIsVideoOn] = useState(true);
  const [sessionComplete, setSessionComplete] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [micError, setMicError] = useState('');

  const [currentScore, setCurrentScore] = useState(null);
  const [currentFeedback, setCurrentFeedback] = useState('');
  const [currentRubric, setCurrentRubric] = useState(null);
  const [currentConcepts, setCurrentConcepts] = useState(null);
  const [scores, setScores] = useState([]);

  const [useServerSTT, setUseServerSTT] = useState(!hasBrowserSTT);
  const [serverRecording, setServerRecording] = useState(false);
  const [serverTranscribing, setServerTranscribing] = useState(false);
  const [engagementReady, setEngagementReady] = useState(false);
  const [engagementLoadFailed, setEngagementLoadFailed] = useState(false);
  const [liveEngagement, setLiveEngagement] = useState(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [baselineSamples, setBaselineSamples] = useState([]);
  const [calibrationProgress, setCalibrationProgress] = useState(0);
  const [engagementBaseline, setEngagementBaseline] = useState(
    initState.engagementBaseline || null
  );
  const [calibrationComplete, setCalibrationComplete] = useState(
    Boolean(initState.engagementBaseline || initState.engagementCalibrationSkipped)
  );
  const [calibrationSkipped, setCalibrationSkipped] = useState(
    Boolean(initState.engagementCalibrationSkipped)
  );

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

  const stopRecording = useCallback(() => {
    try { recognitionRef.current?.stop(); }
    catch { /* recognition was already stopped */ }
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
    setLiveEngagement(null);
  }, []);

  const finishCalibration = useCallback((samples = [], skipped = false) => {
    const fallback = { label: 'Neutral', confidence: null, sample_count: 0 };
    const baseline = skipped ? fallback : (modeOfLabels(samples) || fallback);
    baselineSamplesRef.current = [];
    setBaselineSamples([]);
    setCalibrationProgress(100);
    setEngagementBaseline(baseline);
    setCalibrationSkipped(skipped);
    setCalibrationComplete(true);
    clearEngagementSamples();
  }, [clearEngagementSamples]);

  const skipCalibration = useCallback(() => {
    finishCalibration([], true);
  }, [finishCalibration]);

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

  useEffect(() => {
    if (!usesInterviewMedia) {
      recognitionRef.current = null;
      return undefined;
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      recognitionRef.current = null;
      setUseServerSTT(true);
      setMicError('');
      return undefined;
    }
    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = 'en-US';
    rec.onstart = () => {
      setMicError('');
      setIsRecording(true);
    };
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
      const errorName = e.error === 'not-allowed' ? 'NotAllowedError' : e.error;
      setMicError(mediaErrorMessage({ name: errorName }, 'Microphone'));
      stopMicrophone();
      setIsRecording(false);
    };
    rec.onend = () => {
      stopMicrophone();
      setIsRecording(false);
      setInterimText('');
    };
    recognitionRef.current = rec;
    return () => {
      try { rec.abort(); }
      catch { /* recognition was never started */ }
    };
  }, [stopMicrophone, usesInterviewMedia]);

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
    if (!sessionId || currentScore !== null || draftLoadedForRef.current === key) return undefined;
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
  }, [sessionId, round, roundType, currentScore]);

  // Phase B: autosave free-text drafts (debounced).
  useEffect(() => {
    if (roundType !== 'technical_short_answer') return undefined;
    if (!sessionId || currentScore !== null || !transcript.trim()) return undefined;
    if (draftTimerRef.current) clearTimeout(draftTimerRef.current);
    draftTimerRef.current = setTimeout(() => {
      saveAnswerDraft(sessionId, { round, answer_text: transcript }).catch(() => {});
    }, 1500);
    return () => {
      if (draftTimerRef.current) clearTimeout(draftTimerRef.current);
    };
  }, [transcript, sessionId, round, roundType, currentScore]);

  useEffect(() => {
    if (!usesInterviewMedia || calibrationComplete) return;
    if (!isVideoOn || cameraError || engagementLoadFailed) {
      finishCalibration([], true);
    }
  }, [calibrationComplete, cameraError, engagementLoadFailed, finishCalibration, isVideoOn, usesInterviewMedia]);

  const showCalibrationScreen =
    usesInterviewMedia &&
    !calibrationComplete &&
    isVideoOn &&
    !engagementLoadFailed &&
    currentScore === null &&
    !sessionComplete;
  const calibrationActive = showCalibrationScreen && cameraReady;

  useEffect(() => {
    if (!calibrationActive) return undefined;

    let cancelled = false;
    let elapsed = 0;
    baselineSamplesRef.current = [];
    setBaselineSamples([]);
    setCalibrationProgress(0);

    const captureBaselineFrame = async () => {
      elapsed += 1;
      if (engagementReadyRef.current) {
        const sample = await classifyFrame(videoRef.current);
        if (cancelled) return;
        if (sample) {
          baselineSamplesRef.current.push(sample);
          setBaselineSamples([...baselineSamplesRef.current]);
        }
      }

      if (cancelled) return;
      setCalibrationProgress(Math.min(100, elapsed * 10));
      if (elapsed >= 10) {
        finishCalibration(baselineSamplesRef.current, false);
      }
    };

    const id = setInterval(captureBaselineFrame, 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [calibrationActive, finishCalibration]);

  useEffect(() => {
    const shouldClassify =
      usesInterviewMedia &&
      isVideoOn &&
      engagementReady &&
      calibrationComplete &&
      !sessionComplete &&
      currentScore === null &&
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
          setLiveEngagement(sample);
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
  }, [calibrationComplete, currentScore, engagementReady, isRecording, isVideoOn, serverRecording, sessionComplete, transcript, usesInterviewMedia]);

  useEffect(() => {
    return () => {
      stopServerRecording(true);
      stopCamera();
      stopMicrophone();
    };
  }, [stopCamera, stopMicrophone, stopServerRecording]);

  useEffect(() => {
    if (!sessionId || sessionComplete || currentScore !== null) return;
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
      engagementBaseline,
      engagementCalibrationSkipped: calibrationSkipped,
    });
  }, [
    allSkills,
    blockCategory,
    calibrationSkipped,
    candidateId,
    configJson,
    currentScore,
    currentSkill,
    difficulty,
    elo,
    engagementBaseline,
    expiresAt,
    question,
    questionContext,
    round,
    roundType,
    sessionComplete,
    sessionId,
    totalRounds,
  ]);

  useEffect(() => {
    if (!sessionId || blockCategory) return undefined;
    let cancelled = false;
    fetchSession(sessionId)
      .then((data) => {
        if (cancelled) return;
        const cr = data?.active_round || data?.current_round;
        if (cr?.block_category) setBlockCategory(cr.block_category);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [sessionId, blockCategory]);

  useEffect(() => {
    if (!sessionId) return;
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

    try {
      setMicError('');
      await ensureMicrophone();
      recognitionRef.current.start();
      setIsRecording(true);
    } catch (err) {
      if (err?.name === 'InvalidStateError') {
        setIsRecording(true);
        return;
      }
      setMicError(mediaErrorMessage(err, 'Microphone'));
      stopMicrophone();
      setIsRecording(false);
    }
  }, [ensureMicrophone, isRecording, stopMicrophone, stopRecording]);

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
    if (!isMcq && (!answerText && !force) || isScoring) return;
    if (isRecording) stopRecording();
    if (serverRecording) stopServerRecording(false);
    setIsScoring(true);
    try {
      const metrics = (!isMcq && !isSystemDesign) ? buildAnswerMetrics(answerText) : {};
      const engagement = isVideoOn ? modeOfLabels(engagementSamplesRef.current) : null;
      const engagementDelta = calibrationSkipped
        ? 0
        : computeEngagementDelta(engagement?.label, engagementBaseline?.label);
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
      if (roundType === 'coding') {
        payload.language = options.language || configJson.language || 'python';
        delete payload.engagement_label;
        delete payload.engagement_confidence;
        delete payload.engagement_delta;
        delete payload.wpm;
        delete payload.pause_count;
      }
      const resp = await apiSubmitAnswer(payload);

      // Never invent a score when the API omits one.
      const score = typeof resp.final_score === 'number' ? resp.final_score : null;
      const feedbackRaw = resp.feedback?.next_step || resp.feedback?.content?.[0] || resp.feedback || '';
      const feedback = typeof feedbackRaw === 'string' ? feedbackRaw : '';
      const rubric = resp.rubric || resp.scoring_breakdown?.rubric || null;
      const concepts = resp.concepts || resp.scoring_breakdown?.concepts || null;
      setCurrentScore(score);
      let feedbackWithMode = feedback;
      if (resp.scoring_mode === 'lexical_fallback_degraded') {
        feedbackWithMode = (
          'Scoring mode: lexical fallback (semantic scorer unavailable). '
          + 'This score is not equivalent to a full semantic-scorer result.'
          + (feedback ? `\n\n${feedback}` : '')
        );
      } else if (resp.scoring_mode === 'self_reported') {
        feedbackWithMode = (
          'Scoring mode: self-reported (not measured mastery).'
          + (feedback ? `\n\n${feedback}` : '')
        );
      }
      setCurrentFeedback(feedbackWithMode);
      setCurrentRubric(rubric && typeof rubric === 'object' ? rubric : null);
      setCurrentConcepts(concepts && typeof concepts === 'object' ? concepts : null);
      setCurrentArtifact(resp.artifact_json || resp);
      setEvaluationMode(resp.evaluation_mode || null);
      setEvaluationBoundary(resp.evaluation_boundary || null);
      setElo(resp.elo_after ?? elo);
      if (score !== null) {
        setScores(p => [...p, {
          round,
          skill: currentSkill,
          score,
          question,
          answer: isMcq ? JSON.stringify(answers) : answerText,
          feedback,
          engagement_label: engagement?.label ?? null,
          engagement_confidence: engagement?.confidence ?? null,
          engagement_delta: engagementDelta,
        }]);
      }

      if (resp.session_complete) {
        setSessionComplete(true);
      } else if (resp.next_question || resp.next_round_type) {
        // Prefetch next round fields; UI keeps currentScore until Next.
        const nextCategory = resp.next_block_category ?? null;
        const enteringMedia =
          blockUsesInterviewMedia(nextCategory, resp.next_round_type) &&
          !blockUsesInterviewMedia(blockCategory, roundType);
        setQuestion(resp.next_question || '');
        setRoundType(resp.next_round_type || 'technical_short_answer');
        setBlockCategory(nextCategory);
        setDifficulty(resp.next_difficulty || resp.difficulty || 'medium');
        setCurrentSkill(resp.next_skill || resp.current_skill || currentSkill);
        setQuestionContext(resp.next_question_context || {});
        setConfigJson(resp.next_config_json || {});
        setExpiresAt(resp.next_expires_at || null);
        setRound(round + 1);
        if (enteringMedia) {
          // Mixed Verbal/OA → Interview: present calibration for the media block.
          setCalibrationComplete(false);
          setEngagementBaseline(null);
          setCalibrationSkipped(false);
          setCalibrationProgress(0);
          setBaselineSamples([]);
          setCameraError('');
          setIsVideoOn(true);
        } else {
          setCalibrationComplete(true);
        }
      }
    } catch (err) {
      setCurrentFeedback('Scoring failed — ' + err.message);
    } finally {
      setIsScoring(false);
    }
  };

  useEffect(() => {
    setTimeLeft(ROUND_SECONDS);
  }, [round]);

  useEffect(() => {
    if (sessionComplete || currentScore !== null || isScoring || showCalibrationScreen || roundType !== 'technical_short_answer') return undefined;
    const id = setInterval(() => {
      setTimeLeft(seconds => Math.max(0, seconds - 1));
    }, 1000);
    return () => clearInterval(id);
  }, [currentScore, isScoring, roundType, sessionComplete, showCalibrationScreen]);

  useEffect(() => {
    if (
      timeLeft > 0 ||
      currentScore !== null ||
      isScoring ||
      sessionComplete ||
      showCalibrationScreen ||
      roundType !== 'technical_short_answer'
    ) {
      return;
    }
    submitAnswer({ force: true });
  }, [currentScore, isScoring, roundType, sessionComplete, showCalibrationScreen, submitAnswer, timeLeft]);

  const handleNext = () => {
    if (sessionComplete) {
      clearInterviewState();
      navigate(`/dashboard/${sessionId}`);
      return;
    }
    setTranscript(''); setInterimText('');
    setCurrentScore(null); setCurrentFeedback('');
    setCurrentRubric(null); setCurrentConcepts(null);
    setCurrentArtifact(null);
    stopRecording();
    stopServerRecording(true);
    clearEngagementSamples();
  };

  const resetAnswer = () => {
    if (isRecording) stopRecording();
    if (serverRecording) stopServerRecording(true);
    setTranscript(''); setInterimText('');
    setDraftNotice('');
    setCurrentScore(null); setCurrentFeedback('');
    setCurrentRubric(null); setCurrentConcepts(null);
    setIsRecording(false);
    clearEngagementSamples();
  };

  const fmt = (s) => `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;
  const scoreColor = (score) => score >= 75 ? '#16A34A' : score >= 50 ? '#D97706' : '#DC2626';
  const progress = totalRounds ? ((round - 1 + (currentScore !== null ? 1 : 0)) / totalRounds) * 100 : 0;
  const answerWordCount = transcript.trim().split(/\s+/).filter(Boolean).length;
  const serverSttActive = useServerSTT || !hasBrowserSTT;
  const canSubmit = transcript.trim().length > 0 && !isScoring && currentScore === null && !serverRecording && !serverTranscribing && isSupportedRoundType(roundType);
  const voiceButtonBusy = serverSttActive ? (serverRecording || serverTranscribing) : isRecording;
  const voiceButtonDisabled = isScoring || currentScore !== null || serverTranscribing;
  const voiceStatus = serverTranscribing
    ? 'Transcribing'
    : serverRecording
      ? 'Recording Server'
      : isRecording
        ? 'Recording'
        : micError
          ? 'Mic Check'
          : 'Standby';
  const engagementStatus = !isVideoOn
    ? 'Off'
    : engagementLoadFailed
      ? 'Unavailable'
      : !engagementReady
        ? 'Loading'
        : liveEngagement?.label || 'Waiting';
  const engagementConfidence = liveEngagement?.confidence != null
    ? `${Math.round(liveEngagement.confidence * 100)}%`
    : null;
  const engagementTone = engagementStatus === 'High'
    ? 'bg-emerald-500'
    : engagementStatus === 'Low'
      ? 'bg-red-500'
      : engagementStatus === 'Neutral'
        ? 'bg-blue-500'
        : engagementStatus === 'Uncertain'
          ? 'bg-amber-500'
          : 'bg-[#6F6F6F]/30';
  const baselineLabel = engagementBaseline?.label || 'Neutral';

  if (showCalibrationScreen) {
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
          <span className="text-sm font-mono text-[#6F6F6F]">{fmt(ROUND_SECONDS)}</span>
        </header>

        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[7fr_3fr] gap-4 p-4 overflow-hidden">
          <div className="relative flex-1 bg-black/[0.02] rounded-2xl overflow-hidden border border-black/8">
            <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
            <div className="absolute top-4 left-4 flex items-center gap-2 bg-white/90 backdrop-blur-sm px-3 py-1.5 rounded-full border border-black/8">
              <div className={`w-2 h-2 rounded-full ${engagementReady ? 'bg-blue-500' : 'bg-[#6F6F6F]/30'}`} />
              <span className="text-[10px] font-medium uppercase tracking-wider text-[#6F6F6F]"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                Calibration
              </span>
            </div>
          </div>

          <div className="rounded-2xl border border-black/8 p-6 flex flex-col justify-center">
            <h1 className="text-4xl tracking-tight mb-3"
              style={{ fontFamily: "'Instrument Serif', serif" }}>
              Calibration
            </h1>
            <p className="text-sm text-[#6F6F6F] leading-relaxed mb-8"
              style={{ fontFamily: "'Inter', sans-serif" }}>
              Look at the camera with a relaxed expression for 10 seconds.
            </p>
            <div className="h-2 rounded-full bg-black/5 overflow-hidden mb-3">
              <div className="h-full bg-black rounded-full transition-all duration-500"
                style={{ width: `${calibrationProgress}%` }} />
            </div>
            <div className="flex items-center justify-between mb-8">
              <span className="text-xs text-[#6F6F6F]" style={{ fontFamily: "'Inter', sans-serif" }}>
                {calibrationProgress}%
              </span>
              <span className="text-xs text-[#6F6F6F]" style={{ fontFamily: "'Inter', sans-serif" }}>
                {baselineSamples.length} samples
              </span>
            </div>
            <button
              onClick={skipCalibration}
              className="rounded-full px-6 py-3 text-sm font-medium text-white cursor-pointer hover:scale-[1.01] transition-transform"
              style={{ backgroundColor: '#000', fontFamily: "'Inter', sans-serif" }}>
              Skip
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (sessionComplete && roundType !== 'coding') {
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
                {scores.length} rounds · Average{' '}
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
          {usesInterviewMedia && (
            <span
              className={`text-sm font-mono ${timeLeft <= 15 ? 'text-red-500' : 'text-[#6F6F6F]'}`}
              title="Time left in this round"
            >
              {fmt(timeLeft)}
            </span>
          )}
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

      {roundType === 'mcq' ? (
        <div className="flex-1 overflow-y-auto min-h-0">
          <MCQRound
            sessionId={sessionId}
            round={round}
            questionContext={questionContext}
            configJson={configJson}
            expiresAt={expiresAt}
            isScoring={isScoring}
            currentScore={currentScore}
            currentArtifact={currentArtifact}
            currentFeedback={currentFeedback}
            onSubmit={(payload) => submitAnswer(payload)}
            onNextRound={handleNext}
            sessionComplete={sessionComplete}
          />
        </div>
      ) : roundType === 'sql' ? (
        <div className="flex-1 overflow-y-auto min-h-0">
          <SQLRound
            sessionId={sessionId}
            round={round}
            question={question}
            questionContext={questionContext}
            configJson={configJson}
            expiresAt={expiresAt}
            isScoring={isScoring}
            currentScore={currentScore}
            currentArtifact={currentArtifact}
            currentFeedback={currentFeedback}
            onSubmit={(payload) => submitAnswer(payload)}
            onNextRound={handleNext}
            sessionComplete={sessionComplete}
          />
        </div>
      ) : roundType === 'coding' ? (
        <div className="flex-1 overflow-y-auto min-h-0">
          <CodingRound key={`${sessionId}:${round}`}
            sessionId={sessionId}
            round={round}
            question={question}
            questionContext={questionContext}
            configJson={configJson}
            expiresAt={expiresAt}
            isScoring={isScoring}
            currentScore={currentScore}
            currentArtifact={currentArtifact}
            currentFeedback={currentFeedback}
            onSubmit={(payload) => submitAnswer(payload)}
            onNextRound={handleNext}
            sessionComplete={sessionComplete}
          />
        </div>
      ) : roundType === 'ml_primitives' ? (
        <div className="flex-1 overflow-y-auto min-h-0">
          <MLPrimitivesRound key={`${sessionId}:${round}`}
            sessionId={sessionId} round={round} questionContext={questionContext}
            configJson={configJson} expiresAt={expiresAt} />
        </div>
      ) : roundType === 'system_design' ? (
        <div className="flex-1 overflow-y-auto min-h-0">
          <SystemDesignRound
            sessionId={sessionId}
            round={round}
            question={question}
            questionContext={questionContext}
            configJson={configJson}
            expiresAt={expiresAt}
            isScoring={isScoring}
            currentScore={currentScore}
            currentArtifact={currentArtifact}
            currentFeedback={currentFeedback}
            evaluationMode={evaluationMode}
            evaluationBoundary={evaluationBoundary}
            onSubmit={(payload) => submitAnswer(payload)}
            onNextRound={handleNext}
            sessionComplete={sessionComplete}
          />
        </div>
      ) : (
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[7fr_3fr] gap-4 p-4 overflow-hidden">
        <div className="relative flex-1 rounded-2xl overflow-hidden border border-black/8 bg-white flex flex-col min-h-0">
          {/* Live status chips */}
          <div className="flex flex-wrap items-center gap-2 px-6 pt-5">
            {avState && avState !== AV_STATES.READY ? (
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
            <div className="flex items-center gap-2 bg-black/[0.03] px-3 py-1.5 rounded-full border border-black/8">
              <div className={`w-2 h-2 rounded-full ${isRecording || serverRecording ? 'bg-red-500 animate-pulse' : serverTranscribing ? 'bg-blue-500 animate-pulse' : micError ? 'bg-amber-500' : 'bg-[#6F6F6F]/30'}`} />
              <span className="text-[10px] font-medium uppercase tracking-wider text-[#6F6F6F]"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                {voiceStatus}
              </span>
            </div>
            <div className="flex items-center gap-2 bg-black/[0.03] px-3 py-1.5 rounded-full border border-black/8">
              <div className={`w-2 h-2 rounded-full ${engagementTone}`} />
              <span className="text-[10px] font-medium uppercase tracking-wider text-[#6F6F6F]"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                Engagement {engagementStatus}{engagementConfidence ? ` · ${engagementConfidence}` : ''}
              </span>
            </div>
            <div className="bg-black/[0.03] px-3 py-1.5 rounded-full border border-black/8">
              <span className="text-[10px] font-medium uppercase tracking-wider text-[#6F6F6F]"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                Baseline {calibrationSkipped ? 'Skipped' : baselineLabel}
              </span>
            </div>
          </div>

          {/* Question — the primary focus of the screen */}
          <div className="flex-1 flex flex-col justify-center px-8 md:px-12 py-6 overflow-y-auto min-h-0">
            <div className="flex items-center gap-3 mb-5 flex-wrap">
              <span className="text-[11px] font-medium uppercase tracking-[0.15em] text-[#6F6F6F]"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                Question {String(round).padStart(2, '0')} / {String(totalRounds).padStart(2, '0')}
              </span>
              <span className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-black/[0.04] text-[#6F6F6F] capitalize"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                {currentSkill} · {difficulty}
              </span>
            </div>
            <p className="text-2xl md:text-3xl lg:text-[34px] font-normal text-black leading-[1.3] max-w-3xl"
              style={{ fontFamily: "'Instrument Serif', serif" }}>
              {question || 'Loading…'}
            </p>
          </div>

          {/* Compact self-view — small and out of the way so it isn't distracting */}
          <div className="absolute bottom-4 right-4 w-36 lg:w-48 aspect-video rounded-xl overflow-hidden border border-black/10 bg-black/[0.04] shadow-md">
            {isVideoOn
              ? <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
              : (
                <div className="w-full h-full flex flex-col items-center justify-center gap-1.5 px-2 text-center">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6F6F6F" strokeWidth="1.2">
                    <path d="M16 16v1a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2m5.66 0H14a2 2 0 0 1 2 2v3.34l1 1L23 7v10"/>
                    <line x1="1" y1="1" x2="23" y2="23"/>
                  </svg>
                  <span className="text-[9px] text-[#6F6F6F] leading-tight" style={{ fontFamily: "'Inter', sans-serif" }}>
                    {cameraError || 'Camera Off'}
                  </span>
                </div>
              )
            }
          </div>
        </div>

        <div className="flex flex-col gap-3 overflow-hidden min-h-0">
          {!isSupportedRoundType(roundType) ? (
            <div role="alert" data-testid="unsupported-round-type"
              className="rounded-2xl border border-red-300 bg-red-50 p-5 flex-1 flex flex-col justify-center">
              <h3 className="text-sm font-medium text-red-800"
                style={{ fontFamily: "'Inter', sans-serif" }}>Unsupported round type</h3>
              <p className="mt-2 text-xs leading-relaxed text-red-700"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                This round uses type &ldquo;{roundType}&rdquo;, which this version cannot
                render. Nothing was submitted and nothing was scored — your progress
                is saved.
              </p>
            </div>
          ) : (
          <div className="rounded-2xl border border-black/8 p-5 flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[10px] font-medium uppercase tracking-wider text-[#6F6F6F]"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                Answer Draft
                {draftNotice && (
                  <span className="ml-2 normal-case text-blue-600" role="status"> — {draftNotice}</span>
                )}
              </h3>
              <div className="flex items-center gap-3">
                {answerWordCount > 0 && (
                  <span className="text-[10px] text-[#6F6F6F]/60" style={{ fontFamily: "'Inter', sans-serif" }}>
                    {answerWordCount} words
                  </span>
                )}
                <label className="flex items-center gap-1.5 text-[10px] text-[#6F6F6F] select-none"
                  style={{ fontFamily: "'Inter', sans-serif" }}>
                  <input
                    type="checkbox"
                    checked={serverSttActive}
                    disabled={!hasBrowserSTT || isRecording || serverRecording || serverTranscribing || isScoring || currentScore !== null}
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
              disabled={isScoring || currentScore !== null}
              placeholder={isRecording || serverRecording ? 'Listening...' : serverTranscribing ? 'Transcribing...' : 'Type your answer here or use the microphone.'}
              className="flex-1 min-h-[180px] w-full resize-none rounded-xl border border-transparent bg-transparent text-sm leading-relaxed text-[#333] outline-none transition-colors placeholder:text-[#6F6F6F]/40 focus:border-black/10 focus:bg-black/[0.015] disabled:cursor-default"
              style={{ fontFamily: "'Inter', sans-serif" }}
            />
            {interimText && currentScore === null && (
              <p className="mt-3 rounded-xl bg-black/[0.03] px-3 py-2 text-xs italic text-[#6F6F6F]/70"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                {interimText}
              </p>
            )}
            {micError && currentScore === null && (
              <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                {micError}
              </p>
            )}
          </div>
          )}

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
              {currentRubric && (
                <div className="mt-4 space-y-2">
                  {['correctness', 'coverage', 'depth', 'clarity'].map((dim) => {
                    const val = Number(currentRubric[dim]);
                    if (!Number.isFinite(val)) return null;
                    const pct = Math.max(0, Math.min(100, val * 10));
                    return (
                      <div key={dim} className="flex items-center gap-2">
                        <span className="text-[10px] uppercase tracking-wider text-[#6F6F6F] w-[68px] shrink-0 capitalize"
                          style={{ fontFamily: "'Inter', sans-serif" }}>{dim}</span>
                        <div className="flex-1 h-1.5 rounded-full bg-black/5 overflow-hidden">
                          <div className="h-full rounded-full transition-all duration-500"
                            style={{ width: `${pct}%`, backgroundColor: scoreColor(pct) }} />
                        </div>
                        <span className="text-[10px] text-[#6F6F6F] w-7 text-right tabular-nums"
                          style={{ fontFamily: "'Inter', sans-serif" }}>{val.toFixed(1)}</span>
                      </div>
                    );
                  })}
                </div>
              )}
              {currentConcepts?.missing?.length > 0 && (
                <p className="mt-3 text-[11px] text-[#6F6F6F] leading-relaxed"
                  style={{ fontFamily: "'Inter', sans-serif" }}>
                  <span className="font-medium text-black">Review:</span> {currentConcepts.missing.slice(0, 4).join(', ')}
                </p>
              )}
            </div>
          )}

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsVideoOn(p => !p)}
              aria-label={isVideoOn ? 'Turn camera off' : 'Turn camera on'}
              title={isVideoOn ? 'Turn camera off' : 'Turn camera on'}
              className={`w-11 h-11 rounded-full flex items-center justify-center cursor-pointer transition-all border ${!isVideoOn ? 'bg-red-50 border-red-200 text-red-500' : 'bg-white border-black/10 text-[#6F6F6F]'}`}>
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
              className={`${serverSttActive ? 'h-11 min-w-[142px] px-4 gap-2' : 'w-11 h-11'} rounded-full flex items-center justify-center cursor-pointer transition-all border disabled:cursor-not-allowed disabled:opacity-40 ${voiceButtonBusy ? 'bg-red-50 border-red-200 text-red-500' : 'bg-white border-black/10 text-[#6F6F6F]'}`}>
              {serverTranscribing
                ? <span className="w-3.5 h-3.5 border border-current/30 border-t-current rounded-full animate-spin" />
                : voiceButtonBusy
                ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/></svg>
                : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
              }
              {serverSttActive && (
                <span className="text-xs font-medium" style={{ fontFamily: "'Inter', sans-serif" }}>
                  {serverTranscribing ? 'Transcribing' : serverRecording ? 'Stop' : 'Record (server)'}
                </span>
              )}
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
      )}
    </div>
  );
}
