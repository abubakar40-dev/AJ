import type { ActivityItem } from "../types";

/** 61440 -> "60 KB". Uses 1024 base to match the reference ("60 KB of 120 KB"). */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb >= 100 ? Math.round(kb) : Math.round(kb * 10) / 10} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${Math.round(mb * 10) / 10} MB`;
  return `${Math.round((mb / 1024) * 100) / 100} GB`;
}

/** 0..1, or null when the total size is unknown (indeterminate). */
export function progressFraction(item: ActivityItem): number | null {
  if (item.status === "completed") return 1;
  if (item.sizeBytes === null) return null;
  if (item.sizeBytes === 0) return item.status === "queued" ? 0 : 1;
  return Math.max(0, Math.min(1, item.transferredBytes / item.sizeBytes));
}

export function isActive(item: ActivityItem): boolean {
  return (
    item.status === "queued" ||
    item.status === "uploading" ||
    item.status === "paused"
  );
}

export function isFinished(item: ActivityItem): boolean {
  return (
    item.status === "completed" ||
    item.status === "error" ||
    item.status === "cancelled"
  );
}

export function extensionOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i > 0 && i < name.length - 1 ? name.slice(i + 1).toLowerCase() : "";
}
