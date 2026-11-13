/**
 * DEMO ADAPTER — NOT PART OF THE AJ INTEGRATION.
 *
 * This file exists only so the UI can be exercised in a browser. It is the
 * place Freebuff REPLACES with an adapter that talks to the real AJ inbox
 * backend (see docs/INTEGRATION.md).
 *
 * What is real here:   transferred bytes = bytes actually read from the File
 *                      the user dropped/picked (File.stream()).
 * What is simulated:   the "transport" is throttled (see harness speed slider)
 *                      and there is no AJ backend, so chat messages cannot be
 *                      answered — they end in the `error` delivery state.
 * No records are pre-seeded: the list starts empty.
 */
import { useCallback, useMemo, useRef, useState } from "react";
import type {
  ActivityItem,
  AjOrbCallbacks,
  ChatMessage,
  ConnectionState,
  OrbCapabilities,
  SubmitPayload,
} from "../aj/types";
import { isFinished } from "../aj/lib/format";

export interface DemoSettings {
  /** Simulated transport speed in KB/s. */
  kbps: number;
  /** Fail the next transfer at ~50 % (to exercise the error state). */
  failNext: boolean;
}

interface Control {
  paused: boolean;
  cancelled: boolean;
  started: boolean;
  resume?: () => void;
}

const CONCURRENCY = 2;
const SLICE = 32 * 1024;
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, Math.max(2, ms)));

let seq = 0;
const uid = (p: string) => `${p}-${Date.now().toString(36)}-${(seq++).toString(36)}`;

export function useDemoAdapter() {
  const [items, setItemsState] = useState<ActivityItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connection, setConnection] = useState<ConnectionState>("connected");
  const [settings, setSettings] = useState<DemoSettings>({ kbps: 256, failNext: false });

  const itemsRef = useRef<ActivityItem[]>([]);
  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const files = useRef(new Map<string, File>());
  const controls = useRef(new Map<string, Control>());
  const running = useRef(0);

  const commit = useCallback((next: ActivityItem[]) => {
    itemsRef.current = next;
    setItemsState(next);
  }, []);

  const patch = useCallback(
    (id: string, p: Partial<ActivityItem>) => {
      commit(itemsRef.current.map((i) => (i.id === id ? { ...i, ...p } : i)));
    },
    [commit]
  );

  const addMessage = useCallback((m: Omit<ChatMessage, "id" | "createdAt">) => {
    setMessages((prev) => [...prev, { ...m, id: uid("msg"), createdAt: Date.now() }]);
  }, []);

  /* ----------------- transfer engine (throttled real reads) ----------------- */
  const pumpRef = useRef<() => void>(() => undefined);

  const transfer = useCallback(
    async (id: string) => {
      const file = files.current.get(id);
      const c = controls.current.get(id);
      if (!file || !c) return;
      const failThis = settingsRef.current.failNext;
      if (failThis) setSettings((s) => ({ ...s, failNext: false }));
      patch(id, { status: "uploading", transferredBytes: 0, errorMessage: undefined });

      /** Waits while paused. Returns false if cancelled meanwhile. */
      const gate = async () => {
        while (c.paused && !c.cancelled) await new Promise<void>((r) => (c.resume = r));
        return !c.cancelled;
      };

      try {
        const reader = file.stream().getReader();
        let sent = 0;
        let lastPaint = 0;
        for (;;) {
          if (!(await gate())) {
            await reader.cancel();
            patch(id, { status: "cancelled" });
            return;
          }
          const { done, value } = await reader.read();
          if (done) break;
          for (let off = 0; off < value.length; off += SLICE) {
            if (!(await gate())) {
              await reader.cancel();
              patch(id, { status: "cancelled" });
              return;
            }
            const n = Math.min(SLICE, value.length - off);
            await sleep((n / (settingsRef.current.kbps * 1024)) * 1000);
            sent += n;
            if (failThis && sent >= file.size * 0.5) {
              throw new Error("Simulated failure requested from the demo harness.");
            }
            const now = performance.now();
            if (now - lastPaint > 60) {
              lastPaint = now;
              patch(id, { transferredBytes: sent });
            }
          }
        }
        patch(id, { status: "completed", transferredBytes: file.size });
        addMessage({
          role: "system",
          text: `**${file.name}** was added successfully. (demo adapter)`,
        });
      } catch (e) {
        patch(id, {
          status: "error",
          errorMessage: e instanceof Error ? e.message : "The file could not be read.",
        });
      }
    },
    [addMessage, patch]
  );

  const pump = useCallback(() => {
    for (const it of itemsRef.current) {
      if (running.current >= CONCURRENCY) return;
      const c = controls.current.get(it.id);
      if (it.status === "queued" && c && !c.started && !c.paused) {
        c.started = true;
        running.current++;
        void transfer(it.id).finally(() => {
          running.current--;
          pumpRef.current();
        });
      }
    }
  }, [transfer]);
  pumpRef.current = pump;

  /* ----------------- AjOrbCallbacks implementation ----------------- */
  const enqueue = useCallback(
    (list: File[]) => {
      const added: ActivityItem[] = list.map((f) => {
        const id = uid("item");
        files.current.set(id, f);
        controls.current.set(id, { paused: false, cancelled: false, started: false });
        return {
          id,
          name: f.name,
          mimeType: f.type || undefined,
          sizeBytes: f.size,
          transferredBytes: 0,
          status: "queued",
          addedAt: Date.now(),
        };
      });
      commit([...itemsRef.current, ...added]);
      pump();
    },
    [commit, pump]
  );

  const callbacks: AjOrbCallbacks = useMemo(
    () => ({
      onSubmit: async (payload: SubmitPayload) => {
        const list = [...payload.files];
        if (payload.text) {
          const label = payload.text.replace(/\s+/g, " ").slice(0, 24);
          list.push(new File([payload.text], `Note – ${label}.txt`, { type: "text/plain" }));
        }
        if (list.length === 0) {
          throw new Error(
            "This payload only contains file URIs. The demo adapter can read File objects only — the GTK adapter resolves URIs."
          );
        }
        enqueue(list);
      },
      onCancel: (id) => {
        const c = controls.current.get(id);
        if (!c) return;
        c.cancelled = true;
        c.resume?.();
        if (!c.started) patch(id, { status: "cancelled" });
      },
      onRetry: (id) => {
        const c = { paused: false, cancelled: false, started: false } as Control;
        controls.current.set(id, c);
        patch(id, { status: "queued", transferredBytes: 0, errorMessage: undefined });
        pump();
      },
      onPause: (id) => {
        const c = controls.current.get(id);
        if (!c) return;
        c.paused = true;
        patch(id, { status: "paused" });
      },
      onResume: (id) => {
        const c = controls.current.get(id);
        if (!c) return;
        c.paused = false;
        if (c.started) {
          patch(id, { status: "uploading" });
          c.resume?.();
        } else {
          patch(id, { status: "queued" });
          pump();
        }
      },
      onPauseAll: () => {
        for (const it of itemsRef.current) {
          if (it.status === "uploading" || it.status === "queued") {
            const c = controls.current.get(it.id);
            if (c) c.paused = true;
            patch(it.id, { status: "paused" });
          }
        }
      },
      onResumeAll: () => {
        for (const it of itemsRef.current) {
          if (it.status !== "paused") continue;
          const c = controls.current.get(it.id);
          if (!c) continue;
          c.paused = false;
          if (c.started) {
            patch(it.id, { status: "uploading" });
            c.resume?.();
          } else {
            patch(it.id, { status: "queued" });
          }
        }
        pump();
      },
      onClearFinished: () => {
        const keep = itemsRef.current.filter((i) => !isFinished(i));
        for (const i of itemsRef.current) {
          if (isFinished(i)) {
            files.current.delete(i.id);
            controls.current.delete(i.id);
          }
        }
        commit(keep);
      },
      onSendMessage: async (text) => {
        const id = uid("msg");
        setMessages((prev) => [
          ...prev,
          { id, role: "user", text, createdAt: Date.now(), delivery: "sending" },
        ]);
        await sleep(350);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === id
              ? {
                  ...m,
                  delivery: "error",
                  errorMessage: "No AJ backend is connected to this demo adapter.",
                }
              : m
          )
        );
      },
      onRetryMessage: async (id) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === id ? { ...m, delivery: "sending", errorMessage: undefined } : m))
        );
        await sleep(350);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === id
              ? { ...m, delivery: "error", errorMessage: "No AJ backend is connected to this demo adapter." }
              : m
          )
        );
      },
    }),
    [commit, enqueue, patch, pump]
  );

  const capabilities: OrbCapabilities = {
    pause: true,
    cancel: true,
    retry: true,
    chat: true,
    clipboard: true,
  };

  return {
    items,
    messages,
    connection,
    setConnection,
    settings,
    setSettings,
    callbacks,
    capabilities,
  };
}
