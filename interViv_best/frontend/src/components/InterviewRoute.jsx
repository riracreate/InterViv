import React, { lazy, Suspense, useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { fetchSession } from '../lib/api';
import { interviewStateFromSession } from '../lib/accountOverview';

const Interview = lazy(() => import('../pages/Interview.jsx'));

export default function InterviewRoute() {
  const { sessionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [loaded, setLoaded] = useState(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setLoaded(null);
    setError('');
    fetchSession(sessionId).then(session => {
      if (cancelled) return;
      if (session.status === 'completed') {
        navigate(`/dashboard/${encodeURIComponent(sessionId)}`, { replace: true });
        return;
      }
      // The server owns the resume context; browser storage may belong to a
      // different account/session and must not replace a deep-linked session.
      setLoaded(interviewStateFromSession(session));
    }).catch(err => {
      if (cancelled) return;
      if (err.status === 401) navigate('/login', { replace: true, state: { next: location.pathname + location.search } });
      else setError(err.message || 'This session is not available.');
    });
    return () => { cancelled = true; };
  }, [sessionId, navigate, location.pathname, location.search, retry]);

  const waiting = <div className="min-h-screen grid place-items-center bg-white text-slate-700"><p role="status">Loading interview…</p></div>;
  if (error) return <main className="min-h-screen grid place-items-center bg-white p-6"><div><p role="alert">{error}</p><button type="button" className="mt-4 mr-5 underline" onClick={() => setRetry(value => value + 1)}>Try again</button><Link to="/home" className="underline">Back to Home</Link></div></main>;
  if (!loaded || loaded.sessionId !== sessionId) return waiting;
  return <Suspense fallback={waiting}><Interview key={sessionId} sessionState={loaded} /></Suspense>;
}
