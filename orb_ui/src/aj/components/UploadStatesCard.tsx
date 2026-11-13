import { useEffect, useState } from "react";
import type { ActivityItem, OrbCapabilities } from "../types";
import { isFinished, progressFraction } from "../lib/format";
import { FileBadge } from "./FileBadge";
import { ItemMeta } from "./ItemMeta";
import {
  IconClose,
  IconPause,
  IconPlay,
  IconRefresh,
  IconSpinner,
} from "./icons";

export interface ItemActions {
  cancel?: (id: string) => Promise<void>;
  retry?: (id: string) => Promise<void>;
  pause?: (id: string) => Promise<void>;
  resume?: (id: string) => Promise<void>;
}

interface RowProps {
  item: ActivityItem;
  selected: boolean;
  capabilities: OrbCapabilities;
  actions: ItemActions;
  onSelect: (id: string) => void;
}

function RowButton({
  label,
  onClick,
  pending,
  variant,
  children,
}: {
  label: string;
  onClick: () => void;
  pending: boolean;
  variant: "dark" | "ghost";
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      disabled={pending}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={
        "aj-rowbtn " + (variant === "dark" ? "aj-rowbtn--dark" : "aj-rowbtn--ghost")
      }
    >
      {pending ? <IconSpinner size={13} className="aj-spin" /> : children}
    </button>
  );
}

function UploadRow({ item, selected, capabilities, actions, onSelect }: RowProps) {
  const [pending, setPending] = useState(false);

  // A status change means the host acted on the request: clear local pending.
  useEffect(() => {
    setPending(false);
  }, [item.status]);

  const run = (fn?: (id: string) => Promise<void>) => async () => {
    if (!fn) return;
    setPending(true);
    try {
      await fn(item.id);
    } finally {
      setPending(false);
    }
  };

  const fraction = progressFraction(item);
  const indeterminate = fraction === null && item.status === "uploading";
  const running = item.status === "uploading" || item.status === "queued";

  const canPause = capabilities.pause && !!actions.pause && item.status === "uploading";
  const canResume = capabilities.pause && !!actions.resume && item.status === "paused";
  const canCancel =
    capabilities.cancel && !!actions.cancel && (running || item.status === "paused");
  const canRetry =
    capabilities.retry &&
    !!actions.retry &&
    (item.status === "error" || item.status === "cancelled");

  return (
    <li>
      <div
        role="button"
        tabIndex={0}
        aria-pressed={selected}
        onClick={() => onSelect(item.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect(item.id);
          }
        }}
        className="aj-row"
        data-selected={selected || undefined}
        data-status={item.status}
      >
        <div className="flex items-start gap-3">
          <FileBadge name={item.name} mimeType={item.mimeType} />
          <div className="min-w-0 flex-1 pt-0.5">
            <p className="truncate text-[15px] font-medium leading-5 text-[#1d1b2e]" title={item.name}>
              {item.name}
            </p>
            <ItemMeta item={item} />
            {item.status === "error" && item.errorMessage && (
              <p className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-red-600">
                {item.errorMessage}
              </p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            {canPause && (
              <RowButton label="Pause" variant="ghost" pending={pending} onClick={run(actions.pause)}>
                <IconPause size={14} />
              </RowButton>
            )}
            {canResume && (
              <RowButton label="Resume" variant="ghost" pending={pending} onClick={run(actions.resume)}>
                <IconPlay size={14} />
              </RowButton>
            )}
            {canCancel && (
              <RowButton label="Cancel" variant="dark" pending={pending} onClick={run(actions.cancel)}>
                <IconClose size={12} strokeWidth={2.4} />
              </RowButton>
            )}
            {canRetry && (
              <RowButton label="Retry" variant="ghost" pending={pending} onClick={run(actions.retry)}>
                <IconRefresh size={20} strokeWidth={1.8} />
              </RowButton>
            )}
          </div>
        </div>

        <div
          className="aj-bar"
          role="progressbar"
          aria-label={`${item.name} progress`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={fraction === null ? undefined : Math.round(fraction * 100)}
          aria-valuetext={item.status}
        >
          {indeterminate ? (
            <span className="aj-bar__indeterminate" />
          ) : item.status === "error" ? null : (
            <span
              className="aj-bar__fill"
              data-paused={item.status === "paused" || undefined}
              style={{ width: `${(fraction ?? 0) * 100}%` }}
            />
          )}
        </div>
      </div>
    </li>
  );
}

interface Props {
  items: ActivityItem[];
  selectedId: string | null;
  capabilities: OrbCapabilities;
  actions: ItemActions;
  onSelect: (id: string) => void;
  onClearFinished?: () => Promise<void>;
  dropActive: boolean;
}

/** Left card of reference image 3: "Upload States". */
export function UploadStatesCard({
  items,
  selectedId,
  capabilities,
  actions,
  onSelect,
  onClearFinished,
  dropActive,
}: Props) {
  const [clearing, setClearing] = useState(false);
  const finished = items.filter(isFinished).length;
  const sorted = [...items].sort((a, b) => b.addedAt - a.addedAt);

  return (
    <section className="aj-upcard" data-drop={dropActive || undefined} aria-label="Upload states">
      <header className="flex items-center justify-between px-1 pb-3">
        <h2 className="text-[18px] font-medium tracking-[-0.01em] text-[#1d1b2e]">Upload States</h2>
        <div className="flex items-center gap-2">
          {items.length > 0 && (
            <span className="rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-semibold text-[#4a3a85]">
              {items.length}
            </span>
          )}
          {onClearFinished && (
            <button
              type="button"
              disabled={finished === 0 || clearing}
              onClick={async () => {
                setClearing(true);
                try {
                  await onClearFinished();
                } finally {
                  setClearing(false);
                }
              }}
              className="aj-linkbtn"
            >
              {clearing ? "Clearing…" : "Clear finished"}
            </button>
          )}
        </div>
      </header>

      {sorted.length === 0 ? (
        <div className="aj-empty">
          <p className="text-[14px] font-medium text-[#3b3556]">Nothing uploaded yet</p>
          <p className="mt-1 text-[12px] leading-snug text-slate-500">
            Drop files on the orb, or use the radial menu to add some. Progress appears here.
          </p>
        </div>
      ) : (
        <ul className="aj-scroll -mr-2 flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pr-2">
          {sorted.map((item) => (
            <UploadRow
              key={item.id}
              item={item}
              selected={item.id === selectedId}
              capabilities={capabilities}
              actions={actions}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}

      {dropActive && <div className="aj-dropveil">Drop to add</div>}
    </section>
  );
}
