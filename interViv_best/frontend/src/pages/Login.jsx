import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, LogIn } from 'lucide-react';
import { login } from '../lib/api';
import { authDestination } from '../lib/authRedirect';
import { hasFieldErrors, validateLoginFields } from '../lib/authForm';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const next = authDestination(location, window.location.origin);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    const validation = validateLoginFields({ email, password });
    setFieldErrors(validation);
    if (hasFieldErrors(validation)) {
      setError('');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await login({ email, password });
      navigate(next, { replace: true });
    } catch (err) {
      setError(err.message || 'Login failed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="iv-auth min-h-screen bg-white text-slate-950">
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
            <h1 className="mt-4 text-5xl font-normal leading-[0.96] tracking-normal sm:text-6xl" style={{ fontFamily: "var(--font-display)" }}>
              Continue your readiness practice.
            </h1>
            <p className="mt-5 max-w-lg text-base leading-7 text-slate-600">
              Sign in to pick up your practice, revisit feedback, and keep working toward your goals.
            </p>
          </div>

          <form
            onSubmit={handleSubmit}
            noValidate
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
              <div role="alert" className="app-form-error mt-5">
                {error}
              </div>
            )}

            <div className="mt-6">
              <label htmlFor="login-email" className="block text-sm font-medium text-slate-700">
                Email
              </label>
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="app-field mt-2"
                placeholder="you@example.com"
                autoComplete="email"
                aria-invalid={fieldErrors.email ? 'true' : undefined}
                aria-describedby={fieldErrors.email ? 'login-email-error' : undefined}
              />
              {fieldErrors.email && (
                <p id="login-email-error" role="alert" className="app-field-error-text">
                  {fieldErrors.email}
                </p>
              )}
            </div>

            <div className="mt-4">
              <label htmlFor="login-password" className="block text-sm font-medium text-slate-700">
                Password
              </label>
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="app-field mt-2"
                placeholder="Your password"
                autoComplete="current-password"
                aria-invalid={fieldErrors.password ? 'true' : undefined}
                aria-describedby={fieldErrors.password ? 'login-password-error' : undefined}
              />
              {fieldErrors.password && (
                <p id="login-password-error" role="alert" className="app-field-error-text">
                  {fieldErrors.password}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="mt-6 w-full rounded-full bg-slate-950 px-5 py-3 text-base font-semibold text-white transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? 'Signing in...' : 'Login'}
            </button>

            <p className="mt-5 text-center text-sm text-slate-600">
              Don&apos;t have an account?{' '}
              <Link to="/signup" state={{ next }} className="font-semibold text-cyan-700 hover:text-cyan-800">
                Sign up
              </Link>
            </p>
          </form>
        </section>
      </div>
    </main>
  );
}
