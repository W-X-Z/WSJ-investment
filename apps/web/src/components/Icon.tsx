import type { SVGProps } from "react";

type IconName =
  | "grid" | "network" | "rss" | "lightbulb" | "radar" | "search" | "database"
  | "arrow-up-right" | "arrow-right" | "chevron-down" | "chevron-right" | "activity"
  | "layers" | "cpu" | "zap" | "book" | "filter" | "external" | "clock"
  | "x" | "menu" | "command" | "target" | "shield" | "file" | "git-branch"
  | "check" | "alert" | "plus" | "calendar" | "link" | "eye";

const paths: Record<IconName, React.ReactNode> = {
  grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
  network: <><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="M6.8 7.1 10.9 16M17.2 7.1 13.1 16M7 6h10"/></>,
  rss: <><circle cx="5" cy="19" r="1"/><path d="M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16"/></>,
  lightbulb: <><path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7c1.2.9 1.6 2.2 1.6 3.3h4.8c0-1.1.4-2.4 1.6-3.3A7 7 0 0 0 12 2Z"/></>,
  radar: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 12 18 5M10.5 12a1.5 1.5 0 1 0 3 0 1.5 1.5 0 0 0-3 0"/></>,
  search: <><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/></>,
  database: <><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5M3 12c0 1.7 4 3 9 3s9-1.3 9-3"/></>,
  "arrow-up-right": <><path d="M6 18 18 6M8 6h10v10"/></>,
  "arrow-right": <><path d="M4 12h16m-6-6 6 6-6 6"/></>,
  "chevron-down": <path d="m6 9 6 6 6-6"/>,
  "chevron-right": <path d="m9 6 6 6-6 6"/>,
  activity: <path d="M2 12h4l3-8 5 16 3-8h5"/>,
  layers: <><path d="m12 2 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 17l9 5 9-5"/></>,
  cpu: <><rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3"/></>,
  zap: <path d="M13 2 4 13h7l-1 9 10-12h-7V2Z"/>,
  book: <><path d="M12 6c-3-2-6-2-10-1v15c4-1 7-1 10 1 3-2 6-2 10-1V5c-4-1-7-1-10 1Zm0 0v15"/></>,
  filter: <><path d="M3 5h18l-7 8v6l-4 2v-8L3 5Z"/></>,
  external: <><path d="M13 5h7v7M20 5 10 15"/><path d="M20 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/></>,
  x: <path d="M5 5 19 19M19 5 5 19"/>,
  menu: <path d="M4 6h16M4 12h16M4 18h16"/>,
  command: <><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 9H6a3 3 0 1 1 3-3v3Zm6 0h3a3 3 0 1 0-3-3v3Zm-6 6H6a3 3 0 1 0 3 3v-3Zm6 0h3a3 3 0 1 1-3 3v-3Z"/></>,
  target: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></>,
  shield: <><path d="M12 2 21 6v6c0 5.5-3.5 8.5-9 10-5.5-1.5-9-4.5-9-10V6l9-4Z"/><path d="m8 12 3 3 5-6"/></>,
  file: <><path d="M6 2h8l5 5v15H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm8 0v6h6M8 13h8m-8 4h8"/></>,
  "git-branch": <><circle cx="6" cy="4" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="20" r="2"/><path d="M6 6v12M18 8c0 6-12 1-12 10"/></>,
  check: <path d="m4 12 5 5L20 6"/>,
  alert: <><path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3h.01"/></>,
  plus: <path d="M12 4v16M4 12h16"/>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6m10-6v6M3 10h18"/></>,
  link: <><path d="m10 13 4-4M7 15H6a4 4 0 0 1 0-8h4m4 2h4a4 4 0 0 1 0 8h-4"/></>,
  eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>,
};
export function Icon({
  name, size = 18, ...props
}: SVGProps<SVGSVGElement> & { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" focusable="false" {...props}>
      {paths[name]}
    </svg>
  );
}
