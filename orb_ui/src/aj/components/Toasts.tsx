import { useEffect } from "react";
import { IconAlertCircle, IconCheckCircle, IconClose } from "./icons";

export type ToastKind = "success" | "error" | "warning" | "info";

export interface ToastData {
  id: number;
  kind: ToastKind;
  title: string;
  body?: string;
}

const DURATION: Record<ToastKind, number> = {
  success: 4000,
  info: 4000,
  warning: 6500,
  error: 8000,
};

function Toast({ toast, onDismiss }: { toast: ToastData; onDismiss: (id: number) => void }) {
  useEffect(() => {
    const t = window.setTimeout(() => onDismiss(toast.id), DURATION[toast.kind]);
    return () => window.clearTimeout(t);
  }, [toast.id, toast.kind, onDismiss]);

  return (
    <div className="aj-toast" data-kind={toast.kind} role={toast.kind === "error" ? "alert" : "status"}>
      <span className="aj-toast__icon">
        {toast.kind === "success" ? (
          <IconCheckCircle size={18} className="text-emerald-500" />
        ) : toast.kind === "info" ? (
          <span className="block h-[18px] w-[18px] rounded-full bg-sky-400" />
        ) : (
          <IconAlertCircle
            size={18}
            className={toast.kind === "error" ? "text-red-500" : "text-amber-500"}
          />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-semibold text-slate-800">{toast.title}</p>
        {toast.body && (
          <p className="mt-0.5 line-clamp-3 text-[12px] leading-snug text-slate-600">{toast.body}</p>
        )}
      </div>
      <button
        type="button"
        className="aj-toast__close"
        aria-label="Dismiss notification"
        onClick={() => onDismiss(toast.id)}
      >
        <IconClose size={14} />
      </button>
    </div>
  );
}

interface Props {
  toasts: ToastData[];
  onDismiss: (id: number) => void;
  orb: { x: number; y: number; size: number };
}

/** Stack of event-driven notifications anchored to the orb. */
export function Toasts({ toasts, onDismiss, orb }: Props) {
  if (toasts.length === 0) return null;
  const W = 300;
  const above = orb.y + orb.size / 2 > window.innerHeight / 2;
  const alignRight = orb.x + orb.size / 2 > window.innerWidth / 2;
  let left = alignRight ? orb.x + orb.size - W : orb.x;
  left = Math.max(10, Math.min(left, window.innerWidth - W - 10));
  const style = above
    ? { left, width: W, bottom: window.innerHeight - orb.y + 14 }
    : { left, width: W, top: orb.y + orb.size + 14 };
  return (
    <div
      className="aj-toasts"
      style={style}
      data-above={above || undefined}
    >
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
