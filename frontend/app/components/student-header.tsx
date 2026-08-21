'use client';
import Link from 'next/link';
import {usePathname} from 'next/navigation';
import {useAuth} from '@/app/providers/auth-context';
import {BoltIcon,HomeIcon,LeagueIcon,LogoutIcon,RouteIcon,UserIcon} from './ui-icons';

const links=[
 {href:'/dashboard',label:'Overview',icon:HomeIcon},
 {href:'/journey',label:'Journey',icon:RouteIcon},
 {href:'/leaderboard',label:'Leaderboard',icon:LeagueIcon},
 {href:'/profile',label:'Profile',icon:UserIcon},
];

export function StudentHeader(){
 const pathname=usePathname();const{user,logout}=useAuth();
 return <>
  <aside className="student-sidebar fixed inset-y-0 left-0 z-40 hidden w-[244px] flex-col border-r border-slate-200 bg-white px-5 py-7 dark:border-slate-800 dark:bg-slate-950 md:flex">
   <Link href="/dashboard" className="flex items-center gap-3 px-1 font-black tracking-tight"><span className="brand-mark"><BoltIcon/></span><span>ElectroQuest</span></Link>
   <p className="mb-3 mt-12 px-2 text-[10px] font-black uppercase tracking-[.2em] text-slate-400">Learn</p>
   <nav className="space-y-1">{links.slice(0,3).map(({href,label,icon:Icon})=><Link key={href} href={href} className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-bold transition ${pathname===href?'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300':'text-slate-600 hover:bg-slate-50 hover:text-slate-950 dark:text-slate-400 dark:hover:bg-slate-900'}`}><Icon className="h-[18px] w-[18px]"/>{label}</Link>)}</nav>
   <p className="mb-3 mt-9 px-2 text-[10px] font-black uppercase tracking-[.2em] text-slate-400">Account</p>
   <nav>{links.slice(3).map(({href,label,icon:Icon})=><Link key={href} href={href} className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-bold transition ${pathname===href?'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300':'text-slate-600 hover:bg-slate-50 hover:text-slate-950 dark:text-slate-400 dark:hover:bg-slate-900'}`}><Icon className="h-[18px] w-[18px]"/>{label}</Link>)}</nav>
   <div className="mt-auto border-t border-slate-200 pt-5 dark:border-slate-800"><Link href="/profile" className="flex items-center gap-3 rounded-xl p-2 hover:bg-slate-50 dark:hover:bg-slate-900"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-slate-900 text-sm font-black text-white">{user?.full_name?.charAt(0).toUpperCase()||'U'}</span><span className="min-w-0 flex-1"><strong className="block truncate text-sm">{user?.full_name}</strong><small className="block truncate text-slate-500">@{user?.username}</small></span></Link><button onClick={logout} className="mt-2 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-bold text-slate-500 hover:bg-red-50 hover:text-red-600"><LogoutIcon className="h-[18px] w-[18px]"/>Sign out</button></div>
  </aside>
  <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95 md:hidden"><div className="flex h-16 items-center justify-between"><Link href="/dashboard" className="flex items-center gap-2 font-black"><span className="brand-mark"><BoltIcon/></span>ElectroQuest</Link><Link href="/profile" className="grid h-9 w-9 place-items-center rounded-lg bg-slate-900 text-sm font-black text-white">{user?.full_name?.charAt(0).toUpperCase()||'U'}</Link></div></header>
  <nav className="mobile-bottom-nav grid-cols-4 md:hidden">{links.map(({href,label,icon:Icon})=><Link key={href} href={href} className={`mobile-nav-item ${pathname===href?'mobile-nav-item-active':''}`}><Icon className="h-5 w-5"/><span>{label}</span></Link>)}</nav>
 </>
}
