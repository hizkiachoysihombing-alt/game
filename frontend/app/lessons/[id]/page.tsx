'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { StudentHeader } from '@/app/components/student-header';
import { CheckIcon, SourceIcon } from '@/app/components/ui-icons';
import { useAuth } from '@/app/providers/auth-context';
import { apiClient, type Lesson } from '@/services/api-client';

export default function LessonPage() {
  const params = useParams<{ id: string }>();
  const { user, loading: authLoading } = useAuth();
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (authLoading || !user) return;
    const lessonId = Number(params.id);
    if (!lessonId) {
      setError('Tautan materi tidak valid.');
      return;
    }
    let active = true;
    apiClient.getLesson(lessonId).then((data) => {
      if (active) setLesson(data);
    }).catch(() => {
      if (active) setError('Materi tidak ditemukan atau belum diterbitkan.');
    });
    return () => {
      active = false;
    };
  }, [authLoading, user, params.id]);

  async function markComplete() {
    if (!lesson || saving || lesson.progress.is_completed) return;
    setSaving(true);
    try {
      await apiClient.markLessonComplete(lesson.id);
      setLesson({ ...lesson, progress: { is_completed: true } });
    } catch {
      setError('Progress belum dapat disimpan. Silakan coba lagi.');
    } finally {
      setSaving(false);
    }
  }

  if (authLoading || (user && !lesson && !error)) return <main className="app-page grid place-items-center">Memuat materi...</main>;
  if (!user) return <main className="app-page grid place-items-center"><Link href="/login" className="btn-primary">Masuk untuk belajar</Link></main>;

  return (
    <main className="app-page min-h-screen pb-28 md:pl-[244px] md:pb-12">
      <StudentHeader />
      <div className="mx-auto max-w-5xl px-4 py-7 sm:px-7 sm:py-10">
        {error && !lesson ? (
          <section className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center text-red-700"><h1 className="text-xl font-black">Materi tidak tersedia</h1><p className="mt-2 text-sm">{error}</p><Link href="/courses" className="btn-secondary mt-5 inline-flex">Kembali ke Explore</Link></section>
        ) : lesson ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3"><Link href={lesson.course ? `/courses/${lesson.course.id}` : '/courses'} className="text-sm font-black text-blue-600">&larr; {lesson.course?.name || 'Explore'}</Link><span className={`rounded-lg px-3 py-1.5 text-xs font-black ${lesson.progress.is_completed ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-300'}`}>{lesson.progress.is_completed ? 'Selesai' : 'Sedang dipelajari'}</span></div>
            <header className="mt-5 rounded-3xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900 sm:p-9"><p className="eyebrow">Learning material</p><h1 className="page-title">{lesson.name}</h1><p className="mt-3 text-sm text-slate-500">Baca materi, buka referensi asli, kemudian tandai selesai saat konsepnya sudah dipahami.</p></header>

            {error && <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{error}</div>}

            <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1fr_260px]">
              <article className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900 sm:p-9"><div className="prose max-w-none leading-7 dark:prose-invert" dangerouslySetInnerHTML={{ __html: lesson.content_html }} /></article>
              <aside className="space-y-4 lg:sticky lg:top-6">
                <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"><h2 className="font-black">Progress materi</h2><p className="mt-2 text-sm leading-6 text-slate-500">Menandai materi selesai membantu aplikasi menyusun rekomendasi berikutnya.</p><button type="button" onClick={markComplete} disabled={saving || lesson.progress.is_completed} className={`mt-4 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-black ${lesson.progress.is_completed ? 'bg-emerald-100 text-emerald-700' : 'bg-blue-600 text-white hover:bg-blue-700'} disabled:cursor-default`}><CheckIcon className="h-4 w-4" />{lesson.progress.is_completed ? 'Sudah selesai' : saving ? 'Menyimpan...' : 'Tandai selesai'}</button></section>
                <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"><div className="flex items-center gap-2"><SourceIcon className="h-5 w-5 text-blue-600" /><h2 className="font-black">Referensi materi</h2></div>{lesson.citations?.length ? <div className="mt-4 space-y-2">{lesson.citations.map((citation, index) => { const publicId = citation.public_id || citation.source_id || ''; const page = citation.page_start || 1; const href = citation.href || `/sources/${encodeURIComponent(publicId)}?version_id=${citation.version_id || ''}&version=${citation.version || ''}&page=${page}`; return <Link key={`${publicId}-${index}`} href={href} className="block rounded-xl border border-blue-100 bg-blue-50 p-3 text-sm text-blue-900 transition hover:border-blue-300 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-200"><strong className="block text-xs">{citation.label || citation.section_label || citation.title || citation.source_title || 'Buka source'}</strong><span className="mt-1 block text-[11px] text-blue-600 dark:text-blue-400">Halaman {page}{citation.page_end && citation.page_end !== page ? `–${citation.page_end}` : ''} &rarr;</span></Link>; })}</div> : <><p className="mt-2 text-sm leading-6 text-slate-500">Belum ada citation khusus untuk materi ini.</p><Link href="/sources" className="mt-4 inline-flex text-sm font-black text-blue-600">Cari di Sources &rarr;</Link></>}</section>
              </aside>
            </div>
          </>
        ) : null}
      </div>
    </main>
  );
}
