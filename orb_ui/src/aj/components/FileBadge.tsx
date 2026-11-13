import { badgeFor } from "../lib/fileKinds";

/** Page glyph with a coloured extension label (the red "PDF" tag in reference image 3). */
export function FileBadge({
  name,
  mimeType,
  height = 44,
}: {
  name: string;
  mimeType?: string;
  height?: number;
}) {
  const { label, color } = badgeFor(name, mimeType);
  const w = (height * 38) / 46;
  return (
    <svg viewBox="0 0 38 46" width={w} height={height} aria-hidden="true" className="shrink-0">
      <path
        d="M8 1.5h17l10.5 10.5v30.5a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-38a3 3 0 0 1 3-3z"
        fill="#fff"
        stroke="#cfd2e0"
        strokeWidth="1.6"
      />
      <path d="M25 1.5V9a3 3 0 0 0 3 3h7.5" fill="#eceef6" stroke="#cfd2e0" strokeWidth="1.6" strokeLinejoin="round" />
      <rect x="0" y="19" width="26" height="14.5" rx="3.2" fill={color} />
      <text
        x="13"
        y="29.6"
        textAnchor="middle"
        fontSize={label.length > 3 ? 7.6 : 9}
        fontWeight="800"
        fill="#fff"
        fontFamily="Plus Jakarta Sans, Inter, system-ui, sans-serif"
        letterSpacing=".3"
      >
        {label}
      </text>
    </svg>
  );
}
