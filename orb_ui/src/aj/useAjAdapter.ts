/**
 * Real AJ adapter.
 *
 * Replaces `useDemoAdapter` when the app runs inside the AJ desktop host.
 * State is pushed from Python (canonical InboxStore); callbacks send intent
 * back over the bridge. There is no local queue, storage or fake progress.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  ActivityItem,
  AjOrbCallbacks,
  ChatMessage,
  ConnectionState,
  OrbCapabilities,
  SubmitPayload,
} from "./types";
import { bridgeAvailable, post, type HostState } from "./bridge";

const DEFAULT_CAPABILITIES: OrbCapabilities = {
  pause: false,
  cancel: false,
  retry: true,
  chat: false,
  clipboard: true,
};

export function useAjAdapter() {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [messages] = useState<ChatMessage[]>([]);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [connectionLabel, setConnectionLabel] = useState<string | undefined>();
  const [capabilities, setCapabilities] = useState<OrbCapabilities>(DEFAULT_CAPABILITIES);
  const [storageRoot, setStorageRoot] = useState<string | undefined>();
  const [storageError, setStorageError] = useState<string | undefined>();
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const initialPosition =
    typeof window !== "undefined" ? window.__AJ_INITIAL_POSITION__ : undefined;

  useEffect(() => {
    if (!bridgeAvailable()) return;
    window.__AJ_SET_STATE = (patch: Partial<HostState>) => {
      if (patch.items) setItems(patch.items as ActivityItem[]);
      if (patch.connection) setConnection(patch.connection);
      if ("connectionLabel" in patch) setConnectionLabel(patch.connectionLabel);
      if (patch.capabilities) {
        setCapabilities((prev) => ({ ...prev, ...patch.capabilities }));
      }
      if ("storageRoot" in patch) setStorageRoot(patch.storageRoot);
      if ("storageError" in patch) setStorageError(patch.storageError);
    };
    post({ type: "ready" });
    return () => {
      delete window.__AJ_SET_STATE;
    };
  }, []);

  const clearFinished = useCallback(() => {
    const finished = new Set(
      items.filter((i) => i.status === "completed" || i.status === "cancelled").map((i) => i.id)
    );
    if (finished.size === 0) return;
    setHidden((prev) => new Set([...prev, ...finished]));
    post({ type: "clearFinished", ids: [...finished] });
  }, [items]);

  const callbacks: AjOrbCallbacks = useMemo(
    () => ({
      onSubmit: async (payload: SubmitPayload, intent) => {
        // External drops carry a host-issued id instead of bytes: Python owns
        // the real file paths and performs the canonical capture.
        const dropRef = payload.uris.find((u) => u.startsWith("ajdrop:"));
        if (dropRef) {
          if (!post({ type: "submitDrop", dropId: dropRef.slice("ajdrop:".length), intent })) {
            throw new Error("AJ host is not reachable.");
          }
          return;
        }
        if (payload.text) {
          if (!post({ type: "captureText", text: payload.text, intent })) {
            throw new Error("AJ host is not reachable.");
          }
          return;
        }
        if (payload.files.length > 0) {
          // The desktop host opens a native picker, so this path only happens
          // in a browser: refuse rather than silently dropping the payload.
          throw new Error("File bytes must be handed to AJ through the desktop host.");
        }
        throw new Error("Nothing to add.");
      },
      onRetry: async (id) => {
        if (!post({ type: "retry", id })) throw new Error("AJ host is not reachable.");
      },
      onClearFinished: clearFinished,
      onPositionChange: (pos) => {
        post({ type: "position", x: Math.round(pos.x), y: Math.round(pos.y) });
      },
      onOpenInbox: () => {
        post({ type: "openInbox" });
      },
      onOpenStorage: () => {
        post({ type: "openStorage" });
      },
      onQuit: () => {
        post({ type: "quit" });
      },
    }),
    [clearFinished]
  );

  const visibleItems = useMemo(
    () => items.filter((i) => !hidden.has(i.id)),
    [items, hidden]
  );

  return {
    items: visibleItems,
    messages,
    connection,
    connectionLabel,
    capabilities,
    callbacks,
    initialPosition,
    storageRoot,
    storageError,
  };
}
