'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/app/providers/auth-context';

export default function RegisterPage() {
  const { register } = useAuth();
  const [form, setForm] = useState({ fullName: '', username: '', email: '', password: '' });
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setError(''); setBusy(true); try { await register(form.email, form.username, form.password, form.fullName); } catch (err: any) { setError(err.response?.data?.detail || 'Registration failed'); } finally { setBusy(false); } }
  return <main className="min-h-screen bg-slate-950 flex items-center justify-center p-6"><form onSubmit={submit} className="card w-full max-w-md"><h1 className="text-3xl font-bold text-primary mb-2">Start learning</h1><p className="text-secondary mb-6">Create your free ElectroQuest account.</p>{error && <p className="mb-4 text-red-600">{error}</p>}{[['fullName','Full name'],['username','Username'],['email','Email']].map(([key,label]) => <label key={key} className="block text-sm font-medium mb-4">{label}<input className="input-base mt-1" type={key === 'email' ? 'email' : 'text'} value={(form as any)[key]} onChange={e => setForm({ ...form, [key]: e.target.value })} required /></label>)}<label className="block text-sm font-medium">Password<input className="input-base mt-1" type="password" minLength={8} value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required /></label><button className="btn-primary w-full mt-6" disabled={busy}>{busy ? 'Creating account...' : 'Create account'}</button><p className="text-secondary text-sm mt-5">Already registered? <Link className="text-blue-600" href="/login">Sign in</Link></p></form></main>;
}
