'use client';

import Link from 'next/link';
import {useEffect,useMemo,useState} from 'react';
import {StudentHeader} from '@/app/components/student-header';
import {SourceIcon} from '@/app/components/ui-icons';
import {useAuth} from '@/app/providers/auth-context';
import {apiClient,type SourceFile,type SourceLibrary} from '@/services/api-client';

function formatBytes(bytes:number){
 if(bytes===0)return '0 B';
 const units=['B','KB','MB','GB'];
 const unitIndex=Math.min(Math.floor(Math.log(bytes)/Math.log(1024)),units.length-1);
 const value=bytes/1024**unitIndex;
 return `${new Intl.NumberFormat('id-ID',{maximumFractionDigits:value>=10||unitIndex===0?0:1}).format(value)} ${units[unitIndex]}`;
}

export default function SourcesPage(){
 const{user,loading:authLoading}=useAuth();
 const[library,setLibrary]=useState<SourceLibrary|null>(null);
 const[query,setQuery]=useState('');
 const[error,setError]=useState('');
 const[downloading,setDownloading]=useState('');
 const[downloadError,setDownloadError]=useState('');

 useEffect(()=>{
  if(authLoading||!user)return;
  let active=true;
  setError('');
  apiClient.getSources().then(data=>{if(active)setLibrary(data)}).catch(()=>{if(active)setError('Koleksi source belum dapat dimuat. Coba muat ulang halaman ini.')});
  return()=>{active=false};
 },[authLoading,user]);

 const visibleCategories=useMemo(()=>{
  if(!library)return[];
  const normalizedQuery=query.trim().toLocaleLowerCase('id-ID');
  if(!normalizedQuery)return library.categories;
  return library.categories.map(category=>({...category,files:category.files.filter(file=>file.name.toLocaleLowerCase('id-ID').includes(normalizedQuery))})).filter(category=>category.files.length>0);
 },[library,query]);

 const visibleFileCount=visibleCategories.reduce((total,category)=>total+category.files.length,0);

 async function download(file:SourceFile){
  setDownloading(file.id);setDownloadError('');
  try{await apiClient.downloadSource(file.id,file.name)}catch{setDownloadError(`File "${file.name}" gagal diunduh. Silakan coba lagi.`)}finally{setDownloading('')}
 }

 if(authLoading)return <main className="app-page grid place-items-center"><p className="font-semibold text-slate-500">Memeriksa akun...</p></main>;
 if(!user)return <main className="app-page grid place-items-center px-4 text-center"><div><SourceIcon className="mx-auto h-10 w-10 text-slate-300"/><h1 className="mt-4 text-xl font-black">Masuk untuk melihat source</h1><p className="mt-2 text-sm text-slate-500">Koleksi materi hanya tersedia untuk pengguna yang sudah masuk.</p><Link href="/login" className="btn-primary mt-5 inline-flex">Sign in</Link></div></main>;

 return <main className="app-page min-h-screen pb-28 md:pl-[244px] md:pb-12"><StudentHeader/><div className="mx-auto max-w-5xl px-4 py-7 sm:px-6 sm:py-10">
  <header className="flex flex-col gap-5 border-b border-slate-200 pb-7 dark:border-slate-800 sm:flex-row sm:items-end sm:justify-between">
   <div><p className="eyebrow">Learning library</p><h1 className="page-title">Sources</h1><p className="page-description">Temukan dan unduh PDF serta dokumen referensi yang sudah dikelompokkan berdasarkan mata kuliah.</p></div>
   {library&&<div className="flex shrink-0 gap-2"><span className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">{library.total_categories} mata kuliah</span><span className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">{library.total_files} file</span></div>}
  </header>

  <section className="mt-6"><label htmlFor="source-search" className="sr-only">Cari nama file</label><div className="relative"><span aria-hidden="true" className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">⌕</span><input id="source-search" value={query} onChange={event=>setQuery(event.target.value)} placeholder="Cari nama file..." className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-11 pr-24 text-sm font-medium outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100 dark:border-slate-800 dark:bg-slate-900 dark:focus:ring-blue-950"/>{query&&<button type="button" onClick={()=>setQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md px-2 py-1 text-xs font-bold text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-white">Hapus</button>}</div></section>

  {error?<section className="mt-7 rounded-2xl border border-red-200 bg-red-50 p-7 text-center dark:border-red-900 dark:bg-red-950/30"><p className="font-black text-red-700 dark:text-red-300">Source tidak dapat dimuat</p><p className="mt-1 text-sm text-red-600 dark:text-red-400">{error}</p><button type="button" onClick={()=>window.location.reload()} className="mt-4 rounded-lg border border-red-300 px-3 py-2 text-xs font-black text-red-700 hover:bg-red-100 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950">Muat ulang</button></section>:
  !library?<div className="mt-7 space-y-4" aria-label="Memuat source"><div className="h-28 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800"/><div className="h-44 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800"/><div className="h-36 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800"/></div>:
  library.total_files===0?<section className="mt-7 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900"><SourceIcon className="mx-auto h-10 w-10 text-slate-300"/><h2 className="mt-4 font-black">Belum ada source</h2><p className="mt-1 text-sm text-slate-500">File yang sudah ditinjau akan tampil di sini berdasarkan mata kuliahnya.</p></section>:
  visibleCategories.length===0?<section className="mt-7 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900"><p className="font-black">File tidak ditemukan</p><p className="mt-1 text-sm text-slate-500">Tidak ada nama file yang cocok dengan “{query.trim()}”.</p><button type="button" onClick={()=>setQuery('')} className="mt-4 text-sm font-black text-blue-600 hover:text-blue-700">Hapus pencarian</button></section>:
  <div className="mt-7 space-y-7">{query&&<p className="text-sm text-slate-500">Menampilkan <b className="text-slate-900 dark:text-white">{visibleFileCount}</b> dari {library.total_files} file.</p>}{visibleCategories.map(category=><section key={category.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"><header className="flex items-center justify-between gap-4 border-b border-slate-100 bg-slate-50/70 px-4 py-4 dark:border-slate-800 dark:bg-slate-900 sm:px-6"><div className="flex min-w-0 items-center gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"><SourceIcon className="h-5 w-5"/></span><div className="min-w-0"><h2 className="truncate font-black sm:text-lg">{category.name}</h2><p className="text-xs text-slate-500">{category.files.length} file</p></div></div></header><div>{category.files.map(file=><article key={file.id} className="flex items-center gap-3 border-b border-slate-100 px-4 py-4 last:border-0 dark:border-slate-800 sm:gap-4 sm:px-6"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-slate-100 text-[10px] font-black uppercase text-slate-600 dark:bg-slate-800 dark:text-slate-300">{file.extension}</span><div className="min-w-0 flex-1"><h3 className="break-words text-sm font-bold leading-5">{file.name}</h3><p className="mt-1 text-[11px] text-slate-400">{formatBytes(file.size_bytes)}</p></div><button type="button" onClick={()=>download(file)} disabled={downloading===file.id} className="shrink-0 rounded-lg bg-slate-900 px-3 py-2 text-xs font-black text-white transition hover:bg-blue-600 disabled:cursor-wait disabled:opacity-60 dark:bg-white dark:text-slate-900 dark:hover:bg-blue-400 sm:px-4">{downloading===file.id?'Mengunduh...':'Unduh'}</button></article>)}</div></section>)}</div>}
  {downloadError&&<div role="alert" className="fixed bottom-24 left-4 right-4 z-50 mx-auto max-w-xl rounded-xl border border-red-200 bg-white p-4 text-sm font-semibold text-red-700 shadow-xl dark:border-red-900 dark:bg-slate-900 dark:text-red-300 md:bottom-6">{downloadError}</div>}
 </div></main>
}
