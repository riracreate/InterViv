import React, { useCallback, useId, useState } from 'react';
import { uploadResume, saveTargetContext } from '../lib/api';
import { MAX_RESUME_LABEL, resumeFileError } from '../lib/resumeUpload';

function hasSkill(list, skill) {
  const key = String(skill || '').trim().toLowerCase();
  return (list || []).some((item) => String(item || '').trim().toLowerCase() === key);
}

function toggleSkillInList(list, skill) {
  const clean = String(skill || '').trim();
  if (!clean) return list || [];
  if (hasSkill(list, clean)) {
    const key = clean.toLowerCase();
    return (list || []).filter((item) => String(item || '').trim().toLowerCase() !== key);
  }
  return [...(list || []), clean];
}

/**
 * Inline resume upload & extracted-skill selector embedded inside the
 * Interview setup modes on /practice (Full interview and Interview practice).
 */
export default function InterviewResumePanel({
  candidateId = '',
  fileName = '',
  extractedSkills = [],
  selectedSkills = [],
  onResumeExtracted,
  onSkillsChange,
}) {
  const inputId = useId();
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState('');

  const handleFile = useCallback((f) => {
    if (!f) return;
    const problem = resumeFileError(f);
    if (problem) {
      setFile(null);
      setError(problem);
      return;
    }
    setFile(f);
    setError('');
  }, []);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragOver(false);
      handleFile(e.dataTransfer?.files?.[0]);
    },
    [handleFile]
  );

  const processResume = async () => {
    if (!file) return;
    const problem = resumeFileError(file);
    if (problem) {
      setError(problem);
      return;
    }
    setIsProcessing(true);
    setError('');
    try {
      const r = await uploadResume(file);
      const detected = Array.isArray(r.skills) ? r.skills : [];
      const nextCandidateId = r.candidate_id || '';
      const nextDomainProfile = r.domain_profile || {};
      if (nextCandidateId) {
        saveTargetContext({ resume_ref: nextCandidateId }).catch(() => {});
      }
      setFile(null);
      onResumeExtracted?.({
        candidateId: nextCandidateId,
        fileName: file.name,
        extractedSkills: detected,
        domainProfile: nextDomainProfile,
      });
    } catch (err) {
      setError(err?.message || 'Resume processing failed.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <section
      data-testid="interview-resume-panel"
      className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--color-accent)]">
            Resume for interview rounds (optional)
          </h3>
          <p className="mt-1 text-sm text-[var(--color-ink-muted)]">
            Upload your PDF resume to extract skills and tailor your interview rounds, or pick skills manually below.
          </p>
        </div>
        {candidateId && (
          <span
            data-testid="interview-resume-active"
            className="rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-xs font-medium text-[var(--color-ink)]"
          >
            Resume active{fileName ? `: ${fileName}` : ''}
          </span>
        )}
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`mt-4 flex flex-col items-center justify-between gap-3 rounded-[var(--radius-card)] border-2 border-dashed p-4 transition sm:flex-row ${
          file || dragOver
            ? 'border-[var(--color-ink)] bg-[var(--color-surface)]'
            : 'border-[var(--color-border)]'
        }`}
      >
        <div className="text-center sm:text-left">
          {file ? (
            <>
              <p className="text-sm font-medium text-[var(--color-ink)]">{file.name}</p>
              <p className="text-xs text-[var(--color-ink-muted)]">
                Ready to extract interview skills
              </p>
            </>
          ) : (
            <>
              <p className="text-sm font-medium text-[var(--color-ink)]">
                {candidateId ? 'Upload a different PDF resume' : 'Drag and drop your PDF resume, or select a file'}
              </p>
              <p className="text-xs text-[var(--color-ink-muted)]">
                Maximum file size {MAX_RESUME_LABEL}
              </p>
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <input
            id={inputId}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <label
            htmlFor={inputId}
            className="cursor-pointer rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-white px-4 py-2 text-xs font-semibold text-[var(--color-ink)] transition hover:border-slate-400"
          >
            {file ? 'Change PDF' : 'Select PDF'}
          </label>
          {file && (
            <>
              <button
                type="button"
                disabled={isProcessing}
                onClick={processResume}
                className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-40"
              >
                {isProcessing ? 'Extracting skills…' : 'Extract skills'}
              </button>
              <button
                type="button"
                onClick={() => setFile(null)}
                className="px-2 py-1 text-xs text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
              >
                Remove
              </button>
            </>
          )}
        </div>
      </div>

      {error && (
        <p className="app-form-error mt-3" role="alert">
          {error}
        </p>
      )}

      {extractedSkills.length > 0 && (
        <div className="mt-4 border-t border-[var(--color-border)] pt-4" data-testid="interview-extracted-skills">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-ink-muted)]">
            Found in your resume ({extractedSkills.length}, listed A–Z) — tap the skills to practise
          </p>
          <div className="mt-2.5 flex flex-wrap gap-2">
            {extractedSkills.map((skill) => {
              const active = hasSkill(selectedSkills, skill);
              return (
                <button
                  key={skill}
                  type="button"
                  aria-pressed={active}
                  onClick={() => onSkillsChange?.(toggleSkillInList(selectedSkills, skill))}
                  className={`rounded-[var(--radius-pill)] border px-3 py-1 text-xs font-medium transition ${
                    active
                      ? 'border-[var(--color-ink)] bg-[var(--color-ink)] text-white'
                      : 'border-[var(--color-border)] bg-white text-[var(--color-ink)] hover:border-slate-400'
                  }`}
                >
                  {skill}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

