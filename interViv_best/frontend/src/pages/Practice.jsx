import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import {
  fetchMe,
  fetchCompanies,
  fetchPracticeBank,
  fetchAvailability,
  startSession,
  saveInterviewState,
  fetchPresets,
  createPreset,
  deletePreset,
  fetchBuilderDraft,
  saveBuilderDraft,
  fetchTargetContext,
} from '../lib/api';
import CompanySelector from '../components/CompanySelector';
import ResourceLinks from '../components/ResourceLinks';
import AppNav from '../components/AppNav';
import AccountGate from '../components/AccountGate';
import SkillChipInput from '../components/SkillChipInput';
import PlannedScope from '../components/PlannedScope';
import InterviewResumePanel from '../components/InterviewResumePanel';
import { readScoped, writeScoped } from '../lib/accountStorage';
import {
  WIZARD_STORAGE_NAME,
  WIZARD_STORAGE_VERSION,
  restoreWizard,
  serializeWizard,
} from '../lib/uploadWizard';
import { COMMON_SKILLS } from '../lib/skillChips';
import { useAccountRetry } from '../lib/useAccountRetry';
import {
  roleRequiredSkills,
  PRACTICE_TRACKS,
  modeById,
  BLOCK_CATEGORIES,
  PRESET_VERSION,
  BUILDER_DRAFT_VERSION,
  blockCategoryButtonLabel,
  createBlockId,
  addBlock,
  removeBlock,
  moveBlock,
  duplicateBlock,
  formatBlockLabel,
  totalTimeSummary,
  validateBuilderBlocks,
  validateDraftPayload,
  loadLocalBuilderDraft,
  saveLocalBuilderDraft,
  mapFullInterviewToStartPayload,
  mapOaSqlToStartPayload,
  mapProblemItemToStartPayload,
  mapBlocksToStartPayload,
  mapStandaloneToStartPayload,
  applyTargetPrefill,
  isAvailabilityMessage,
  multiSkillTopicNote,
  payloadHasInterview,
  reconcileTopic,
  sharedTopicsForSkills,
  summarizeAvailability,
  summarizePlannedScope,
} from '../lib/practiceBuilder';

const DEFAULT_SKILLS = ['DBMS', 'OOP', 'DSA'];
const DEFAULT_STANDALONE_TOPICS = 'DBMS';

function stripClientOnly(payload) {
  const next = { ...payload };
  delete next._client_timer_seconds;
  return next;
}

function navigateToInterview(navigate, startResp, extras = {}) {
  const state = {
    candidateId: startResp.candidate_id,
    skill: (startResp.skills && startResp.skills[0]) || 'DBMS',
    allSkills: startResp.skills || [],
    sessionId: startResp.session_id,
    question: startResp.question,
    difficulty: startResp.difficulty,
    round_type: startResp.round_type || 'technical_short_answer',
    block_category: startResp.block_category || null,
    question_context: startResp.question_context || {},
    config_json: startResp.config_json || {},
    expires_at: startResp.expires_at || null,
    round: startResp.round || 1,
    elo: startResp.elo || 1200,
    totalRounds: startResp.total_rounds || 1,
    roundsPerSkill: startResp.rounds_per_skill || 1,
    ...extras,
  };
  saveInterviewState(state);
  navigate(`/interview/${startResp.session_id}`, { state });
}

export default function Practice() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const mode = searchParams.get('mode') || '';

  const { accountError, accountAttempt, retryAccount, onAccountError } = useAccountRetry();

  const [authReady, setAuthReady] = useState(false);
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');
  const [availability, setAvailability] = useState(null);
  const [busy, setBusy] = useState(false);
  const [skills, setSkills] = useState(DEFAULT_SKILLS);
  const [skillsExplicit, setSkillsExplicit] = useState(false);
  // Async target prefill reads the latest values, not a stale closure.
  const skillsRef = useRef(DEFAULT_SKILLS);
  const skillsExplicitRef = useRef(false);
  skillsRef.current = skills;
  skillsExplicitRef.current = skillsExplicit;
  const [prefillNote, setPrefillNote] = useState('');
  const [target, setTarget] = useState({ companyId: '', roleId: '' });
  // Phase 4A: assessment vs coached practice; follow-ups default off for assessment.
  const [practiceMode, setPracticeMode] = useState('coached_practice');
  const [allowOptionalFollowUps, setAllowOptionalFollowUps] = useState(false);

  // Full interview
  const [roundsPerSkill, setRoundsPerSkill] = useState(3);

  // OA + SQL
  const [oaDuration, setOaDuration] = useState(45);
  const [mcqCount, setMcqCount] = useState(10);
  const [sqlCases, setSqlCases] = useState(1);

  // Phase B standalone forms
  const [standaloneCount, setStandaloneCount] = useState(10);
  const [standaloneDuration, setStandaloneDuration] = useState(20);
  const [standaloneDifficulty, setStandaloneDifficulty] = useState('');
  const [standaloneTopics, setStandaloneTopics] = useState(DEFAULT_STANDALONE_TOPICS);
  const [standaloneTopic, setStandaloneTopic] = useState('');
  const [topicNote, setTopicNote] = useState('');
  const [topicMetadata, setTopicMetadata] = useState(null);
  const [topicMetadataError, setTopicMetadataError] = useState(false);

  // Phase B block builder
  const [blocks, setBlocks] = useState([]);
  const [builderLoaded, setBuilderLoaded] = useState(false);
  const [draftStatus, setDraftStatus] = useState('');
  const [presets, setPresets] = useState([]);
  const [presetName, setPresetName] = useState('');
  const draftTimer = useRef(null);
  const userId = user?.id || null;

  // Problem bank
  const [bank, setBank] = useState({ mcq: [], verbal: [], sql: [], coding: [], ml_primitives: [] });
  const [bankType, setBankType] = useState('all');
  const [bankDifficulty, setBankDifficulty] = useState('all');
  const [bankSkill, setBankSkill] = useState('all');
  const [selectedItem, setSelectedItem] = useState(null);

  // Resume state for main interview rounds (shared with upload wizard storage)
  const [resumeState, setResumeState] = useState({
    candidateId: '',
    fileName: '',
    extractedSkills: [],
    domainProfile: {},
  });

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        const u = me.user || me;
        const id = u.id || u.user_id || null;
        setUser(u);
        setAuthReady(true);
        const saved = restoreWizard(readScoped('session', id, WIZARD_STORAGE_NAME, WIZARD_STORAGE_VERSION));
        if (saved.candidateId || saved.extractedSkills?.length) {
          setResumeState({
            candidateId: saved.candidateId || '',
            fileName: saved.fileName || '',
            extractedSkills: saved.extractedSkills || [],
            domainProfile: saved.domainProfile || {},
          });
        }
        return fetchTargetContext().catch(() => null);
      })
      .then((data) => {
        if (cancelled || !data?.target) return;
        if (data.target.resume_ref) {
          setResumeState((prev) => (prev.candidateId ? prev : { ...prev, candidateId: data.target.resume_ref }));
        }
        if (data.target.company_id && data.target.role_id) {
          // The saved target is a default only: a target passed by the
          // Gap/Roadmap hop (or picked already) wins.
          setTarget((prev) => (prev.companyId && prev.roleId ? prev : {
            companyId: data.target.company_id,
            roleId: data.target.role_id,
          }));
        }
      })
      .catch((err) => {
        if (!cancelled) onAccountError(err);
      });
    return () => {
      cancelled = true;
    };
    // Load once per retry; mode changes (?mode=) must not refetch and reset the target.
  }, [accountAttempt]);

  useEffect(() => {
    if (!authReady || mode !== 'problems') return undefined;
    let cancelled = false;
    fetchPracticeBank()
      .then((data) => {
        if (!cancelled) setBank({ mcq: data.mcq || [], verbal: data.verbal || [], sql: data.sql || [], coding: data.coding || [], ml_primitives: data.ml_primitives || [] });
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load practice bank.');
      });
    return () => {
      cancelled = true;
    };
  }, [authReady, mode]);

  // Interview topic metadata (skill -> topics) for standalone + builder.
  // A failed load degrades to unrestricted topics (starting still works)
  // but says so, with a retry: per the explicit-topic contract, topics
  // are only offered when their per-skill scope is actually known.
  useEffect(() => {
    if (!authReady || (mode !== 'interview' && mode !== 'custom')) return undefined;
    let cancelled = false;
    setTopicMetadataError(false);
    fetchPracticeBank()
      .then((data) => {
        if (cancelled) return;
        setTopicMetadataError(false);
        setTopicMetadata(data.interview_topics || {});
      })
      .catch(() => {
        if (cancelled) return;
        setTopicMetadata({});
        setTopicMetadataError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [authReady, mode]);

  const retryTopicMetadata = () => {
    setTopicMetadataError(false);
    fetchPracticeBank()
      .then((data) => {
        setTopicMetadataError(false);
        setTopicMetadata(data.interview_topics || {});
      })
      .catch(() => {
        setTopicMetadata({});
        setTopicMetadataError(true);
      });
  };

  // Phase B: load builder draft (server first, local fallback) + presets.
  useEffect(() => {
    if (!authReady || mode !== 'custom') return undefined;
    let cancelled = false;
    fetchBuilderDraft()
      .then((data) => {
        if (cancelled) return;
        const serverBlocks = !validateDraftPayload(data) && data.blocks?.length ? data.blocks : null;
        const found = serverBlocks || loadLocalBuilderDraft(userId);
        if (found) setBlocks(found.map((b) => ({ ...b, id: b.id || createBlockId() })));
        setBuilderLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        const local = loadLocalBuilderDraft(userId);
        if (local) setBlocks(local.map((b) => ({ ...b, id: b.id || createBlockId() })));
        setBuilderLoaded(true);
      });
    fetchPresets()
      .then((data) => {
        if (!cancelled) setPresets(data.presets || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [authReady, mode, userId]);

  // Phase B: autosave builder drafts (debounced server + immediate local).
  useEffect(() => {
    if (!authReady || mode !== 'custom' || !builderLoaded) return undefined;
    saveLocalBuilderDraft(userId, blocks);
    setDraftStatus(blocks.length ? 'Saving…' : '');
    if (draftTimer.current) clearTimeout(draftTimer.current);
    draftTimer.current = setTimeout(() => {
      saveBuilderDraft({ version: BUILDER_DRAFT_VERSION, blocks })
        .then(() => setDraftStatus(blocks.length ? 'Draft saved' : ''))
        .catch(() => setDraftStatus('Local only (server unavailable)'));
    }, 800);
    return () => {
      if (draftTimer.current) clearTimeout(draftTimer.current);
    };
  }, [blocks, authReady, mode, builderLoaded, userId]);

  // Soft-load role skills when company graph is available. Prefill only:
  // an explicitly chosen topic list is never overridden.
  useEffect(() => {
    if (!target.companyId || !target.roleId) return undefined;
    let cancelled = false;
    fetchCompanies()
      .then((data) => {
        if (cancelled) return;
        const company = (data.companies || []).find((c) => c.id === target.companyId);
        const role = (company?.roles || []).find((r) => r.id === target.roleId);
        const req = roleRequiredSkills(role);
        const explicit = skillsExplicitRef.current;
        const { skills: next, applied } = applyTargetPrefill(skillsRef.current, req, explicit);
        if (applied) {
          setSkills(next);
          setPrefillNote(`Prefilled from ${role?.title || 'target role'} required skills.`);
        } else if (explicit) {
          setPrefillNote('Showing your explicitly chosen topics; target prefill skipped.');
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target.companyId, target.roleId]);

  // Connected hop: gap/roadmap weak-area skills arrive as prefill, not
  // an override. Runs once per navigation state.
  const hopAppliedFor = useRef(null);
  useEffect(() => {
    const incoming = location.state?.prefilledSkills;
    if (!Array.isArray(incoming) || !incoming.length) return undefined;
    const key = JSON.stringify([location.key, incoming]);
    if (hopAppliedFor.current === key) return undefined;
    hopAppliedFor.current = key;
    const { skills: next, applied } = applyTargetPrefill(skills, incoming, skillsExplicit);
    if (applied) {
      setSkills(next);
      // Weak areas are a deliberate choice: mark them explicit at once so a
      // target default arriving later cannot overwrite them.
      setSkillsExplicit(true);
      skillsExplicitRef.current = true;
      skillsRef.current = next;
      setPrefillNote(
        `Prefilled from ${location.state?.prefillSource || 'gap analysis'} weak areas.`
      );
    }
    // Adopt the hop's target only when no target is set yet.
    const hopCompany = location.state?.targetCompanyId || '';
    const hopRole = location.state?.targetRoleId || '';
    if (hopCompany && hopRole && !target.companyId && !target.roleId) {
      setTarget({ companyId: hopCompany, roleId: hopRole });
    }
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key]);

  const standaloneSkillList = useMemo(
    () => standaloneTopics.split(',').map((s) => s.trim()).filter(Boolean),
    [standaloneTopics]
  );

  // Planned scope preview: the server's plan for the current interview
  // selection, from the same endpoint the start button probes.
  const [plannedScope, setPlannedScope] = useState(null);
  const scopePayload = useMemo(() => {
    let mapped = null;
    if (mode === 'interview') {
      mapped = mapStandaloneToStartPayload('interview', {
        skills: standaloneSkillList,
        count: standaloneCount,
        difficulty: standaloneDifficulty || undefined,
        topic: standaloneTopic || undefined,
        targetCompanyId: target.companyId,
        targetRoleId: target.roleId,
      });
    } else if (mode === 'full') {
      mapped = mapFullInterviewToStartPayload({
        skills,
        roundsPerSkill,
        targetCompanyId: target.companyId,
        targetRoleId: target.roleId,
      });
    } else if (mode === 'custom') {
      mapped = mapBlocksToStartPayload(blocks, {
        targetCompanyId: target.companyId,
        targetRoleId: target.roleId,
      });
    }
    return mapped?.payload && payloadHasInterview(mapped.payload) ? mapped.payload : null;
  }, [mode, standaloneSkillList, standaloneCount, standaloneDifficulty, standaloneTopic,
    skills, roundsPerSkill, blocks, target.companyId, target.roleId]);
  useEffect(() => {
    if (!scopePayload || !userId) {
      setPlannedScope(null);
      return undefined;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      fetchAvailability(stripClientOnly(scopePayload))
        .then((resp) => {
          if (!cancelled) setPlannedScope(summarizePlannedScope(resp));
        })
        .catch(() => {
          if (!cancelled) setPlannedScope(null);
        });
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [scopePayload, userId]);
  const metadataReady = topicMetadata != null && Object.keys(topicMetadata).length > 0;
  const standaloneTopicOptions = useMemo(
    () => sharedTopicsForSkills(standaloneSkillList, topicMetadata),
    [standaloneSkillList, topicMetadata]
  );
  const standaloneSharedTopicNote = useMemo(
    () => multiSkillTopicNote(standaloneSkillList, topicMetadata, metadataReady),
    [standaloneSkillList, topicMetadata, metadataReady]
  );
  // Metadata failure must never look selected while starting unrestricted.
  // Held explicit topics block start until retry or the user clears them.
  const interviewTopicHeldOnMetadataError = Boolean(
    topicMetadataError && standaloneTopic
  );
  const customTopicsHeldOnMetadataError = Boolean(
    topicMetadataError
    && blocks.some((b) => b.category === 'interview' && Boolean(b.topic))
  );

  // Standalone interview: clear a topic the (changed) skills no longer
  // offer, and say so. Skipped until metadata loads so a slow or failed
  // load never destroys a selection.
  useEffect(() => {
    if (mode !== 'interview' || !metadataReady || !standaloneTopic) return;
    const { cleared } = reconcileTopic(standaloneTopic, standaloneSkillList, topicMetadata);
    if (cleared) {
      setStandaloneTopic('');
      setTopicNote(`Topic '${standaloneTopic}' isn't offered for the selected skills, so it was cleared.`);
    }
  }, [mode, metadataReady, standaloneSkillList, topicMetadata, standaloneTopic]);

  // Builder: one-shot sweep when metadata arrives, so stale saved topics
  // (drafts/presets from changed banks) reconcile visibly.
  useEffect(() => {
    if (mode !== 'custom' || !builderLoaded || !metadataReady) return undefined;
    const stale = blocks.filter(
      (b) => b.category === 'interview' && b.topic
        && !sharedTopicsForSkills(b.skills, topicMetadata).includes(b.topic)
    );
    if (stale.length === 0) return undefined;
    const ids = new Set(stale.map((b) => b.id));
    setBlocks((prev) => prev.map((b) => (ids.has(b.id) ? { ...b, topic: undefined } : b)));
    setTopicNote(
      `${stale.length} saved topic${stale.length === 1 ? ' was' : 's were'} no longer offered and ${stale.length === 1 ? 'was' : 'were'} cleared.`
    );
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, builderLoaded, metadataReady]);

  const bankItems = useMemo(() => {
    let items = [];
    if (bankType === 'all' || bankType === 'mcq') {
      items = items.concat((bank.mcq || []).map((q) => ({ ...q, type: 'mcq' })));
    }
    if (bankType === 'all' || bankType === 'verbal') {
      items = items.concat((bank.verbal || []).map((q) => ({ ...q, type: 'mcq', category: 'verbal' })));
    }
    if (bankType === 'all' || bankType === 'sql') {
      items = items.concat((bank.sql || []).map((q) => ({ ...q, type: 'sql' })));
    }
    if (bankType === 'all' || bankType === 'coding') {
      items = items.concat((bank.coding || []).map((q) => ({ ...q, type: 'coding', skill: 'DSA' })));
    }
    if (bankDifficulty !== 'all') {
      items = items.filter((i) => String(i.difficulty).toLowerCase() === bankDifficulty);
    }
    if (bankSkill !== 'all') {
      items = items.filter((i) => String(i.skill || '') === bankSkill);
    }
    return items;
  }, [bank, bankType, bankDifficulty, bankSkill]);

  const skillFilterOptions = useMemo(() => {
    const set = new Set();
    (bank.mcq || []).forEach((q) => q.skill && set.add(q.skill));
    (bank.verbal || []).forEach((q) => q.skill && set.add(q.skill));
    (bank.sql || []).forEach(() => set.add('SQL'));
    (bank.coding || []).forEach(() => set.add('DSA'));
    return Array.from(set).sort();
  }, [bank]);

  const setMode = (id) => {
    setError('');
    setAvailability(null);
    setTopicNote('');
    setSearchParams(id ? { mode: id } : {});
  };

  const skillSuggestions = useMemo(
    () => [...new Set([...COMMON_SKILLS, ...Object.keys(topicMetadata || {})])],
    [topicMetadata]
  );

  const updateBlockSkills = (block, index, value) => {
    const nextSkills = Array.isArray(value)
      ? value
      : value.split(',').map((s) => s.trim()).filter(Boolean);
    if (block.category === 'interview' && block.topic && metadataReady) {
      const { cleared } = reconcileTopic(block.topic, nextSkills, topicMetadata);
      if (cleared) {
        setTopicNote(`Block ${index + 1}: topic '${block.topic}' isn't offered for these skills, so it was cleared.`);
        setBlocks((prev) => prev.map((b) => (b.id === block.id ? { ...b, skills: nextSkills, topic: undefined } : b)));
        return;
      }
    }
    setBlocks((prev) => prev.map((b) => (b.id === block.id ? { ...b, skills: nextSkills } : b)));
  };

  // Start-time content failures (422/503 with availability wording) go
  // to the availability panel; malformed-request 422s keep the error box.
  const reportStartIssue = (err) => {
    const message = err?.message || 'Could not start session.';
    if ((err?.status === 422 || err?.status === 503) && isAvailabilityMessage(message)) {
      setAvailability({
        title: /reviewed/i.test(message)
          ? 'Assessed practice is unavailable'
          : 'Practice content is unavailable',
        reasons: [message],
        reviewedOnly: /reviewed/i.test(message),
      });
    } else {
      setError(message);
    }
  };

  const runStart = async (mapped) => {
    if (mapped.error) {
      setError(mapped.error);
      return;
    }
    // Never submit unrestricted while the UI still implies a selected topic.
    if (interviewTopicHeldOnMetadataError || customTopicsHeldOnMetadataError) {
      setError(
        'Interview topics could not be loaded. Retry topic loading, or clear the selected topic before starting unrestricted.'
      );
      return;
    }
    setBusy(true);
    setError('');
    setAvailability(null);
    try {
      const body = stripClientOnly(mapped.payload);
      if (resumeState.candidateId && !body.candidate_id) {
        body.candidate_id = resumeState.candidateId;
      }
      body.practice_mode = practiceMode;
      body.allow_optional_follow_ups =
        practiceMode === 'assessment' ? false : allowOptionalFollowUps;
      if (payloadHasInterview(body) && allowOptionalFollowUps && practiceMode !== 'assessment') {
        // Opt interview blocks into optional follow-ups when the session setting is on.
        body.blocks = (body.blocks || []).map((b) => (
          b?.category === 'interview' || b?.round_type === 'technical_short_answer'
            ? { ...b, allow_optional_follow_ups: true }
            : b
        ));
      }
      if (payloadHasInterview(body)) {
        // Pre-commit probe: interview content resolves per skill on the
        // server. Unavailable inventory stops here, before any session.
        // A probe failure falls through to start; the server re-validates.
        try {
          const summary = summarizeAvailability(await fetchAvailability(body));
          if (summary) {
            setAvailability(summary);
            return;
          }
        } catch {
          /* fall through to start */
        }
      }
      const resp = await startSession(body);
      navigateToInterview(navigate, resp);
    } catch (err) {
      reportStartIssue(err);
    } finally {
      setBusy(false);
    }
  };

  const handleResumeExtracted = ({ candidateId, fileName, extractedSkills, domainProfile }) => {
    const nextState = {
      candidateId: candidateId || '',
      fileName: fileName || '',
      extractedSkills: extractedSkills || [],
      domainProfile: domainProfile || {},
    };
    setResumeState(nextState);
    // The extracted list is alphabetical, not ranked, so nothing is chosen on
    // the candidate's behalf. This mode's placeholder default is cleared and
    // the interview covers only the skills they confirm; a selection they
    // already made is kept.
    const found = extractedSkills || [];
    let selected = skillsRef.current;
    if (found.length > 0) {
      if (mode === 'full' && !skillsExplicitRef.current) {
        selected = [];
        skillsRef.current = selected;
        setSkills(selected);
      }
      if (mode === 'interview') {
        setStandaloneTopics((prev) => (prev === DEFAULT_STANDALONE_TOPICS ? '' : prev));
      }
      setPrefillNote(`Found ${found.length} skill${found.length === 1 ? '' : 's'} in ${fileName || 'your resume'}. Choose the ones to practise.`);
    }
    if (userId) {
      writeScoped(
        'session',
        userId,
        WIZARD_STORAGE_NAME,
        serializeWizard({
          ...nextState,
          selectedSkills: selected,
          targetSelection: target,
        }),
        WIZARD_STORAGE_VERSION
      );
    }
  };

  if (!authReady) {
    return (
      <main className="min-h-screen bg-[var(--color-surface)] text-[var(--color-ink)] grid place-items-center">
        <AccountGate error={accountError} onRetry={retryAccount} />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--color-surface)] text-[var(--color-ink)]">
      <div className="app-container">
        <AppNav
          userId={user?.id || user?.user_id || null}
          roleId={target.roleId || user?.target_role_id || null}
        />

        <header className="app-page-hero">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--color-accent)]">
            Practice Hub
          </p>
          <h1
            className="mt-2 text-[length:var(--text-3xl)] font-semibold tracking-normal sm:text-[length:var(--text-5xl)]"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Choose how you want to practice
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-[var(--color-ink-muted)]">
            Standalone blocks, guided modes, and a custom builder for Verbal, OA, SQL, coding, and interview practice.
            Coding practice runs Python with visible examples and hidden-test scoring; SQL practice uses the sandboxed SQL runner only.
          </p>
          <p className="mt-3 text-sm">
            <Link to="/problems" className="font-semibold text-[var(--color-ink)] underline-offset-2 hover:underline">
              Open coding Problems →
            </Link>
            <span className="text-[var(--color-ink-muted)]"> Python problems with examples and coach hints.</span>
          </p>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:gap-6">
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-[var(--color-ink)]">Session mode</span>
              <select
                className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2"
                value={practiceMode}
                onChange={(e) => {
                  const next = e.target.value;
                  setPracticeMode(next);
                  if (next === 'assessment') setAllowOptionalFollowUps(false);
                }}
                aria-label="Session mode"
              >
                <option value="coached_practice">Coached practice</option>
                <option value="assessment">Assessment</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-[var(--color-ink)]">
              <input
                type="checkbox"
                checked={allowOptionalFollowUps && practiceMode !== 'assessment'}
                disabled={practiceMode === 'assessment'}
                onChange={(e) => setAllowOptionalFollowUps(e.target.checked)}
              />
              Allow optional follow-ups (Interview blocks; max 1 per parent, 2 per block)
            </label>
          </div>
          {practiceMode === 'assessment' && (
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Assessment keeps hints and follow-ups off by default. Assisted work is labeled Practiced with help and stays out of primary metrics.
            </p>
          )}
        </header>

        {error && (
          <div className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-danger)]/30 bg-[var(--color-danger-soft)] px-4 py-3 text-sm text-[var(--color-danger)]">
            {error}
          </div>
        )}

        {availability && (
          <div
            data-testid="availability-notice"
            role="alert"
            className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] px-4 py-3"
          >
            <h2 className="text-base font-semibold text-[var(--color-ink)]">{availability.title}</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--color-ink-muted)]">
              {availability.reasons.map((reason, index) => (
                <li key={index}>{reason}</li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-[var(--color-ink-muted)]">
              No session was started and nothing was consumed. Adjust the topics or settings and try again.
            </p>
          </div>
        )}

        {!mode && (
          <div className="mt-6 space-y-8" data-testid="practice-tracks">
            {PRACTICE_TRACKS.map((track) => (
              <section key={track.id} aria-labelledby={`track-${track.id}`} data-track={track.id}>
                <h2 id={`track-${track.id}`} className="text-lg font-semibold text-[var(--color-ink)]">{track.title}</h2>
                <p className="mt-1 text-sm text-[var(--color-ink-muted)]">{track.blurb}</p>
                <div className="mt-3 grid gap-4 sm:grid-cols-2">
                  {track.modes.map(modeById).filter(Boolean).map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      data-mode={m.id}
                      onClick={() => setMode(m.id)}
                      className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5 text-left shadow-sm transition hover:border-slate-300"
                    >
                      <h3 className="text-base font-semibold text-[var(--color-ink)]">{m.title}</h3>
                      <p className="mt-2 text-sm leading-6 text-[var(--color-ink-muted)]">{m.blurb}</p>
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}

        {mode && (
          <div className="mt-4">
            <button
              type="button"
              onClick={() => setMode('')}
              className="text-sm text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
            >
              ← All modes
            </button>
          </div>
        )}

        {(mode === 'full' || mode === 'interview') && (
          <InterviewResumePanel
            candidateId={resumeState.candidateId}
            fileName={resumeState.fileName}
            extractedSkills={resumeState.extractedSkills}
            selectedSkills={mode === 'full' ? skills : standaloneSkillList}
            onResumeExtracted={handleResumeExtracted}
            onSkillsChange={(next) => {
              if (mode === 'full') {
                setSkillsExplicit(true);
                skillsExplicitRef.current = true;
                skillsRef.current = next;
                setPrefillNote('');
                setSkills(next);
              } else {
                setStandaloneTopics(next.join(', '));
              }
            }}
          />
        )}

        {(mode === 'full' || mode === 'oa_sql' || mode === 'custom') && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--color-accent)]">
              Target role & skills
            </h3>
            <div className="mt-3">
              <CompanySelector
                isAuthenticated={Boolean(user)}
                initialCompanyId={target.companyId}
                initialRoleId={target.roleId}
                onSelectionChange={setTarget}
              />
            </div>
            <div className="mt-4">
              <SkillChipInput
                label="Skills"
                testId="practice-skills"
                value={skills}
                suggestions={skillSuggestions}
                onChange={(next) => {
                  setSkillsExplicit(true);
                  setPrefillNote('');
                  setSkills(next);
                }}
              />
            </div>
            {prefillNote && (
              <p className="mt-2 text-xs text-[var(--color-ink-muted)]">{prefillNote}</p>
            )}
          </section>
        )}

        {(mode === 'verbal' || mode === 'oa' || mode === 'sql' || mode === 'coding' || mode === 'system_design' || mode === 'ml_primitives' || mode === 'interview') && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--color-accent)]">
              Target (optional)
            </h3>
            <div className="mt-3">
              <CompanySelector
                isAuthenticated={Boolean(user)}
                initialCompanyId={target.companyId}
                initialRoleId={target.roleId}
                onSelectionChange={setTarget}
              />
            </div>
            <p className="mt-3 text-xs text-[var(--color-ink-muted)]">
              Targets may prefill settings but never override an explicitly chosen topic.
            </p>
          </section>
        )}

        {mode === 'full' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Full interview</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Starts a multi-skill free-text session. Difficulty follows your Elo (not a separate start field). Voice
              input is available on the interview page.
            </p>
            <label className="mt-4 block text-sm">
              Rounds per skill
              <input
                type="number"
                min={1}
                max={10}
                className="mt-1 w-32 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                value={roundsPerSkill}
                onChange={(e) => setRoundsPerSkill(Number(e.target.value))}
              />
            </label>
            <PlannedScope scope={plannedScope} />
            <button
              type="button"
              disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() =>
                runStart(
                  mapFullInterviewToStartPayload({
                    skills,
                    roundsPerSkill,
                    candidateId: resumeState.candidateId || undefined,
                    targetCompanyId: target.companyId,
                    targetRoleId: target.roleId,
                  })
                )
              }
            >
              {busy ? 'Starting…' : 'Start full interview'}
            </button>
          </section>
        )}

        {mode === 'oa_sql' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">OA + SQL</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              One MCQ block, then SQL problem(s). This is not “OA + Coding” — there is no DSA coding judge.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <label className="text-sm">
                Duration (minutes)
                <input
                  type="number"
                  min={10}
                  max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={oaDuration}
                  onChange={(e) => setOaDuration(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                MCQ count
                <input
                  type="number"
                  min={1}
                  max={30}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={mcqCount}
                  onChange={(e) => setMcqCount(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                SQL cases
                <input
                  type="number"
                  min={1}
                  max={5}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={sqlCases}
                  onChange={(e) => setSqlCases(Number(e.target.value))}
                />
              </label>
            </div>
            <button
              type="button"
              disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() =>
                runStart(
                  mapOaSqlToStartPayload({
                    skills,
                    durationMinutes: oaDuration,
                    mcqCount,
                    sqlCases,
                    targetCompanyId: target.companyId,
                    targetRoleId: target.roleId,
                  })
                )
              }
            >
              {busy ? 'Starting…' : 'Start OA + SQL'}
            </button>
          </section>
        )}

        {mode === 'verbal' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Verbal Ability</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              English MCQs only — grammar, vocabulary, comprehension, ordering, idioms. Not a speaking assessment.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                Questions (1–30)
                <input
                  type="number" min={1} max={30}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneCount}
                  onChange={(e) => setStandaloneCount(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Time budget (minutes)
                <input
                  type="number" min={1} max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDuration}
                  onChange={(e) => setStandaloneDuration(Number(e.target.value))}
                />
              </label>
            </div>
            <button
              type="button" disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() => runStart(mapStandaloneToStartPayload('verbal', {
                count: standaloneCount, durationMinutes: standaloneDuration,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}
            >
              {busy ? 'Starting…' : 'Start Verbal practice'}
            </button>
          </section>
        )}

        {mode === 'oa' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">OA practice</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Technical MCQs restricted to your selected topics. Other subjects are never mixed in to fill the count.
            </p>
            <div className="mt-4">
              <SkillChipInput
                label="Topics"
                testId="oa-topics"
                value={standaloneSkillList}
                suggestions={skillSuggestions}
                onChange={(next) => setStandaloneTopics(next.join(', '))}
              />
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <label className="text-sm">
                Questions (1–30)
                <input
                  type="number" min={1} max={30}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneCount}
                  onChange={(e) => setStandaloneCount(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Time budget (minutes)
                <input
                  type="number" min={1} max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDuration}
                  onChange={(e) => setStandaloneDuration(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Difficulty
                <select
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDifficulty}
                  onChange={(e) => setStandaloneDifficulty(e.target.value)}
                >
                  <option value="">Mixed</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </label>
            </div>
            <button
              type="button" disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() => runStart(mapStandaloneToStartPayload('oa', {
                skills: standaloneTopics.split(',').map((s) => s.trim()).filter(Boolean),
                count: standaloneCount, durationMinutes: standaloneDuration,
                difficulty: standaloneDifficulty || undefined,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}
            >
              {busy ? 'Starting…' : 'Start OA practice'}
            </button>
          </section>
        )}

        {mode === 'sql' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">SQL practice</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              SQL problems with schemas and execution-based evaluation.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                Time budget (minutes)
                <input
                  type="number" min={1} max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDuration}
                  onChange={(e) => setStandaloneDuration(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Difficulty
                <select
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDifficulty}
                  onChange={(e) => setStandaloneDifficulty(e.target.value)}
                >
                  <option value="">Mixed</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </label>
            </div>
            <button
              type="button" disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() => runStart(mapStandaloneToStartPayload('sql', {
                durationMinutes: standaloneDuration,
                difficulty: standaloneDifficulty || undefined,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}
            >
              {busy ? 'Starting…' : 'Start SQL practice'}
            </button>
          </section>
        )}

        {mode === 'coding' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Coding practice</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Python problems with visible examples and hidden-test scoring (60% visible, 40% hidden).
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                Time budget (minutes)
                <input
                  type="number" min={1} max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDuration}
                  onChange={(e) => setStandaloneDuration(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Difficulty
                <select
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDifficulty}
                  onChange={(e) => setStandaloneDifficulty(e.target.value)}
                >
                  <option value="">Mixed</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </label>
            </div>
            <button
              type="button" disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() => runStart(mapStandaloneToStartPayload('coding', {
                durationMinutes: standaloneDuration,
                difficulty: standaloneDifficulty || undefined,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}
            >
              {busy ? 'Starting…' : 'Start coding practice'}
            </button>
          </section>
        )}

        {mode === 'ml_primitives' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-lg font-semibold">ML primitives</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">Implement numerical algorithms in Python. Submissions are saved without being run or graded; scoring is unavailable.</p>
            <label className="mt-4 block text-sm">Problem
              <select value={selectedItem?.type === 'ml_primitives' ? selectedItem.id : ''}
                onChange={e => setSelectedItem(bank.ml_primitives.find(p => p.id === e.target.value) || null)}
                className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2">
                <option value="">Choose automatically</option>
                {bank.ml_primitives.map(p => <option key={p.id} value={p.id}>{p.title} · {p.difficulty}</option>)}
              </select>
            </label>
            <label className="mt-4 block text-sm">Time budget (minutes)
              <input type="number" min={1} max={180} value={standaloneDuration}
                onChange={e => setStandaloneDuration(Number(e.target.value))}
                className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2" />
            </label>
            <button type="button" disabled={busy}
              className="mt-4 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              onClick={() => runStart(mapStandaloneToStartPayload('ml_primitives', {
                durationMinutes: standaloneDuration,
                problemId: selectedItem?.type === 'ml_primitives' ? selectedItem.id : undefined,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}>
              {busy ? 'Starting…' : 'Start ML primitives'}
            </button>
          </section>
        )}

        {mode === 'system_design' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">System design</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Design prompts with an explicit self-assessment rubric. Scores are self-reported — diagrams are not auto-scored.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                Prompts (1–5)
                <input
                  type="number" min={1} max={5}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneCount}
                  onChange={(e) => setStandaloneCount(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Time budget (minutes)
                <input
                  type="number" min={1} max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDuration}
                  onChange={(e) => setStandaloneDuration(Number(e.target.value))}
                />
              </label>
            </div>
            <button
              type="button" disabled={busy}
              className="mt-4 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              onClick={() => runStart(mapStandaloneToStartPayload('system_design', {
                count: Math.min(5, Math.max(1, Number(standaloneCount) || 1)),
                durationMinutes: standaloneDuration,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}
            >
              {busy ? 'Starting…' : 'Start system design'}
            </button>
          </section>
        )}

        {mode === 'interview' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Interview practice</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Technical/HR questions with text and voice input on the interview page.
            </p>
            <div className="mt-4">
              <SkillChipInput
                label="Skills"
                testId="interview-skills"
                value={standaloneSkillList}
                suggestions={skillSuggestions}
                onChange={(next) => setStandaloneTopics(next.join(', '))}
              />
            </div>
            {topicMetadataError && (
              <p className="mt-4 text-xs text-[var(--color-danger)]" role="alert">
                {interviewTopicHeldOnMetadataError
                  ? `Interview topics could not be loaded. Topic “${standaloneTopic}” is still selected — retry loading, or clear the topic before starting unrestricted.`
                  : 'Interview topics could not be loaded. Starting without a topic filter is allowed.'}
                {' '}
                <button type="button" className="underline" onClick={retryTopicMetadata}>
                  Retry
                </button>
                {interviewTopicHeldOnMetadataError && (
                  <>
                    {' '}
                    <button
                      type="button"
                      className="underline"
                      onClick={() => {
                        setStandaloneTopic('');
                        setTopicNote('');
                      }}
                    >
                      Clear topic
                    </button>
                  </>
                )}
              </p>
            )}
            {!topicMetadataError && standaloneSharedTopicNote && (
              <p className="mt-4 text-xs text-[var(--color-ink-muted)]" role="status">
                {standaloneSharedTopicNote}
              </p>
            )}
            {(standaloneTopicOptions.length > 0 || interviewTopicHeldOnMetadataError) && (
              <label className="mt-4 block text-sm">
                Topic (optional)
                <select
                  aria-label="Interview topic"
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneTopic}
                  disabled={topicMetadataError}
                  onChange={(e) => {
                    setStandaloneTopic(e.target.value);
                    setTopicNote('');
                  }}
                >
                  <option value="">All topics</option>
                  {standaloneTopicOptions.map((topic) => (
                    <option key={topic} value={topic}>
                      {topic}
                    </option>
                  ))}
                  {interviewTopicHeldOnMetadataError
                    && !standaloneTopicOptions.includes(standaloneTopic) && (
                    <option value={standaloneTopic}>{standaloneTopic}</option>
                  )}
                </select>
              </label>
            )}
            {topicNote && (
              <p className="mt-2 text-xs text-[var(--color-ink-muted)]" role="status">{topicNote}</p>
            )}
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                Questions (1–10)
                <input
                  type="number" min={1} max={10}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneCount}
                  onChange={(e) => setStandaloneCount(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Difficulty
                <select
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDifficulty}
                  onChange={(e) => setStandaloneDifficulty(e.target.value)}
                >
                  <option value="">Adaptive (Elo)</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </label>
            </div>
            <PlannedScope scope={plannedScope} />
            <button
              type="button" disabled={busy || interviewTopicHeldOnMetadataError}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() => runStart(mapStandaloneToStartPayload('interview', {
                skills: standaloneSkillList,
                count: standaloneCount,
                difficulty: standaloneDifficulty || undefined,
                topic: standaloneTopic || undefined,
                candidateId: resumeState.candidateId || undefined,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}
            >
              {busy ? 'Starting…' : 'Start interview practice'}
            </button>
          </section>
        )}

        {mode === 'custom' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Custom interview builder</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Add, reorder, and repeat Verbal, OA, SQL, coding, system design, ML primitives, and interview blocks with independent settings.
              If your settings cannot be combined, you will see an explanation before starting.
            </p>
            {!builderLoaded && (
              <p className="mt-4 text-sm text-[var(--color-ink-muted)]">Loading saved draft…</p>
            )}
            {builderLoaded && (
              <>
                <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Add block">
                  {BLOCK_CATEGORIES.map((category) => (
                    <button
                      key={category}
                      type="button"
                      onClick={() => setBlocks((prev) => addBlock(prev, category))}
                      className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold hover:border-slate-400"
                    >
                      + {blockCategoryButtonLabel(category)}
                    </button>
                  ))}
                </div>

                {blocks.length === 0 && (
                  <p className="mt-4 text-sm text-[var(--color-ink-muted)]">
                    No blocks yet. Add Verbal, OA, SQL, coding, system design, ML primitives, or interview blocks above. Adding Verbal never erases your sequence.
                  </p>
                )}

                <ol className="mt-4 space-y-3">
                  {blocks.map((block, index) => (
                    <li
                      key={block.id}
                      className="rounded-[var(--radius-card)] border border-[var(--color-border)] p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-[var(--color-ink)]">
                          {index + 1}. {formatBlockLabel(block)}
                        </p>
                        <div className="flex flex-wrap gap-1.5" role="group" aria-label={`Reorder block ${index + 1}`}>
                          <button
                            type="button"
                            aria-label={`Move block ${index + 1} up`}
                            disabled={index === 0}
                            onClick={() => setBlocks((prev) => moveBlock(prev, block.id, 'up'))}
                            className="rounded border border-[var(--color-border)] px-2 py-1 text-xs disabled:opacity-40"
                          >
                            ↑ Up
                          </button>
                          <button
                            type="button"
                            aria-label={`Move block ${index + 1} down`}
                            disabled={index === blocks.length - 1}
                            onClick={() => setBlocks((prev) => moveBlock(prev, block.id, 'down'))}
                            className="rounded border border-[var(--color-border)] px-2 py-1 text-xs disabled:opacity-40"
                          >
                            ↓ Down
                          </button>
                          <button
                            type="button"
                            aria-label={`Repeat block ${index + 1}`}
                            onClick={() => setBlocks((prev) => duplicateBlock(prev, block.id))}
                            className="rounded border border-[var(--color-border)] px-2 py-1 text-xs"
                          >
                            Repeat
                          </button>
                          <button
                            type="button"
                            aria-label={`Remove block ${index + 1}`}
                            onClick={() => setBlocks((prev) => removeBlock(prev, block.id))}
                            className="rounded border border-[var(--color-danger)]/40 px-2 py-1 text-xs text-[var(--color-danger)]"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                      <div className="mt-3 grid gap-3 sm:grid-cols-2">
                        {block.category !== 'verbal' && block.category !== 'sql' && (
                          <SkillChipInput
                            label={block.category === 'oa' ? 'Topics' : 'Skills'}
                            value={block.skills || []}
                            suggestions={skillSuggestions}
                            onChange={(next) => updateBlockSkills(block, index, next)}
                          />
                        )}
                        {block.category === 'interview' && (() => {
                          if (topicMetadataError) {
                            return (
                              <div className="text-xs text-[var(--color-danger)]" role="alert">
                                <p>
                                  Topics unavailable.
                                  {block.topic
                                    ? ` Topic “${block.topic}” is still selected — retry, or clear it before starting unrestricted.`
                                    : ' Starting without a topic filter is allowed.'}
                                  {' '}
                                  <button type="button" className="underline" onClick={retryTopicMetadata}>
                                    Retry
                                  </button>
                                  {block.topic && (
                                    <>
                                      {' '}
                                      <button
                                        type="button"
                                        className="underline"
                                        onClick={() => {
                                          setBlocks((prev) => prev.map((b) => (
                                            b.id === block.id ? { ...b, topic: undefined } : b
                                          )));
                                        }}
                                      >
                                        Clear topic
                                      </button>
                                    </>
                                  )}
                                </p>
                              </div>
                            );
                          }
                          const options = sharedTopicsForSkills(block.skills, topicMetadata);
                          if (options.length === 0) {
                            const note = multiSkillTopicNote(block.skills, topicMetadata, metadataReady);
                            if (!note) return null;
                            return (
                              <p className="text-xs text-[var(--color-ink-muted)]" role="status">
                                {note}
                              </p>
                            );
                          }
                          return (
                            <label className="text-xs text-[var(--color-ink-muted)]">
                              Topic (optional)
                              <select
                                aria-label={`Topic for block ${index + 1}`}
                                className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] bg-white px-3 py-2 text-sm text-[var(--color-ink)]"
                                value={block.topic || ''}
                                onChange={(e) => {
                                  const value = e.target.value || undefined;
                                  setBlocks((prev) => prev.map((b) => (b.id === block.id ? { ...b, topic: value } : b)));
                                  setTopicNote('');
                                }}
                              >
                                <option value="">All topics</option>
                                {options.map((topic) => (
                                  <option key={topic} value={topic}>
                                    {topic}
                                  </option>
                                ))}
                              </select>
                            </label>
                          );
                        })()}
                        {block.category === 'verbal' && (
                          <p className="text-xs text-[var(--color-ink-muted)]">
                            Topics: Verbal Ability (fixed English MCQs)
                          </p>
                        )}
                        <label className="text-xs text-[var(--color-ink-muted)]">
                          {['sql', 'coding', 'ml_primitives'].includes(block.category) ? 'Problems' : 'Questions'}
                          <input
                            type="number"
                            min={1}
                            max={['sql', 'coding', 'ml_primitives'].includes(block.category) ? 5 : block.category === 'interview' ? 10 : 30}
                            className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-ink)]"
                            value={block.count}
                            onChange={(e) =>
                              setBlocks((prev) =>
                                prev.map((b) => (b.id === block.id ? { ...b, count: Number(e.target.value) } : b))
                              )
                            }
                          />
                        </label>
                        <label className="text-xs text-[var(--color-ink-muted)]">
                          Time budget (minutes){block.category === 'interview' ? ' — optional' : ''}
                          <input
                            type="number"
                            min={1}
                            max={180}
                            placeholder={block.category === 'interview' ? 'Untimed' : ''}
                            className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-ink)]"
                            value={block.duration_minutes ?? ''}
                            onChange={(e) =>
                              setBlocks((prev) =>
                                prev.map((b) =>
                                  b.id === block.id
                                    ? { ...b, duration_minutes: e.target.value === '' ? undefined : Number(e.target.value) }
                                    : b
                                )
                              )
                            }
                          />
                        </label>
                        <label className="text-xs text-[var(--color-ink-muted)]">
                          Difficulty
                          <select
                            className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-ink)]"
                            value={block.difficulty || ''}
                            onChange={(e) =>
                              setBlocks((prev) =>
                                prev.map((b) =>
                                  b.id === block.id ? { ...b, difficulty: e.target.value || undefined } : b
                                )
                              )
                            }
                          >
                            <option value="">{block.category === 'interview' ? 'Adaptive (Elo)' : 'Mixed'}</option>
                            <option value="easy">Easy</option>
                            <option value="medium">Medium</option>
                            <option value="hard">Hard</option>
                          </select>
                        </label>
                      </div>
                    </li>
                  ))}
                </ol>

                {blocks.length > 0 && (() => {
                  const summary = totalTimeSummary(blocks);
                  return (
                    <p className="mt-4 text-sm text-[var(--color-ink-muted)]" data-testid="builder-summary">
                      {summary.blockCount} {summary.blockCount === 1 ? 'block' : 'blocks'}
                      {' · '}
                      {summary.timedMinutes} timed minutes
                      {summary.untimedBlocks > 0 && ` · ${summary.untimedBlocks} untimed interview block${summary.untimedBlocks === 1 ? '' : 's'}`}
                      {' — '}
                      {blocks.map(formatBlockLabel).join(' → ')}
                    </p>
                  );
                })()}
                {draftStatus && (
                  <p className="mt-2 text-xs text-[var(--color-ink-muted)]" role="status">{draftStatus}</p>
                )}
                {topicNote && (
                  <p className="mt-2 text-xs text-[var(--color-ink-muted)]" role="status">{topicNote}</p>
                )}

                <div className="mt-6 border-t border-[var(--color-border)] pt-4">
                  <h3 className="text-sm font-semibold text-[var(--color-ink)]">Saved presets</h3>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <input
                      aria-label="Preset name"
                      placeholder="Preset name"
                      className="min-w-0 flex-1 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm"
                      value={presetName}
                      onChange={(e) => setPresetName(e.target.value)}
                    />
                    <button
                      type="button"
                      disabled={busy || blocks.length === 0 || !presetName.trim()}
                      onClick={async () => {
                        setBusy(true);
                        setError('');
                        try {
                          const saved = await createPreset({
                            name: presetName.trim(),
                            version: PRESET_VERSION,
                            blocks,
                          });
                          setPresets((prev) => [...prev, saved]);
                          setPresetName('');
                        } catch (err) {
                          setError(err.message || 'Could not save preset.');
                        } finally {
                          setBusy(false);
                        }
                      }}
                      className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-4 py-2 text-sm font-semibold disabled:opacity-40"
                    >
                      Save preset
                    </button>
                  </div>
                  {presets.length > 0 && (
                    <ul className="mt-3 space-y-2">
                      {presets.map((preset) => (
                        <li
                          key={preset.id}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                        >
                          <span className="text-sm font-medium">{preset.name}</span>
                          <span className="flex gap-1.5">
                            <button
                              type="button"
                              aria-label={`Load preset ${preset.name}`}
                              onClick={() => {
                                const loaded = (preset.blocks || []).map((b) => ({ ...b, id: b.id || createBlockId() }));
                                const validation = validateBuilderBlocks(loaded);
                                if (validation) {
                                  setError(`Preset "${preset.name}" is invalid: ${validation}`);
                                  return;
                                }
                                setBlocks(loaded);
                                setError('');
                              }}
                              className="rounded border border-[var(--color-border)] px-2 py-1 text-xs"
                            >
                              Load
                            </button>
                            <button
                              type="button"
                              aria-label={`Delete preset ${preset.name}`}
                              onClick={async () => {
                                try {
                                  await deletePreset(preset.id);
                                  setPresets((prev) => prev.filter((p) => p.id !== preset.id));
                                } catch (err) {
                                  setError(err.message || 'Could not delete preset.');
                                }
                              }}
                              className="rounded border border-[var(--color-danger)]/40 px-2 py-1 text-xs text-[var(--color-danger)]"
                            >
                              Delete
                            </button>
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <p className="mt-4 text-xs text-[var(--color-ink-muted)]">
                  Mode: text (default). Voice input remains available inside the interview UI — the session API does not
                  distinguish text/voice/mixed starts.
                </p>
                {customTopicsHeldOnMetadataError && (
                  <p className="mt-4 text-xs text-[var(--color-danger)]" role="alert">
                    Interview topics could not be loaded while a block still has a selected topic.
                    Retry topic loading, or clear those topics before starting unrestricted.{' '}
                    <button type="button" className="underline" onClick={retryTopicMetadata}>
                      Retry
                    </button>
                  </p>
                )}
                <PlannedScope scope={plannedScope} />
                <button
                  type="button"
                  disabled={busy || blocks.length === 0 || customTopicsHeldOnMetadataError}
                  className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
                  onClick={() =>
                    runStart(
                      mapBlocksToStartPayload(blocks, {
                        targetCompanyId: target.companyId,
                        targetRoleId: target.roleId,
                      })
                    )
                  }
                >
                  {busy ? 'Starting…' : 'Start custom session'}
                </button>
              </>
            )}
          </section>
        )}

        {mode === 'problems' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Problem practice</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              OA, Verbal Ability, SQL, and coding banks. Coding items score against visible examples and hidden tests.
            </p>
            <div className="mt-4 flex flex-wrap gap-3 text-sm">
              <label>
                Type{' '}
                <select
                  className="ml-1 rounded border border-[var(--color-border)] px-2 py-1"
                  value={bankType}
                  onChange={(e) => setBankType(e.target.value)}
                >
                  <option value="all">all</option>
                  <option value="mcq">mcq</option>
                  <option value="verbal">verbal</option>
                  <option value="sql">sql</option>
                  <option value="coding">coding</option>
                </select>
              </label>
              <label>
                Difficulty{' '}
                <select
                  className="ml-1 rounded border border-[var(--color-border)] px-2 py-1"
                  value={bankDifficulty}
                  onChange={(e) => setBankDifficulty(e.target.value)}
                >
                  <option value="all">all</option>
                  <option value="easy">easy</option>
                  <option value="medium">medium</option>
                  <option value="hard">hard</option>
                </select>
              </label>
              <label>
                Skill{' '}
                <select
                  className="ml-1 rounded border border-[var(--color-border)] px-2 py-1"
                  value={bankSkill}
                  onChange={(e) => setBankSkill(e.target.value)}
                >
                  <option value="all">all</option>
                  {skillFilterOptions.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <ul className="mt-4 max-h-[28rem] space-y-2 overflow-auto">
              {bankItems.map((item) => (
                <li
                  key={`${item.type}-${item.id}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => setSelectedItem(item)}
                  >
                    <p className="truncate text-sm font-medium text-[var(--color-ink)]">
                      {item.type === 'sql' || item.type === 'coding' ? item.title : item.stem}
                    </p>
                    <p className="text-xs text-[var(--color-ink-muted)]">
                      {item.type} · {item.difficulty || '—'} · {item.skill || '—'}
                    </p>
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
                    onClick={() =>
                      runStart(
                        mapProblemItemToStartPayload(item, {
                          skills: item.skill ? [item.skill] : skills,
                        })
                      )
                    }
                  >
                    Practice
                  </button>
                </li>
              ))}
              {bankItems.length === 0 && (
                <li className="text-sm text-[var(--color-ink-muted)]">No items match these filters.</li>
              )}
            </ul>
            {selectedItem && (
              <div className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] p-4">
                <p className="text-sm font-semibold text-[var(--color-ink)]">
                  {selectedItem.type === 'sql' || selectedItem.type === 'coding' ? selectedItem.title : selectedItem.stem}
                </p>
                <ResourceLinks
                  questionId={selectedItem.id}
                  heading="Solution / lecture"
                  variant="light"
                  maxPerLevel={3}
                />
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
