import { useId } from "react";

/**
 * Orb artwork: the glass sphere with a luminous cyan circuit board inside.
 * Vector-native so it stays crisp at any DPI/scale factor and needs no raster
 * asset (the Claude handoff's `assets/orb.jpg` was not included in the source
 * drop; this reproduces its described subject: glass rim, top-left gloss,
 * cyan traces/chip/nodes, blue light bleeding at the lower rim).
 */
export function OrbArtwork({ className }: { className?: string }) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const gid = (name: string) => `aj-orb-${name}-${uid}`;
  return (
    <svg
      viewBox="0 0 200 200"
      className={className}
      style={{ width: "100%", height: "100%", display: "block" }}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <radialGradient id={gid("core")} cx="42%" cy="34%" r="72%">
          <stop offset="0%" stopColor="#123a5c" />
          <stop offset="42%" stopColor="#0a1f38" />
          <stop offset="100%" stopColor="#02060d" />
        </radialGradient>
        <radialGradient id={gid("depth")} cx="50%" cy="78%" r="60%">
          <stop offset="0%" stopColor="#2aa7d8" stopOpacity="0.38" />
          <stop offset="60%" stopColor="#12557e" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#000000" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={gid("rim")} x1="20%" y1="8%" x2="82%" y2="96%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.55" />
          <stop offset="32%" stopColor="#8fd8ff" stopOpacity="0.16" />
          <stop offset="70%" stopColor="#1a6d9c" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#7fd6ff" stopOpacity="0.42" />
        </linearGradient>
        <radialGradient id={gid("gloss")} cx="32%" cy="17%" r="52%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.5" />
          <stop offset="55%" stopColor="#ffffff" stopOpacity="0.08" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
        <filter id={gid("glow")} x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="3.2" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <clipPath id={gid("clip")}>
          <circle cx="100" cy="100" r="86" />
        </clipPath>
      </defs>

      <circle cx="100" cy="100" r="86" fill={`url(#${gid("core")})`} />
      <g clipPath={`url(#${gid("clip")})`}>
        <circle cx="100" cy="100" r="86" fill={`url(#${gid("depth")})`} />

        {/* circuit traces */}
        <g
          stroke="#5ee1ff"
          strokeWidth="1.5"
          fill="none"
          opacity="0.72"
          filter={`url(#${gid("glow")})`}
          strokeLinecap="round"
        >
          <path d="M22 74h18l10 10h16l8-8h14" />
          <path d="M18 104h24l12-12h22l10 10h20" />
          <path d="M30 132h16l12-12h18l10 10h14" />
          <path d="M52 40v10l12 12h14l8-8h16" />
          <path d="M146 58h12l10 10v18l-8 8v14" />
          <path d="M154 128v14l-10 10h-16l-8-8h-18" />
          <path d="M128 44h16l10 10v10" />
          <path d="M96 160v12" />
          <path d="M60 150h20l10-10" />
        </g>
        <g fill="#bff4ff" opacity="0.9">
          <circle cx="22" cy="74" r="2.1" />
          <circle cx="18" cy="104" r="2.1" />
          <circle cx="30" cy="132" r="2.1" />
          <circle cx="52" cy="40" r="2.1" />
          <circle cx="146" cy="58" r="2.1" />
          <circle cx="154" cy="128" r="2.1" />
          <circle cx="128" cy="44" r="2.1" />
          <circle cx="96" cy="172" r="2.1" />
          <circle cx="60" cy="150" r="2.1" />
        </g>

        {/* central chip */}
        <g opacity="0.95">
          <rect x="84" y="84" width="32" height="32" rx="5" fill="#071726" stroke="#5ee1ff" strokeWidth="1.4" />
          <rect x="91" y="91" width="18" height="18" rx="2.5" fill="#0d2c46" stroke="#9feaff" strokeWidth="0.9" />
          <g stroke="#5ee1ff" strokeWidth="1.2">
            <path d="M84 92h-7M84 100h-7M84 108h-7M116 92h7M116 100h7M116 108h7" />
            <path d="M92 84v-7M100 84v-7M108 84v-7M92 116v7M100 116v7M108 116v7" />
          </g>
          <circle cx="100" cy="100" r="3.2" fill="#bff4ff" opacity="0.85" />
        </g>

        {/* scattered micro components */}
        <g fill="#2f7fa8" opacity="0.5">
          <rect x="56" y="98" width="8" height="4" rx="1" />
          <rect x="136" y="96" width="7" height="4" rx="1" />
          <rect x="66" y="118" width="6" height="4" rx="1" />
          <rect x="128" y="118" width="6" height="4" rx="1" />
        </g>

        <circle cx="100" cy="100" r="86" fill={`url(#${gid("gloss")})`} />
      </g>

      {/* glass rim */}
      <circle cx="100" cy="100" r="86" fill="none" stroke={`url(#${gid("rim")})`} strokeWidth="2.2" />
      <circle cx="100" cy="100" r="84" fill="none" stroke="#ffffff" strokeOpacity="0.1" strokeWidth="0.8" />
      <path
        d="M36 84a68 68 0 0 1 40-40"
        fill="none"
        stroke="#ffffff"
        strokeOpacity="0.5"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
