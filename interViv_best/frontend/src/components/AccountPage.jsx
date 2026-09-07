import React, { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { clearAuthToken, clearInterviewState, fetchAccountOverview } from '../lib/api';
import AppNav from './AppNav';
import '../styles/hub.css';

export function useAccountOverview() {
  const location = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision(value => value + 1), []);
  useEffect(() => {
    let cancelled = false;
    setError('');
    fetchAccountOverview().then(result => {
      if (!cancelled) setData(result);
    }).catch(err => {
      if (cancelled) return;
      if (err.status === 401) {
        navigate('/login', { replace: true, state: { next: location.pathname + location.search + location.hash } });
      } else setError(err.message || 'Your progress is not available right now.');
    });
    return () => { cancelled = true; };
  }, [navigate, location.pathname, location.search, location.hash, revision]);
  return { data, error, reload };
}

export default function AccountPage({ data, error, reload, children }) {
  const navigate = useNavigate();
  const user = data?.user;
  return (
    <main className="hub-page">
      <div className="hub-container">
        <AppNav userId={user?.id} roleId={data?.target?.role_id} trailing={user && <div className="hub-account">
          <span className="hub-avatar" aria-hidden="true">{user.name?.trim().charAt(0).toUpperCase() || 'I'}</span>
          <button type="button" onClick={() => { clearAuthToken(); clearInterviewState(); navigate('/login', { replace: true }); }}>Sign out</button>
        </div>} />
        {error && <div className="hub-error" role="alert">{error} <button type="button" onClick={reload}>Try again</button></div>}
        {!data && !error && <p className="hub-loading" role="status">Loading your account…</p>}
        {data && children}
      </div>
    </main>
  );
}
