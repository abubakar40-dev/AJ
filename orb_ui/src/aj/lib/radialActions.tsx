import type { ComponentType } from "react";
import type { OrbIntent, SubmitPayload } from "../types";
import {
  IconBrush,
  IconClipboardList,
  IconFileClock,
  IconFileSearch,
  IconFileUpload,
  IconImages,
  IconLines,
  IconTable,
} from "../components/icons";
import { classifyFile, type FileKind } from "./fileKinds";

/**
 * The 8 segments of the radial menu (reference image 2), listed clockwise
 * starting at the top-right slot. `angle` is the segment CENTRE in degrees,
 * clockwise from 12 o'clock — exactly matching the reference layout:
 *
 *   top-left  = add-file     top-right    = recent
 *   left-up   = add-table    right-up     = cleanup
 *   left-down = add-image    right-down   = analyze
 *   bot-left  = paste        bot-right    = add-text
 */
export interface RadialAction {
  intent: OrbIntent;
  label: string;
  /** Shown in the centre disc when hovering during a drag. */
  dropLabel: string;
  angle: number;
  Icon: ComponentType<{ size?: number; className?: string; strokeWidth?: number }>;
  /** File kinds this segment accepts on drop. null = does not accept files. */
  acceptsKinds: FileKind[] | "any" | null;
  acceptsText: boolean;
  /** Native picker configuration when clicked (null = no picker). */
  picker: { accept: string; multiple: boolean } | null;
}

export const RADIAL_ACTIONS: RadialAction[] = [
  {
    intent: "recent",
    label: "Recent activity",
    dropLabel: "Doesn’t accept drops",
    angle: 22.5,
    Icon: IconFileClock,
    acceptsKinds: null,
    acceptsText: false,
    picker: null,
  },
  {
    intent: "cleanup",
    label: "Clean up",
    dropLabel: "Clean up",
    angle: 67.5,
    Icon: IconBrush,
    acceptsKinds: "any",
    acceptsText: false,
    picker: { accept: "", multiple: true },
  },
  {
    intent: "analyze",
    label: "Analyze document",
    dropLabel: "Analyze",
    angle: 112.5,
    Icon: IconFileSearch,
    acceptsKinds: ["document", "text"],
    acceptsText: true,
    picker: {
      accept: ".pdf,.doc,.docx,.odt,.rtf,.ppt,.pptx,.odp,.epub,.txt,.md,text/plain",
      multiple: true,
    },
  },
  {
    intent: "add-text",
    label: "Add text note",
    dropLabel: "Add as text",
    angle: 157.5,
    Icon: IconLines,
    acceptsKinds: ["text"],
    acceptsText: true,
    picker: null,
  },
  {
    intent: "paste-clipboard",
    label: "Paste clipboard",
    dropLabel: "Doesn’t accept drops",
    angle: 202.5,
    Icon: IconClipboardList,
    acceptsKinds: null,
    acceptsText: false,
    picker: null,
  },
  {
    intent: "add-image",
    label: "Add images",
    dropLabel: "Add images",
    angle: 247.5,
    Icon: IconImages,
    acceptsKinds: ["image"],
    acceptsText: false,
    picker: { accept: "image/*", multiple: true },
  },
  {
    intent: "add-table",
    label: "Add spreadsheets",
    dropLabel: "Add tables",
    angle: 292.5,
    Icon: IconTable,
    acceptsKinds: ["table"],
    acceptsText: false,
    picker: {
      accept: ".csv,.tsv,.xlsx,.xls,.xlsm,.ods,text/csv",
      multiple: true,
    },
  },
  {
    intent: "add-file",
    label: "Add files",
    dropLabel: "Add files",
    angle: 337.5,
    Icon: IconFileUpload,
    acceptsKinds: "any",
    acceptsText: true,
    picker: { accept: "", multiple: true },
  },
];

export function actionFor(intent: OrbIntent): RadialAction {
  return RADIAL_ACTIONS.find((a) => a.intent === intent)!;
}

function kindAccepted(action: RadialAction, kind: FileKind): boolean {
  if (action.acceptsKinds === null) return false;
  if (action.acceptsKinds === "any") return true;
  if (kind === "unknown") return true; // cannot judge yet
  return action.acceptsKinds.includes(kind);
}

/* ------------------------------------------------------------------ */
/* Drop parsing / validation                                           */
/* ------------------------------------------------------------------ */

/** Synchronously read a DataTransfer (must be called inside the drop event). */
export function extractDrop(dt: DataTransfer): SubmitPayload {
  const payload: SubmitPayload = { files: [], uris: [], text: null, rejected: [] };
  const dirNames = new Set<string>();

  for (const item of Array.from(dt.items ?? [])) {
    if (item.kind !== "file") continue;
    const entry = item.webkitGetAsEntry?.();
    if (entry?.isDirectory) {
      dirNames.add(entry.name);
      payload.rejected.push({ name: entry.name, reason: "Folders are not supported" });
    }
  }
  for (const f of Array.from(dt.files ?? [])) {
    if (!dirNames.has(f.name)) payload.files.push(f);
  }
  const uriList = dt.getData("text/uri-list");
  if (uriList) {
    payload.uris = uriList
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#"));
  }
  if (payload.files.length === 0) {
    const text = dt.getData("text/plain").trim();
    if (text) payload.text = text;
  }
  return payload;
}

export function extractFromFileList(list: FileList | null): SubmitPayload {
  return {
    files: list ? Array.from(list) : [],
    uris: [],
    text: null,
    rejected: [],
  };
}

export type DropVerdict = "accept" | "reject" | "unknown";

/**
 * Judge a drag while it is still in flight. Browsers expose MIME types but not
 * file names during dragover, so this can only reject on certainty.
 */
export function previewDrop(dt: DataTransfer, action: RadialAction): DropVerdict {
  const items = Array.from(dt.items ?? []);
  if (items.length === 0) return "unknown";
  const fileItems = items.filter((i) => i.kind === "file");
  const stringItems = items.filter((i) => i.kind === "string");

  if (fileItems.length > 0) {
    if (action.acceptsKinds === null) return "reject";
    let anyUnknown = false;
    for (const it of fileItems) {
      const kind = classifyFile("", it.type);
      if (kind === "unknown") anyUnknown = true;
      else if (!kindAccepted(action, kind)) return "reject";
    }
    return anyUnknown ? "unknown" : "accept";
  }
  if (stringItems.length > 0) return action.acceptsText ? "accept" : "reject";
  return "unknown";
}

/** Final validation at drop time (names are available now). */
export function validatePayload(
  payload: SubmitPayload,
  action: RadialAction
): { accepted: SubmitPayload; rejected: { name: string; reason: string }[] } {
  const rejected = [...payload.rejected];
  const files: File[] = [];
  for (const f of payload.files) {
    const kind = classifyFile(f.name, f.type);
    if (kindAccepted(action, kind) || kind === "unknown") files.push(f);
    else
      rejected.push({
        name: f.name,
        reason: `“${action.label}” doesn’t accept this type of file`,
      });
  }
  const text = payload.text && action.acceptsText ? payload.text : null;
  if (payload.text && !action.acceptsText && payload.files.length === 0) {
    rejected.push({
      name: "Text",
      reason: `“${action.label}” doesn’t accept text`,
    });
  }
  const uris = action.acceptsKinds === null ? [] : payload.uris;
  return { accepted: { files, uris, text, rejected: [] }, rejected };
}
