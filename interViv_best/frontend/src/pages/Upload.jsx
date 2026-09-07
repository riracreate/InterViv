import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadResume, startSession, saveInterviewState, fetchMe, saveTargetContext } from '../lib/api';
import CompanySelector from '../components/CompanySelector';

const ROUNDS_PER_SKILL = 3;

const DOMAIN_PRESETS = [
  {
    name: 'Data Structures & Algorithms',
    short: 'DSA',
    tags: ['Arrays', 'Trees', 'Graphs', 'DP'],
    skills: ['DSA', 'Data Structures', 'Algorithms', 'Dynamic Programming', 'Graphs', 'Recursion', 'Greedy', 'Sorting'],
  },
  {
    name: 'CS Fundamentals',
    short: 'CS Core',
    tags: ['OOP', 'OS', 'DBMS', 'CN'],
    skills: ['OOP', 'DBMS', 'OS', 'CN', 'System Design'],
  },
  {
    name: 'Backend Engineering',
    short: 'Backend',
    tags: ['Python', 'Node.js', 'REST', 'Databases'],
    skills: ['Python', 'Node.js', 'Java', 'Go', 'FastAPI', 'Spring Boot', 'REST', 'GraphQL', 'PostgreSQL'],
  },
  {
    name: 'Frontend Engineering',
    short: 'Frontend',
    tags: ['React', 'TypeScript', 'CSS', 'Performance'],
    skills: ['JavaScript', 'TypeScript', 'React', 'Next.js', 'Vue', 'HTML', 'CSS', 'Tailwind CSS'],
  },
  {
    name: 'System Design',
    short: 'System Design',
    tags: ['Scalability', 'Caching', 'Queues', 'Microservices'],
    skills: ['System Design', 'Scalability', 'Microservices', 'Caching', 'Load Balancing', 'Message Queues', 'Kafka'],
  },
  {
    name: 'Databases',
    short: 'Databases',
    tags: ['SQL', 'MongoDB', 'Redis', 'Indexing'],
    skills: ['DBMS', 'SQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Indexing', 'Transactions', 'NoSQL'],
  },
  {
    name: 'DevOps & Cloud',
    short: 'DevOps',
    tags: ['Docker', 'Kubernetes', 'AWS', 'CI/CD'],
    skills: ['Docker', 'Kubernetes', 'AWS', 'CI/CD', 'Terraform', 'Linux', 'Monitoring'],
  },
  {
    name: 'Machine Learning',
    short: 'ML',
    tags: ['PyTorch', 'scikit-learn', 'NLP', 'CV'],
    skills: ['ML', 'PyTorch', 'TensorFlow', 'scikit-learn', 'NLP', 'Computer Vision', 'Deep Learning'],
  },
  {
    name: 'AI & LLMs',
    short: 'AI / LLMs',
    tags: ['LLMs', 'RAG', 'Prompting', 'Embeddings'],
    skills: ['LLMs', 'Transformers', 'Prompt Engineering', 'RAG', 'Embeddings', 'Fine-tuning'],
  },
  {
    name: 'Data Engineering',
    short: 'Data Eng',
    tags: ['Spark', 'Kafka', 'Airflow', 'ETL'],
    skills: ['SQL', 'Spark', 'Kafka', 'Airflow', 'ETL', 'Data Warehousing', 'Pandas'],
  },
  {
    name: 'Mobile Engineering',
    short: 'Mobile',
    tags: ['Android', 'iOS', 'Flutter', 'React Native'],
    skills: ['Android', 'iOS', 'Swift', 'Kotlin', 'Flutter', 'React Native'],
  },
  {
    name: 'Security',
    short: 'Security',
    tags: ['Crypto', 'OWASP', 'Auth', 'Network'],
    skills: ['Security', 'Cryptography', 'OWASP', 'Network Security', 'Authentication'],
  },
  {
    name: 'Programming Languages',
    short: 'Languages',
    tags: ['C++', 'Go', 'Rust', 'TypeScript'],
    skills: ['C++', 'C', 'Java', 'Python', 'Go', 'Rust', 'TypeScript'],
  },
  {
    name: 'Behavioural',
    short: 'Behavioural',
    tags: ['Leadership', 'Teamwork', 'Communication'],
    skills: ['HR', 'Communication', 'Leadership', 'Teamwork', 'Problem Solving'],
  },
];

const ALL_SUGGESTED_SKILLS = Array.from(new Set(DOMAIN_PRESETS.flatMap(d => d.skills)));

function mergeUnique(...groups) {
  const seen = new Set();
  const merged = [];
  groups.flat().forEach((item) => {
    const skill = String(item || '').trim();
    const key = skill.toLowerCase();
    if (!skill || seen.has(key)) return;
    seen.add(key);
    merged.push(skill);
  });
  return merged;
}

function hasSkill(list, skill) {
  const key = String(skill || '').trim().toLowerCase();
  return list.some(item => String(item || '').trim().toLowerCase() === key);
}

function withoutSkill(list, skill) {
  const key = String(skill || '').trim().toLowerCase();
  return list.filter(item => String(item || '').trim().toLowerCase() !== key);
}

export default function Upload() {
  const navigate = useNavigate();
  const [step, setStep] = useState('upload');
  const [file, setFile] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [extractedSkills, setExtractedSkills] = useState([]);
  const [candidateId, setCandidateId] = useState('');
  const [domainProfile, setDomainProfile] = useState({});
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [targetSelection, setTargetSelection] = useState({ companyId: '', roleId: '' });

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then(() => { if (!cancelled) setIsAuthenticated(true); })
      .catch(() => { if (!cancelled) setIsAuthenticated(false); });
    return () => { cancelled = true; };
  }, []);

  const handleFile = (f) => {
    if (f && f.type === 'application/pdf') { setFile(f); setError(''); }
    else setError('Please upload a PDF file.');
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    handleFile(e.dataTransfer.files[0]);
  }, []);

  const processResume = async () => {
    if (!file) return;
    setIsProcessing(true);
    setError('');
    try {
      const r = await uploadResume(file);
      const detected = r.skills || [];
      setCandidateId(r.candidate_id);
      setExtractedSkills(detected);
      setDomainProfile(r.domain_profile || {});
      setSelectedSkills(detected.slice(0, 3));
      setStep('skills');
      // Carry the resume forward: later hops (ATS, coach, gaps) prefill
      // from the shared target context instead of re-prompting.
      if (r.candidate_id) {
        saveTargetContext({ resume_ref: r.candidate_id }).catch(() => {});
      }
    } catch (err) {
      setError(err.message || 'Resume processing failed.');
    } finally {
      setIsProcessing(false);
    }
  };

  const toggleSkill = (skill) => {
    setExtractedSkills(prev => mergeUnique(prev, [skill]));
    setSelectedSkills(prev =>
      hasSkill(prev, skill) ? withoutSkill(prev, skill) : mergeUnique(prev, [skill])
    );
  };

  const startInterview = async () => {
    if (selectedSkills.length === 0) return;
    setIsStarting(true);
    setError('');
    try {
      const primarySkill = selectedSkills[0];
      // Authenticated users can persist target company/role. Anonymous users
      // still pass the selected target into this one session.
      const r = await startSession({
        candidate_id: candidateId,
        skill: primarySkill,
        skills: selectedSkills,
        sub_domain: domainProfile[primarySkill] || 'general',
        rounds_per_skill: ROUNDS_PER_SKILL,
        target_company_id: targetSelection.companyId || null,
        target_role_id: targetSelection.roleId || null,
      });
      const totalRounds = r.total_rounds || (selectedSkills.length * ROUNDS_PER_SKILL);
      const resolvedCandidateId = r.candidate_id || candidateId;
      const state = {
        candidateId: resolvedCandidateId,
        skill: primarySkill,
        allSkills: selectedSkills,
        subDomain: domainProfile[primarySkill] || 'general',
        sessionId: r.session_id,
        question: r.question,
        difficulty: r.difficulty,
        round_type: r.round_type || 'technical_short_answer',
        block_category: r.block_category || null,
        question_context: r.question_context || {},
        config_json: r.config_json || {},
        expires_at: r.expires_at || null,
        round: r.round || 1,
        elo: r.elo || 1200,
        totalRounds,
        roundsPerSkill: ROUNDS_PER_SKILL,
      };
      saveInterviewState(state);
      navigate(`/interview/${r.session_id}`, { state });
    } catch (err) {
      setError(err.message || 'Failed to start session.');
    } finally {
      setIsStarting(false);
    }
  };

  const chooseDomainPreset = (domain) => {
    const skills = domain.skills || [domain.short];
    setCandidateId('');
    setExtractedSkills(skills);
    setDomainProfile(skills.reduce((profile, skill) => ({ ...profile, [skill]: 'general' }), {}));
    setSelectedSkills(skills.slice(0, Math.min(3, skills.length)));
    setStep('skills');
  };

  const suggestedSkills = mergeUnique(ALL_SUGGESTED_SKILLS, extractedSkills);

  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="w-full border-b border-black/5">
        <div className="flex items-center justify-between px-8 py-5 max-w-7xl mx-auto">
          <a href="/" onClick={(e) => { e.preventDefault(); navigate('/'); }}
            className="text-2xl tracking-tight text-black"
            style={{ fontFamily: "'Instrument Serif', serif" }}>
            interViv<sup className="text-xs align-super">©</sup>
          </a>
          <button onClick={() => {
            if (step === 'domains') setStep('skills');
            else if (step === 'skills') setStep('upload');
            else navigate('/');
          }}
            className="text-sm text-[#6F6F6F] hover:text-black transition-colors cursor-pointer"
            style={{ fontFamily: "'Inter', sans-serif" }}>
            ← {step === 'upload' ? 'Home' : 'Back'}
          </button>
        </div>
      </nav>

      <div className="max-w-3xl mx-auto px-6 pt-16 pb-24">
        {/* Progress */}
        <div className="flex items-center gap-3 mb-14">
          {['Upload', 'Skills', 'Start'].map((s, i) => {
            const stepKeys = ['upload', 'skills', 'domains'];
            const stepIndex = stepKeys.indexOf(step);
            const isActive = i <= stepIndex;
            const isDone = i < stepIndex;
            return (
              <React.Fragment key={s}>
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-full text-xs font-medium flex items-center justify-center border transition-all duration-300"
                    style={{
                      backgroundColor: isActive ? '#000' : 'transparent',
                      color: isActive ? '#fff' : '#6F6F6F',
                      borderColor: isActive ? '#000' : '#E0E0E0',
                      fontFamily: "'Inter', sans-serif",
                    }}>
                    {isDone ? '✓' : i + 1}
                  </div>
                  <span className="text-xs font-medium hidden sm:inline"
                    style={{ fontFamily: "'Inter', sans-serif", color: isActive ? '#000' : '#6F6F6F' }}>
                    {s}
                  </span>
                </div>
                {i < 2 && <div className="flex-1 h-px" style={{ backgroundColor: i < stepIndex ? '#000' : '#E0E0E0' }} />}
              </React.Fragment>
            );
          })}
        </div>

        {/* ═══ STEP 1: Upload ═══ */}
        {step === 'upload' && (
          <div className="animate-fade-rise">
            <h1 className="text-4xl md:text-5xl tracking-tight mb-3"
              style={{ fontFamily: "'Instrument Serif', serif", color: '#000', letterSpacing: '-1.5px' }}>
              Upload your profile
            </h1>
            <p className="text-base mb-10" style={{ fontFamily: "'Inter', sans-serif", color: '#6F6F6F' }}>
              Our resume parser extracts your skills and builds your interview profile.
            </p>

            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => !file && document.getElementById('fileInput').click()}
              className="rounded-2xl p-20 flex flex-col items-center justify-center cursor-pointer transition-all duration-300 border-2 border-dashed"
              style={{ borderColor: file ? '#000' : dragOver ? '#000' : '#E0E0E0', backgroundColor: file ? 'rgba(0,0,0,0.02)' : 'transparent' }}>
              {file ? (
                <div className="text-center">
                  <div className="w-14 h-14 rounded-xl bg-black/5 flex items-center justify-center mb-5 mx-auto">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                  </div>
                  <p className="text-lg font-medium text-black mb-1" style={{ fontFamily: "'Inter', sans-serif" }}>{file.name}</p>
                  <p className="text-xs font-medium tracking-wider uppercase text-[#6F6F6F]" style={{ fontFamily: "'Inter', sans-serif" }}>Ready to process</p>
                  <button onClick={(e) => { e.stopPropagation(); setFile(null); }}
                    className="mt-3 text-xs text-[#6F6F6F] hover:text-black transition-colors"
                    style={{ fontFamily: "'Inter', sans-serif" }}>
                    ✕ Remove
                  </button>
                </div>
              ) : (
                <div className="text-center">
                  <div className="w-14 h-14 rounded-xl bg-black/5 flex items-center justify-center mb-5 mx-auto">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#6F6F6F" strokeWidth="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                  </div>
                  <p className="text-lg font-medium text-black mb-1" style={{ fontFamily: "'Inter', sans-serif" }}>Drag and drop your PDF resume</p>
                  <p className="text-sm text-[#6F6F6F] mb-6" style={{ fontFamily: "'Inter', sans-serif" }}>Maximum file size 10MB</p>
                  <input type="file" accept=".pdf" className="hidden" id="fileInput" onChange={(e) => handleFile(e.target.files[0])} />
                  <label htmlFor="fileInput"
                    className="rounded-full px-6 py-2.5 text-sm text-black cursor-pointer border border-black/15 hover:border-black/30 transition-colors"
                    style={{ fontFamily: "'Inter', sans-serif" }}>
                    Select File
                  </label>
                </div>
              )}
            </div>

            {error && <p className="mt-4 text-sm text-red-600" style={{ fontFamily: "'Inter', sans-serif" }}>{error}</p>}

            {/* Quick start without resume */}
            <div className="mt-8">
              <p className="text-sm text-[#6F6F6F] mb-4" style={{ fontFamily: "'Inter', sans-serif" }}>
                Or pick domains directly to start immediately:
              </p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {DOMAIN_PRESETS.map(d => (
                  <button key={d.short} onClick={() => chooseDomainPreset(d)}
                    className="rounded-2xl border border-black/8 p-4 text-left hover:border-black/20 transition-all cursor-pointer">
                    <p className="text-sm font-medium text-black" style={{ fontFamily: "'Inter', sans-serif" }}>{d.name}</p>
                    <p className="text-xs text-[#6F6F6F] mt-1" style={{ fontFamily: "'Inter', sans-serif" }}>
                      {d.skills.slice(0, 3).join(' · ')}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {file && (
              <button disabled={isProcessing} onClick={processResume}
                className="w-full mt-6 rounded-full py-4 text-sm font-medium text-white cursor-pointer transition-transform hover:scale-[1.01] disabled:opacity-50"
                style={{ backgroundColor: '#000', fontFamily: "'Inter', sans-serif" }}>
                {isProcessing ? 'Extracting Intelligence...' : 'Continue →'}
              </button>
            )}
          </div>
        )}

        {/* ═══ STEP 2: Skills extracted ═══ */}
        {step === 'skills' && (
          <div className="animate-fade-rise">
            <h1 className="text-4xl md:text-5xl tracking-tight mb-3"
              style={{ fontFamily: "'Instrument Serif', serif", color: '#000', letterSpacing: '-1.5px' }}>
              Extracted intelligence
            </h1>
            <p className="text-base mb-10" style={{ fontFamily: "'Inter', sans-serif", color: '#6F6F6F' }}>
              We identified these core competencies from your resume. Select the ones to practice.
            </p>

            <div className="rounded-2xl border border-black/8 p-8 mb-6">
              <div className="flex items-center justify-between gap-3 mb-4">
                <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F]"
                  style={{ fontFamily: "'Inter', sans-serif" }}>
                  {extractedSkills.length ? 'Detected skills' : 'Choose skills'}
                </p>
                <p className="text-xs text-[#6F6F6F]" style={{ fontFamily: "'Inter', sans-serif" }}>
                  Tap chips to select or remove
                </p>
              </div>
              <div className="flex flex-wrap gap-2.5">
                {(extractedSkills.length ? extractedSkills : suggestedSkills.slice(0, 8)).map(skill => (
                  <button key={skill} onClick={() => toggleSkill(skill)}
                    className="rounded-full px-4 py-2 text-sm border transition-all cursor-pointer"
                    style={{
                      fontFamily: "'Inter', sans-serif",
                      borderColor: hasSkill(selectedSkills, skill) ? '#000' : 'rgba(0,0,0,0.08)',
                      backgroundColor: hasSkill(selectedSkills, skill) ? '#000' : 'transparent',
                      color: hasSkill(selectedSkills, skill) ? '#fff' : '#000',
                    }}>
                    {skill}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-black/8 p-6 mb-6">
              <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-4"
                style={{ fontFamily: "'Inter', sans-serif" }}>
                Add more skills or languages
              </p>
              <div className="space-y-5">
                {DOMAIN_PRESETS.map(domain => (
                  <div key={domain.short}>
                    <div className="flex items-center justify-between gap-3 mb-2">
                      <p className="text-sm font-medium text-black" style={{ fontFamily: "'Inter', sans-serif" }}>
                        {domain.name}
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          setExtractedSkills(prev => mergeUnique(prev, domain.skills));
                          setSelectedSkills(prev => mergeUnique(prev, domain.skills));
                        }}
                        className="text-xs text-[#6F6F6F] hover:text-black transition-colors"
                        style={{ fontFamily: "'Inter', sans-serif" }}
                      >
                        Select all
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {domain.skills.map(skill => {
                        const active = hasSkill(selectedSkills, skill);
                        return (
                          <button
                            key={`${domain.short}-${skill}`}
                            type="button"
                            onClick={() => toggleSkill(skill)}
                            className="rounded-full px-3 py-1.5 text-xs border transition-all cursor-pointer"
                            style={{
                              fontFamily: "'Inter', sans-serif",
                              borderColor: active ? '#000' : 'rgba(0,0,0,0.10)',
                              backgroundColor: active ? '#000' : 'rgba(0,0,0,0.02)',
                              color: active ? '#fff' : '#000',
                            }}
                          >
                            {skill}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {selectedSkills.length > 0 && (
              <p className="text-sm text-[#6F6F6F] mb-6" style={{ fontFamily: "'Inter', sans-serif" }}>
                {selectedSkills.length} skill{selectedSkills.length > 1 ? 's' : ''} selected · {selectedSkills.length * ROUNDS_PER_SKILL} total rounds
              </p>
            )}

            <div className="mb-6">
              <CompanySelector
                isAuthenticated={isAuthenticated}
                onSelectionChange={setTargetSelection}
              />
            </div>

            <button onClick={() => setStep('domains')} disabled={selectedSkills.length === 0}
              className="w-full rounded-full py-4 text-sm font-medium text-white cursor-pointer transition-transform hover:scale-[1.01] disabled:opacity-30"
              style={{ backgroundColor: '#000', fontFamily: "'Inter', sans-serif" }}>
              Choose Interview Domains →
            </button>
          </div>
        )}

        {/* ═══ STEP 3: Confirm & Start ═══ */}
        {step === 'domains' && (
          <div className="animate-fade-rise">
            <h1 className="text-4xl md:text-5xl tracking-tight mb-3"
              style={{ fontFamily: "'Instrument Serif', serif", color: '#000', letterSpacing: '-1.5px' }}>
              Ready to begin
            </h1>
            <p className="text-base mb-10" style={{ fontFamily: "'Inter', sans-serif", color: '#6F6F6F' }}>
              Your adaptive session is configured. Each skill is tested in rotation.
            </p>

            <div className="rounded-2xl border border-black/8 overflow-hidden mb-8">
              {(selectedSkills.length > 0 ? selectedSkills : DOMAIN_PRESETS.slice(0, 3).map(d => d.short)).map((skill, i) => (
                <div key={skill} className="px-6 py-4 border-b border-black/5 last:border-0 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-full bg-black text-white flex items-center justify-center text-xs font-bold"
                      style={{ fontFamily: "'Inter', sans-serif" }}>{i + 1}</span>
                    <span className="text-sm font-medium text-black" style={{ fontFamily: "'Inter', sans-serif" }}>{skill}</span>
                  </div>
                  <span className="text-xs text-[#6F6F6F]" style={{ fontFamily: "'Inter', sans-serif" }}>
                    Rounds {i * ROUNDS_PER_SKILL + 1}–{(i + 1) * ROUNDS_PER_SKILL}
                  </span>
                </div>
              ))}
            </div>

            {error && <p className="mb-4 text-sm text-red-600" style={{ fontFamily: "'Inter', sans-serif" }}>{error}</p>}

            <button disabled={isStarting} onClick={startInterview}
              className="w-full rounded-full py-4 text-sm font-medium text-white cursor-pointer transition-transform hover:scale-[1.01] disabled:opacity-50"
              style={{ backgroundColor: '#000', fontFamily: "'Inter', sans-serif" }}>
              {isStarting ? 'Starting Session...' : `Start Interview · ${(selectedSkills.length || 1) * ROUNDS_PER_SKILL} Rounds →`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
