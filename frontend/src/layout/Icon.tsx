import type { ReactNode, SVGProps } from 'react'

export type IconName = 'overview' | 'fleet' | 'missions' | 'dispatch' | 'alerts' | 'users' | 'profile' | 'menu' | 'close' | 'bell' | 'chevron'

const paths: Record<IconName, ReactNode> = {
  overview: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  fleet: <><path d="M5 17h14l-1.4-6.2A2.4 2.4 0 0 0 15.3 9H8.7a2.4 2.4 0 0 0-2.3 1.8L5 17Z" /><path d="M7 9V6h10v3M7 17v2M17 17v2M4 13H2M22 13h-2" /><circle cx="8" cy="14" r="1" /><circle cx="16" cy="14" r="1" /></>,
  missions: <><path d="M9 5h10a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V9" /><path d="M9 3H5a2 2 0 0 0-2 2v4M9 3v6H3M9 13h8M9 17h6" /></>,
  dispatch: <><circle cx="12" cy="12" r="3" /><circle cx="12" cy="12" r="8" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></>,
  alerts: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
  users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
  profile: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h12" /><path d="M10 21h4" /></>,
  chevron: <path d="m9 18 6-6-6-6" />,
}

export function Icon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...props}>{paths[name]}</svg>
}
