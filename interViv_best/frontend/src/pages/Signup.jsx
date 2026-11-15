import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, UserPlus } from 'lucide-react';
import { signup } from '../lib/api';
import { authDestination } from '../lib/authRedirect';
import { hasFieldErrors, validateSignupFields } from '../lib/authForm';

export default function Signup() {
  const navigate = useNavigate();
  const location = useLocation();
  const next = authDestination(location, window.location.origin);
  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  function update(field) {
    return (event) => setForm((current) => ({ ...current, [field]: event.target.value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const validation = validateSignupFields(form);
    setFieldErrors(validation);
    if (hasFieldErrors(validation)) {
      setError('');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await signup({ name: form.name, email: form.email, password: form.password });
      navigate(next, { replace: true });
    } catch (err) {
      setError(err.message || 'Signup failed.');
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
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-700">Your preparation space</p>
            <h1 className="mt-4 text-5xl font-normal leading-[0.96] tracking-normal sm:text-6xl" style={{ fontFamily: "var(--font-display)" }}>
              Build a practice record that follows your goals.
            </h1>
            <p className="mt-5 max-w-lg text-base leading-7 text-slate-600">
              Save your skills, target, and interview reports in one place as you practice.
            </p>
          </div>

          <form
            onSubmit={handleSubmit}
            noValidate
            className="w-full rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_24px_80px_rgba(15,23,42,0.10)] sm:p-8"
          >
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold tracking-normal text-slate-950">Sign up</h2>
                <p className="mt-1 text-sm text-slate-500">Start with a secure readiness profile.</p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-950 text-white">
                <UserPlus className="h-5 w-5" />
              </div>
            </div>

            {error && (
              <div role="alert" className="app-form-error mt-5">
                {error}
              </div>
            )}

            <div className="mt-6">
              <label htmlFor="signup-name" className="block text-sm font-medium text-slate-700">
                Name
              </label>
              <input
                id="signup-name"
                type="text"
                value={form.name}
                onChange={update('name')}
                className="app-field mt-2"
                placeholder="Your name"
                autoComplete="name"
                aria-invalid={fieldErrors.name ? 'true' : undefined}
                aria-describedby={fieldErrors.name ? 'signup-name-error' : undefined}
              />
              {fieldErrors.name && (
                <p id="signup-name-error" role="alert" className="app-field-error-text">
                  {fieldErrors.name}
                </p>
              )}
            </div>

            <div className="mt-4">
              <label htmlFor="signup-email" className="block text-sm font-medium text-slate-700">
                Email
              </label>
              <input
                id="signup-email"
                type="email"
                value={form.email}
                onChange={update('email')}
                className="app-field mt-2"
                placeholder="you@example.com"
                autoComplete="email"
                aria-invalid={fieldErrors.email ? 'true' : undefined}
                aria-describedby={fieldErrors.email ? 'signup-email-error' : undefined}
              />
              {fieldErrors.email && (
                <p id="signup-email-error" role="alert" className="app-field-error-text">
                  {fieldErrors.email}
                </p>
              )}
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="signup-password" className="block text-sm font-medium text-slate-700">
                  Password
                </label>
                <input
                  id="signup-password"
                  type="password"
                  value={form.password}
                  onChange={update('password')}
                  className="app-field mt-2"
                  placeholder="8+ characters"
                  autoComplete="new-password"
                  aria-invalid={fieldErrors.password ? 'true' : undefined}
                  aria-describedby={fieldErrors.password ? 'signup-password-error signup-password-hint' : 'signup-password-hint'}
                />
                {fieldErrors.password && (
                  <p id="signup-password-error" role="alert" className="app-field-error-text">
                    {fieldErrors.password}
                  </p>
                )}
              </div>

              <div>
                <label htmlFor="signup-confirm-password" className="block text-sm font-medium text-slate-700">
                  Confirm password
                </label>
                <input
                  id="signup-confirm-password"
                  type="password"
                  value={form.confirmPassword}
                  onChange={update('confirmPassword')}
                  className="app-field mt-2"
                  placeholder="Repeat password"
                  autoComplete="new-password"
                  aria-invalid={fieldErrors.confirmPassword ? 'true' : undefined}
                  aria-describedby={fieldErrors.confirmPassword ? 'signup-confirm-password-error' : undefined}
                />
                {fieldErrors.confirmPassword && (
                  <p id="signup-confirm-password-error" role="alert" className="app-field-error-text">
                    {fieldErrors.confirmPassword}
                  </p>
                )}
              </div>
            </div>

            <p id="signup-password-hint" className="mt-3 text-xs leading-5 text-slate-500">
              Password must be at least 8 characters and include at least one letter and one number.
            </p>

            <button
              type="submit"
              disabled={loading}
              className="mt-6 w-full rounded-full bg-slate-950 px-5 py-3 text-base font-semibold text-white transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? 'Creating account...' : 'Create account'}
            </button>

            <p className="mt-5 text-center text-sm text-slate-600">
              Already have an account?{' '}
              <Link to="/login" state={{ next }} className="font-semibold text-cyan-700 hover:text-cyan-800">
                Login
              </Link>
            </p>
          </form>
        </section>
      </div>
    </main>
  );
}
