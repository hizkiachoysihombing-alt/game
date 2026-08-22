'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { StudentHeader } from '@/app/components/student-header';
import { BookmarkIcon, HistoryIcon, SourceIcon } from '@/app/components/ui-icons';
import { useAuth } from '@/app/providers/auth-context';
import { apiClient, type SourceDocument, type SourceLibrary } from '@/services/api-client';

type LibraryTab = 'all' | 'bookmarks' | 'history';
type LibraryItem = { document: SourceDocument; categoryId: string; categoryName: string };

function formatBytes(bytes: number) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** index;
  return `${new Intl.NumberFormat('id-ID', { maximumFractionDigits: value >= 10 ? 0 : 1 }).format(value)} ${units[index]}`;
}

function normalizeDocument(value: Partial<SourceDocument> & { id: string; name?: string }): SourceDocument {
  return {
    id: value.id,
    legacy_id: value.legacy_id,
    title: value.title || value.name || 'Source tanpa judul',
    name: value.name || value.title || 'Source',
    description: value.description || null,
    extension: (value.extension || 'pdf').replace('.', '').toLowerCase(),
    size_bytes: value.size_bytes || 0,
    content_type: value.content_type || 'application/octet-stream',
    status: value.status || 'published',
    subject: value.subject || null,
    topics: Array.isArray(value.topics) ? value.topics : [],
    version: value.version || { id: 0, version_number: 1, page_count: null },
    is_bookmarked: Boolean(value.is_bookmarked),
    reading_progress: Number(value.reading_progress || 0),
    last_page: value.last_page || null,
    updated_at: value.updated_at || null,
    last_opened_at: value.last_opened_at || null,
  };
}

function flattenLibrary(library: SourceLibrary): LibraryItem[] {
  return (library.categories || []).flatMap((category) =>
    (category.files || []).map((file) => ({
      document: normalizeDocument(file),
      categoryId: category.id,
      categoryName: category.name,
    })),
  );
}

function flattenFeed(payload: unknown): LibraryItem[] {
  if (!payload) return [];
  if (Array.isArray(payload)) {
    return payload.map((item) => {
      const source = normalizeDocument(item as Partial<SourceDocument> & { id: string });
      return {
        document: source,
        categoryId: source.subject?.slug || String(source.subject?.id || 'lainnya'),
        categoryName: source.subject?.name || 'Lainnya',
      };
    });
  }
  const record = payload as Record<string, unknown>;
  if (Array.isArray(record.items)) return flattenFeed(record.items);
  if (Array.isArray(record.sources)) return flattenFeed(record.sources);
  if (Array.isArray(record.documents)) return flattenFeed(record.documents);
  if (Array.isArray(record.categories)) return flattenLibrary(record as unknown as SourceLibrary);
  return [];
}

const tabs: Array<{ id: LibraryTab; label: string; icon: typeof SourceIcon }> = [
  { id: 'all', label: 'Semua source', icon: SourceIcon },
  { id: 'bookmarks', label: 'Tersimpan', icon: BookmarkIcon },
  { id: 'history', label: 'Riwayat', icon: HistoryIcon },
];

export default function SourcesPage() {
  const { user, loading: authLoading } = useAuth();
  const [tab, setTab] = useState<LibraryTab>('all');
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [library, setLibrary] = useState<SourceLibrary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [subject, setSubject] = useState('all');
  const [topic, setTopic] = useState('all');
  const [extension, setExtension] = useState('all');
  const [bookmarkBusy, setBookmarkBusy] = useState('');

  useEffect(() => {
    const initialQuery = new URLSearchParams(window.location.search).get('q');
    if (initialQuery) setQuery(initialQuery);
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;
    let active = true;
    setLoading(true);
    setError('');
    const request =
      tab === 'all'
        ? apiClient.getSources()
        : tab === 'bookmarks'
          ? apiClient.getSourceBookmarks()
          : apiClient.getSourceHistory();
    request
      .then((payload) => {
        if (!active) return;
        if (tab === 'all') {
          const sourceLibrary = payload as SourceLibrary;
          setLibrary(sourceLibrary);
          setItems(flattenLibrary(sourceLibrary));
        } else {
          setItems(flattenFeed(payload));
        }
      })
      .catch(() => {
        if (active) setError('Koleksi source belum dapat dimuat. Silakan coba lagi.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authLoading, user, tab]);

  const subjects = useMemo(() => {
    const values = new Map<string, string>();
    items.forEach((item) => values.set(item.categoryId, item.document.subject?.name || item.categoryName));
    return Array.from(values, ([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name, 'id'));
  }, [items]);

  const topics = useMemo(() => {
    const values = new Map<string, string>();
    items
      .filter((item) => subject === 'all' || item.categoryId === subject)
      .forEach((item) => item.document.topics.forEach((entry) => values.set(String(entry.id), entry.name)));
    return Array.from(values, ([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name, 'id'));
  }, [items, subject]);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase('id-ID');
    return items.filter(({ document, categoryId, categoryName }) => {
      const matchesQuery =
        !normalizedQuery ||
        document.title.toLocaleLowerCase('id-ID').includes(normalizedQuery) ||
        categoryName.toLocaleLowerCase('id-ID').includes(normalizedQuery) ||
        document.topics.some((entry) => entry.name.toLocaleLowerCase('id-ID').includes(normalizedQuery));
      return (
        matchesQuery &&
        (subject === 'all' || categoryId === subject) &&
        (topic === 'all' || document.topics.some((entry) => String(entry.id) === topic)) &&
        (extension === 'all' || document.extension === extension)
      );
    });
  }, [items, query, subject, topic, extension]);

  const grouped = useMemo(() => {
    const groups = new Map<string, { id: string; name: string; items: SourceDocument[] }>();
    filtered.forEach(({ document, categoryId, categoryName }) => {
      const group = groups.get(categoryId) || { id: categoryId, name: document.subject?.name || categoryName, items: [] };
      group.items.push(document);
      groups.set(categoryId, group);
    });
    return Array.from(groups.values()).sort((a, b) => a.name.localeCompare(b.name, 'id'));
  }, [filtered]);

  async function toggleBookmark(document: SourceDocument) {
    if (bookmarkBusy) return;
    setBookmarkBusy(document.id);
    const nextValue = !document.is_bookmarked;
    setItems((current) =>
      current.map((item) =>
        item.document.id === document.id
          ? { ...item, document: { ...item.document, is_bookmarked: nextValue } }
          : item,
      ),
    );
    try {
      if (nextValue) await apiClient.bookmarkSource(document.id, document.last_page || 1);
      else await apiClient.removeSourceBookmark(document.id);
      if (!nextValue && tab === 'bookmarks') {
        setItems((current) => current.filter((item) => item.document.id !== document.id));
      }
    } catch {
      setItems((current) =>
        current.map((item) =>
          item.document.id === document.id
            ? { ...item, document: { ...item.document, is_bookmarked: !nextValue } }
            : item,
        ),
      );
    } finally {
      setBookmarkBusy('');
    }
  }

  if (authLoading) return <main className="app-page grid place-items-center"><p className="font-semibold text-slate-500">Memeriksa akun...</p></main>;

  if (!user) {
    return (
      <main className="app-page grid place-items-center px-4 text-center">
        <div>
          <SourceIcon className="mx-auto h-10 w-10 text-slate-300" />
          <h1 className="mt-4 text-xl font-black">Masuk untuk membaca source</h1>
          <p className="mt-2 text-sm text-slate-500">Koleksi pembelajaran tersedia setelah Anda masuk.</p>
          <Link href="/login" className="btn-primary mt-5 inline-flex">Sign in</Link>
        </div>
      </main>
    );
  }

  const total = library?.total_documents ?? library?.total_files ?? items.length;

  return (
    <main className="app-page min-h-screen pb-28 md:pl-[244px] md:pb-12">
      <StudentHeader />
      <div className="mx-auto max-w-6xl px-4 py-7 sm:px-7 sm:py-10">
        <header className="flex flex-col gap-5 border-b border-slate-200 pb-7 dark:border-slate-800 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="eyebrow">Learning library</p>
            <h1 className="page-title">Sources</h1>
            <p className="page-description">Temukan referensi berdasarkan mata kuliah dan topik, simpan halaman penting, lalu lanjutkan dari bacaan terakhir.</p>
          </div>
          <div className="flex shrink-0 gap-2">
            <span className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">{total} dokumen</span>
            <span className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">{library?.total_categories ?? subjects.length} mata kuliah</span>
          </div>
        </header>

        <nav className="mt-6 flex gap-2 overflow-x-auto pb-1" aria-label="Bagian source">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`flex shrink-0 items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-black transition ${tab === id ? 'bg-slate-950 text-white dark:bg-white dark:text-slate-950' : 'border border-slate-200 bg-white text-slate-500 hover:text-slate-950 dark:border-slate-800 dark:bg-slate-900 dark:hover:text-white'}`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </nav>

        <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
          <label htmlFor="source-search" className="sr-only">Cari source</label>
          <input id="source-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari judul, mata kuliah, atau topik..." className="input-base" />
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <label className="text-xs font-bold text-slate-500">Mata kuliah
              <select value={subject} onChange={(event) => { setSubject(event.target.value); setTopic('all'); }} className="input-base mt-1.5 py-2.5 text-sm">
                <option value="all">Semua mata kuliah</option>
                {subjects.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}
              </select>
            </label>
            <label className="text-xs font-bold text-slate-500">Topik
              <select value={topic} onChange={(event) => setTopic(event.target.value)} className="input-base mt-1.5 py-2.5 text-sm">
                <option value="all">Semua topik</option>
                {topics.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}
              </select>
            </label>
            <label className="text-xs font-bold text-slate-500">Format
              <select value={extension} onChange={(event) => setExtension(event.target.value)} className="input-base mt-1.5 py-2.5 text-sm">
                <option value="all">Semua format</option>
                <option value="pdf">PDF</option>
                <option value="docx">DOCX</option>
              </select>
            </label>
          </div>
        </section>

        {error ? (
          <section className="mt-7 rounded-2xl border border-red-200 bg-red-50 p-7 text-center text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
            <p className="font-black">Source tidak dapat dimuat</p>
            <p className="mt-1 text-sm">{error}</p>
            <button type="button" onClick={() => window.location.reload()} className="mt-4 rounded-lg border border-red-300 px-3 py-2 text-xs font-black">Muat ulang</button>
          </section>
        ) : loading ? (
          <div className="mt-7 space-y-4" aria-label="Memuat source"><div className="h-32 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" /><div className="h-44 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" /></div>
        ) : grouped.length === 0 ? (
          <section className="mt-7 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900">
            <SourceIcon className="mx-auto h-10 w-10 text-slate-300" />
            <h2 className="mt-4 font-black">Belum ada source di bagian ini</h2>
            <p className="mt-1 text-sm text-slate-500">Ubah filter atau buka koleksi lengkap untuk menemukan materi.</p>
            <button type="button" onClick={() => { setTab('all'); setQuery(''); setSubject('all'); setTopic('all'); setExtension('all'); }} className="mt-4 text-sm font-black text-blue-600">Lihat semua source</button>
          </section>
        ) : (
          <div className="mt-7 space-y-7">
            <p className="text-sm text-slate-500">Menampilkan <b className="text-slate-950 dark:text-white">{filtered.length}</b> dokumen.</p>
            {grouped.map((group) => (
              <section key={group.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <header className="flex items-center justify-between border-b border-slate-100 bg-slate-50/70 px-4 py-4 dark:border-slate-800 dark:bg-slate-900 sm:px-6">
                  <div className="flex items-center gap-3">
                    <span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"><SourceIcon className="h-5 w-5" /></span>
                    <div><h2 className="font-black sm:text-lg">{group.name}</h2><p className="text-xs text-slate-500">{group.items.length} dokumen</p></div>
                  </div>
                </header>
                <div>
                  {group.items.map((document) => {
                    const page = document.last_page || 1;
                    const href = `/sources/${encodeURIComponent(document.id)}?version_id=${encodeURIComponent(document.version.id)}&version=${document.version.version_number}&page=${page}`;
                    return (
                      <article key={document.id} className="border-b border-slate-100 px-4 py-4 last:border-0 dark:border-slate-800 sm:px-6">
                        <div className="flex items-start gap-3 sm:gap-4">
                          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-slate-100 text-[10px] font-black uppercase text-slate-600 dark:bg-slate-800 dark:text-slate-300">{document.extension}</span>
                          <div className="min-w-0 flex-1">
                            <Link href={href} className="break-words text-sm font-black leading-5 hover:text-blue-600 sm:text-base">{document.title}</Link>
                            <p className="mt-1 flex flex-wrap gap-x-2 text-[11px] text-slate-400">
                              <span>{formatBytes(document.size_bytes)}</span>
                              <span>Versi {document.version.version_number}</span>
                              {document.version.page_count ? <span>{document.version.page_count} halaman</span> : null}
                            </p>
                            {document.topics.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{document.topics.map((entry) => <span key={entry.id} className="rounded-md bg-blue-50 px-2 py-1 text-[10px] font-bold text-blue-700 dark:bg-blue-950 dark:text-blue-300">{entry.name}</span>)}</div>}
                          </div>
                          <button type="button" onClick={() => toggleBookmark(document)} disabled={bookmarkBusy === document.id} aria-label={document.is_bookmarked ? 'Hapus dari tersimpan' : 'Simpan source'} className={`grid h-10 w-10 shrink-0 place-items-center rounded-lg border transition ${document.is_bookmarked ? 'border-amber-300 bg-amber-50 text-amber-600' : 'border-slate-200 text-slate-400 hover:text-amber-600 dark:border-slate-700'}`}><BookmarkIcon className={`h-4 w-4 ${document.is_bookmarked ? 'fill-current' : ''}`} /></button>
                          <Link href={href} className="hidden shrink-0 rounded-lg bg-slate-950 px-4 py-2.5 text-xs font-black text-white hover:bg-blue-600 dark:bg-white dark:text-slate-950 sm:inline-flex">{document.reading_progress > 0 ? 'Lanjutkan' : 'Buka'}</Link>
                        </div>
                        {document.reading_progress > 0 && <div className="mt-3 pl-14 sm:pl-[60px]"><div className="h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-full rounded-full bg-blue-600" style={{ width: `${Math.min(100, document.reading_progress)}%` }} /></div><p className="mt-1 text-[10px] text-slate-400">Terakhir halaman {page} · {Math.round(document.reading_progress)}%</p></div>}
                      </article>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
