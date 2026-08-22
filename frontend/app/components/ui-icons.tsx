import type { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement>;
const base = { width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true };

export const BoltIcon = (p: IconProps) => <svg {...base} {...p}><path d="m13 2-9 12h7l-1 8 9-12h-7l1-8Z"/></svg>;
export const HomeIcon = (p: IconProps) => <svg {...base} {...p}><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10M9 20v-6h6v6"/></svg>;
export const RouteIcon = (p: IconProps) => <svg {...base} {...p}><circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/><path d="M8 18h3a3 3 0 0 0 3-3V9a3 3 0 0 1 3-3"/></svg>;
export const SourceIcon = (p: IconProps) => <svg {...base} {...p}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/><path d="M8 7h8M8 11h6"/></svg>;
export const LeagueIcon = (p: IconProps) => <svg {...base} {...p}><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4Z"/><path d="M7 6H4v2a4 4 0 0 0 4 4M17 6h3v2a4 4 0 0 1-4 4"/></svg>;
export const FlameIcon = (p: IconProps) => <svg {...base} {...p}><path d="M12 22c4 0 7-3 7-7 0-3-2-6-5-9 0 3-2 4-3 5 0-4-2-7-2-9-3 3-4 7-4 11 0 5 3 9 7 9Z"/></svg>;
export const TargetIcon = (p: IconProps) => <svg {...base} {...p}><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></svg>;
export const CheckIcon = (p: IconProps) => <svg {...base} {...p}><path d="m5 12 4 4L19 6"/></svg>;
export const LockIcon = (p: IconProps) => <svg {...base} {...p}><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>;
export const GaugeIcon = (p: IconProps) => <svg {...base} {...p}><path d="M4 14a8 8 0 1 1 16 0"/><path d="m12 14 4-4M5 19h14"/></svg>;
export const ActivityIcon = (p: IconProps) => <svg {...base} {...p}><path d="M3 12h4l2-6 4 12 2-6h6"/></svg>;
export const ArrowRightIcon = (p: IconProps) => <svg {...base} {...p}><path d="M5 12h14m-6-6 6 6-6 6"/></svg>;
export const UserIcon = (p: IconProps) => <svg {...base} {...p}><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>;
export const LogoutIcon = (p: IconProps) => <svg {...base} {...p}><path d="M10 17l5-5-5-5M15 12H3M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/></svg>;
export const SettingsIcon = (p: IconProps) => <svg {...base} {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></svg>;
