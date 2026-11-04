import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchCompanies, setTargetCompany } from '../lib/api';

/**
 * CompanySelector — let the candidate pick a target company + role so we can
 * compute readiness against a specific hiring profile. If the user is not
 * authenticated we surface the picker as a soft prompt only; the rest of the
 * upload flow continues with general practice mode.
 *
 * UI disclaimer is sourced from the API response payload and surfaced verbatim
 * below the picker — never claim these are exact hiring criteria.
 */
export default function CompanySelector({
  isAuthenticated,
  onSelectionChange,
  initialCompanyId,
  initialRoleId,
  onSaved,
}) {
  const [companies, setCompanies] = useState([]);
  const [disclaimer, setDisclaimer] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedCompany, setSelectedCompany] = useState(initialCompanyId || '');
  const [selectedRole, setSelectedRole] = useState(initialRoleId || '');
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const prefilled = useRef(Boolean(initialCompanyId && initialRoleId));

  // Shared target context may arrive after first paint. Prefill once;
  // never override a company/role the user already picked.
  useEffect(() => {
    if (prefilled.current) return;
    if (initialCompanyId && initialRoleId) {
      setSelectedCompany(initialCompanyId);
      setSelectedRole(initialRoleId);
      prefilled.current = true;
    }
  }, [initialCompanyId, initialRoleId]);

  useEffect(() => {
    let cancelled = false;
    fetchCompanies()
      .then((data) => {
        if (cancelled) return;
        setCompanies(data.companies || []);
        setDisclaimer(data.disclaimer || '');
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || 'Could not load companies.');
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const roles = useMemo(() => {
    if (!selectedCompany) return [];
    const company = companies.find((c) => c.id === selectedCompany);
    return company ? company.roles || [] : [];
  }, [companies, selectedCompany]);

  useEffect(() => {
    if (roles.length > 0 && !roles.find((r) => r.id === selectedRole)) {
      setSelectedRole(roles[0].id);
    }
  }, [roles, selectedRole]);

  // Notify on changes only: mounting must never report a value back to the
  // parent, or a remount (e.g. returning from Review) would overwrite the
  // parent's current selection with this component's starting state.
  const lastNotified = useRef({ companyId: initialCompanyId || '', roleId: initialRoleId || '' });
  useEffect(() => {
    const next = { companyId: selectedCompany, roleId: selectedRole };
    if (next.companyId === lastNotified.current.companyId && next.roleId === lastNotified.current.roleId) {
      return;
    }
    lastNotified.current = next;
    onSelectionChange?.(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCompany, selectedRole]);

  const persistSelection = async () => {
    if (!isAuthenticated) {
      setSaveMessage('Sign in to save this as your target. For now, continuing in general practice mode.');
      return;
    }
    if (!selectedCompany || !selectedRole) return;
    setSaving(true);
    setSaveMessage('');
    try {
      await setTargetCompany(selectedCompany, selectedRole);
      setSaveMessage('Saved as your target.');
      onSaved?.();
    } catch (err) {
      setSaveMessage(err.message || 'Could not save target.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-2xl border border-[var(--color-border)] bg-white p-6 text-sm text-[var(--color-ink-muted)]"
           style={{ fontFamily: "var(--font-body)" }}>
        Loading target companies…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-300 bg-red-50 p-6 text-sm text-red-700"
           style={{ fontFamily: "var(--font-body)" }}>
        {error} — continuing in general practice mode.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-white p-6 space-y-4"
         data-testid="company-selector">
      <div>
        <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-ink-muted)] mb-2"
           style={{ fontFamily: "var(--font-body)" }}>
          Pick your target (optional — skip for general practice)
        </p>
        <h3 className="text-2xl tracking-tight text-[var(--color-ink)]"
            style={{ fontFamily: "var(--font-display)", letterSpacing: '-0.5px' }}>
          Target company &amp; role
        </h3>
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wider text-[var(--color-ink-muted)] mb-1 block"
                style={{ fontFamily: "var(--font-body)" }}>
            Company
          </span>
          <select
            value={selectedCompany}
            onChange={(e) => {
              setSelectedCompany(e.target.value);
              setSelectedRole('');
            }}
            className="w-full rounded-xl border border-[var(--color-border)] px-4 py-3 text-sm bg-white"
            style={{ fontFamily: "var(--font-body)" }}
          >
            <option value="">— Select —</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wider text-[var(--color-ink-muted)] mb-1 block"
                style={{ fontFamily: "var(--font-body)" }}>
            Role
          </span>
          <select
            value={selectedRole}
            disabled={!selectedCompany}
            onChange={(e) => setSelectedRole(e.target.value)}
            className="w-full rounded-xl border border-[var(--color-border)] px-4 py-3 text-sm bg-white disabled:opacity-50"
            style={{ fontFamily: "var(--font-body)" }}
          >
            <option value="">— Select —</option>
            {roles.map((r) => (
              <option key={r.id} value={r.id}>{r.title}{r.level ? ` (${r.level})` : ''}</option>
            ))}
          </select>
        </label>
      </div>

      {selectedCompany && selectedRole && (
        <div className="rounded-xl bg-black/[0.03] border border-[var(--color-border)] p-4">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-ink-muted)] mb-2"
             style={{ fontFamily: "var(--font-body)" }}>
            Skill profile for this role
          </p>
          <ul className="space-y-1">
            {(roles.find((r) => r.id === selectedRole)?.skill_requirements || []).map((req) => (
              <li key={req.skill} className="flex items-center justify-between text-sm"
                  style={{ fontFamily: "var(--font-body)" }}>
                <span className="text-[var(--color-ink)]">{req.display_name || req.skill}</span>
                <span className="text-[var(--color-ink-muted)]">
                  target {Math.round(req.required_level)} · weight {Math.round((req.importance_weight || 0) * 100)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!selectedCompany || !selectedRole || saving}
          onClick={persistSelection}
          className="rounded-full px-5 py-2 text-sm font-medium text-white bg-black disabled:opacity-30 cursor-pointer"
          style={{ fontFamily: "var(--font-body)" }}
        >
          {saving ? 'Saving…' : isAuthenticated ? 'Save as my target' : 'Use for this session'}
        </button>
        {selectedRole && (
          <Link
            to={`/gap-analysis/${isAuthenticated ? 'me' : 'anonymous'}/${selectedRole}`}
            className="rounded-full px-5 py-2 text-sm font-medium text-[var(--color-ink)] border border-[var(--color-border)] hover:border-black/30 cursor-pointer"
            style={{ fontFamily: "var(--font-body)" }}
            data-testid="open-gap-analysis"
          >
            See readiness →
          </Link>
        )}
      </div>

      {saveMessage && (
        <p className="text-xs text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
          {saveMessage}
        </p>
      )}

      {disclaimer && (
        <p
          data-testid="company-disclaimer"
          className="text-xs text-[var(--color-ink-muted)] leading-relaxed border-t border-[var(--color-border)] pt-3"
          style={{ fontFamily: "var(--font-body)" }}
        >
          <span className="font-medium text-[var(--color-ink)]">Note:</span> {disclaimer}
        </p>
      )}
    </div>
  );
}
