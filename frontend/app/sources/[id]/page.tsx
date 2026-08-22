'use client';

import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { StudentHeader } from '@/app/components/student-header';
import { BookmarkIcon, SourceIcon } from '@/app/components/ui-icons';
import { useAuth } from '@/app/providers/auth-context';
import { apiClient, type SourceDocument } from '@/services/api-client';

function normalizeSource(value: Partial<SourceDocument> & { id: string; name?: string }): SourceDocument {
  return {
    id: value.id,
    legacy_id: value.legacy_id,
    title: value.title || value.name || 'Source',
    name: value.name || value.title || 'Source',
    description: value.description || null,
    extension: (value.extension || 'pdf').replace('.', '').toLowerCase(),
    size_bytes: value.size_bytes || 0,
    content_type: value.content_type || 'application/octet-stream',
    status: value.status || 'published',
    subject: value.subject || null,
    topics: value.topics || [],
    version: value.version || { id: 0, version_number: 1, page_count: null },
    is_bookmarked: Boolean(value.is_bookmarked),
    reading_progress: Number(value.reading_progress || 0),
    last_page: value.last_page || null,
    updated_at: value.updated_at || null,
    last_opened_at: value.last_opened_at || null,
  };
}

export default function SourceViewerPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const sourceId = decodeURIComponent(params.id);
  const requestedPage = Math.max(1, Number(searchParams.get('page')) || 1);
  const requestedVersionId = Number(searchParams.get('version_id')) || undefined;
  const [source, setSource] = useState<SourceDocument | null>(null);
  const [page, setPage] = useState(requestedPage);
  const [blobUrl, setBlobUrl] = useState('');
  const [docxBlob, setDocxBlob] = useState<Blob | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewerLoading, setViewerLoading] = useState(true);
  const [error, setError] = useState('');
  const [bookmarkBusy, setBookmarkBusy] = useState(false);
  const docxContainer = useRef<HTMLDivElement>(null);
  const currentObjectUrl = useRef('');

  useEffect(() => setPage(requestedPage), [requestedPage]);

  useEffect(() => {
    if (authLoading || !user) return;
    let active = true;
    setLoading(true);
    setError('');
    apiClient
      .getSource(sourceId)
      .then((candidate) => {
        if (!active) return;
        setSource(normalizeSource(candidate));
      })
      .catch(() => {
        if (active) setError('Source tidak ditemukan atau belum dipublikasikan.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authLoading, user, sourceId]);

  useEffect(() => {
    if (!source) return;
    let active = true;
    setViewerLoading(true);
    setError('');
    setBlobUrl('');
    setDocxBlob(null);
    if (currentObjectUrl.current) {
      URL.revokeObjectURL(currentObjectUrl.current);
      currentObjectUrl.current = '';
    }
    apiClient
      .getSourceBlob(source.id, requestedVersionId || source.version.id)
      .then((blob) => {
        if (!active) return;
        if (source.extension === 'pdf') {
          const url = URL.createObjectURL(blob);
          currentObjectUrl.current = url;
          setBlobUrl(url);
          setViewerLoading(false);
        } else if (source.extension === 'docx') {
          setDocxBlob(blob);
        } else {
          setError(`Format .${source.extension} belum dapat dibaca di dalam aplikasi.`);
          setViewerLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setError('Isi source belum dapat dibuka. Silakan coba lagi.');
          setViewerLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [source?.id, source?.extension, source?.version.id, requestedVersionId]);

  useEffect(() => {
    if (!docxBlob || !docxContainer.current) return;
    let active = true;
    const container = docxContainer.current;
    container.replaceChildren();
    import('docx-preview')
      .then(({ renderAsync }) => renderAsync(docxBlob, container, container, {
        className: 'source-docx',
        inWrapper: true,
        breakPages: true,
        ignoreWidth: false,
        ignoreHeight: false,
        ignoreFonts: false,
        useBase64URL: true,
      }))
      .then(() => {
        if (active) setViewerLoading(false);
      })
      .catch(() => {
        if (active) {
          setError('Dokumen Word belum dapat dirender.');
          setViewerLoading(false);
        }
      });
    return () => {
      active = false;
      container.replaceChildren();
    };
  }, [docxBlob]);

  useEffect(() => () => {
    if (currentObjectUrl.current) URL.revokeObjectURL(currentObjectUrl.current);
  }, []);

  const pageCount = source?.version.page_count || null;
  const progress = useMemo(() => pageCount ? Math.min(100, Math.round((page / pageCount) * 100)) : Math.max(source?.reading_progress || 0, 1), [page, pageCount, source?.reading_progress]);

  useEffect(() => {
    if (!source) return;
    const timeout = window.setTimeout(() => {
      apiClient.updateSourceProgress(source.id, page, progress).catch(() => undefined);
    }, 700);
    return () => window.clearTimeout(timeout);
  }, [source, page, progress]);

  function changePage(nextPage: number) {
    const safePage = Math.max(1, pageCount ? Math.min(pageCount, nextPage) : nextPage);
    setPage(safePage);
    const query = new URLSearchParams(searchParams.toString());
    query.set('page', String(safePage));
    if (!query.get('version_id') && source) query.set('version_id', String(source.version.id));
    if (!query.get('version') && source) query.set('version', String(source.version.version_number));
    router.replace(`/sources/${encodeURIComponent(sourceId)}?${query.toString()}`, { scroll: false });
  }

  async function toggleBookmark() {
    if (!source || bookmarkBusy) return;
    setBookmarkBusy(true);
    const bookmarked = !source.is_bookmarked;
    setSource({ ...source, is_bookmarked: bookmarked });
    try {
      if (bookmarked) await apiClient.bookmarkSource(source.id, page);
      else await apiClient.removeSourceBookmark(source.id);
    } catch {
      setSource((current) => current ? { ...current, is_bookmarked: !bookmarked } : current);
    } finally {
      setBookmarkBusy(false);
    }
  }

  if (authLoading || loading) return <main className="app-page grid place-items-center"><p className="font-semibold text-slate-500">Menyiapkan pembaca...</p></main>;
  if (!user) return <main className="app-page grid place-items-center"><Link href="/login" className="btn-primary">Masuk untuk membaca</Link></main>;

  return (
    <main className="app-page min-h-screen pb-24 md:pl-[244px] md:pb-0">
      <StudentHeader />
      <div className="flex min-h-[calc(100dvh-4rem)] flex-col md:min-h-screen">
        <header className="border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950 sm:px-6">
          <div className="mx-auto flex max-w-7xl items-center gap-3">
            <Link href="/sources" className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-slate-200 text-lg text-slate-500 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-900" aria-label="Kembali ke Sources">&larr;</Link>
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-blue-100 text-[9px] font-black uppercase text-blue-700 dark:bg-blue-950 dark:text-blue-300">{source?.extension || 'SRC'}</span>
            <div className="min-w-0 flex-1">
              <h1 className="truncate text-sm font-black sm:text-base">{source?.title || 'Source'}</h1>
              <p className="truncate text-[11px] text-slate-500">{source?.subject?.name || 'Materi pembelajaran'}{source?.topics.length ? ` · ${source.topics.map((entry) => entry.name).join(', ')}` : ''}</p>
            </div>
            {source?.extension === 'pdf' && (
              <div className="hidden items-center gap-1 rounded-lg border border-slate-200 p-1 dark:border-slate-700 sm:flex">
                <button type="button" onClick={() => changePage(page - 1)} disabled={page <= 1} className="grid h-8 w-8 place-items-center rounded text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800">&minus;</button>
                <label className="flex items-center gap-1 text-xs font-bold text-slate-500">Hal.
                  <input value={page} onChange={(event) => changePage(Number(event.target.value) || 1)} className="h-8 w-12 rounded border border-slate-200 bg-transparent text-center text-slate-950 outline-none dark:border-slate-700 dark:text-white" inputMode="numeric" />
                  {pageCount ? <span>/ {pageCount}</span> : null}
                </label>
                <button type="button" onClick={() => changePage(page + 1)} disabled={Boolean(pageCount && page >= pageCount)} className="grid h-8 w-8 place-items-center rounded text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800">+</button>
              </div>
            )}
            <button type="button" onClick={toggleBookmark} disabled={!source || bookmarkBusy} className={`grid h-10 w-10 shrink-0 place-items-center rounded-lg border ${source?.is_bookmarked ? 'border-amber-300 bg-amber-50 text-amber-600' : 'border-slate-200 text-slate-500 dark:border-slate-700'}`} aria-label={source?.is_bookmarked ? 'Hapus bookmark' : 'Bookmark halaman ini'}><BookmarkIcon className={`h-4 w-4 ${source?.is_bookmarked ? 'fill-current' : ''}`} /></button>
          </div>
        </header>

        {source?.extension === 'pdf' && (
          <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2 dark:border-slate-800 dark:bg-slate-950 sm:hidden">
            <button type="button" onClick={() => changePage(page - 1)} disabled={page <= 1} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-black disabled:opacity-30 dark:border-slate-700">Sebelumnya</button>
            <span className="text-xs font-bold text-slate-500">Halaman {page}{pageCount ? ` / ${pageCount}` : ''}</span>
            <button type="button" onClick={() => changePage(page + 1)} disabled={Boolean(pageCount && page >= pageCount)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-black disabled:opacity-30 dark:border-slate-700">Berikutnya</button>
          </div>
        )}

        <div className="relative min-h-[65dvh] flex-1 overflow-hidden bg-slate-200 dark:bg-slate-900">
          {error ? (
            <div className="grid h-full min-h-[60dvh] place-items-center p-8 text-center"><div><SourceIcon className="mx-auto h-10 w-10 text-slate-300" /><h2 className="mt-4 font-black text-red-700 dark:text-red-300">Source tidak dapat dibuka</h2><p className="mt-2 text-sm text-slate-500">{error}</p><Link href="/sources" className="btn-secondary mt-5 inline-flex">Kembali ke library</Link></div></div>
          ) : source?.extension === 'pdf' && blobUrl ? (
            <iframe key={`${blobUrl}-${page}`} src={`${blobUrl}#page=${page}&toolbar=0&navpanes=0`} title={`Pembaca PDF: ${source.title}`} className="h-full min-h-[70dvh] w-full border-0 bg-white md:min-h-0" />
          ) : source?.extension === 'docx' ? (
            <div className="h-full min-h-[70dvh] overflow-auto"><div ref={docxContainer} className="min-h-full [&_.docx-wrapper]:!bg-transparent [&_.docx-wrapper]:!p-3 sm:[&_.docx-wrapper]:!p-6" /></div>
          ) : null}
          {viewerLoading && !error && <div className="absolute inset-0 grid place-items-center bg-slate-100/95 dark:bg-slate-900/95"><div className="text-center"><span className="mx-auto block h-9 w-9 animate-spin rounded-full border-4 border-slate-300 border-t-blue-600" /><p className="mt-4 text-sm font-bold text-slate-500">Menyiapkan isi source...</p></div></div>}
        </div>
      </div>
    </main>
  );
}
