import React, { useCallback, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { fetchAccountOverview } from '../lib/api';
import { accountLoadAction } from '../lib/requestErrors';
import AppNav from './AppNav';
import '../styles/hub.css';

export function useAccountOverview() {
  const location = useLocation();
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
      if (cancelled || accountLoadAction(err) === 'ignore') return;
      // A confirmed expiry is handled centrally (lib/api.js); anything else
      // keeps this page with a retry.
      setError(err.message || 'Your progress is not available right now.');
    });
    return () => { cancelled = true; };
  }, [location.pathname, location.search, location.hash, revision]);
  return { data, error, reload };
}

export default function AccountPage({ data, error, reload, children }) {
  const user = data?.user;
  return (
    <main className="hub-page">
      <div className="hub-container">
        <AppNav userId={user?.id} roleId={data?.target?.role_id} userName={user?.name || ''} userEmail={user?.email || ''} />
        {error && <div className="hub-error" role="alert">{error} <button type="button" onClick={reload}>Try again</button></div>}
        {!data && !error && <p className="hub-loading" role="status">Loading your account…</p>}
        {data && children}
      </div>
    </main>
  );
}
