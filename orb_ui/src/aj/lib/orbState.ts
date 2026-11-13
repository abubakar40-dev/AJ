import type { ActivityItem, OrbVisualState } from "../types";
import { isActive } from "./format";

export interface DerivedOrb {
  state: OrbVisualState;
  /** queued + uploading + paused rows (shown as the number badge). */
  activeCount: number;
  /** error rows the user has not yet seen in the panel. */
  unseenErrorCount: number;
  anyPaused: boolean;
  anyRunning: boolean;
}

/**
 * Pure function: backend data in -> orb visual state out.
 * Priority: unseen error > processing > paused > transient success > idle.
 */
export function deriveOrbState(args: {
  items: ActivityItem[];
  unseenErrorIds: Set<string>;
  successFlash: boolean;
  submitting: boolean;
}): DerivedOrb {
  const { items, unseenErrorIds, successFlash, submitting } = args;
  const activeCount = items.filter(isActive).length;
  const unseenErrorCount = items.filter(
    (i) => i.status === "error" && unseenErrorIds.has(i.id)
  ).length;
  const anyRunning = items.some(
    (i) => i.status === "uploading" || i.status === "queued"
  );
  const anyPaused = items.some((i) => i.status === "paused");

  let state: OrbVisualState = "idle";
  if (unseenErrorCount > 0) state = "error";
  else if (anyRunning || submitting) state = "processing";
  else if (anyPaused) state = "paused";
  else if (successFlash) state = "success";

  return { state, activeCount, unseenErrorCount, anyPaused, anyRunning };
}
