import type { ActivityItem } from "../types";
import { formatBytes } from "../lib/format";
import { IconAlertCircle, IconCheckCircle, IconClock, IconPause, IconSpinner } from "./icons";

/**
 * "60 KB of 120 KB • ⟳ Uploading…" line from reference image 3.
 * Every value comes from the ActivityItem; nothing is invented here.
 */
export function ItemMeta({ item }: { item: ActivityItem }) {
  const total = item.sizeBytes;
  const sizeText =
    total === null
      ? formatBytes(item.transferredBytes)
      : item.status === "completed"
        ? `${formatBytes(total)} of ${formatBytes(total)}`
        : item.status === "queued"
          ? formatBytes(total)
          : `${formatBytes(item.transferredBytes)} of ${formatBytes(total)}`;

  let status: React.ReactNode;
  switch (item.status) {
    case "uploading":
      status = (
        <>
          <IconSpinner size={13} className="aj-spin text-slate-500" />
          Uploading…
        </>
      );
      break;
    case "queued":
      status = (
        <>
          <IconClock size={14} className="text-slate-500" />
          Queued
        </>
      );
      break;
    case "paused":
      status = (
        <>
          <span className="grid h-[14px] w-[14px] place-items-center rounded-full bg-amber-500 text-white">
            <IconPause size={9} strokeWidth={3} />
          </span>
          Paused
        </>
      );
      break;
    case "completed":
      status = (
        <>
          <IconCheckCircle size={14} className="text-emerald-500" />
          Completed
        </>
      );
      break;
    case "error":
      status = (
        <>
          <IconAlertCircle size={14} className="text-red-500" />
          Error
        </>
      );
      break;
    case "cancelled":
      status = <>Cancelled</>;
      break;
  }

  return (
    <p className="mt-0.5 flex items-center gap-1.5 text-[12px] leading-4 text-slate-600">
      <span className="tabular-nums">{sizeText}</span>
      <span aria-hidden="true">•</span>
      <span className="inline-flex items-center gap-1">{status}</span>
    </p>
  );
}
