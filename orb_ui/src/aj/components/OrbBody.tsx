import type { OrbVisualState } from "../types";
import { OrbArtwork } from "./OrbArtwork";

interface Props {
  state: OrbVisualState;
  /** A file is hovering over the orb (drag-over). */
  dragOver: boolean;
  /** The current drag target would reject the payload (drag-rejected). */
  rejected: boolean;
  /** Move mode armed with double-click. */
  moveMode: boolean;
  dragging: boolean;
  menuOpen: boolean;
  /** A file is being dragged somewhere on screen: orb "perks up". */
  attention: boolean;
  disconnected: boolean;
  activeCount: number;
  errorCount: number;
}

/**
 * Reference image 1: a glass sphere with a luminous circuit board inside.
 * Visual only — no behaviour. All state arrives via props / data attributes,
 * and all styling lives in index.css (.aj-orb*) so it can be ported to Cairo.
 */
export function OrbBody({
  state,
  dragOver,
  rejected,
  moveMode,
  dragging,
  menuOpen,
  attention,
  disconnected,
  activeCount,
  errorCount,
}: Props) {
  const badge = errorCount > 0 ? "!" : activeCount > 0 ? String(Math.min(activeCount, 99)) : null;
  return (
    <div
      className="aj-orb"
      data-state={state}
      data-drag-over={dragOver || undefined}
      data-rejected={rejected || undefined}
      data-move={moveMode || undefined}
      data-dragging={dragging || undefined}
      data-menu={menuOpen || undefined}
      data-attention={attention || undefined}
      data-disconnected={disconnected || undefined}
    >
      <div className="aj-orb__float">
        <span className="aj-orb__halo" />
        <span className="aj-ring aj-ring--base" />
        <span className="aj-ring aj-ring--spin" />
        <span className="aj-ring aj-ring--move" />
        <div className="aj-orb__sphere">
          <OrbArtwork className="aj-orb__img" />
          <span className="aj-orb__gloss" />
          <span className="aj-orb__rim" />
        </div>
      </div>
      {badge && (
        <span
          className="aj-orb__badge"
          data-error={errorCount > 0 || undefined}
          aria-hidden="true"
        >
          {badge}
        </span>
      )}
      {disconnected && <span className="aj-orb__offline" aria-hidden="true" />}
    </div>
  );
}
