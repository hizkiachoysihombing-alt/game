'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { StudentHeader } from '@/app/components/student-header';
import { ReviewIcon, SourceIcon, StudioIcon } from '@/app/components/ui-icons';
import { useAuth } from '@/app/providers/auth-context';
import {
  apiClient,
  type ManagedQuestion,
  type QuestionStatus,
  type SourceCitation,
  type SourceDocument,
} from '@/services/api-client';

type QuestionView = ManagedQuestion & { status: QuestionStatus };

const filters: Array<{ id: 'all' | QuestionStatus; label: string }> = [
  { id: 'all', label: 'Semua' },
  { id: 'draft', label: 'Draft' },
  { id: 'pending_review', label: 'Perlu ditinjau' },
  { id: 'rejected', label: 'Perlu revisi' },
  { id: 'approved', label: 'Disetujui' },
  { id: 'published', label: 'Terbit' },
  { id: 'archived', label: 'Arsip' },
];

function statusLabel(status: QuestionStatus) {
  return {
    draft: 'Draft',
    pending_review: 'Perlu ditinjau',
    rejected: 'Perlu revisi',
    approved: 'Disetujui',
    published: 'Terbit',
    archived: 'Arsip',
  }[status];
}

function statusStyle(status: QuestionStatus) {
  if (status === 'published' || status === 'approved') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300';
  if (status === 'pending_review') return 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300';
  if (status === 'rejected') return 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300';
  if (status === 'archived') return 'bg-slate-200 text-slate-500 dark:bg-slate-800 dark:text-slate-400';
  return 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300';
}

function normalizeQuestion(value: ManagedQuestion): QuestionView {
  return {
    ...value,
    workflow_status: value.workflow_status || value.status || 'draft',
    status: value.workflow_status || value.status || 'draft',
    citations: value.citations || [],
  };
}

function extractQuestions(payload: unknown): QuestionView[] {
  if (Array.isArray(payload)) return (payload as ManagedQuestion[]).map(normalizeQuestion);
  if (!payload) return [];
  const record = payload as Record<string, unknown>;
  if (Array.isArray(record.items)) return (record.items as ManagedQuestion[]).map(normalizeQuestion);
  if (Array.isArray(record.questions)) return (record.questions as ManagedQuestion[]).map(normalizeQuestion);
  return [];
}

function citationLink(citation: SourceCitation) {
  if (citation.href) return citation.href;
  const sourceId = citation.public_id || citation.source_id || '';
  const page = citation.page_start || 1;
  return `/sources/${encodeURIComponent(sourceId)}?version_id=${citation.version_id || ''}&version=${citation.version || ''}&page=${page}`;
}

export default function StudioQuestionsPage() {
  const { user, loading: authLoading } = useAuth();
  const canManage = user?.role === 'instructor' || user?.role === 'admin';
  const [questions, setQuestions] = useState<QuestionView[]>([]);
  const [sources, setSources] = useState<SourceDocument[]>([]);
  const [status, setStatus] = useState<'all' | QuestionStatus>('all');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState('');
  const [generatorOpen, setGeneratorOpen] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [sourceId, setSourceId] = useState('');
  const [topicId, setTopicId] = useState('');
  const [count, setCount] = useState(3);
  const [pageStart, setPageStart] = useState(1);
  const [pageEnd, setPageEnd] = useState(1);
  const [sectionLabel, setSectionLabel] = useState('');
  const [guidance, setGuidance] = useState('');
  const [reviewNotes, setReviewNotes] = useState<Record<number, string>>({});

  const selectedSource = sources.find((source) => source.id === sourceId);

  async function loadQuestions() {
    setLoading(true);
    setError('');
    try {
      const payload = await apiClient.getManagedQuestions(status === 'all' ? {} : { status });
      setQuestions(extractQuestions(payload));
    } catch {
      setError('Antrean soal belum dapat dimuat.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (authLoading || !canManage) return;
    loadQuestions();
  }, [authLoading, canManage, status]);

  useEffect(() => {
    if (authLoading || !canManage) return;
    apiClient
      .getSources()
      .then((library) => setSources(library.categories.flatMap((category) => category.files)))
      .catch(() => undefined);
  }, [authLoading, canManage]);

  const visible = useMemo(() => {
    const search = query.trim().toLocaleLowerCase('id-ID');
    return questions.filter(
      (question) =>
        !search ||
        question.title.toLocaleLowerCase('id-ID').includes(search) ||
        question.topic?.name.toLocaleLowerCase('id-ID').includes(search) ||
        question.subject?.name.toLocaleLowerCase('id-ID').includes(search),
    );
  }, [questions, query]);

  async function generate(event: FormEvent) {
    event.preventDefault();
    if (!selectedSource || !topicId || !selectedSource.version.id) return;
    setBusy('generate');
    setError('');
    setMessage('');
    try {
      await apiClient.generateManagedQuestions({
        source_version_id: selectedSource.version.id,
        topic_id: Number(topicId),
        count,
        page_start: pageStart,
        page_end: Math.max(pageStart, pageEnd),
        section_label: sectionLabel.trim() || undefined,
        guidance: guidance.trim() || undefined,
      });
      setMessage('Draft soal berhasil dibuat. Periksa isi, jawaban, dan citation sebelum mengirimnya untuk ditinjau.');
      setGeneratorOpen(false);
      setStatus('draft');
      await loadQuestions();
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Draft belum dapat dibuat. Periksa konfigurasi AI, topik, dan halaman source.');
    } finally {
      setBusy('');
    }
  }

  async function submitReview(question: QuestionView) {
    setBusy(String(question.id));
    setError('');
    try {
      await apiClient.submitQuestionReview(question.id);
      setMessage('Soal dikirim ke antrean peninjauan.');
      await loadQuestions();
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Lengkapi jawaban deterministik dan citation sebelum mengirim soal.');
    } finally {
      setBusy('');
    }
  }

  async function review(question: QuestionView, action: 'approve' | 'reject') {
    setBusy(String(question.id));
    setError('');
    try {
      await apiClient.reviewManagedQuestion(question.id, action, reviewNotes[question.id] || '');
      setMessage(action === 'approve' ? 'Soal disetujui.' : 'Soal dikembalikan untuk direvisi.');
      await loadQuestions();
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Hasil review belum dapat disimpan.');
    } finally {
      setBusy('');
    }
  }

  async function transition(question: QuestionView, action: 'publish' | 'archive') {
    setBusy(String(question.id));
    setError('');
    try {
      await apiClient.transitionManagedQuestion(question.id, action);
      setMessage(action === 'publish' ? 'Soal sudah diterbitkan ke Journey.' : 'Soal dipindahkan ke arsip.');
      await loadQuestions();
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Status soal belum dapat diperbarui.');
    } finally {
      setBusy('');
    }
  }

  if (authLoading) return <main className="app-page grid place-items-center">Memeriksa izin...</main>;
  if (!user) return <main className="app-page grid place-items-center"><Link href="/login" className="btn-primary">Masuk</Link></main>;
  if (!canManage) return <main className="app-page min-h-screen pb-28 md:pl-[244px]"><StudentHeader /><div className="mx-auto max-w-xl px-4 py-16 text-center"><StudioIcon className="mx-auto h-12 w-12 text-slate-300" /><h1 className="mt-5 text-2xl font-black">Anda tidak memiliki akses ke Studio</h1><Link href="/journey" className="btn-primary mt-6 inline-flex">Buka Journey</Link></div></main>;

  return (
    <main className="app-page min-h-screen pb-28 md:pl-[244px] md:pb-12">
      <StudentHeader />
      <div className="mx-auto max-w-7xl px-4 py-7 sm:px-7 sm:py-10">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div><Link href="/studio" className="text-sm font-black text-violet-600">&larr; Content Studio</Link><h1 className="page-title">Question workflow</h1><p className="page-description">Setiap soal dimulai sebagai draft dan harus menyertakan lokasi source yang dapat diperiksa.</p></div>
          <div className="flex flex-col gap-2 sm:flex-row"><button type="button" onClick={() => { setManualOpen((value) => !value); setGeneratorOpen(false); }} className="btn-secondary flex items-center justify-center gap-2"><ReviewIcon className="h-4 w-4" />Tulis manual</button><button type="button" onClick={() => { setGeneratorOpen((value) => !value); setManualOpen(false); }} className="btn-primary flex items-center justify-center gap-2"><ReviewIcon className="h-4 w-4" />Buat dengan AI</button></div>
        </div>

        {(message || error) && <div className={`mt-5 rounded-xl border px-4 py-3 text-sm font-semibold ${error ? 'border-red-200 bg-red-50 text-red-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>{error || message}</div>}

        {manualOpen && (
          <ManualQuestionForm
            sources={sources}
            onCancel={() => setManualOpen(false)}
            onCreated={async (notice) => {
              setMessage(notice);
              setError('');
              setManualOpen(false);
              setStatus('draft');
              await loadQuestions();
            }}
            onError={(notice) => { setError(notice); setMessage(''); }}
          />
        )}

        {generatorOpen && (
          <form onSubmit={generate} className="mt-6 rounded-3xl border border-violet-200 bg-violet-50 p-5 dark:border-violet-900 dark:bg-violet-950/20 sm:p-7">
            <div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-violet-600 text-white"><ReviewIcon /></span><div><h2 className="text-lg font-black">Rancang soal berbasis source</h2><p className="text-sm text-slate-500">AI hanya membuat draft; instruktur tetap wajib memeriksa isi, jawaban, dan citation.</p></div></div>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <label className="sm:col-span-2 lg:col-span-3"><span className="mb-2 block text-sm font-bold">Source acuan</span><select value={sourceId} onChange={(event) => { const nextId = event.target.value; setSourceId(nextId); const nextSource = sources.find((source) => source.id === nextId); setTopicId(nextSource?.topics[0] ? String(nextSource.topics[0].id) : ''); }} required className="input-base"><option value="">Pilih source terbit...</option>{sources.map((source) => <option key={source.id} value={source.id}>{source.subject?.name ? `${source.subject.name} · ` : ''}{source.title || source.name}</option>)}</select></label>
              <label><span className="mb-2 block text-sm font-bold">Topik soal</span><select value={topicId} onChange={(event) => setTopicId(event.target.value)} required disabled={!selectedSource} className="input-base"><option value="">Pilih topik...</option>{selectedSource?.topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}</select></label>
              <label><span className="mb-2 block text-sm font-bold">Jumlah draft</span><input type="number" min={1} max={10} value={count} onChange={(event) => setCount(Number(event.target.value))} className="input-base" /></label>
              <label><span className="mb-2 block text-sm font-bold">Bagian/bab (opsional)</span><input value={sectionLabel} onChange={(event) => setSectionLabel(event.target.value)} className="input-base" placeholder="Contoh: Hukum Newton II" /></label>
              <label><span className="mb-2 block text-sm font-bold">Halaman mulai</span><input type="number" min={1} max={selectedSource?.version.page_count || undefined} value={pageStart} onChange={(event) => { const value = Number(event.target.value); setPageStart(value); if (pageEnd < value) setPageEnd(value); }} className="input-base" /></label>
              <label><span className="mb-2 block text-sm font-bold">Halaman akhir</span><input type="number" min={pageStart} max={selectedSource?.version.page_count || undefined} value={pageEnd} onChange={(event) => setPageEnd(Number(event.target.value))} className="input-base" /></label>
              <label className="sm:col-span-2 lg:col-span-3"><span className="mb-2 block text-sm font-bold">Arahan tambahan (opsional)</span><textarea value={guidance} onChange={(event) => setGuidance(event.target.value)} className="input-base min-h-24" placeholder="Misalnya: fokus pada penerapan konsep, bukan hafalan." /></label>
            </div>
            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><button type="button" onClick={() => setGeneratorOpen(false)} className="btn-secondary">Batal</button><button disabled={busy === 'generate' || !selectedSource || !topicId} className="btn-primary">{busy === 'generate' ? 'Membuat draft...' : `Buat ${count} draft`}</button></div>
          </form>
        )}

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari judul atau topik soal..." className="input-base" /><nav className="mt-3 flex gap-2 overflow-x-auto pb-1">{filters.map((entry) => <button key={entry.id} type="button" onClick={() => setStatus(entry.id)} className={`shrink-0 rounded-lg px-3 py-2 text-xs font-black ${status === entry.id ? 'bg-slate-950 text-white dark:bg-white dark:text-slate-950' : 'bg-slate-100 text-slate-500 dark:bg-slate-800'}`}>{entry.label}</button>)}</nav></section>

        {loading ? (
          <div className="mt-6 space-y-4">{[1, 2, 3].map((item) => <div key={item} className="h-52 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />)}</div>
        ) : visible.length === 0 ? (
          <section className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900"><ReviewIcon className="mx-auto h-10 w-10 text-slate-300" /><h2 className="mt-4 font-black">Belum ada soal di bagian ini</h2><p className="mt-1 text-sm text-slate-500">Buat draft dari source terbit atau pilih status lain.</p></section>
        ) : (
          <div className="mt-6 space-y-4">
            {visible.map((question) => (
              <article key={question.id} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900 sm:p-6">
                <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className={`rounded-md px-2 py-1 text-[10px] font-black uppercase tracking-wide ${statusStyle(question.status)}`}>{statusLabel(question.status)}</span><span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-black capitalize text-slate-500 dark:bg-slate-800">{question.difficulty}</span><span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-black text-slate-500 dark:bg-slate-800">{question.question_type.replace(/_/g, ' ')}</span></div><h2 className="mt-3 text-lg font-black">{question.title}</h2><p className="mt-1 text-xs text-slate-500">{question.subject?.name || 'Mata kuliah belum dipilih'}{question.topic?.name ? ` · ${question.topic.name}` : ''}</p></div><span className="text-xs text-slate-400">#{question.id}</span></div>
                <div className="prose mt-5 max-w-none rounded-xl bg-slate-50 p-4 text-sm dark:bg-slate-800 dark:prose-invert" dangerouslySetInnerHTML={{ __html: question.content_html }} />
                {editingId === question.id && (
                  <DraftQuestionEditor
                    question={question}
                    sources={sources}
                    onCancel={() => setEditingId(null)}
                    onSaved={async (notice) => {
                      setMessage(notice);
                      setError('');
                      setEditingId(null);
                      await loadQuestions();
                    }}
                    onError={(notice) => { setError(notice); setMessage(''); }}
                  />
                )}
                <section className="mt-4"><div className="flex items-center gap-2"><SourceIcon className="h-4 w-4 text-blue-600" /><h3 className="text-xs font-black uppercase tracking-wider text-slate-400">Citation</h3></div>{question.citations.length ? <div className="mt-2 flex flex-wrap gap-2">{question.citations.map((citation, index) => { const page = citation.page_start || 1; return <Link key={`${citation.id || citation.public_id}-${index}`} href={citationLink(citation)} className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-bold text-blue-700 hover:border-blue-400 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300">{citation.section_label || citation.title || citation.source_title || 'Source'} · hlm. {page}{citation.page_end && citation.page_end !== page ? `–${citation.page_end}` : ''}</Link>; })}</div> : <p className="mt-2 text-xs font-bold text-red-600">Belum memiliki citation. Soal tidak boleh diterbitkan.</p>}</section>
                {question.review_notes && <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">Catatan reviewer: {question.review_notes}</p>}
                {question.status === 'pending_review' && <textarea value={reviewNotes[question.id] || ''} onChange={(event) => setReviewNotes((current) => ({ ...current, [question.id]: event.target.value }))} className="input-base mt-4 min-h-20 text-sm" placeholder="Catatan pemeriksaan (wajib bila menolak)..." />}
                <div className="mt-5 flex flex-wrap justify-end gap-2">
                  {(question.status === 'draft' || question.status === 'rejected') && <button type="button" onClick={() => setEditingId(editingId === question.id ? null : question.id)} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-black text-slate-600 dark:border-slate-700 dark:text-slate-300">{editingId === question.id ? 'Tutup editor' : 'Edit draft'}</button>}
                  {(question.status === 'draft' || question.status === 'rejected') && <button type="button" disabled={busy === String(question.id) || !question.citations.length} onClick={() => submitReview(question)} className="rounded-lg bg-amber-500 px-3 py-2 text-xs font-black text-white disabled:opacity-40">Kirim tinjau</button>}
                  {question.status === 'pending_review' && <><button type="button" disabled={busy === String(question.id) || !(reviewNotes[question.id] || '').trim()} onClick={() => review(question, 'reject')} className="rounded-lg border border-red-300 px-3 py-2 text-xs font-black text-red-700 disabled:opacity-40">Minta revisi</button><button type="button" disabled={busy === String(question.id) || !question.citations.length} onClick={() => review(question, 'approve')} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-black text-white disabled:opacity-40">Setujui</button></>}
                  {question.status === 'approved' && <button type="button" disabled={busy === String(question.id)} onClick={() => transition(question, 'publish')} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-black text-white">Terbitkan ke Journey</button>}
                  {question.status === 'published' && <button type="button" disabled={busy === String(question.id)} onClick={() => transition(question, 'archive')} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-black text-slate-500">Arsipkan</button>}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

function ManualQuestionForm({
  sources,
  onCancel,
  onCreated,
  onError,
}: {
  sources: SourceDocument[];
  onCancel: () => void;
  onCreated: (message: string) => void | Promise<void>;
  onError: (message: string) => void;
}) {
  const [sourceId, setSourceId] = useState('');
  const [topicId, setTopicId] = useState('');
  const [title, setTitle] = useState('');
  const [contentHtml, setContentHtml] = useState('');
  const [solutionHtml, setSolutionHtml] = useState('');
  const [explanation, setExplanation] = useState('');
  const [questionType, setQuestionType] = useState('numerical');
  const [difficulty, setDifficulty] = useState('medium');
  const [expectedAnswer, setExpectedAnswer] = useState('');
  const [tolerance, setTolerance] = useState('0.01');
  const [units, setUnits] = useState('');
  const [pageStart, setPageStart] = useState(1);
  const [pageEnd, setPageEnd] = useState(1);
  const [sectionLabel, setSectionLabel] = useState('');
  const [busy, setBusy] = useState(false);
  const selectedSource = sources.find((source) => source.id === sourceId);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selectedSource || !topicId || !title.trim() || !contentHtml.trim() || !expectedAnswer.trim()) {
      onError('Lengkapi source, topik, judul, isi soal, dan jawaban yang diharapkan.');
      return;
    }
    setBusy(true);
    try {
      const question = await apiClient.createManagedQuestion({
        topic_id: Number(topicId),
        title: title.trim(),
        question_type: questionType,
        difficulty,
        content_html: contentHtml.trim(),
        solution_html: solutionHtml.trim() || null,
        explanation: explanation.trim() || null,
        expected_answer: expectedAnswer.trim(),
        numerical_tolerance: tolerance.trim() ? Number(tolerance) : null,
        accepted_units: units.split(',').map((unit) => unit.trim()).filter(Boolean),
        estimated_time_minutes: 5,
      });
      try {
        await apiClient.addQuestionCitation(question.id, {
          source_version_id: selectedSource.version.id,
          page_start: pageStart,
          page_end: Math.max(pageStart, pageEnd),
          section_label: sectionLabel.trim() || null,
          purpose: 'prompt',
        });
        await onCreated('Draft manual dan citation berhasil dibuat. Periksa kembali sebelum mengirimnya untuk ditinjau.');
      } catch (citationError: any) {
        await onCreated(`Draft berhasil dibuat, tetapi citation belum tersimpan: ${citationError?.response?.data?.detail || 'buka Edit draft untuk menambah citation.'}`);
      }
    } catch (requestError: any) {
      onError(requestError?.response?.data?.detail || 'Draft manual belum dapat dibuat.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-6 rounded-3xl border border-blue-200 bg-blue-50 p-5 dark:border-blue-900 dark:bg-blue-950/20 sm:p-7">
      <div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-600 text-white"><ReviewIcon /></span><div><h2 className="text-lg font-black">Tulis draft secara manual</h2><p className="text-sm text-slate-500">Jalur ini tidak memerlukan OpenAI. Jawaban dan halaman source tetap wajib diisi.</p></div></div>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <label className="sm:col-span-2"><span className="mb-2 block text-sm font-bold">Source acuan <b className="text-red-600">*</b></span><select value={sourceId} onChange={(event) => { const nextId = event.target.value; setSourceId(nextId); const nextSource = sources.find((source) => source.id === nextId); setTopicId(nextSource?.topics[0] ? String(nextSource.topics[0].id) : ''); setPageStart(1); setPageEnd(1); }} required className="input-base"><option value="">Pilih source terbit...</option>{sources.map((source) => <option key={source.id} value={source.id}>{source.subject?.name ? `${source.subject.name} · ` : ''}{source.title}</option>)}</select></label>
        <label><span className="mb-2 block text-sm font-bold">Topik <b className="text-red-600">*</b></span><select value={topicId} onChange={(event) => setTopicId(event.target.value)} required disabled={!selectedSource} className="input-base"><option value="">Pilih topik...</option>{selectedSource?.topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}</select></label>
        <label><span className="mb-2 block text-sm font-bold">Judul soal <b className="text-red-600">*</b></span><input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={3} className="input-base" /></label>
        <label><span className="mb-2 block text-sm font-bold">Tipe</span><select value={questionType} onChange={(event) => setQuestionType(event.target.value)} className="input-base"><option value="numerical">Numerik</option><option value="calculation">Perhitungan</option><option value="short_answer">Jawaban singkat</option></select></label>
        <label><span className="mb-2 block text-sm font-bold">Kesulitan</span><select value={difficulty} onChange={(event) => setDifficulty(event.target.value)} className="input-base"><option value="easy">Mudah</option><option value="medium">Menengah</option><option value="hard">Sulit</option></select></label>
        <label className="sm:col-span-2"><span className="mb-2 block text-sm font-bold">Isi soal (HTML sederhana) <b className="text-red-600">*</b></span><textarea value={contentHtml} onChange={(event) => setContentHtml(event.target.value)} required minLength={3} className="input-base min-h-28 font-mono text-sm" placeholder="<p>Sebuah rangkaian memiliki...</p>" /></label>
        <label><span className="mb-2 block text-sm font-bold">Jawaban yang diharapkan <b className="text-red-600">*</b></span><input value={expectedAnswer} onChange={(event) => setExpectedAnswer(event.target.value)} required className="input-base" placeholder="Contoh: 2 A" /></label>
        <label><span className="mb-2 block text-sm font-bold">Toleransi numerik</span><input type="number" min={0} step="any" value={tolerance} onChange={(event) => setTolerance(event.target.value)} className="input-base" /></label>
        <label className="sm:col-span-2"><span className="mb-2 block text-sm font-bold">Satuan diterima</span><input value={units} onChange={(event) => setUnits(event.target.value)} className="input-base" placeholder="A, mA (pisahkan dengan koma)" /></label>
        <label className="sm:col-span-2"><span className="mb-2 block text-sm font-bold">Solusi (HTML)</span><textarea value={solutionHtml} onChange={(event) => setSolutionHtml(event.target.value)} className="input-base min-h-24 font-mono text-sm" placeholder="<p>Langkah penyelesaian...</p>" /></label>
        <label className="sm:col-span-2"><span className="mb-2 block text-sm font-bold">Penjelasan feedback</span><textarea value={explanation} onChange={(event) => setExplanation(event.target.value)} className="input-base min-h-20" /></label>
        <label><span className="mb-2 block text-sm font-bold">Halaman mulai <b className="text-red-600">*</b></span><input type="number" min={1} max={selectedSource?.version.page_count || undefined} value={pageStart} onChange={(event) => { const value = Number(event.target.value); setPageStart(value); if (pageEnd < value) setPageEnd(value); }} required className="input-base" /></label>
        <label><span className="mb-2 block text-sm font-bold">Halaman akhir</span><input type="number" min={pageStart} max={selectedSource?.version.page_count || undefined} value={pageEnd} onChange={(event) => setPageEnd(Number(event.target.value))} className="input-base" /></label>
        <label className="sm:col-span-2"><span className="mb-2 block text-sm font-bold">Nama bagian/bab</span><input value={sectionLabel} onChange={(event) => setSectionLabel(event.target.value)} className="input-base" placeholder="Contoh: Hukum Ohm" /></label>
      </div>
      <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><button type="button" onClick={onCancel} className="btn-secondary">Batal</button><button disabled={busy || !selectedSource || !topicId || !title.trim() || !contentHtml.trim() || !expectedAnswer.trim()} className="btn-primary">{busy ? 'Menyimpan...' : 'Simpan draft manual'}</button></div>
    </form>
  );
}

function DraftQuestionEditor({
  question,
  sources,
  onCancel,
  onSaved,
  onError,
}: {
  question: QuestionView;
  sources: SourceDocument[];
  onCancel: () => void;
  onSaved: (message: string) => void | Promise<void>;
  onError: (message: string) => void;
}) {
  const supportedTypes = ['numerical', 'calculation', 'short_answer'];
  const [title, setTitle] = useState(question.title);
  const [contentHtml, setContentHtml] = useState(question.content_html);
  const [solutionHtml, setSolutionHtml] = useState(question.solution_html || '');
  const [explanation, setExplanation] = useState(question.explanation || '');
  const [expectedAnswer, setExpectedAnswer] = useState(question.expected_answer || '');
  const [difficulty, setDifficulty] = useState(question.difficulty);
  const [questionType, setQuestionType] = useState(question.question_type);
  const [tolerance, setTolerance] = useState(question.numerical_tolerance === null || question.numerical_tolerance === undefined ? '' : String(question.numerical_tolerance));
  const [units, setUnits] = useState((question.accepted_units || []).join(', '));
  const compatibleSources = sources.filter((source) => !question.topic || source.topics.some((topic) => topic.id === question.topic?.id));
  const [citationSourceId, setCitationSourceId] = useState(compatibleSources[0]?.id || '');
  const [citationPageStart, setCitationPageStart] = useState(1);
  const [citationPageEnd, setCitationPageEnd] = useState(1);
  const [citationSection, setCitationSection] = useState('');
  const [busy, setBusy] = useState('');
  const citationSource = compatibleSources.find((source) => source.id === citationSourceId);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !contentHtml.trim() || !expectedAnswer.trim()) {
      onError('Judul, isi soal, dan jawaban yang diharapkan wajib diisi.');
      return;
    }
    setBusy('save');
    try {
      await apiClient.updateManagedQuestion(question.id, {
        title: title.trim(),
        content_html: contentHtml.trim(),
        solution_html: solutionHtml.trim() || null,
        explanation: explanation.trim() || null,
        expected_answer: expectedAnswer.trim(),
        question_type: questionType,
        difficulty,
        numerical_tolerance: tolerance.trim() ? Number(tolerance) : null,
        accepted_units: units.split(',').map((unit) => unit.trim()).filter(Boolean),
      });
      await onSaved(question.status === 'rejected' ? 'Revisi tersimpan dan status dikembalikan menjadi Draft.' : 'Perubahan draft berhasil disimpan.');
    } catch (requestError: any) {
      onError(requestError?.response?.data?.detail || 'Perubahan draft belum dapat disimpan.');
    } finally {
      setBusy('');
    }
  }

  async function addCitation() {
    if (!citationSource) {
      onError('Tidak ada source terbit yang cocok dengan topik soal ini.');
      return;
    }
    setBusy('citation');
    try {
      await apiClient.addQuestionCitation(question.id, {
        source_version_id: citationSource.version.id,
        page_start: citationPageStart,
        page_end: Math.max(citationPageStart, citationPageEnd),
        section_label: citationSection.trim() || null,
        purpose: 'prompt',
      });
      await onSaved('Citation berhasil ditambahkan dan draft diperbarui.');
    } catch (requestError: any) {
      onError(requestError?.response?.data?.detail || 'Citation belum dapat ditambahkan.');
    } finally {
      setBusy('');
    }
  }

  async function removeCitation(citation: SourceCitation) {
    if (!citation.id) return;
    setBusy(`citation-${citation.id}`);
    try {
      await apiClient.deleteQuestionCitation(question.id, citation.id);
      await onSaved('Citation dihapus; soal tetap menjadi Draft sampai citation pengganti ditambahkan.');
    } catch (requestError: any) {
      onError(requestError?.response?.data?.detail || 'Citation belum dapat dihapus.');
    } finally {
      setBusy('');
    }
  }

  return (
    <section className="mt-5 rounded-2xl border border-violet-200 bg-violet-50 p-4 dark:border-violet-900 dark:bg-violet-950/20 sm:p-5">
      <div className="flex items-center justify-between gap-3"><div><h3 className="font-black">Edit draft #{question.id}</h3><p className="mt-1 text-xs text-slate-500">Menyimpan perubahan akan membatalkan approval lama dan mengembalikan soal ke Draft.</p></div><button type="button" onClick={onCancel} className="text-sm font-black text-slate-500">Tutup</button></div>
      <form onSubmit={save} className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-black">Judul</span><input value={title} onChange={(event) => setTitle(event.target.value)} required className="input-base" /></label>
        <label><span className="mb-1.5 block text-xs font-black">Tipe</span><select value={questionType} onChange={(event) => setQuestionType(event.target.value)} className="input-base">{!supportedTypes.includes(questionType) && <option value={questionType}>{questionType.replace(/_/g, ' ')} (opsi lanjutan)</option>}{supportedTypes.map((type) => <option key={type} value={type}>{type.replace(/_/g, ' ')}</option>)}</select></label>
        <label><span className="mb-1.5 block text-xs font-black">Kesulitan</span><select value={difficulty} onChange={(event) => setDifficulty(event.target.value)} className="input-base"><option value="easy">Mudah</option><option value="medium">Menengah</option><option value="hard">Sulit</option></select></label>
        <label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-black">Isi soal (HTML)</span><textarea value={contentHtml} onChange={(event) => setContentHtml(event.target.value)} required className="input-base min-h-28 font-mono text-sm" /></label>
        <label><span className="mb-1.5 block text-xs font-black">Jawaban yang diharapkan</span><input value={expectedAnswer} onChange={(event) => setExpectedAnswer(event.target.value)} required className="input-base" /></label>
        <label><span className="mb-1.5 block text-xs font-black">Toleransi</span><input type="number" min={0} step="any" value={tolerance} onChange={(event) => setTolerance(event.target.value)} className="input-base" /></label>
        <label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-black">Satuan diterima</span><input value={units} onChange={(event) => setUnits(event.target.value)} className="input-base" placeholder="A, mA" /></label>
        <label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-black">Solusi (HTML)</span><textarea value={solutionHtml} onChange={(event) => setSolutionHtml(event.target.value)} className="input-base min-h-24 font-mono text-sm" /></label>
        <label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-black">Penjelasan feedback</span><textarea value={explanation} onChange={(event) => setExplanation(event.target.value)} className="input-base min-h-20" /></label>
        <div className="sm:col-span-2 flex justify-end"><button disabled={busy === 'save'} className="btn-primary">{busy === 'save' ? 'Menyimpan...' : 'Simpan perubahan'}</button></div>
      </form>

      <div className="mt-6 border-t border-violet-200 pt-5 dark:border-violet-900"><h4 className="text-xs font-black uppercase tracking-wider text-violet-700 dark:text-violet-300">Kelola citation</h4>{question.citations.length > 0 && <div className="mt-3 space-y-2">{question.citations.map((citation, index) => <div key={citation.id || index} className="flex items-center gap-3 rounded-lg border border-violet-200 bg-white px-3 py-2 dark:border-violet-900 dark:bg-slate-900"><Link href={citationLink(citation)} target="_blank" className="min-w-0 flex-1 truncate text-xs font-bold text-blue-700">{citation.section_label || citation.title || 'Source'} · hlm. {citation.page_start || 1}</Link>{citation.id && <button type="button" disabled={busy === `citation-${citation.id}`} onClick={() => removeCitation(citation)} className="shrink-0 text-xs font-black text-red-600">Hapus</button>}</div>)}</div>}
        <div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-black">Source terbit yang cocok dengan topik</span><select value={citationSourceId} onChange={(event) => setCitationSourceId(event.target.value)} className="input-base" disabled={!compatibleSources.length}><option value="">Pilih source...</option>{compatibleSources.map((source) => <option key={source.id} value={source.id}>{source.title}</option>)}</select></label><label><span className="mb-1.5 block text-xs font-black">Halaman mulai</span><input type="number" min={1} max={citationSource?.version.page_count || undefined} value={citationPageStart} onChange={(event) => { const value = Number(event.target.value); setCitationPageStart(value); if (citationPageEnd < value) setCitationPageEnd(value); }} className="input-base" /></label><label><span className="mb-1.5 block text-xs font-black">Halaman akhir</span><input type="number" min={citationPageStart} max={citationSource?.version.page_count || undefined} value={citationPageEnd} onChange={(event) => setCitationPageEnd(Number(event.target.value))} className="input-base" /></label><label className="sm:col-span-2"><span className="mb-1.5 block text-xs font-black">Nama bagian/bab</span><input value={citationSection} onChange={(event) => setCitationSection(event.target.value)} className="input-base" /></label></div><button type="button" onClick={addCitation} disabled={busy === 'citation' || !citationSource} className="btn-secondary mt-3">{busy === 'citation' ? 'Menambahkan...' : 'Tambah citation'}</button>{!compatibleSources.length && <p className="mt-2 text-xs font-semibold text-red-600">Tidak ada source terbit yang diklasifikasikan ke topik soal ini.</p>}</div>
    </section>
  );
}
