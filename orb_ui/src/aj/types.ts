/**
 * AJ ORB — INTEGRATION CONTRACT (presentation <-> AJ application layer)
 *
 * Everything the UI needs from AJ is expressed here as plain data (props) and
 * callbacks. The UI NEVER talks to a backend, database, or filesystem path.
 * Freebuff wires these types to the real AJ inbox backend (see docs/INTEGRATION.md).
 *
 * Nothing in this file names an existing AJ API — these are UI-side interfaces
 * that the adapter layer must implement.
 */

/* ------------------------------------------------------------------ */
/* Activity records (right-click → "Show progress", reference image 3) */
/* ------------------------------------------------------------------ */

export type ActivityStatus =
  | "queued" // accepted, not started
  | "uploading" // in flight (transferredBytes advancing)
  | "paused" // user/host paused
  | "completed"
  | "error"
  | "cancelled";

/** One row in the "Upload States" list. Must be produced from REAL backend events. */
export interface ActivityItem {
  /** Stable unique id assigned by the adapter layer. */
  id: string;
  /** Display name, e.g. "Google-certificate.pdf". */
  name: string;
  /** Optional MIME type, used only to pick the file badge. */
  mimeType?: string;
  /** Total size in bytes, or null if unknown (progress bar becomes indeterminate). */
  sizeBytes: number | null;
  /** Bytes transferred/processed so far (real value from the backend). */
  transferredBytes: number;
  status: ActivityStatus;
  /** Human readable reason when status === "error". */
  errorMessage?: string;
  /** Epoch ms when the item was added (used for ordering, newest first). */
  addedAt: number;
}

/* ------------------------------------------------------------------ */
/* Chat ("Ask a question…") — right-hand card in reference image 3     */
/* ------------------------------------------------------------------ */

export type ChatRole = "user" | "assistant" | "system";
export type ChatDelivery = "sending" | "sent" | "read" | "error";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  /** Plain text. `**bold**` spans are rendered bold. No other markup. */
  text: string;
  createdAt: number;
  /** Only meaningful for role === "user". Drives the "Read" label. */
  delivery?: ChatDelivery;
  errorMessage?: string;
}

/* ------------------------------------------------------------------ */
/* Orb actions (radial menu — reference image 2)                       */
/* ------------------------------------------------------------------ */

/**
 * What the user chose on the radial menu. These ids are UI-level intent hints.
 * The adapter decides what each one means in AJ (see docs/FEATURE_INVENTORY.md
 * for the assumption made for every icon).
 */
export type OrbIntent =
  | "add-file" // document-with-up-arrow icon
  | "recent" // document-with-clock icon      (opens activity panel)
  | "cleanup" // brush icon
  | "analyze" // document-with-magnifier icon
  | "add-text" // text-lines icon
  | "paste-clipboard" // clipboard icon
  | "add-image" // stacked-images icon
  | "add-table"; // table icon

/** Everything dropped / picked / pasted onto the orb, normalised. */
export interface SubmitPayload {
  /** Browser File objects (empty in a GTK port — use `uris` there). */
  files: File[];
  /** `text/uri-list` entries (file:// URIs on GTK/Wayland). */
  uris: string[];
  /** Dropped / typed / pasted plain text, or null. */
  text: string | null;
  /** Things the UI already rejected (folders etc.). Informational. */
  rejected: { name: string; reason: string }[];
}

export type ConnectionState = "connected" | "connecting" | "disconnected";

/** Which controls the host can actually honour. Unsupported controls are hidden/disabled. */
export interface OrbCapabilities {
  pause: boolean;
  cancel: boolean;
  retry: boolean;
  chat: boolean;
  clipboard: boolean;
}

export interface OrbPosition {
  x: number;
  y: number;
}

/**
 * Callbacks the host (AJ application layer) must implement.
 * Any callback may return a Promise; a rejection/throw is caught by the UI and
 * shown as an error toast. Callbacks must NOT block the UI thread.
 */
export interface AjOrbCallbacks {
  /** Files / text submitted via drop, picker, note composer or clipboard. */
  onSubmit: (payload: SubmitPayload, intent: OrbIntent) => void | Promise<void>;
  onCancel?: (itemId: string) => void | Promise<void>;
  onRetry?: (itemId: string) => void | Promise<void>;
  onPause?: (itemId: string) => void | Promise<void>;
  onResume?: (itemId: string) => void | Promise<void>;
  onPauseAll?: () => void | Promise<void>;
  onResumeAll?: () => void | Promise<void>;
  /** Remove completed / cancelled / errored rows from the list. */
  onClearFinished?: () => void | Promise<void>;
  onSendMessage?: (text: string) => void | Promise<void>;
  onRetryMessage?: (messageId: string) => void | Promise<void>;
  /** Called after the user finishes moving/throwing the orb. */
  onPositionChange?: (pos: OrbPosition) => void;
  /** Called when the activity panel opens/closes. */
  onPanelVisibilityChange?: (open: boolean) => void;
  /** Open the inbox viewer / storage folder in the desktop file manager. */
  onOpenInbox?: () => void;
  onOpenStorage?: () => void;
  /** Close the desktop orb host. */
  onQuit?: () => void;
}

export interface AjOrbProps {
  /** Controlled list of activity rows (REAL data from the backend adapter). */
  items: ActivityItem[];
  /** Controlled chat transcript. */
  messages: ChatMessage[];
  /** True while the assistant is producing an answer (shows typing dots). */
  assistantBusy?: boolean;
  connection: ConnectionState;
  /** Optional override for the subtitle under the assistant name. */
  connectionLabel?: string;
  capabilities: OrbCapabilities;
  callbacks: AjOrbCallbacks;
  /** Initial top-left position of the orb in CSS px. Defaults to bottom-right. */
  initialPosition?: OrbPosition;
  /** Orb diameter in CSS px (default 104). Scale with the display scale factor. */
  size?: number;
  /** Assistant display name in the chat header. Default "AJ". */
  assistantName?: string;
}

/* ------------------------------------------------------------------ */
/* Derived visual state                                                */
/* ------------------------------------------------------------------ */

export type OrbVisualState =
  | "idle"
  | "processing"
  | "paused"
  | "error"
  | "success";
