'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { StudentHeader } from '@/app/components/student-header';
import { ArrowRightIcon, CompassIcon, RouteIcon, SourceIcon } from '@/app/components/ui-icons';
import { useAuth } from '@/app/providers/auth-context';
import { apiClient, type Course } from '@/services/api-client';

export default function CourseDetailPage() {
  const params = useParams<{ id: string }>();
  const { user, loading: authLoading } = useAuth();
  const [course, setCourse] = useState<Course | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (authLoading || !user) return;
    const id = Number(params.id);
    if (!id) {
      setError('Tautan mata kuliah tidak valid.');
      return;
    }
    let active = true;
    apiClient.getCourse(id).then((data) => {
      if (active) setCourse(data);
    }).catch(() => {
      if (active) setError('Mata kuliah tidak ditemukan atau belum diterbitkan.');
    });
    return () => {
      active = false;
    };
  }, [authLoading, user, params.id]);

  const lessonCount = useMemo(() => course?.modules?.reduce((total, module) => total + (module.lessons?.length || 0), 0) || 0, [course]);
  const firstLesson = course?.modules?.flatMap((module) => module.lessons || [])[0];

  if (authLoading || (user && !course && !error)) return <main className="app-page grid place-items-center">Menyiapkan mata kuliah...</main>;
  if (!user) return <main className="app-page grid place-items-center"><Link href="/login" className="btn-primary">Masuk untuk belajar</Link></main>;

  return (
    <main className="app-page min-h-screen pb-28 md:pl-[244px] md:pb-12">
      <StudentHeader />
      <div className="mx-auto max-w-6xl px-4 py-7 sm:px-7 sm:py-10">
        {error || !course ? (
          <section className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center text-red-700"><CompassIcon className="mx-auto h-10 w-10 opacity-40" /><h1 className="mt-4 text-xl font-black">Mata kuliah tidak tersedia</h1><p className="mt-2 text-sm">{error}</p><Link href="/courses" className="btn-secondary mt-5 inline-flex">Kembali ke Explore</Link></section>
        ) : (
          <>
            <Link href="/courses" className="text-sm font-black text-blue-600">&larr; Semua mata kuliah</Link>
            <header className="mt-5 overflow-hidden rounded-3xl bg-[#101b2d] text-white">
              <div className="grid gap-7 p-6 sm:p-9 lg:grid-cols-[1fr_280px] lg:items-end">
                <div><p className="text-xs font-black uppercase tracking-[.2em] text-blue-300">{course.subject?.name || 'Open course'}</p><h1 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">{course.name}</h1><p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300 sm:text-base">{course.description || 'Pelajari konsep inti, baca materi pendukung, dan uji pemahaman Anda.'}</p><div className="mt-6 flex flex-wrap gap-2 text-xs font-bold"><span className="rounded-lg bg-white/10 px-3 py-2 capitalize">{course.difficulty || 'Semua tingkat'}</span><span className="rounded-lg bg-white/10 px-3 py-2">{course.modules?.length || 0} topik</span><span className="rounded-lg bg-white/10 px-3 py-2">{lessonCount} materi</span><span className="rounded-lg bg-white/10 px-3 py-2">± {course.estimated_hours || '—'} jam</span></div></div>
                <div className="rounded-2xl border border-white/15 bg-white/5 p-5"><p className="text-xs font-black uppercase tracking-widest text-slate-400">Mulai belajar</p><p className="mt-2 text-sm leading-6 text-slate-300">Tidak ada prasyarat enrollment. Anda bebas membuka bagian mana pun.</p>{firstLesson ? <Link href={`/lessons/${firstLesson.id}`} className="mt-5 flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-black text-white hover:bg-blue-500">Buka materi pertama <ArrowRightIcon className="h-4 w-4" /></Link> : <Link href="/journey" className="mt-5 flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-black text-white">Mulai latihan <ArrowRightIcon className="h-4 w-4" /></Link>}</div>
              </div>
            </header>

            <div className="mt-7 grid items-start gap-6 lg:grid-cols-[1fr_300px]">
              <section>
                <div className="flex items-end justify-between"><div><p className="eyebrow">Course map</p><h2 className="mt-2 text-2xl font-black">Topik dan materi</h2></div><span className="text-xs text-slate-400">Semua bagian terbuka</span></div>
                <div className="mt-5 space-y-4">
                  {(course.modules || []).map((module, moduleIndex) => (
                    <article key={module.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
                      <header className="flex items-center gap-4 border-b border-slate-100 px-5 py-4 dark:border-slate-800"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-600 text-sm font-black text-white">{moduleIndex + 1}</span><div><p className="text-[10px] font-black uppercase tracking-wider text-slate-400">Topik {moduleIndex + 1}</p><h3 className="font-black">{module.name}</h3></div></header>
                      <div className="divide-y divide-slate-100 dark:divide-slate-800">
                        {(module.lessons || []).length ? module.lessons.map((lesson, lessonIndex) => <Link key={lesson.id} href={`/lessons/${lesson.id}`} className="flex items-center gap-3 px-5 py-4 transition hover:bg-slate-50 dark:hover:bg-slate-800"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-slate-100 text-xs font-black text-slate-500 dark:bg-slate-800">{lessonIndex + 1}</span><span className="min-w-0 flex-1 text-sm font-bold">{lesson.name}</span><ArrowRightIcon className="h-4 w-4 text-slate-400" /></Link>) : <p className="px-5 py-5 text-sm text-slate-500">Materi untuk topik ini sedang disiapkan.</p>}
                      </div>
                    </article>
                  ))}
                </div>
              </section>

              <aside className="space-y-4 lg:sticky lg:top-6">
                <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"><SourceIcon className="h-6 w-6 text-blue-600" /><h2 className="mt-4 font-black">Source terkait</h2><p className="mt-2 text-sm leading-6 text-slate-500">Cari buku, PDF, dan dokumen untuk memperdalam mata kuliah ini.</p><Link href={`/sources?q=${encodeURIComponent(course.subject?.name || course.name)}`} className="mt-4 inline-flex text-sm font-black text-blue-600">Cari di Sources &rarr;</Link></section>
                <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"><RouteIcon className="h-6 w-6 text-teal-600" /><h2 className="mt-4 font-black">Latihan adaptif</h2><p className="mt-2 text-sm leading-6 text-slate-500">Journey menyesuaikan tingkat soal dengan hasil latihan Anda.</p><Link href="/journey" className="mt-4 inline-flex text-sm font-black text-teal-700 dark:text-teal-300">Buka Journey &rarr;</Link></section>
              </aside>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
