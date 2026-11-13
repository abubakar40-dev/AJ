import type { DragEvent, KeyboardEvent } from "react";
import type { OrbIntent } from "../types";
import { RADIAL_ACTIONS } from "../lib/radialActions";

/** Geometry derived from reference image 2 (outer R : inner R ≈ 360 : 140). */
export const MENU_R = 170;
const INNER_R = 68;
const ICON_R = 119;
const GAP_DEG = 1.4;

const rad = (deg: number) => (deg * Math.PI) / 180;
const polar = (r: number, deg: number) => ({
  x: MENU_R + r * Math.sin(rad(deg)),
  y: MENU_R - r * Math.cos(rad(deg)),
});

function sectorPath(centerDeg: number): string {
  const a0 = centerDeg - 22.5 + GAP_DEG / 2;
  const a1 = centerDeg + 22.5 - GAP_DEG / 2;
  const o0 = polar(MENU_R, a0);
  const o1 = polar(MENU_R, a1);
  const i1 = polar(INNER_R, a1);
  const i0 = polar(INNER_R, a0);
  return `M${o0.x} ${o0.y} A${MENU_R} ${MENU_R} 0 0 1 ${o1.x} ${o1.y} L${i1.x} ${i1.y} A${INNER_R} ${INNER_R} 0 0 0 ${i0.x} ${i0.y}Z`;
}

interface Props {
  open: boolean;
  /** hover = opened by pointer; drag = a payload is being dragged over the orb. */
  mode: "hover" | "drag";
  orbSize: number;
  hovered: OrbIntent | null;
  rejected: OrbIntent | null;
  disabled: Set<OrbIntent>;
  centerText: string;
  centerTone: "neutral" | "accent" | "danger";
  onHover: (intent: OrbIntent | null) => void;
  onActivate: (intent: OrbIntent) => void;
  onSegmentDragOver: (e: DragEvent, intent: OrbIntent) => void;
  onSegmentDragLeave: (intent: OrbIntent) => void;
  onSegmentDrop: (e: DragEvent, intent: OrbIntent) => void;
}

/**
 * Reference image 2: dark circular menu with 8 outlined icons and a darker
 * centre disc reading "Release to Select".
 *
 * Rendered as TWO stacked layers around the orb (the orb sits between them):
 *   back  = dark ring disc
 *   front = centre disc (dims the orb), hit-testable sectors, icons
 */
export function RadialMenu({
  open,
  mode,
  orbSize,
  hovered,
  rejected,
  disabled,
  centerText,
  centerTone,
  onHover,
  onActivate,
  onSegmentDragOver,
  onSegmentDragLeave,
  onSegmentDrop,
}: Props) {
  const offset = orbSize / 2 - MENU_R;
  const boxStyle = { left: offset, top: offset, width: MENU_R * 2, height: MENU_R * 2 };

  return (
    <>
      <div className="aj-menu aj-menu--back" data-open={open || undefined} style={boxStyle} aria-hidden="true">
        <div className="aj-menu__disc" />
      </div>

      <div className="aj-menu aj-menu--front" data-open={open || undefined} style={boxStyle}>
        <div
          className="aj-menu__center"
          data-tone={centerTone}
          style={{ width: INNER_R * 2, height: INNER_R * 2, left: MENU_R - INNER_R, top: MENU_R - INNER_R }}
        >
          <span aria-live="polite">{centerText}</span>
        </div>

        <svg
          width={MENU_R * 2}
          height={MENU_R * 2}
          viewBox={`0 0 ${MENU_R * 2} ${MENU_R * 2}`}
          className="aj-menu__svg"
          role="menu"
          aria-label="AJ Orb actions"
        >
          {RADIAL_ACTIONS.map((a) => {
            const isDisabled = disabled.has(a.intent);
            const isHover = hovered === a.intent;
            const isRejected = rejected === a.intent;
            const tone = isRejected
              ? "rejected"
              : isHover && mode === "drag"
                ? "target"
                : isHover
                  ? "hover"
                  : "none";
            return (
              <path
                key={a.intent}
                d={sectorPath(a.angle)}
                className="aj-menu__sector"
                data-tone={tone}
                data-disabled={isDisabled || undefined}
                role="menuitem"
                aria-label={a.label}
                aria-disabled={isDisabled}
                tabIndex={isDisabled ? -1 : 0}
                onPointerEnter={() => onHover(a.intent)}
                onPointerLeave={() => onHover(null)}
                onFocus={() => onHover(a.intent)}
                onBlur={() => onHover(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  if (!isDisabled) onActivate(a.intent);
                }}
                onDoubleClick={(e) => e.stopPropagation()}
                onKeyDown={(e: KeyboardEvent<SVGPathElement>) => {
                  if ((e.key === "Enter" || e.key === " ") && !isDisabled) {
                    e.preventDefault();
                    onActivate(a.intent);
                  }
                }}
                onDragEnter={(e) => onSegmentDragOver(e, a.intent)}
                onDragOver={(e) => onSegmentDragOver(e, a.intent)}
                onDragLeave={() => onSegmentDragLeave(a.intent)}
                onDrop={(e) => onSegmentDrop(e, a.intent)}
              />
            );
          })}
        </svg>

        {RADIAL_ACTIONS.map((a) => {
          const p = polar(ICON_R, a.angle);
          const isHover = hovered === a.intent;
          const isRejected = rejected === a.intent;
          const isDisabled = disabled.has(a.intent);
          return (
            <span
              key={a.intent}
              className="aj-menu__icon"
              data-hover={isHover || undefined}
              data-rejected={isRejected || undefined}
              data-target={(isHover && mode === "drag" && !isRejected) || undefined}
              data-disabled={isDisabled || undefined}
              style={{ left: p.x, top: p.y }}
            >
              <a.Icon size={28} strokeWidth={1.5} />
            </span>
          );
        })}
      </div>
    </>
  );
}
