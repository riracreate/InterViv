import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, UserPlus } from 'lucide-react';
import { signup } from '../lib/api';
import { authDestination } from '../lib/authRedirect';

function validate({ name, email, password, confirmPassword }) {
  if (!name.trim()) return 'Name is required.';
  if (!email.trim()) return 'Email is required.';
  if (!email.includes('@')) return 'Enter a valid email address.';
  if (password.length < 8) return 'Password must be at least 8 characters.';
  if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
    return 'Password must contain at least one letter and one number.';
  }
  if (password !== confirmPassword) return 'Passwords do not match.';
  return '';
}

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
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  function update(field) {
    return (event) => setForm((current) => ({ ...current, [field]: event.target.value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const validation = validate(form);
    if (validation) {
      setError(validation);
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
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-cyan-700">Student readiness profile</p>
            <h1 className="mt-4 text-5xl font-normal leading-[0.96] tracking-normal sm:text-6xl" style={{ fontFamily: "var(--font-display)" }}>
              Build a practice record that follows your goals.
            </h1>
            <p className="mt-5 max-w-lg text-base leading-7 text-slate-600">
              Create an account to persist your resume skills, company target, concept mastery, and interview reports.
            </p>
          </div>

          <form
            onSubmit={handleSubmit}
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
              <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <label className="mt-6 block text-sm font-medium text-slate-700">
              Name
              <input
                type="text"
                value={form.name}
                onChange={update('name')}
                className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-base outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
                placeholder="Your name"
                autoComplete="name"
              />
            </label>

            <label className="mt-4 block text-sm font-medium text-slate-700">
              Email
              <input
                type="email"
                value={form.email}
                onChange={update('email')}
                className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-base outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
                placeholder="you@example.com"
                autoComplete="email"
              />
            </label>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700">
                Password
                <input
                  type="password"
                  value={form.password}
                  onChange={update('password')}
                  className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-base outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
                  placeholder="8+ characters"
                  autoComplete="new-password"
                />
              </label>

              <label className="block text-sm font-medium text-slate-700">
                Confirm password
                <input
                  type="password"
                  value={form.confirmPassword}
                  onChange={update('confirmPassword')}
                  className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-base outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
                  placeholder="Repeat password"
                  autoComplete="new-password"
                />
              </label>
            </div>

            <p className="mt-3 text-xs leading-5 text-slate-500">
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
