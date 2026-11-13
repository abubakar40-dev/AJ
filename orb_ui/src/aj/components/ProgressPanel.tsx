import { useState, type DragEvent } from "react";
import type {
  ActivityItem,
  ChatMessage,
  ConnectionState,
  OrbCapabilities,
  OrbVisualState,
} from "../types";
import { ChatCard } from "./ChatCard";
import { UploadStatesCard, type ItemActions } from "./UploadStatesCard";

const STATUS_TEXT: Record<OrbVisualState, string> = {
  idle: "Idle",
  processing: "Working",
  paused: "Paused",
  error: "Needs attention",
  success: "Done",
};

interface Props {
  box: { left: number; top: number; w: number; h: number };
  narrow: boolean;
  hidden: boolean;
  orbState: OrbVisualState;
  assistantName: string;
  connection: ConnectionState;
  connectionLabel?: string;
  capabilities: OrbCapabilities;
  items: ActivityItem[];
  messages: ChatMessage[];
  assistantBusy: boolean;
  actions: ItemActions;
  onClearFinished?: () => Promise<void>;
  onSend?: (text: string) => Promise<void>;
  onRetryMessage?: (id: string) => Promise<void>;
  onClose: () => void;
  /** Files/text dropped directly onto the panel. */
  onDropData: (dt: DataTransfer) => void;
}

/**
 * Reference image 3, composed as one floating window:
 *   left  = "Upload States" frosted card (progress rows)
 *   right = assistant chat card
 *   top-right = small iridescent status orb (live aggregate status)
 * Below 760px viewport width the two cards become tabs.
 */
export function ProgressPanel(props: Props) {
  const {
    box,
    narrow,
    hidden,
    orbState,
    items,
    messages,
    onClose,
    onDropData,
  } = props;
  const [minimized, setMinimized] = useState(false);
  const [tab, setTab] = useState<"uploads" | "ask">("uploads");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dropActive, setDropActive] = useState(false);

  const newest = [...items].sort((a, b) => b.addedAt - a.addedAt);
  const focusItem =
    items.find((i) => i.id === selectedId) ??
    newest.find((i) => i.status === "completed") ??
    newest[0] ??
    null;

  const hasPayload = (e: DragEvent) =>
    Array.from(e.dataTransfer.types).some((t) => t === "Files" || t === "text/plain" || t === "text/uri-list");

  const showUploads = !narrow || tab === "uploads";
  const showChat = !narrow || tab === "ask";

  return (
    <div
      role="dialog"
      aria-label="AJ activity"
      className="aj-panel"
      data-hidden={hidden || undefined}
      data-narrow={narrow || undefined}
      style={{ left: box.left, top: box.top, width: box.w, height: box.h }}
      onDragEnter={(e) => {
        if (!hasPayload(e)) return;
        e.preventDefault();
        setDropActive(true);
      }}
      onDragOver={(e) => {
        if (!hasPayload(e)) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
        setDropActive(true);
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDropActive(false);
      }}
      onDrop={(e) => {
        if (!hasPayload(e)) return;
        e.preventDefault();
        setDropActive(false);
        onDropData(e.dataTransfer);
      }}
    >
      <span
        className="aj-statusorb"
        data-state={orbState}
        role="status"
        aria-label={`AJ status: ${STATUS_TEXT[orbState]}`}
        title={`AJ status: ${STATUS_TEXT[orbState]}`}
      />

      {narrow && (
        <div className="aj-tabs" role="tablist" aria-label="Activity panel sections">
          <button
            role="tab"
            type="button"
            aria-selected={tab === "uploads"}
            className="aj-tab"
            onClick={() => setTab("uploads")}
          >
            Uploads{items.length > 0 ? ` (${items.length})` : ""}
          </button>
          <button
            role="tab"
            type="button"
            aria-selected={tab === "ask"}
            className="aj-tab"
            onClick={() => setTab("ask")}
          >
            Ask
          </button>
          <button type="button" className="aj-tab aj-tab--close" aria-label="Close activity panel" onClick={onClose}>
            ✕
          </button>
        </div>
      )}

      <div className={"flex min-h-0 flex-1 gap-5 " + (narrow ? "flex-col" : "items-center")}>
        {showUploads && (
          <div className={narrow ? "min-h-0 flex-1" : "flex max-h-full w-[336px] shrink-0"}>
            <UploadStatesCard
              items={items}
              selectedId={selectedId}
              capabilities={props.capabilities}
              actions={props.actions}
              onSelect={(id) => {
                setSelectedId(id);
                setMinimized(false);
              }}
              onClearFinished={props.onClearFinished}
              dropActive={dropActive}
            />
          </div>
        )}
        {showChat && (
          <div
            className={
              narrow ? "min-h-0 flex-1" : "w-[340px] shrink-0 self-stretch py-0 " + (minimized ? "flex items-start" : "")
            }
          >
            <ChatCard
              assistantName={props.assistantName}
              connection={props.connection}
              connectionLabel={props.connectionLabel}
              capabilities={props.capabilities}
              messages={messages}
              busy={props.assistantBusy}
              focusItem={focusItem}
              minimized={minimized && !narrow}
              onMinimize={() => setMinimized((m) => !m)}
              onClose={onClose}
              onSend={props.onSend}
              onRetryMessage={props.onRetryMessage}
            />
          </div>
        )}
      </div>
    </div>
  );
}
