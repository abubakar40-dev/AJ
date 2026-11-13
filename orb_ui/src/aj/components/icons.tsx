import type { ReactNode } from "react";

interface IconProps {
  size?: number;
  className?: string;
  strokeWidth?: number;
}

function Base({
  size = 24,
  className,
  strokeWidth = 1.6,
  children,
}: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

/* ---------- Radial menu icons (reference image 2), outline style ---------- */

export const IconFileUpload = (p: IconProps) => (
  <Base {...p}>
    <path d="M14 3H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7z" />
    <path d="M14 3v4h4" />
    <path d="M12 17.5v-6" />
    <path d="m9.6 13.8 2.4-2.4 2.4 2.4" />
  </Base>
);

export const IconFileClock = (p: IconProps) => (
  <Base {...p}>
    <path d="M11.5 21H17a2 2 0 0 0 2-2V8l-5-5H8a2 2 0 0 0-2 2v6" />
    <path d="M14 3v5h5" />
    <circle cx="7" cy="17" r="4.4" fill="currentColor" stroke="none" />
    <path d="M7 14.7V17h2.2" stroke="#1a1c28" strokeWidth="1.5" />
  </Base>
);

export const IconBrush = (p: IconProps) => (
  <Base {...p}>
    <path d="m14.2 3.8 6 6-3.3 3.3-6-6z" />
    <path d="m10.9 7.1 5.9-3.6" opacity="0" />
    <path d="M10.2 8.4 7 11.6" />
    <path d="m7.3 12.9 3.8 3.8-4.2 4.2a2.7 2.7 0 0 1-3.8-3.8z" />
  </Base>
);

export const IconFileSearch = (p: IconProps) => (
  <Base {...p}>
    <path d="M12 21H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v6" />
    <path d="M9 7.5h6M9 11h6M9 14.5h2" />
    <circle cx="16" cy="17" r="3.2" />
    <path d="m18.4 19.4 2.4 2.4" />
  </Base>
);

export const IconLines = (p: IconProps) => (
  <Base {...p}>
    <path d="M4 6h16M4 10.5h16M4 15h16M4 19.5h10" />
  </Base>
);

export const IconClipboardList = (p: IconProps) => (
  <Base {...p}>
    <rect x="5" y="4.5" width="14" height="17" rx="2.4" />
    <path d="M9.5 4.5V4a1.2 1.2 0 0 1 1.2-1.2h2.6A1.2 1.2 0 0 1 14.5 4v.5" />
    <path d="M8.6 10h.01M8.6 13.4h.01M8.6 16.8h.01" strokeWidth="2.2" />
    <path d="M11.5 10H16M11.5 13.4H16M11.5 16.8H16" />
  </Base>
);

export const IconImages = (p: IconProps) => (
  <Base {...p}>
    <path d="M7 7V5.6A2.1 2.1 0 0 1 9.1 3.5h9.8A2.1 2.1 0 0 1 21 5.6v7.8a2.1 2.1 0 0 1-2.1 2.1H18" />
    <rect x="3" y="7.5" width="15" height="13" rx="2.2" />
    <circle cx="9.2" cy="12" r="1.5" fill="currentColor" stroke="none" />
    <path d="m3.4 18.6 4.6-4.3 3.4 3 2.4-2 4.2 3.6" fill="currentColor" fillOpacity=".9" />
  </Base>
);

export const IconTable = (p: IconProps) => (
  <Base {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2.2" />
    <path d="M3 10h18M3 14.5h18M12 10v9" />
  </Base>
);

/* ---------- Activity / chat icons ---------- */

export const IconClose = (p: IconProps) => (
  <Base {...p}>
    <path d="m6 6 12 12M18 6 6 18" />
  </Base>
);

export const IconMinus = (p: IconProps) => (
  <Base {...p}>
    <path d="M6 12h12" />
  </Base>
);

export const IconRefresh = (p: IconProps) => (
  <Base {...p}>
    <path d="M20 12a8 8 0 1 1-2.6-5.9" />
    <path d="M20 4v4.5h-4.5" />
  </Base>
);

export const IconPause = (p: IconProps) => (
  <Base {...p}>
    <path d="M9 6v12M15 6v12" strokeWidth={2.4} />
  </Base>
);

export const IconPlay = (p: IconProps) => (
  <Base {...p}>
    <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" />
  </Base>
);

export const IconSend = (p: IconProps) => (
  <Base {...p}>
    <path d="M4 4.5v15L21 12z" fill="currentColor" stroke="none" />
  </Base>
);

export const IconCheckCircle = (p: IconProps) => (
  <svg viewBox="0 0 16 16" width={p.size ?? 16} height={p.size ?? 16} className={p.className} aria-hidden="true">
    <circle cx="8" cy="8" r="7.5" fill="currentColor" />
    <path d="m4.8 8.2 2.2 2.2 4.2-4.6" fill="none" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const IconAlertCircle = (p: IconProps) => (
  <svg viewBox="0 0 16 16" width={p.size ?? 16} height={p.size ?? 16} className={p.className} aria-hidden="true">
    <circle cx="8" cy="8" r="7.5" fill="currentColor" />
    <path d="M8 4.4v4.2" stroke="#fff" strokeWidth="1.7" strokeLinecap="round" />
    <circle cx="8" cy="11.4" r="1" fill="#fff" />
  </svg>
);

export const IconSpinner = (p: IconProps) => (
  <svg viewBox="0 0 16 16" width={p.size ?? 14} height={p.size ?? 14} className={p.className} aria-hidden="true">
    {Array.from({ length: 8 }).map((_, i) => (
      <rect
        key={i}
        x="7.2"
        y="1"
        width="1.6"
        height="3.6"
        rx=".8"
        fill="currentColor"
        opacity={0.25 + (i / 8) * 0.75}
        transform={`rotate(${i * 45} 8 8)`}
      />
    ))}
  </svg>
);

export const IconClock = (p: IconProps) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </Base>
);

export const IconPaste = (p: IconProps) => (
  <Base {...p}>
    <rect x="6" y="5" width="12" height="16" rx="2" />
    <path d="M9 5V4h6v1M9 11h6M9 15h4" />
  </Base>
);

export const IconMove = (p: IconProps) => (
  <Base {...p}>
    <path d="M12 3v18M3 12h18M12 3l-2.6 2.6M12 3l2.6 2.6M12 21l-2.6-2.6M12 21l2.6-2.6M3 12l2.6-2.6M3 12l2.6 2.6M21 12l-2.6-2.6M21 12l-2.6 2.6" />
  </Base>
);

export const IconTrash = (p: IconProps) => (
  <Base {...p}>
    <path d="M4 7h16M9 7V4.5h6V7M6.5 7l1 13h9l1-13M10 11v6M14 11v6" />
  </Base>
);

export const IconPanel = (p: IconProps) => (
  <Base {...p}>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2.4" />
    <path d="M10 4.5v15" />
  </Base>
);
