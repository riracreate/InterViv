import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, LogIn } from 'lucide-react';
import { login } from '../lib/api';

function validate(email, password) {
  if (!email.trim()) return 'Email is required.';
  if (!email.includes('@')) return 'Enter a valid email address.';
  if (!password) return 'Password is required.';
  return '';
}

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    const validation = validate(email, password);
    if (validation) {
      setError(validation);
      return;
    }
    setError('');
    setLoading(true);
    try {
      await login({ email, password });
      const next = location.state?.next || '/upload';
      navigate(next);
    } catch (err) {
      setError(err.message || 'Login failed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-white text-slate-950">
      <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 py-6 sm:px-8">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="inline-flex w-fit items-center gap-2 rounded-full border border-slate-200 px-4 py-2 text-sm text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
        >
          <ArrowLeft className="h-4 w-4" />
          Home
        </button>

        <section className="grid flex-1 items-center gap-10 py-12 lg:grid-cols-[0.92fr_1.08fr]">
          <div className="max-w-xl">
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-700">interViv account</p>
            <h1 className="mt-4 text-5xl font-normal leading-[0.96] tracking-normal sm:text-6xl" style={{ fontFamily: "'Instrument Serif', serif" }}>
              Continue your readiness practice.
            </h1>
            <p className="mt-5 max-w-lg text-base leading-7 text-slate-600">
              Sign in to keep your skill graph, company target, practice history, and roadmap tied to your profile.
            </p>
          </div>

          <form
            onSubmit={handleSubmit}
            className="w-full rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_24px_80px_rgba(15,23,42,0.10)] sm:p-8"
          >
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold tracking-normal text-slate-950">Login</h2>
                <p className="mt-1 text-sm text-slate-500">Use the email you registered with.</p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-950 text-white">
                <LogIn className="h-5 w-5" />
              </div>
            </div>

            {error && (
              <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <label className="mt-6 block text-sm font-medium text-slate-700">
              Email
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-base outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
                placeholder="you@example.com"
                autoComplete="email"
              />
            </label>

            <label className="mt-4 block text-sm font-medium text-slate-700">
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-base outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
                placeholder="Your password"
                autoComplete="current-password"
              />
            </label>

            <button
              type="submit"
              disabled={loading}
              className="mt-6 w-full rounded-full bg-slate-950 px-5 py-3 text-base font-semibold text-white transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? 'Signing in...' : 'Login'}
            </button>

            <p className="mt-5 text-center text-sm text-slate-600">
              Don&apos;t have an account?{' '}
              <Link to="/signup" className="font-semibold text-cyan-700 hover:text-cyan-800">
                Sign up
              </Link>
            </p>
          </form>
        </section>
      </div>
    </main>
  );
}

