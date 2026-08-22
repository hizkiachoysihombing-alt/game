'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { StudentHeader } from '@/app/components/student-header';
import { ArrowRightIcon, CompassIcon, SourceIcon } from '@/app/components/ui-icons';
import { useAuth } from '@/app/providers/auth-context';
import { apiClient, type Course } from '@/services/api-client';

export default function CoursesPage() {
  const { user, loading: authLoading } = useAuth();
  const [courses, setCourses] = useState<Course[]>([]);
  const [query, setQuery] = useState('');
  const [subject, setSubject] = useState('all');
  const [difficulty, setDifficulty] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (authLoading || !user) return;
    let active = true;
    setLoading(true);
    apiClient
      .getCourses()
      .then((data) => {
        if (active) setCourses(data);
      })
      .catch(() => {
        if (active) setError('Katalog mata kuliah belum dapat dimuat.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authLoading, user]);

  const subjects = useMemo(() => {
    const values = new Map<number, string>();
    courses.forEach((course) => {
      if (course.subject) values.set(course.subject.id, course.subject.name);
    });
    return Array.from(values, ([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name, 'id'));
  }, [courses]);

  const visible = useMemo(() => {
    const search = query.trim().toLocaleLowerCase('id-ID');
    return courses.filter((course) =>
      (!search || course.name.toLocaleLowerCase('id-ID').includes(search) || course.description?.toLocaleLowerCase('id-ID').includes(search) || course.subject?.name.toLocaleLowerCase('id-ID').includes(search)) &&
      (subject === 'all' || String(course.subject?.id) === subject) &&
      (difficulty === 'all' || course.difficulty === difficulty),
    );
  }, [courses, query, subject, difficulty]);

  if (authLoading) return <main className="app-page grid place-items-center">Memeriksa akun...</main>;
  if (!user) return <main className="app-page grid place-items-center"><Link href="/login" className="btn-primary">Masuk untuk menjelajah</Link></main>;

  return (
    <main className="app-page min-h-screen pb-28 md:pl-[244px] md:pb-12">
      <StudentHeader />
      <div className="mx-auto max-w-6xl px-4 py-7 sm:px-7 sm:py-10">
        <header className="rounded-3xl bg-[#101b2d] p-6 text-white sm:p-9">
          <p className="text-xs font-black uppercase tracking-[.2em] text-blue-300">Open learning explorer</p>
          <h1 className="mt-3 max-w-3xl text-3xl font-black tracking-tight sm:text-4xl">Pelajari mata kuliah apa pun, tanpa menunggu kurikulum kampus.</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">Seluruh mata kuliah yang sudah diterbitkan terbuka. Pilih topik yang Anda butuhkan, baca materinya, lalu lanjutkan latihan adaptif.</p>
          <div className="mt-6 flex flex-wrap gap-3 text-xs font-bold"><span className="rounded-lg bg-white/10 px-3 py-2">{courses.length} mata kuliah</span><span className="rounded-lg bg-white/10 px-3 py-2">Bebas dipilih</span><span className="rounded-lg bg-white/10 px-3 py-2">Terhubung dengan Sources</span></div>
        </header>

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari mata kuliah atau topik..." className="input-base" aria-label="Cari mata kuliah" />
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <select value={subject} onChange={(event) => setSubject(event.target.value)} className="input-base py-2.5 text-sm" aria-label="Filter rumpun mata kuliah"><option value="all">Semua rumpun</option>{subjects.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select>
            <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)} className="input-base py-2.5 text-sm" aria-label="Filter tingkat"><option value="all">Semua tingkat</option><option value="beginner">Pemula</option><option value="intermediate">Menengah</option><option value="advanced">Lanjutan</option></select>
          </div>
        </section>

        {error ? <div className="mt-7 rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">{error}</div> : loading ? <div className="mt-7 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{[1, 2, 3, 4, 5, 6].map((item) => <div key={item} className="h-64 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />)}</div> : visible.length === 0 ? <div className="mt-7 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900"><CompassIcon className="mx-auto h-10 w-10 text-slate-300" /><h2 className="mt-4 font-black">Mata kuliah tidak ditemukan</h2><button type="button" onClick={() => { setQuery(''); setSubject('all'); setDifficulty('all'); }} className="mt-4 text-sm font-black text-blue-600">Hapus filter</button></div> : (
          <div className="mt-7 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map((course, index) => {
              const lessons = (course.modules || []).reduce((total, module) => total + (module.lessons || []).length, 0);
              return <article key={course.id} className="flex min-h-64 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-800 dark:bg-slate-900"><div className={`h-2 ${['bg-blue-600', 'bg-teal-600', 'bg-violet-600'][index % 3]}`} /><div className="flex flex-1 flex-col p-6"><div className="flex items-start justify-between gap-3"><span className="rounded-lg bg-blue-50 px-2.5 py-1 text-[10px] font-black uppercase tracking-wide text-blue-700 dark:bg-blue-950 dark:text-blue-300">{course.subject?.name || 'Engineering'}</span><span className="text-xs font-bold capitalize text-slate-400">{course.difficulty || 'open'}</span></div><h2 className="mt-5 text-xl font-black leading-tight">{course.name}</h2><p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-500">{course.description || 'Jelajahi materi, source, dan latihan dalam mata kuliah ini.'}</p><div className="mt-auto flex items-center justify-between border-t border-slate-100 pt-5 text-xs text-slate-500 dark:border-slate-800"><span>{course.modules?.length || 0} topik · {lessons} materi</span><span>{course.estimated_hours || '—'} jam</span></div><Link href={`/courses/${course.id}`} className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-3 text-sm font-black text-white hover:bg-blue-600 dark:bg-white dark:text-slate-950">Buka mata kuliah <ArrowRightIcon className="h-4 w-4" /></Link></div></article>;
            })}
          </div>
        )}

        <section className="mt-8 flex flex-col gap-4 rounded-2xl border border-blue-200 bg-blue-50 p-6 dark:border-blue-900 dark:bg-blue-950/30 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-start gap-3"><SourceIcon className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" /><div><h2 className="font-black text-blue-950 dark:text-blue-100">Butuh referensi sebelum mulai?</h2><p className="mt-1 text-sm text-blue-800 dark:text-blue-300">Buka Source Library dan cari dokumen berdasarkan mata kuliah atau topik.</p></div></div><Link href="/sources" className="shrink-0 text-sm font-black text-blue-700 dark:text-blue-300">Lihat Sources &rarr;</Link></section>
      </div>
    </main>
  );
}
