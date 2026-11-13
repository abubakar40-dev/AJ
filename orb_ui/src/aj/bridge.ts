/**
 * AJ desktop bridge (WebKitGTK).
 *
 * The UI stays a pure presentation layer: it sends *intent* messages to the
 * Python host and receives authoritative state back. No storage or backend
 * logic lives here.
 */

export interface ActivityItemLike {
  id: string;
  name: string;
  mimeType?: string;
  sizeBytes: number | null;
  transferredBytes: number;
  status: "queued" | "uploading" | "paused" | "completed" | "error" | "cancelled";
  errorMessage?: string;
  addedAt: number;
}

export interface HostState {
  items: ActivityItemLike[];
  connection: "connected" | "connecting" | "disconnected";
  connectionLabel?: string;
  capabilities: {
    pause: boolean;
    cancel: boolean;
    retry: boolean;
    chat: boolean;
    clipboard: boolean;
  };
  storageRoot?: string;
  storageError?: string;
}

export type BridgeMessage =
  | { type: "ready" }
  | { type: "submitDrop"; dropId: string; intent: string }
  | { type: "captureText"; text: string; intent: string }
  | { type: "pick"; intent: string }
  | { type: "paste"; intent: string }
  | { type: "retry"; id: string }
  | { type: "clearFinished"; ids: string[] }
  | { type: "position"; x: number; y: number }
  | { type: "regions"; regions: { x: number; y: number; w: number; h: number }[] }
  | { type: "openInbox" }
  | { type: "openStorage" }
  | { type: "quit" }
  | { type: "log"; level: "info" | "warn" | "error"; message: string };

interface WebkitHandler {
  postMessage: (message: unknown) => void;
}

declare global {
  interface Window {
    webkit?: { messageHandlers?: { aj?: WebkitHandler } };
    __AJ_SET_STATE?: (state: Partial<HostState>) => void;
    __AJ_TOAST?: (toast: { kind: "success" | "error" | "warning" | "info"; title: string; body?: string }) => void;
    __AJ_EXTERNAL_DROP?: (payload: {
      dropId: string;
      uris: string[];
      text: string | null;
      files: { name: string; size: number; mime: string }[];
      intent?: string | null;
    }) => void;
    __AJ_DRAG_MOVE?: (x: number, y: number, types: string[]) => void;
    __AJ_DRAG_LEAVE?: () => void;
    __AJ_INITIAL_STATE__?: Partial<HostState>;
    __AJ_INITIAL_POSITION__?: { x: number; y: number };
  }
}

export function bridgeAvailable(): boolean {
  return typeof window !== "undefined" && !!window.webkit?.messageHandlers?.aj;
}

export function post(message: BridgeMessage): boolean {
  const handler = window.webkit?.messageHandlers?.aj;
  if (!handler) return false;
  try {
    handler.postMessage(message);
    return true;
  } catch {
    return false;
  }
}
