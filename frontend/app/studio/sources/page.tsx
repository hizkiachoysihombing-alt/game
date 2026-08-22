'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { StudentHeader } from '@/app/components/student-header';
import { SourceIcon, StudioIcon, UploadIcon } from '@/app/components/ui-icons';
import { useAuth } from '@/app/providers/auth-context';
import { apiClient, type ManagedSource, type SourceDocument, type SourceStatus } from '@/services/api-client';

type CurriculumSubject = { id: number; name: string; topics: Array<{ id: number; name: string }> };

const statuses: Array<{ id: 'all' | SourceStatus; label: string }> = [
  { id: 'all', label: 'Semua' },
  { id: 'inbox', label: 'Inbox' },
  { id: 'review_pending', label: 'Perlu ditinjau' },
  { id: 'published', label: 'Terbit' },
  { id: 'archived', label: 'Arsip' },
];

function statusStyle(status: SourceStatus) {
  if (status === 'published') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300';
  if (status === 'review_pending') return 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300';
  if (status === 'archived') return 'bg-slate-200 text-slate-500 dark:bg-slate-800 dark:text-slate-400';
  return 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300';
}

function statusLabel(status: SourceStatus) {
  return { inbox: 'Inbox', review_pending: 'Perlu ditinjau', published: 'Terbit', archived: 'Arsip' }[status];
}

function normalizeManaged(value: Partial<ManagedSource> & { id: string; name?: string }): ManagedSource {
  const version = value.version || { id: 0, version_number: 1, page_count: null };
  const base: SourceDocument = {
    id: value.id,
    legacy_id: value.legacy_id,
    title: value.title || value.name || 'Source',
    name: value.name || value.title || 'Source',
    description: value.description || null,
    extension: (value.extension || version.extension || version.file_name?.split('.').pop() || 'pdf').replace('.', '').toLowerCase(),
    size_bytes: value.size_bytes || version.size_bytes || 0,
    content_type: value.content_type || version.content_type || 'application/octet-stream',
    status: value.status || 'inbox',
    subject: value.subject || null,
    topics: value.topics || [],
    version,
    is_bookmarked: false,
    reading_progress: 0,
    last_page: null,
    updated_at: value.updated_at || null,
  };
  return { ...base, created_at: value.created_at, review_notes: value.review_notes, versions: value.versions || [base.version] };
}

function extractManaged(payload: unknown): ManagedSource[] {
  if (Array.isArray(payload)) return payload.map((item) => normalizeManaged(item as Partial<ManagedSource> & { id: string }));
  if (!payload) return [];
  const record = payload as Record<string, unknown>;
  if (Array.isArray(record.items)) return extractManaged(record.items);
  if (Array.isArray(record.sources)) return extractManaged(record.sources);
  if (Array.isArray(record.documents)) return extractManaged(record.documents);
  if (Array.isArray(record.categories)) {
    return (record.categories as Array<{ files?: unknown[] }>).flatMap((category) => extractManaged(category.files || []));
  }
  return [];
}

export default function StudioSourcesPage() {
  const { user, loading: authLoading } = useAuth();
  const canManage = user?.role === 'instructor' || user?.role === 'admin';
  const [sources, setSources] = useState<ManagedSource[]>([]);
  const [curriculum, setCurriculum] = useState<CurriculumSubject[]>([]);
  const [status, setStatus] = useState<'all' | SourceStatus>('all');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [busy, setBusy] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [subjectId, setSubjectId] = useState('');
  const [topicIds, setTopicIds] = useState<string[]>([]);

  async function loadSources() {
    setLoading(true);
    setError('');
    try {
      const payload = await apiClient.getManagedSources(status === 'all' ? {} : { status });
      setSources(extractManaged(payload));
    } catch {
      setError('Daftar source belum dapat dimuat.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (authLoading || !canManage) return;
    loadSources();
  }, [authLoading, canManage, status]);

  useEffect(() => {
    if (authLoading || !canManage) return;
    apiClient.getSourceTaxonomy().then((taxonomy) => {
      setCurriculum(taxonomy.subjects.map((subject) => ({
        id: subject.id,
        name: subject.name,
        topics: taxonomy.topics.filter((topic) => topic.subject_id === subject.id).map((topic) => ({ id: topic.id, name: topic.name })),
      })));
    }).catch(() => undefined);
  }, [authLoading, canManage]);

  const visible = useMemo(() => {
    const search = query.trim().toLocaleLowerCase('id-ID');
    return sources.filter((source) => !search || source.title.toLocaleLowerCase('id-ID').includes(search) || source.subject?.name.toLocaleLowerCase('id-ID').includes(search) || source.topics.some((topic) => topic.name.toLocaleLowerCase('id-ID').includes(search)));
  }, [sources, query]);

  const selectedSubject = curriculum.find((entry) => String(entry.id) === subjectId);

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file || !title.trim() || !subjectId || topicIds.length === 0) {
      setError('Pilih mata kuliah dan minimal satu topik agar source tidak tertahan di Inbox.');
      return;
    }
    setBusy('upload');
    setError('');
    setMessage('');
    try {
      await apiClient.uploadManagedSource({ file, title: title.trim(), description: description.trim() || undefined, subjectId: subjectId ? Number(subjectId) : undefined, topicIds: topicIds.map(Number) });
      setMessage('Source berhasil masuk ke Inbox. Periksa klasifikasi sebelum mengirimnya untuk ditinjau.');
      setFile(null);
      setTitle('');
      setDescription('');
      setSubjectId('');
      setTopicIds([]);
      setUploadOpen(false);
      setStatus('all');
      await loadSources();
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Upload gagal. Pastikan file PDF/DOCX valid dan bukan duplikat.');
    } finally {
      setBusy('');
    }
  }

  async function transition(source: ManagedSource, action: 'review' | 'publish' | 'archive') {
    setBusy(source.id);
    setError('');
    setMessage('');
    try {
      await apiClient.transitionManagedSource(source.id, action);
      setMessage(action === 'review' ? 'Source dikirim untuk ditinjau.' : action === 'publish' ? 'Source sudah diterbitkan.' : 'Source dipindahkan ke arsip.');
      await loadSources();
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Status source belum dapat diperbarui.');
    } finally {
      setBusy('');
    }
  }

  async function uploadVersion(source: ManagedSource, versionFile?: File) {
    if (!versionFile) return;
    setBusy(source.id);
    setError('');
    try {
      await apiClient.addManagedSourceVersion(source.id, versionFile);
      setMessage(`Versi baru untuk “${source.title}” berhasil ditambahkan.`);
      await loadSources();
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Versi baru belum dapat diunggah.');
    } finally {
      setBusy('');
    }
  }

  if (authLoading) return <main className="app-page grid place-items-center">Memeriksa izin...</main>;
  if (!user) return <main className="app-page grid place-items-center"><Link href="/login" className="btn-primary">Masuk</Link></main>;
  if (!canManage) return <main className="app-page min-h-screen pb-28 md:pl-[244px]"><StudentHeader /><div className="mx-auto max-w-xl px-4 py-16 text-center"><StudioIcon className="mx-auto h-12 w-12 text-slate-300" /><h1 className="mt-5 text-2xl font-black">Anda tidak memiliki akses ke Studio</h1><Link href="/sources" className="btn-primary mt-6 inline-flex">Buka Sources</Link></div></main>;

  return (
    <main className="app-page min-h-screen pb-28 md:pl-[244px] md:pb-12">
      <StudentHeader />
      <div className="mx-auto max-w-7xl px-4 py-7 sm:px-7 sm:py-10">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between"><div><Link href="/studio" className="text-sm font-black text-violet-600">&larr; Content Studio</Link><h1 className="page-title">Source workflow</h1><p className="page-description">Kelola dokumen melalui Inbox, tinjau metadata, simpan versi, lalu terbitkan.</p></div><button type="button" onClick={() => setUploadOpen((value) => !value)} className="btn-primary flex items-center justify-center gap-2"><UploadIcon className="h-4 w-4" />Upload source</button></div>

        {(message || error) && <div className={`mt-5 rounded-xl border px-4 py-3 text-sm font-semibold ${error ? 'border-red-200 bg-red-50 text-red-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>{error || message}</div>}

        {uploadOpen && <form onSubmit={upload} className="mt-6 rounded-3xl border border-blue-200 bg-blue-50 p-5 dark:border-blue-900 dark:bg-blue-950/20 sm:p-7"><div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-600 text-white"><UploadIcon /></span><div><h2 className="text-lg font-black">Masukkan source baru</h2><p className="text-sm text-slate-500">Source disimpan sebagai Inbox dan belum terlihat oleh mahasiswa.</p></div></div><div className="mt-4 rounded-xl border border-blue-200 bg-white/70 px-4 py-3 text-xs font-semibold text-blue-900 dark:border-blue-900 dark:bg-slate-900/60 dark:text-blue-200">Klasifikasi wajib: pilih satu mata kuliah dan minimal satu topik. Backend hanya menerima source lengkap ke tahap peninjauan.</div><div className="mt-6 grid gap-4 sm:grid-cols-2"><label className="sm:col-span-2"><span className="mb-2 block text-sm font-bold">File PDF atau DOCX</span><input type="file" accept=".pdf,.docx" required onChange={(event) => { const selected = event.target.files?.[0] || null; setFile(selected); if (selected && !title) setTitle(selected.name.replace(/\.[^.]+$/, '')); }} className="block w-full rounded-xl border border-dashed border-blue-300 bg-white p-4 text-sm file:mr-4 file:rounded-lg file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:font-bold file:text-white dark:bg-slate-900" /></label><label><span className="mb-2 block text-sm font-bold">Judul dokumen</span><input value={title} onChange={(event) => setTitle(event.target.value)} required className="input-base" /></label><label><span className="mb-2 block text-sm font-bold">Mata kuliah <b className="text-red-600">*</b></span><select value={subjectId} onChange={(event) => { setSubjectId(event.target.value); setTopicIds([]); setError(''); }} required className="input-base"><option value="">Pilih mata kuliah...</option>{curriculum.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select></label><label className="sm:col-span-2"><span className="mb-2 block text-sm font-bold">Topik <b className="text-red-600">*</b> <small className="font-medium text-slate-400">(boleh lebih dari satu)</small></span><select multiple value={topicIds} onChange={(event) => { setTopicIds(Array.from(event.target.selectedOptions, (option) => option.value)); setError(''); }} className="input-base min-h-28" disabled={!selectedSubject} aria-required="true">{selectedSubject?.topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}</select><span className={`mt-1.5 block text-xs ${subjectId && topicIds.length === 0 ? 'font-semibold text-amber-700' : 'text-slate-500'}`}>{!subjectId ? 'Pilih mata kuliah terlebih dahulu.' : topicIds.length === 0 ? 'Pilih minimal satu topik.' : `${topicIds.length} topik dipilih.`}</span></label><label className="sm:col-span-2"><span className="mb-2 block text-sm font-bold">Deskripsi</span><textarea value={description} onChange={(event) => setDescription(event.target.value)} className="input-base min-h-24" placeholder="Jelaskan cakupan dan asal dokumen secara ringkas." /></label></div><div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><button type="button" onClick={() => setUploadOpen(false)} className="btn-secondary">Batal</button><button disabled={busy === 'upload' || !file || !title.trim() || !subjectId || topicIds.length === 0} className="btn-primary">{busy === 'upload' ? 'Mengunggah...' : 'Simpan ke Inbox'}</button></div></form>}

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari judul, mata kuliah, atau topik..." className="input-base" /><nav className="mt-3 flex gap-2 overflow-x-auto pb-1">{statuses.map((entry) => <button key={entry.id} type="button" onClick={() => setStatus(entry.id)} className={`shrink-0 rounded-lg px-3 py-2 text-xs font-black ${status === entry.id ? 'bg-slate-950 text-white dark:bg-white dark:text-slate-950' : 'bg-slate-100 text-slate-500 dark:bg-slate-800'}`}>{entry.label}</button>)}</nav></section>

        {loading ? <div className="mt-6 space-y-3">{[1, 2, 3].map((item) => <div key={item} className="h-32 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />)}</div> : visible.length === 0 ? <section className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900"><SourceIcon className="mx-auto h-10 w-10 text-slate-300" /><h2 className="mt-4 font-black">Belum ada source</h2><p className="mt-1 text-sm text-slate-500">Upload file baru atau ubah filter status.</p></section> : <div className="mt-6 space-y-3">{visible.map((source) => <article key={source.id} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"><div className="flex flex-col gap-5 lg:flex-row lg:items-center"><div className="flex min-w-0 flex-1 items-start gap-4"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-slate-100 text-[10px] font-black uppercase text-slate-600 dark:bg-slate-800 dark:text-slate-300">{source.extension}</span><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h2 className="break-words font-black">{source.title}</h2><span className={`rounded-md px-2 py-1 text-[10px] font-black uppercase tracking-wide ${statusStyle(source.status)}`}>{statusLabel(source.status)}</span></div><p className="mt-1 text-xs text-slate-500">{source.subject?.name || 'Belum diklasifikasikan'}{source.topics.length ? ` · ${source.topics.map((topic) => topic.name).join(', ')}` : ''}</p><p className="mt-2 text-[11px] text-slate-400">Versi {source.version.version_number}{source.version.page_count ? ` · ${source.version.page_count} halaman` : ''}{source.updated_at ? ` · Diperbarui ${new Date(source.updated_at).toLocaleDateString('id-ID')}` : ''}</p></div></div><div className="flex flex-wrap items-center gap-2 lg:justify-end"><label className={`cursor-pointer rounded-lg border border-slate-200 px-3 py-2 text-xs font-black text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 ${busy === source.id ? 'pointer-events-none opacity-50' : ''}`}>Versi baru<input type="file" accept=".pdf,.docx" className="sr-only" onChange={(event) => uploadVersion(source, event.target.files?.[0])} /></label>{source.status === 'inbox' && <button type="button" disabled={busy === source.id} onClick={() => transition(source, 'review')} className="rounded-lg bg-amber-500 px-3 py-2 text-xs font-black text-white hover:bg-amber-600">Kirim tinjau</button>}{source.status === 'review_pending' && <button type="button" disabled={busy === source.id} onClick={() => transition(source, 'publish')} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-black text-white hover:bg-emerald-700">Terbitkan</button>}{source.status === 'published' && <Link href={`/sources/${encodeURIComponent(source.id)}?version_id=${encodeURIComponent(source.version.id)}&version=${source.version.version_number}&page=1`} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-black text-white">Preview</Link>}{source.status === 'published' && <button type="button" disabled={busy === source.id} onClick={() => transition(source, 'archive')} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-black text-slate-500">Arsipkan</button>}</div></div>{source.review_notes && <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">Catatan review: {source.review_notes}</p>}</article>)}</div>}
      </div>
    </main>
  );
}
