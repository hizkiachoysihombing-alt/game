'use client';

import Link from 'next/link';
import { FormEvent, Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiClient } from '@/services/api-client';
import { BoltIcon, CheckIcon, LeagueIcon, SourceIcon } from '@/app/components/ui-icons';

function PlaySession() {
  const router = useRouter();
  const params = useSearchParams();
  const topic = Number(params.get('topic'));
  const unit = Number(params.get('unit'));
  const [challenge, setChallenge] = useState<any>(null);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [seen, setSeen] = useState<number[]>([]);
  const [number, setNumber] = useState(1);
  const [correct, setCorrect] = useState(0);
  const [xp, setXp] = useState(0);
  const [league, setLeague] = useState(0);
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState('enter');
  const [finished, setFinished] = useState(false);
  const [startedAt, setStartedAt] = useState(Date.now());

  async function loadNext(excluded: number[]) {
    setBusy(true);
    setError('');
    try {
      const next = await apiClient.getNextJourneyProblem(topic, unit, excluded);
      setChallenge(next);
      setAnswer(next.question.starter_code || '');
      setSeen([...excluded, next.question.id]);
      setStartedAt(Date.now());
      setPhase('enter');
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Unit ini belum dapat dimuat.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (topic && unit) loadNext([]);
    else setError('Tautan unit tidak valid.');
  }, [topic, unit]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!challenge) return;
    setBusy(true);
    try {
      const submittedAnswer = challenge.question.coding_language
        ? { code: answer, language: challenge.question.coding_language }
        : answer;
      const response = await apiClient.submitProblem(challenge.question.id, {
        session_id: challenge.session_id,
        answer: submittedAnswer,
        response_time_seconds: Math.max(1, Math.round((Date.now() - startedAt) / 1000)),
      });
      setResult(response);
      setCorrect((value) => value + (response.is_correct ? 1 : 0));
      setXp((value) => value + (response.xp_awarded || 0));
      setLeague((value) => value + (response.ranked_points || 0));
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Jawaban belum dapat diperiksa.');
    } finally {
      setBusy(false);
    }
  }

  function continueRun() {
    if (number >= 20) {
      setPhase('exit');
      setTimeout(() => setFinished(true), 280);
      return;
    }
    setPhase('exit');
    setTimeout(() => {
      setNumber((value) => value + 1);
      setResult(null);
      loadNext(seen);
    }, 280);
  }

  if (finished) {
    return (
      <main className="min-h-screen bg-[#101b2d] p-5 text-white">
        <div className="mx-auto grid min-h-[90vh] max-w-xl place-items-center">
          <section className="play-card-enter w-full text-center">
            <div className="mx-auto grid h-20 w-20 place-items-center rounded-2xl border border-blue-400/30 bg-blue-500/10 text-blue-300"><LeagueIcon className="h-9 w-9" /></div>
            <p className="mt-7 text-xs font-black uppercase tracking-[.25em] text-blue-300">Unit complete</p>
            <h1 className="mt-3 text-4xl font-black">Run finished</h1>
            <p className="mt-3 text-slate-300">Ulangi unit untuk meningkatkan akurasi atau pilih topik lain di Journey.</p>
            <div className="mt-8 grid grid-cols-3 gap-3"><div className="rounded-xl border border-slate-700 bg-[#17243a] p-4"><strong className="text-2xl">{correct}/20</strong><p className="text-xs text-slate-400">benar</p></div><div className="rounded-xl border border-slate-700 bg-[#17243a] p-4"><strong className="text-2xl">+{xp}</strong><p className="text-xs text-slate-400">total XP</p></div><div className="rounded-xl border border-slate-700 bg-[#17243a] p-4"><strong className="text-2xl">+{league}</strong><p className="text-xs text-slate-400">weekly pts</p></div></div>
            <button type="button" onClick={() => location.reload()} className="mt-8 w-full rounded-xl bg-blue-600 px-6 py-4 font-black hover:bg-blue-500">Ulangi unit</button>
            <button type="button" onClick={() => router.push('/journey')} className="mt-3 w-full rounded-xl px-6 py-3 font-bold text-slate-300">Kembali ke Journey</button>
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#f6f7f9] text-slate-950 dark:bg-slate-950 dark:text-white">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
        <div className="mx-auto flex h-20 max-w-4xl items-center gap-4 px-4">
          <button type="button" onClick={() => router.push('/journey')} className="grid h-10 w-10 place-items-center rounded-lg text-xl text-slate-500 hover:bg-slate-100" aria-label="Tutup unit">&times;</button>
          <div className="flex-1"><div className="mb-2 flex justify-between text-xs font-black"><span>UNIT {unit}</span><span>{number}/20</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"><div className="h-full rounded-full bg-blue-600 transition-all duration-500" style={{ width: `${number * 5}%` }} /></div></div>
          <div className="grid h-10 w-10 place-items-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950"><BoltIcon /></div>
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-5 py-8 sm:py-12">
        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-700"><p>{error}</p><button type="button" onClick={() => router.push('/journey')} className="mt-3 font-bold underline">Kembali ke Journey</button></div>
        ) : !challenge ? (
          <div className="grid place-items-center py-32"><div className="h-1 w-28 animate-pulse bg-blue-600" /></div>
        ) : (
          <section key={challenge.session_id} className={phase === 'exit' ? 'play-card-exit' : 'play-card-enter'}>
            <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow">{challenge.question.subject}</p><h1 className="mt-1 text-2xl font-black">{challenge.question.topic}</h1></div><span className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-black text-blue-700">{challenge.question.difficulty}</span></div>
            <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900 sm:p-8">
              <p className="text-xs font-black uppercase tracking-wider text-slate-400">Question {number}</p>
              <h2 className="mt-2 text-2xl font-black">{challenge.question.title}</h2>
              <div className="prose mt-5 text-lg dark:prose-invert" dangerouslySetInnerHTML={{ __html: challenge.question.content_html }} />
              <form onSubmit={submit} className="mt-8">
                {challenge.question.coding_language ? (
                  <div><div className="mb-2 flex items-center justify-between"><label htmlFor="code-editor" className="font-bold">Code editor</label><span className="rounded bg-slate-800 px-2 py-1 font-mono text-xs text-slate-300">{challenge.question.coding_language} · {challenge.question.test_count} checks</span></div><textarea id="code-editor" autoFocus spellCheck={false} className="min-h-[280px] w-full resize-y rounded-xl border border-slate-700 bg-[#0b1220] p-4 font-mono text-sm leading-6 text-slate-100 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20" value={answer} onChange={(event) => setAnswer(event.target.value)} disabled={Boolean(result)} /><p className="mt-2 text-xs text-slate-500">Kode diperiksa dengan aturan aman dan tidak dijalankan di server API.</p></div>
                ) : (
                  <label className="font-bold">Jawaban Anda<input autoFocus className="input-base mt-3 text-lg" value={answer} onChange={(event) => setAnswer(event.target.value)} disabled={Boolean(result)} required placeholder="Ketik jawaban" /></label>
                )}
                {!result && <button disabled={busy || !answer.trim()} className="btn-primary mt-5 w-full py-4">{busy ? 'Memeriksa...' : challenge.question.coding_language ? 'Jalankan pemeriksaan' : 'Periksa jawaban'}</button>}
              </form>
            </div>

            {result && (
              <div className={`play-feedback-enter mt-5 rounded-2xl border p-6 ${result.is_correct ? 'border-emerald-200 bg-emerald-50 text-emerald-950' : 'border-amber-200 bg-amber-50 text-amber-950'}`}>
                <div className="flex items-start justify-between gap-4"><div><h3 className="flex items-center gap-2 text-xl font-black">{result.is_correct && <CheckIcon />}{result.is_correct ? 'Correct' : 'Keep going'}</h3><p className="mt-1">{result.feedback}</p></div><strong className="shrink-0">+{result.xp_awarded || 0} XP</strong></div>
                {!result.is_correct && result.recommended_sources?.length > 0 && (
                  <section className="mt-5 rounded-xl border border-amber-200 bg-white/70 p-4">
                    <div className="flex items-center gap-2"><SourceIcon className="h-4 w-4 text-blue-600" /><h4 className="text-xs font-black uppercase tracking-wider text-slate-500">Pelajari bagian ini</h4></div>
                    <div className="mt-3 space-y-2">
                      {result.recommended_sources.map((source: any, index: number) => {
                        const page = source.page_start || 1;
                        const href = source.href || `/sources/${encodeURIComponent(source.public_id)}?version_id=${source.version_id || ''}&version=${source.version || ''}&page=${page}`;
                        return <Link key={`${source.public_id}-${index}`} href={href} target="_blank" className="flex items-center justify-between gap-3 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-900 transition hover:border-blue-400"><span className="min-w-0"><strong className="block truncate">{source.title || 'Buka source acuan'}</strong><small className="block text-blue-600">{source.section_label ? `${source.section_label} · ` : ''}halaman {page}{source.page_end && source.page_end !== page ? `–${source.page_end}` : ''}</small></span><span className="shrink-0 font-black text-blue-600">Buka ↗</span></Link>;
                      })}
                    </div>
                  </section>
                )}
                <button type="button" onClick={continueRun} className="mt-5 w-full rounded-xl bg-slate-950 px-5 py-4 font-black text-white">{number === 20 ? 'Selesaikan sesi' : 'Lanjutkan'}</button>
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}

export default function PlayPage() {
  return <Suspense fallback={<main className="app-page grid place-items-center">Memulai unit...</main>}><PlaySession /></Suspense>;
}
