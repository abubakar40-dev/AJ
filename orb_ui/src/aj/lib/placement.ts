export interface Viewport {
  w: number;
  h: number;
}

/**
 * Place a floating box (activity panel) beside the orb, on the side with more
 * room, clamped inside the viewport. Mirrors how reference image 3 floats the
 * panel next to the glass orb.
 */
export function placeBeside(
  orb: { x: number; y: number; size: number },
  box: { w: number; h: number },
  vp: Viewport,
  gap = 18,
  margin = 12
): { left: number; top: number; side: "left" | "right" } {
  const cx = orb.x + orb.size / 2;
  const cy = orb.y + orb.size / 2;
  let side: "left" | "right" = cx > vp.w / 2 ? "left" : "right";
  let left =
    side === "left" ? orb.x - gap - box.w : orb.x + orb.size + gap;
  if (left < margin || left + box.w > vp.w - margin) {
    // try the other side
    const alt = side === "left" ? "right" : "left";
    const altLeft = alt === "left" ? orb.x - gap - box.w : orb.x + orb.size + gap;
    if (altLeft >= margin && altLeft + box.w <= vp.w - margin) {
      side = alt;
      left = altLeft;
    }
  }
  left = Math.max(margin, Math.min(left, vp.w - box.w - margin));
  // Panel sits slightly above the orb centre, like the reference composition.
  let top = cy - box.h * 0.62;
  top = Math.max(margin, Math.min(top, vp.h - box.h - margin));
  return { left, top, side };
}

export function clampPoint(
  x: number,
  y: number,
  size: number,
  vp: Viewport,
  margin = 4
): { x: number; y: number } {
  return {
    x: Math.max(margin, Math.min(x, vp.w - size - margin)),
    y: Math.max(margin, Math.min(y, vp.h - size - margin)),
  };
}
