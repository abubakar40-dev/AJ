import { useEffect, useRef, useState } from "react";
import { IconClose, IconSpinner } from "./icons";

interface Props {
  left: number;
  top: number;
  onSubmit: (text: string) => Promise<void>;
  onClose: () => void;
}

/** Small popover opened by the "Add text note" segment. Ctrl/⌘+Enter submits. */
export function NoteComposer({ left, top, onSubmit, onClose }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    ref.current?.focus();
  }, []);

  const submit = async () => {
    const value = text.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(value);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add the note.");
      setBusy(false);
    }
  };

  return (
    <div
      className="aj-note"
      style={{ left, top }}
      role="dialog"
      aria-label="Add text note"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          onClose();
        }
      }}
    >
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-[13px] font-semibold text-[#1d1b2e]">Add text note</h3>
        <button type="button" className="aj-iconbtn" aria-label="Close note" onClick={onClose}>
          <IconClose size={15} />
        </button>
      </div>
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            void submit();
          }
        }}
        rows={4}
        placeholder="Type or paste text…"
        aria-label="Note text"
        className="aj-note__input"
      />
      {error && (
        <p role="alert" className="mt-1 text-[11px] text-red-600">
          {error}
        </p>
      )}
      <div className="mt-2 flex items-center justify-between">
        <span className="text-[10.5px] text-slate-500">Ctrl+Enter to add</span>
        <button
          type="button"
          disabled={!text.trim() || busy}
          onClick={() => void submit()}
          className="aj-primary"
        >
          {busy && <IconSpinner size={12} className="aj-spin" />}
          {busy ? "Adding…" : "Add note"}
        </button>
      </div>
    </div>
  );
}
