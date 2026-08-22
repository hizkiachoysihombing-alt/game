'use client';
import {useEffect,useMemo,useState} from 'react';
import {useRouter} from 'next/navigation';
import {StudentHeader} from '@/app/components/student-header';
import {ActivityIcon,BoltIcon,CheckIcon,FlameIcon} from '@/app/components/ui-icons';
import {useAuth} from '@/app/providers/auth-context';
import {apiClient} from '@/services/api-client';

const chapterColors=['bg-blue-600','bg-slate-800','bg-teal-700'];
function UnitIcon({status}:{status:string}){if(status==='completed')return <CheckIcon/>;if(status==='unavailable')return <span>—</span>;if(status==='endless')return <span className="text-xl">∞</span>;return <BoltIcon/>}

export default function JourneyPage(){
 const router=useRouter();const{user,loading}=useAuth();const[map,setMap]=useState<any>(null),[dashboard,setDashboard]=useState<any>(null),[error,setError]=useState(''),[leaving,setLeaving]=useState('');
 useEffect(()=>{if(!loading&&user)Promise.all([apiClient.getJourneyMap(),apiClient.getStudentDashboard()]).then(([journey,student])=>{setMap(journey);setDashboard(student)}).catch(()=>setError('Journey could not be loaded.'));},[loading,user]);
 const chapters=useMemo(()=>map?map.subjects:[],[map]);
 function play(topicId:number,unit:number,key:string){setLeaving(key);setTimeout(()=>router.push(`/journey/play?topic=${topicId}&unit=${unit}`),280)}
 if(loading||(user&&(!map||!dashboard)&&!error))return <main className="app-page grid place-items-center"><p className="font-semibold text-secondary">Building your journey...</p></main>;
 if(!user)return <main className="app-page grid place-items-center"><a href="/login" className="btn-primary">Sign in</a></main>;
 const stats=dashboard?.gamification,energy=dashboard?.subscription?.energy_remaining;
 return <main className={`app-page pb-28 md:pl-[244px] md:pb-10 ${leaving?'journey-page-leaving':''}`}><StudentHeader/><div className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
  <section className="resource-strip"><div><ActivityIcon className="text-slate-500"/><strong>Level {map.level}</strong></div><div><FlameIcon className="text-orange-600"/><strong>{stats.current_streak_days}</strong><small>day streak</small></div><div><BoltIcon className="text-blue-600"/><strong>{stats.total_xp}</strong><small>XP</small></div><div><span className="text-sm font-black text-blue-600">EN</span><strong>{energy===null?'∞':energy}</strong><small>energy</small></div></section>
  <div className="mt-8"><p className="eyebrow">Open learning explorer</p><h1 className="page-title">Choose any subject to explore</h1><p className="page-description">Every available subject and unit is open. Follow the recommended order or study material beyond your current campus curriculum.</p></div>
  {error&&<div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>}
  <div className="mt-9 space-y-12">{chapters.map((chapter:any,ci:number)=><section key={chapter.id}><header className={`unit-banner ${chapterColors[ci%chapterColors.length]}`}><div><p>SUBJECT {ci+1} · {chapter.topics.length} TOPICS</p><h2>{chapter.name}</h2></div><div className="unit-progress"><strong>{chapter.topics.filter((s:any)=>s.status==='mastered').length}/{chapter.topics.length}</strong><span>mastered</span></div></header>
   <div className="mt-5 space-y-4">{chapter.topics.map((section:any,si:number)=><article key={section.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"><div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4 dark:border-slate-800"><div><p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Section {ci+1}.{si+1}</p><h3 className="mt-1 font-black sm:text-lg">{section.name}</h3></div><div className="text-right"><strong className="text-blue-600">{Math.round(section.mastery)}%</strong><p className="text-[10px] text-slate-400">{section.attempts} answers</p></div></div>
    <div className="relative grid grid-cols-5 gap-2 px-3 py-6 sm:gap-4 sm:px-6"><div className="absolute left-[10%] right-[10%] top-[3.55rem] h-px bg-slate-200 dark:bg-slate-700"/>{section.units.map((unit:any)=>{const key=`${section.id}-${unit.index}`;return <div key={unit.index} className="relative z-10 min-w-0 text-center"><button disabled={unit.status==='unavailable'||!!leaving} onClick={()=>play(section.id,unit.index,key)} className={`mx-auto grid h-12 w-12 place-items-center rounded-xl border text-lg font-black transition hover:-translate-y-0.5 sm:h-16 sm:w-16 ${leaving===key?'scale-110 animate-pulse':unit.status==='completed'?'border-emerald-600 bg-emerald-600 text-white':unit.status==='current'?'border-blue-600 bg-blue-600 text-white shadow-md':unit.status==='endless'?'border-slate-800 bg-slate-800 text-white':'border-slate-200 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800'}`}><UnitIcon status={unit.status}/></button><p className="mt-2 truncate text-[10px] font-bold sm:text-xs">{unit.name}</p><p className="hidden text-[9px] text-slate-400 sm:block">{unit.status==='unavailable'?'Coming soon':unit.recommended?'Recommended · 20 questions':'Open · 20 questions'}</p></div>})}</div>
   </article>)}</div></section>)}
  </div>
 </div></main>
}
