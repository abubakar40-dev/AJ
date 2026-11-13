import { useEffect, useRef, useState } from "react";
import type {
  ActivityItem,
  ChatMessage,
  ConnectionState,
  OrbCapabilities,
} from "../types";
import { FileBadge } from "./FileBadge";
import { ItemMeta } from "./ItemMeta";
import { IconClose, IconMinus, IconSend, IconSpinner } from "./icons";
import { OrbArtwork } from "./OrbArtwork";

function renderRich(text: string) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return parts.map((p, i) => (i % 2 === 1 ? <strong key={i}>{p}</strong> : <span key={i}>{p}</span>));
}

function Avatar({ small }: { small?: boolean }) {
  return (
    <span
      className={
        "aj-avatar " + (small ? "h-[26px] w-[26px]" : "h-[34px] w-[34px]")
      }
    >
      <OrbArtwork />
    </span>
  );
}

const DELIVERY_LABEL = {
  sending: "Sending…",
  sent: "Sent",
  read: "Read",
  error: "Not delivered",
} as const;

interface Props {
  assistantName: string;
  connection: ConnectionState;
  connectionLabel?: string;
  capabilities: OrbCapabilities;
  messages: ChatMessage[];
  busy: boolean;
  /** Item shown in the file chip at the top (selected row, else newest). */
  focusItem: ActivityItem | null;
  minimized: boolean;
  onMinimize: () => void;
  onClose: () => void;
  onSend?: (text: string) => Promise<void>;
  onRetryMessage?: (id: string) => Promise<void>;
}

/** Right card of reference image 3: the "Ask a question…" assistant chat. */
export function ChatCard({
  assistantName,
  connection,
  connectionLabel,
  capabilities,
  messages,
  busy,
  focusItem,
  minimized,
  onMinimize,
  onClose,
  onSend,
  onRetryMessage,
}: Props) {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, busy, minimized]);

  const chatEnabled = capabilities.chat && !!onSend;
  const subtitle =
    connectionLabel ??
    (connection === "connected"
      ? "Active"
      : connection === "connecting"
        ? "Connecting…"
        : "Not connected");

  const submit = async () => {
    const text = draft.trim();
    if (!text || !onSend || sending) return;
    setSending(true);
    setSendError(null);
    try {
      await onSend(text);
      setDraft("");
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Could not send the message.");
    } finally {
      setSending(false);
    }
  };

  return (
    <section
      className="aj-chat"
      data-minimized={minimized || undefined}
      aria-label={`${assistantName} assistant chat`}
    >
      <header className="aj-chat__head">
        <Avatar />
        <div className="min-w-0 flex-1 leading-tight">
          <p className="text-[13px] font-semibold text-[#1d1b2e]">{assistantName}</p>
          <p className="flex items-center gap-1.5 text-[10.5px] text-slate-500">
            <span
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{
                background:
                  connection === "connected"
                    ? "#22c55e"
                    : connection === "connecting"
                      ? "#f59e0b"
                      : "#9ca3af",
              }}
            />
            {subtitle}
          </p>
        </div>
        <button
          type="button"
          className="aj-iconbtn"
          aria-label={minimized ? "Expand chat" : "Minimize chat"}
          aria-expanded={!minimized}
          onClick={onMinimize}
        >
          <IconMinus size={16} />
        </button>
        <button type="button" className="aj-iconbtn" aria-label="Close activity panel" onClick={onClose}>
          <IconClose size={16} />
        </button>
      </header>

      {!minimized && (
        <>
          <div className="aj-scroll flex-1 overflow-y-auto px-3 pb-2 pt-3">
            {focusItem && (
              <div className="mb-3 flex items-center gap-3 rounded-xl bg-white px-3 py-2 shadow-[0_1px_3px_rgba(60,40,120,.12)]">
                <FileBadge name={focusItem.name} mimeType={focusItem.mimeType} height={34} />
                <div className="min-w-0">
                  <p className="truncate text-[12.5px] font-medium text-[#1d1b2e]" title={focusItem.name}>
                    {focusItem.name}
                  </p>
                  <ItemMeta item={focusItem} />
                </div>
              </div>
            )}

            {messages.length === 0 && !busy && (
              <div className="mx-auto mt-6 max-w-[220px] text-center text-[12px] leading-snug text-slate-500">
                {chatEnabled
                  ? "Ask AJ a question about what you’ve added."
                  : "Chat is not available from the current AJ connection."}
              </div>
            )}

            <ul className="flex flex-col gap-3" aria-live="polite">
              {messages.map((m) => (
                <li key={m.id}>
                  {m.role === "user" ? (
                    <div className="flex flex-col items-end">
                      <div className="aj-bubble aj-bubble--user" data-error={m.delivery === "error" || undefined}>
                        {renderRich(m.text)}
                      </div>
                      {m.delivery && (
                        <span
                          className="mt-0.5 flex items-center gap-1 pr-1 text-[10px]"
                          style={{ color: m.delivery === "error" ? "#dc2626" : "#7b7a8c" }}
                          title={m.errorMessage}
                        >
                          {m.delivery === "sending" && <IconSpinner size={10} className="aj-spin" />}
                          {DELIVERY_LABEL[m.delivery]}
                          {m.delivery === "error" && onRetryMessage && (
                            <button
                              type="button"
                              className="font-semibold underline"
                              onClick={() => void onRetryMessage(m.id).catch(() => undefined)}
                            >
                              Retry
                            </button>
                          )}
                        </span>
                      )}
                      {m.delivery === "error" && m.errorMessage && (
                        <span className="max-w-[240px] pr-1 text-right text-[10px] leading-snug text-red-600">
                          {m.errorMessage}
                        </span>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-end gap-2">
                      <Avatar small />
                      <div className="aj-bubble aj-bubble--bot" data-system={m.role === "system" || undefined}>
                        {renderRich(m.text)}
                      </div>
                    </div>
                  )}
                </li>
              ))}
              {busy && (
                <li className="flex items-end gap-2" aria-label={`${assistantName} is typing`}>
                  <Avatar small />
                  <div className="aj-bubble aj-bubble--bot">
                    <span className="aj-dots">
                      <i />
                      <i />
                      <i />
                    </span>
                  </div>
                </li>
              )}
            </ul>
            <div ref={endRef} />
          </div>

          <form
            className="px-3 pb-3"
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            {sendError && (
              <p role="alert" className="mb-1 px-3 text-[11px] text-red-600">
                {sendError}
              </p>
            )}
            <div className="aj-ask" data-disabled={!chatEnabled || undefined}>
              <input
                type="text"
                value={draft}
                disabled={!chatEnabled}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={chatEnabled ? "Ask a question..." : "Chat unavailable"}
                aria-label="Ask a question"
                className="min-w-0 flex-1 bg-transparent text-[12.5px] text-[#1d1b2e] outline-none placeholder:text-slate-500"
              />
              <button
                type="submit"
                aria-label="Send question"
                disabled={!chatEnabled || !draft.trim() || sending}
                className="aj-send"
              >
                {sending ? <IconSpinner size={14} className="aj-spin" /> : <IconSend size={15} />}
              </button>
            </div>
          </form>
        </>
      )}
    </section>
  );
}
