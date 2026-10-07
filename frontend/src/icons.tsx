import type { JSX } from "react";

type P = { size?: number };
const s = (size: number) => ({
  width: size, height: size, viewBox: "0 0 24 24", fill: "none",
  stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

export const IconInbox = ({ size = 21 }: P) => (
  <svg {...s(size)}><path d="M22 12h-6l-2 3h-4l-2-3H2" /><path d="M5.5 5h13l3.5 7v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z" /></svg>
);
export const IconContacts = ({ size = 21 }: P) => (
  <svg {...s(size)}><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /></svg>
);
export const IconKB = ({ size = 21 }: P) => (
  <svg {...s(size)}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></svg>
);
export const IconReports = ({ size = 21 }: P) => (
  <svg {...s(size)}><path d="M3 3v18h18" /><path d="M7 14l3-3 3 3 5-6" /></svg>
);
export const IconUsers = ({ size = 21 }: P) => (
  <svg {...s(size)}><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /></svg>
);
export const IconSettings = ({ size = 21 }: P) => (
  <svg {...s(size)}>
    <circle cx="12" cy="12" r="3.3" />
    <path d="M12 2.5v3M12 18.5v3M21.5 12h-3M5.5 12h-3M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1M18.4 18.4l-2.1-2.1M7.7 7.7L5.6 5.6" />
  </svg>
);
export const IconSearch = ({ size = 15 }: P) => (
  <svg {...s(size)} strokeWidth={2}><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
);
export const IconSend = ({ size = 15 }: P) => (
  <svg {...s(size)} strokeWidth={2.2}><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z" /></svg>
);
export const IconBell = ({ size = 19 }: P) => (
  <svg {...s(size)}><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></svg>
);
export const IconSun = ({ size = 18 }: P) => (
  <svg {...s(size)}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
);
export const IconMoon = ({ size = 18 }: P) => (
  <svg {...s(size)}><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" /></svg>
);
export const IconLogout = ({ size = 18 }: P) => (
  <svg {...s(size)}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="M16 17l5-5-5-5M21 12H9" /></svg>
);
export const IconBack = ({ size = 20 }: P) => (
  <svg {...s(size)} strokeWidth={2.2}><path d="M9 6l6 6-6 6" /></svg>
);
export const IconAttach = ({ size = 18 }: P) => (
  <svg {...s(size)}><path d="M21.4 11.05l-8.5 8.5a5 5 0 0 1-7.07-7.07l8.49-8.49a3.33 3.33 0 0 1 4.71 4.71l-8.5 8.49a1.67 1.67 0 0 1-2.36-2.36l7.78-7.78" /></svg>
);
export const IconImage = ({ size = 18 }: P) => (
  <svg {...s(size)}><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="M21 15l-5-5L5 21" /></svg>
);
export const IconCanned = ({ size = 18 }: P) => (
  <svg {...s(size)}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
);
export const IconPlay = ({ size = 13 }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
);

export function ChannelGlyph({ channel, size = 9 }: { channel: string | null; size?: number }): JSX.Element {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "currentColor" };
  if (channel === "telegram")
    return <svg {...common}><path d="M21.9 4.3L18.6 20c-.25 1.1-.9 1.37-1.84.85l-5.1-3.76-2.46 2.37c-.27.27-.5.5-1.02.5l.36-5.2L18 5.6c.4-.36-.09-.56-.63-.2L6.1 12.6l-5.1-1.6c-1.1-.35-1.12-1.1.23-1.63l19.9-7.67c.92-.34 1.72.2 1.4 1.6z" /></svg>;
  if (channel === "messenger")
    return <svg {...common}><path d="M12 2C6.2 2 2 6.3 2 11.8c0 3.1 1.5 5.9 3.8 7.7V23l3.5-1.9c.9.3 1.9.4 2.7.4 5.8 0 10-4.3 10-9.8S17.8 2 12 2zm1 13.2l-2.5-2.7-4.9 2.7 5.4-5.7 2.6 2.7 4.8-2.7-5.4 5.7z" /></svg>;
  if (channel === "instagram")
    return <svg {...common}><path d="M12 2.2c3.2 0 3.6 0 4.9.07 3.3.15 4.8 1.7 4.95 4.95.06 1.3.07 1.7.07 4.9s0 3.6-.07 4.9c-.15 3.2-1.7 4.8-4.95 4.95-1.3.06-1.7.07-4.9.07s-3.6 0-4.9-.07c-3.3-.15-4.8-1.7-4.95-4.95C2.07 15.6 2.06 15.2 2.06 12s0-3.6.07-4.9C2.28 3.9 3.8 2.3 7.1 2.15 8.4 2.1 8.8 2.2 12 2.2zm0 3.1a6.7 6.7 0 1 0 0 13.4 6.7 6.7 0 0 0 0-13.4zm0 11a4.3 4.3 0 1 1 0-8.6 4.3 4.3 0 0 1 0 8.6zm6.9-11.2a1.56 1.56 0 1 0 0 3.12 1.56 1.56 0 0 0 0-3.12z" /></svg>;
  return <span style={{ width: size, height: size }} />;
}

export const CHANNEL_COLOR: Record<string, string> = {
  telegram: "var(--tg)", messenger: "var(--ms)", instagram: "var(--ig)",
};
