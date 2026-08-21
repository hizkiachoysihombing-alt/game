'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/app/providers/auth-context';

export default function RegisterPage() {
  const { register } = useAuth();
  const [form, setForm] = useState({ fullName: '', username: '', email: '', password: '' });
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      await register(form.email, form.username, form.password, form.fullName);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(
        Array.isArray(detail)
          ? detail.map((item: any) => item.msg).join(' ')
          : typeof detail === 'string'
            ? detail
            : 'Registration failed. Please try again.'
      );
    } finally {
      setBusy(false);
    }
  }

  return <main className="min-h-screen bg-slate-950 flex items-center justify-center p-6"><form onSubmit={submit} className="card w-full max-w-md"><h1 className="text-3xl font-bold text-primary mb-2">Start learning</h1><p className="text-secondary mb-6">Create your free ElectroQuest account.</p>{error && <p className="mb-4 text-red-600">{error}</p>}<label className="block text-sm font-medium mb-4">Full name<input className="input-base mt-1" type="text" minLength={2} maxLength={255} value={form.fullName} onChange={e => setForm({ ...form, fullName: e.target.value })} required /></label><label className="block text-sm font-medium mb-4">Username<input className="input-base mt-1" type="text" minLength={3} maxLength={50} pattern="[A-Za-z0-9_-]+" title="Use only letters, numbers, underscores, or hyphens." value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} required /></label><label className="block text-sm font-medium mb-4">Email<input className="input-base mt-1" type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required /></label><label className="block text-sm font-medium">Password<input className="input-base mt-1" type="password" minLength={8} maxLength={128} value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required /></label><button className="btn-primary w-full mt-6" disabled={busy}>{busy ? 'Creating account...' : 'Create account'}</button><p className="text-secondary text-sm mt-5">Already registered? <Link className="text-blue-600" href="/login">Sign in</Link></p></form></main>;
}
