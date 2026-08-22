'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/app/providers/auth-context';
import {
  BoltIcon,
  CompassIcon,
  HomeIcon,
  LeagueIcon,
  LogoutIcon,
  RouteIcon,
  SourceIcon,
  StudioIcon,
  UserIcon,
} from './ui-icons';

const learnLinks = [
  { href: '/dashboard', label: 'Overview', mobileLabel: 'Home', icon: HomeIcon },
  { href: '/courses', label: 'Explore', mobileLabel: 'Explore', icon: CompassIcon },
  { href: '/journey', label: 'Journey', mobileLabel: 'Journey', icon: RouteIcon },
  { href: '/sources', label: 'Sources', mobileLabel: 'Sources', icon: SourceIcon },
];

const mobileLinks = [
  ...learnLinks,
  { href: '/profile', label: 'Profile', mobileLabel: 'Profile', icon: UserIcon },
];

function activePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function StudentHeader() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const canManage = user?.role === 'instructor' || user?.role === 'admin';

  return (
    <>
      <aside className="student-sidebar fixed inset-y-0 left-0 z-40 hidden w-[244px] flex-col border-r border-slate-200 bg-white px-5 py-7 dark:border-slate-800 dark:bg-slate-950 md:flex">
        <Link href="/dashboard" className="flex items-center gap-3 px-1 font-black tracking-tight">
          <span className="brand-mark"><BoltIcon /></span>
          <span>ElectroQuest</span>
        </Link>

        <p className="mb-3 mt-10 px-2 text-[10px] font-black uppercase tracking-[.2em] text-slate-400">Learn</p>
        <nav className="space-y-1">
          {learnLinks.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-bold transition ${
                activePath(pathname, href)
                  ? 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950 dark:text-slate-400 dark:hover:bg-slate-900'
              }`}
            >
              <Icon className="h-[18px] w-[18px]" />
              {label}
            </Link>
          ))}
        </nav>

        <p className="mb-3 mt-7 px-2 text-[10px] font-black uppercase tracking-[.2em] text-slate-400">Community</p>
        <Link
          href="/leaderboard"
          className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-bold transition ${
            activePath(pathname, '/leaderboard')
              ? 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
              : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950 dark:text-slate-400 dark:hover:bg-slate-900'
          }`}
        >
          <LeagueIcon className="h-[18px] w-[18px]" />
          Leaderboard
        </Link>

        {canManage && (
          <>
            <p className="mb-3 mt-7 px-2 text-[10px] font-black uppercase tracking-[.2em] text-slate-400">Manage</p>
            <Link
              href="/studio"
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-bold transition ${
                activePath(pathname, '/studio')
                  ? 'bg-violet-50 text-violet-700 dark:bg-violet-950 dark:text-violet-300'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950 dark:text-slate-400 dark:hover:bg-slate-900'
              }`}
            >
              <StudioIcon className="h-[18px] w-[18px]" />
              Content Studio
            </Link>
          </>
        )}

        <div className="mt-auto border-t border-slate-200 pt-5 dark:border-slate-800">
          <Link href="/profile" className="flex items-center gap-3 rounded-xl p-2 hover:bg-slate-50 dark:hover:bg-slate-900">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-slate-900 text-sm font-black text-white">
              {user?.full_name?.charAt(0).toUpperCase() || 'U'}
            </span>
            <span className="min-w-0 flex-1">
              <strong className="block truncate text-sm">{user?.full_name}</strong>
              <small className="block truncate text-slate-500">@{user?.username}</small>
            </span>
          </Link>
          <button
            type="button"
            onClick={logout}
            className="mt-2 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-bold text-slate-500 hover:bg-red-50 hover:text-red-600"
          >
            <LogoutIcon className="h-[18px] w-[18px]" />
            Sign out
          </button>
        </div>
      </aside>

      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95 md:hidden">
        <div className="flex h-16 items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-2 font-black">
            <span className="brand-mark"><BoltIcon /></span>
            ElectroQuest
          </Link>
          <div className="flex items-center gap-2">
            {canManage && (
              <Link href="/studio" aria-label="Buka Content Studio" className="grid h-9 w-9 place-items-center rounded-lg bg-violet-50 text-violet-700 dark:bg-violet-950 dark:text-violet-300">
                <StudioIcon className="h-4 w-4" />
              </Link>
            )}
            <Link href="/profile" className="grid h-9 w-9 place-items-center rounded-lg bg-slate-900 text-sm font-black text-white">
              {user?.full_name?.charAt(0).toUpperCase() || 'U'}
            </Link>
          </div>
        </div>
      </header>

      <nav className="mobile-bottom-nav grid-cols-5 md:hidden">
        {mobileLinks.map(({ href, mobileLabel, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={`mobile-nav-item ${activePath(pathname, href) ? 'mobile-nav-item-active' : ''}`}
          >
            <Icon className="h-5 w-5" />
            <span>{mobileLabel}</span>
          </Link>
        ))}
      </nav>
    </>
  );
}
