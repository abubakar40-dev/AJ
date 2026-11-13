import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";

export interface MenuItem {
  id: string;
  label: string;
  hint?: string;
  icon?: ReactNode;
  disabled?: boolean;
  danger?: boolean;
  /** Render a divider above this item. */
  dividerBefore?: boolean;
  onSelect: () => void;
}

interface Props {
  x: number;
  y: number;
  items: MenuItem[];
  onClose: () => void;
}

/**
 * Right-click menu for the orb. Keyboard: ↑/↓ move, Enter selects, Esc closes.
 * Closes on outside press, blur and resize.
 */
export function ContextMenu({ x, y, items, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: x, top: y });
  const [focusIdx, setFocusIdx] = useState(() => items.findIndex((i) => !i.disabled));

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    setPos({
      left: Math.max(8, Math.min(x, window.innerWidth - r.width - 8)),
      top: Math.max(8, Math.min(y, window.innerHeight - r.height - 8)),
    });
    el.focus();
  }, [x, y]);

  useEffect(() => {
    const onDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    window.addEventListener("pointerdown", onDown, true);
    window.addEventListener("blur", onClose);
    window.addEventListener("resize", onClose);
    return () => {
      window.removeEventListener("pointerdown", onDown, true);
      window.removeEventListener("blur", onClose);
      window.removeEventListener("resize", onClose);
    };
  }, [onClose]);

  const move = (dir: 1 | -1) => {
    const enabled = items.map((it, i) => (it.disabled ? -1 : i)).filter((i) => i >= 0);
    if (!enabled.length) return;
    const cur = enabled.indexOf(focusIdx);
    const next = enabled[(cur + dir + enabled.length) % enabled.length];
    setFocusIdx(next);
  };

  return (
    <div
      ref={ref}
      role="menu"
      aria-label="Orb menu"
      tabIndex={-1}
      className="aj-ctx"
      style={{ left: pos.left, top: pos.top }}
      onContextMenu={(e) => e.preventDefault()}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          onClose();
        } else if (e.key === "ArrowDown") {
          e.preventDefault();
          move(1);
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          move(-1);
        } else if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          const it = items[focusIdx];
          if (it && !it.disabled) {
            onClose();
            it.onSelect();
          }
        }
      }}
    >
      {items.map((it, i) => (
        <div key={it.id}>
          {it.dividerBefore && <div className="aj-ctx__divider" role="separator" />}
          <button
            type="button"
            role="menuitem"
            disabled={it.disabled}
            data-focus={i === focusIdx || undefined}
            data-danger={it.danger || undefined}
            className="aj-ctx__item"
            onPointerEnter={() => !it.disabled && setFocusIdx(i)}
            onClick={() => {
              onClose();
              it.onSelect();
            }}
          >
            <span className="aj-ctx__icon">{it.icon}</span>
            <span className="aj-ctx__label">{it.label}</span>
            {it.hint && <span className="aj-ctx__hint">{it.hint}</span>}
          </button>
        </div>
      ))}
    </div>
  );
}
