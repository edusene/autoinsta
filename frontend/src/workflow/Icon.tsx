// Ícones de traço (24x24) usados no editor de workflows.

type IconSpec = { d: string[]; c?: [number, number, number][] }

const ICONS: Record<string, IconSpec> = {
  message: { d: ['M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'] },
  comment: { d: ['M7.9 20A9 9 0 1 0 4 16.1L2 22Z'] },
  userPlus: { d: ['M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2', 'M19 8v6', 'M22 11h-6'], c: [[9, 7, 4]] },
  userCheck: { d: ['M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2', 'm16 11 2 2 4-4'], c: [[9, 7, 4]] },
  at: { d: ['M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-4 8'], c: [[12, 12, 4]] },
  story: { d: ['M12 2a10 10 0 0 1 10 10', 'M12 22A10 10 0 0 1 2 12', 'M2 12A10 10 0 0 1 12 2'], c: [[12, 12, 4]] },
  link: { d: ['M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71', 'M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71'] },
  heart: { d: ['M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z'] },
  live: { d: ['M16.24 7.76a6 6 0 0 1 0 8.49', 'M7.76 16.24a6 6 0 0 1 0-8.49', 'M19.07 4.93a10 10 0 0 1 0 14.14', 'M4.93 19.07a10 10 0 0 1 0-14.14'], c: [[12, 12, 2]] },
  send: { d: ['M22 2 11 13', 'M22 2 15 22 11 13 2 9 22 2'] },
  reply: { d: ['M15 10l5 5-5 5', 'M4 4v7a4 4 0 0 0 4 4h12'] },
  megaphone: { d: ['m3 11 18-5v12L3 14v-3z', 'M11.6 16.8a3 3 0 1 1-5.8-1.6'] },
  buttons: { d: ['M4 4h16a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z', 'M4 14h16a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1z'] },
  clock: { d: ['M12 6v6l4 2'], c: [[12, 12, 10]] },
  hourglass: { d: ['M5 22h14', 'M5 2h14', 'M17 22v-4.17a2 2 0 0 0-.59-1.42L12 12l-4.41 4.41A2 2 0 0 0 7 17.83V22', 'M7 2v4.17a2 2 0 0 0 .59 1.42L12 12l4.41-4.41A2 2 0 0 0 17 6.17V2'] },
  sparkles: { d: ['M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z', 'M5 3v4', 'M3 5h4', 'M19 17v4', 'M17 19h4'] },
  braces: { d: ['M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5c0 1.1.9 2 2 2h1', 'M16 21h1a2 2 0 0 0 2-2v-5c0-1.1.9-2 2-2a2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1'] },
  tag: { d: ['M12 2H2v10l9.29 9.29a2.42 2.42 0 0 0 3.42 0l6.58-6.58a2.42 2.42 0 0 0 0-3.42L12 2Z', 'M7 7h.01'] },
  tagOff: { d: ['M12 2H2v10l9.29 9.29a2.42 2.42 0 0 0 3.42 0l6.58-6.58a2.42 2.42 0 0 0 0-3.42L12 2Z', 'M9 13l6-6'] },
  stop: { d: ['M6 6h12v12H6z'] },
  branch: { d: ['M6 3v12', 'M18 9a9 9 0 0 1-9 9'], c: [[18, 6, 3], [6, 18, 3]] },
  copy: { d: ['M8 8h12v12H8z', 'M4 16V4h12'] },
  trash: { d: ['M3 6h18', 'M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6', 'M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2'] },
  layout: { d: ['M3 3h7v7H3z', 'M14 3h7v7h-7z', 'M8.5 14h7v7h-7z', 'M6.5 10v2h11v-2', 'M12 12v2'] },
  chart: { d: ['M3 3v18h18', 'M7 15l4-4 3 3 5-6'] },
  search: { d: ['m21 21-4.3-4.3'], c: [[11, 11, 8]] },
}

export function Icon({ name, size = 16 }: { name: string; size?: number }) {
  const spec = ICONS[name] ?? ICONS.branch
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {spec.d.map((d) => <path key={d} d={d} />)}
      {spec.c?.map(([cx, cy, r]) => <circle key={`${cx}-${cy}-${r}`} cx={cx} cy={cy} r={r} />)}
    </svg>
  )
}
