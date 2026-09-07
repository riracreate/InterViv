import React, { useEffect, useMemo, useState } from 'react';
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

  useEffect(() => {
    if (onSelectionChange) {
      onSelectionChange({ companyId: selectedCompany, roleId: selectedRole });
    }
    // Only notify on selection changes.
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
      <div className="rounded-2xl border border-black/8 p-6 text-sm text-[#6F6F6F]"
           style={{ fontFamily: "'Inter', sans-serif" }}>
        Loading target companies…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-300 bg-red-50 p-6 text-sm text-red-700"
           style={{ fontFamily: "'Inter', sans-serif" }}>
        {error} — continuing in general practice mode.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-black/8 p-6 space-y-4"
         data-testid="company-selector">
      <div>
        <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-2"
           style={{ fontFamily: "'Inter', sans-serif" }}>
          Pick your target (optional — skip for general practice)
        </p>
        <h3 className="text-2xl tracking-tight text-black"
            style={{ fontFamily: "'Instrument Serif', serif", letterSpacing: '-0.5px' }}>
          Target company &amp; role
        </h3>
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-1 block"
                style={{ fontFamily: "'Inter', sans-serif" }}>
            Company
          </span>
          <select
            value={selectedCompany}
            onChange={(e) => {
              setSelectedCompany(e.target.value);
              setSelectedRole('');
            }}
            className="w-full rounded-xl border border-black/10 px-4 py-3 text-sm bg-white"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            <option value="">— Select —</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-1 block"
                style={{ fontFamily: "'Inter', sans-serif" }}>
            Role
          </span>
          <select
            value={selectedRole}
            disabled={!selectedCompany}
            onChange={(e) => setSelectedRole(e.target.value)}
            className="w-full rounded-xl border border-black/10 px-4 py-3 text-sm bg-white disabled:opacity-50"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            <option value="">— Select —</option>
            {roles.map((r) => (
              <option key={r.id} value={r.id}>{r.title}{r.level ? ` (${r.level})` : ''}</option>
            ))}
          </select>
        </label>
      </div>

      {selectedCompany && selectedRole && (
        <div className="rounded-xl bg-black/[0.03] border border-black/5 p-4">
          <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-2"
             style={{ fontFamily: "'Inter', sans-serif" }}>
            Skill profile for this role
          </p>
          <ul className="space-y-1">
            {(roles.find((r) => r.id === selectedRole)?.skill_requirements || []).map((req) => (
              <li key={req.skill} className="flex items-center justify-between text-sm"
                  style={{ fontFamily: "'Inter', sans-serif" }}>
                <span className="text-black">{req.display_name || req.skill}</span>
                <span className="text-[#6F6F6F]">
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
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          {saving ? 'Saving…' : isAuthenticated ? 'Save as my target' : 'Use for this session'}
        </button>
        {selectedRole && (
          <Link
            to={`/gap-analysis/${isAuthenticated ? 'me' : 'anonymous'}/${selectedRole}`}
            className="rounded-full px-5 py-2 text-sm font-medium text-black border border-black/15 hover:border-black/30 cursor-pointer"
            style={{ fontFamily: "'Inter', sans-serif" }}
            data-testid="open-gap-analysis"
          >
            See readiness →
          </Link>
        )}
      </div>

      {saveMessage && (
        <p className="text-xs text-[#6F6F6F]" style={{ fontFamily: "'Inter', sans-serif" }}>
          {saveMessage}
        </p>
      )}

      {disclaimer && (
        <p
          data-testid="company-disclaimer"
          className="text-xs text-[#6F6F6F] leading-relaxed border-t border-black/5 pt-3"
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          <span className="font-medium text-black">Note:</span> {disclaimer}
        </p>
      )}
    </div>
  );
}
