'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { StudentHeader } from '@/app/components/student-header';
import { ArrowRightIcon, ReviewIcon, SourceIcon, StudioIcon, UploadIcon } from '@/app/components/ui-icons';
import { useAuth } from '@/app/providers/auth-context';
import { apiClient, type SourceManagementDashboard } from '@/services/api-client';

const emptyDashboard: SourceManagementDashboard = {
  sources: { inbox: 0, review_pending: 0, published: 0, archived: 0 },
  questions: {},
  open_reports: 0,
};

export default function StudioPage() {
  const { user, loading: authLoading } = useAuth();
  const [dashboard, setDashboard] = useState<SourceManagementDashboard>(emptyDashboard);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const canManage = user?.role === 'instructor' || user?.role === 'admin';

  useEffect(() => {
    if (authLoading || !canManage) return;
    let active = true;
    apiClient.getSourceManagementDashboard().then((data) => {
      if (active) setDashboard({ ...emptyDashboard, ...data, sources: { ...emptyDashboard.sources, ...data.sources }, questions: data.questions || {} });
    }).catch(() => {
      if (active) setError('Ringkasan Content Studio belum dapat dimuat.');
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [authLoading, canManage]);

  if (authLoading) return <main className="app-page grid place-items-center">Memeriksa izin...</main>;
  if (!user) return <main className="app-page grid place-items-center"><Link href="/login" className="btn-primary">Masuk</Link></main>;
  if (!canManage) return <main className="app-page min-h-screen pb-28 md:pl-[244px]"><StudentHeader /><div className="mx-auto max-w-xl px-4 py-16 text-center"><StudioIcon className="mx-auto h-12 w-12 text-slate-300" /><h1 className="mt-5 text-2xl font-black">Content Studio khusus pengelola</h1><p className="mt-2 text-sm leading-6 text-slate-500">Akun mahasiswa tetap dapat membaca source yang sudah ditinjau dan diterbitkan.</p><Link href="/sources" className="btn-primary mt-6 inline-flex">Buka Sources</Link></div></main>;

  const statusCards = [
    { label: 'Inbox', value: dashboard.sources.inbox, color: 'text-slate-700 bg-slate-100 dark:bg-slate-800 dark:text-slate-200' },
    { label: 'Perlu ditinjau', value: dashboard.sources.review_pending, color: 'text-amber-700 bg-amber-100 dark:bg-amber-950 dark:text-amber-300' },
    { label: 'Terbit', value: dashboard.sources.published, color: 'text-emerald-700 bg-emerald-100 dark:bg-emerald-950 dark:text-emerald-300' },
    { label: 'Arsip', value: dashboard.sources.archived, color: 'text-slate-500 bg-slate-100 dark:bg-slate-800 dark:text-slate-400' },
  ];

  return (
    <main className="app-page min-h-screen pb-28 md:pl-[244px] md:pb-12">
      <StudentHeader />
      <div className="mx-auto max-w-6xl px-4 py-7 sm:px-7 sm:py-10">
        <header className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between"><div><p className="eyebrow">Instructor workspace</p><h1 className="page-title">Content Studio</h1><p className="page-description">Kelola source dari upload hingga terbit, lalu buat soal yang selalu memiliki citation jelas.</p></div><span className="rounded-lg bg-violet-100 px-3 py-2 text-xs font-black capitalize text-violet-700 dark:bg-violet-950 dark:text-violet-300">{user.role}</span></header>
        {error && <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800">{error}</div>}

        <section className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {statusCards.map((card) => <article key={card.label} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"><div className="flex items-center justify-between"><p className="text-[11px] font-black uppercase tracking-wider text-slate-400">{card.label}</p><span className={`h-2.5 w-2.5 rounded-full ${card.color}`} /></div><p className="mt-4 text-3xl font-black">{loading ? '—' : card.value}</p><p className="mt-1 text-xs text-slate-500">source</p></article>)}
        </section>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <Link href="/studio/sources" className="group rounded-3xl border border-slate-200 bg-white p-7 transition hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900"><div className="flex items-start justify-between"><span className="grid h-12 w-12 place-items-center rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"><SourceIcon /></span><ArrowRightIcon className="text-slate-400 transition group-hover:translate-x-1 group-hover:text-blue-600" /></div><h2 className="mt-6 text-2xl font-black">Kelola Sources</h2><p className="mt-2 text-sm leading-6 text-slate-500">Upload dokumen, tentukan mata kuliah dan topik, periksa versi, lalu publikasikan ke mahasiswa.</p><div className="mt-6 flex gap-2 text-xs font-bold"><span className="rounded-lg bg-slate-100 px-3 py-2 dark:bg-slate-800">{Object.values(dashboard.sources).reduce((sum, value) => sum + value, 0)} total</span><span className="rounded-lg bg-amber-50 px-3 py-2 text-amber-700 dark:bg-amber-950 dark:text-amber-300">{dashboard.sources.review_pending} menunggu</span></div></Link>
          <Link href="/studio/questions" className="group rounded-3xl border border-slate-200 bg-white p-7 transition hover:-translate-y-0.5 hover:border-violet-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900"><div className="flex items-start justify-between"><span className="grid h-12 w-12 place-items-center rounded-xl bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300"><ReviewIcon /></span><ArrowRightIcon className="text-slate-400 transition group-hover:translate-x-1 group-hover:text-violet-600" /></div><h2 className="mt-6 text-2xl font-black">Question Review</h2><p className="mt-2 text-sm leading-6 text-slate-500">Buat draft dari source, validasi jawaban dan citation, lalu kirim ke Journey setelah disetujui.</p><div className="mt-6 flex gap-2 text-xs font-bold"><span className="rounded-lg bg-slate-100 px-3 py-2 dark:bg-slate-800">{dashboard.questions.draft || 0} draft</span><span className="rounded-lg bg-amber-50 px-3 py-2 text-amber-700 dark:bg-amber-950 dark:text-amber-300">{dashboard.questions.pending_review || 0} menunggu</span></div></Link>
        </div>

        <section className="mt-6 rounded-3xl bg-[#101b2d] p-6 text-white sm:p-8"><div className="grid gap-6 md:grid-cols-3"><div><UploadIcon className="h-6 w-6 text-blue-300" /><h3 className="mt-4 font-black">1. Upload dan klasifikasi</h3><p className="mt-2 text-sm leading-6 text-slate-300">File masuk ke Inbox dan tidak langsung terlihat oleh mahasiswa.</p></div><div><ReviewIcon className="h-6 w-6 text-amber-300" /><h3 className="mt-4 font-black">2. Tinjau isi</h3><p className="mt-2 text-sm leading-6 text-slate-300">Periksa metadata, hak penggunaan, versi, halaman, dan kualitas citation.</p></div><div><StudioIcon className="h-6 w-6 text-emerald-300" /><h3 className="mt-4 font-black">3. Terbitkan</h3><p className="mt-2 text-sm leading-6 text-slate-300">Hanya source dan soal yang disetujui masuk ke pengalaman belajar.</p></div></div></section>
      </div>
    </main>
  );
}
