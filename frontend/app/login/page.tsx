'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/app/providers/auth-context';

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true);
    try { await login(email, password); } catch (err: any) { setError(err.response?.data?.detail || 'Login failed'); } finally { setBusy(false); }
  }

  return <main className="min-h-screen bg-slate-950 flex items-center justify-center p-6"><form onSubmit={submit} className="card w-full max-w-md bg-white dark:bg-slate-900"><h1 className="text-3xl font-bold text-primary mb-2">Welcome back</h1><p className="text-secondary mb-6">Continue your engineering journey.</p>{error && <p className="mb-4 text-red-600">{error}</p>}<label className="block text-sm font-medium mb-2">Email or username<input className="input-base mt-1" value={email} onChange={e => setEmail(e.target.value)} required /></label><label className="block text-sm font-medium mt-4 mb-2">Password<input className="input-base mt-1" type="password" value={password} onChange={e => setPassword(e.target.value)} required /></label><button className="btn-primary w-full mt-6" disabled={busy}>{busy ? 'Signing in...' : 'Sign in'}</button><p className="text-secondary text-sm mt-5">New to ElectroQuest? <Link className="text-blue-600" href="/register">Create an account</Link></p></form></main>;
}
