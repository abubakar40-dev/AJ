import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import type { OrbPosition } from "../types";
import { clampPoint } from "../lib/placement";

interface Options {
  size: number;
  initial?: OrbPosition;
  /** Dragging is only active in "move mode" (entered with a double-click). */
  enabled: boolean;
  onCommit?: (pos: OrbPosition) => void;
}

const THROW_MIN_SPEED = 320; // px/s below which release just drops in place
const MAX_SPEED = 4200; // px/s clamp
const FRICTION = 3.1; // exponential decay per second
const RESTITUTION = 0.62; // energy kept on edge bounce
const STOP_SPEED = 24; // px/s

/**
 * Move + throw behaviour.
 *
 * Performance: while dragging/flying, the position is written straight to the
 * element's transform (no React re-render per frame). The rAF loop only runs
 * during a throw and stops itself. React state is updated once on settle.
 *
 * GTK/Wayland note: clients cannot set absolute window positions on Wayland,
 * so a throw cannot be reproduced with a normal toplevel. See docs/GTK_PORT_NOTES.md.
 */
export function useOrbMotion({ size, initial, enabled, onCommit }: Options) {
  const elRef = useRef<HTMLDivElement | null>(null);
  const [pos, setPos] = useState<OrbPosition>(() => {
    const vp = { w: window.innerWidth, h: window.innerHeight };
    const start = initial ?? { x: vp.w - size - 56, y: vp.h - size - 56 };
    return clampPoint(start.x, start.y, size, vp);
  });
  const [dragging, setDragging] = useState(false);
  const [flying, setFlying] = useState(false);

  const live = useRef<OrbPosition>(pos);
  const grab = useRef({ dx: 0, dy: 0 });
  const samples = useRef<{ t: number; x: number; y: number }[]>([]);
  const raf = useRef<number | null>(null);
  const movedPx = useRef(0);
  const startPt = useRef({ x: 0, y: 0 });
  const didDrag = useRef(false);
  const onCommitRef = useRef(onCommit);
  onCommitRef.current = onCommit;

  const write = useCallback((p: OrbPosition) => {
    live.current = p;
    if (elRef.current) {
      elRef.current.style.transform = `translate3d(${p.x}px, ${p.y}px, 0)`;
    }
  }, []);

  useLayoutEffect(() => {
    write(pos);
  }, [pos, write]);

  const commit = useCallback(
    (p: OrbPosition) => {
      write(p);
      setPos(p);
      onCommitRef.current?.(p);
    },
    [write]
  );

  const stopFlight = useCallback(() => {
    if (raf.current !== null) cancelAnimationFrame(raf.current);
    raf.current = null;
    setFlying(false);
  }, []);

  const startFlight = useCallback(
    (vx: number, vy: number) => {
      const vp = () => ({ w: window.innerWidth, h: window.innerHeight });
      let last = performance.now();
      let vX = vx;
      let vY = vy;
      setFlying(true);
      const step = (now: number) => {
        const dt = Math.min(0.04, (now - last) / 1000);
        last = now;
        const decay = Math.exp(-FRICTION * dt);
        vX *= decay;
        vY *= decay;
        let x = live.current.x + vX * dt;
        let y = live.current.y + vY * dt;
        const min = 4;
        const maxX = vp().w - size - 4;
        const maxY = vp().h - size - 4;
        if (x < min) { x = min; vX = Math.abs(vX) * RESTITUTION; }
        if (x > maxX) { x = maxX; vX = -Math.abs(vX) * RESTITUTION; }
        if (y < min) { y = min; vY = Math.abs(vY) * RESTITUTION; }
        if (y > maxY) { y = maxY; vY = -Math.abs(vY) * RESTITUTION; }
        write({ x, y });
        if (Math.hypot(vX, vY) < STOP_SPEED) {
          raf.current = null;
          setFlying(false);
          commit({ x, y });
          return;
        }
        raf.current = requestAnimationFrame(step);
      };
      raf.current = requestAnimationFrame(step);
    },
    [commit, size, write]
  );

  const onPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLElement>) => {
      if (!enabled || e.button !== 0) return;
      stopFlight();
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
      grab.current = { dx: e.clientX - live.current.x, dy: e.clientY - live.current.y };
      startPt.current = { x: e.clientX, y: e.clientY };
      movedPx.current = 0;
      didDrag.current = false;
      samples.current = [{ t: performance.now(), x: e.clientX, y: e.clientY }];
      setDragging(true);
    },
    [enabled, stopFlight]
  );

  const onPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLElement>) => {
      if (!dragging) return;
      movedPx.current = Math.hypot(
        e.clientX - startPt.current.x,
        e.clientY - startPt.current.y
      );
      if (movedPx.current > 4) didDrag.current = true;
      const p = clampPoint(
        e.clientX - grab.current.dx,
        e.clientY - grab.current.dy,
        size,
        { w: window.innerWidth, h: window.innerHeight }
      );
      write(p);
      const now = performance.now();
      samples.current.push({ t: now, x: e.clientX, y: e.clientY });
      while (samples.current.length > 2 && now - samples.current[0].t > 90) {
        samples.current.shift();
      }
    },
    [dragging, size, write]
  );

  const endDrag = useCallback(
    (e: ReactPointerEvent<HTMLElement>) => {
      if (!dragging) return;
      setDragging(false);
      try {
        (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
      } catch {
        /* already released */
      }
      const s = samples.current;
      const first = s[0];
      const last = s[s.length - 1];
      const dt = (last.t - first.t) / 1000;
      let vx = 0;
      let vy = 0;
      if (dt > 0.01) {
        vx = (last.x - first.x) / dt;
        vy = (last.y - first.y) / dt;
      }
      const speed = Math.hypot(vx, vy);
      // Released after pausing: treat as drop-in-place, not a throw.
      const stale = performance.now() - last.t > 70;
      if (!stale && speed > THROW_MIN_SPEED) {
        const k = Math.min(1, MAX_SPEED / speed);
        startFlight(vx * k, vy * k);
      } else {
        commit({ ...live.current });
      }
    },
    [commit, dragging, startFlight]
  );

  /** Re-clamp when the window (or display scale) changes. */
  useEffect(() => {
    const onResize = () => {
      const p = clampPoint(live.current.x, live.current.y, size, {
        w: window.innerWidth,
        h: window.innerHeight,
      });
      if (p.x !== live.current.x || p.y !== live.current.y) commit(p);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [commit, size]);

  useEffect(() => () => stopFlight(), [stopFlight]);

  return {
    elRef,
    pos,
    dragging,
    flying,
    /** true if the last pointer gesture was a drag (suppress the click). */
    consumeDidDrag: () => {
      const v = didDrag.current;
      didDrag.current = false;
      return v;
    },
    setPosition: commit,
    handlers: { onPointerDown, onPointerMove, onPointerUp: endDrag, onPointerCancel: endDrag },
  };
}
