import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
  type KeyboardEvent,
  type MouseEvent,
} from "react";
import type {
  ActivityStatus,
  AjOrbProps,
  ConnectionState,
  OrbIntent,
  SubmitPayload,
} from "./types";
import { useOrbMotion } from "./hooks/useOrbMotion";
import { deriveOrbState } from "./lib/orbState";
import { isFinished } from "./lib/format";
import { placeBeside } from "./lib/placement";
import { readClipboardPayload } from "./lib/clipboard";
import {
  RADIAL_ACTIONS,
  actionFor,
  extractDrop,
  extractFromFileList,
  previewDrop,
  validatePayload,
} from "./lib/radialActions";
import { post } from "./bridge";
import { OrbBody } from "./components/OrbBody";
import { RadialMenu } from "./components/RadialMenu";
import { ContextMenu, type MenuItem } from "./components/ContextMenu";
import { ProgressPanel } from "./components/ProgressPanel";
import { NoteComposer } from "./components/NoteComposer";
import { Toasts, type ToastData, type ToastKind } from "./components/Toasts";
import {
  IconFileUpload,
  IconMove,
  IconPanel,
  IconPaste,
  IconPause,
  IconPlay,
  IconTrash,
} from "./components/icons";

const hasDragPayload = (e: { dataTransfer: DataTransfer | null }) =>
  !!e.dataTransfer &&
  Array.from(e.dataTransfer.types).some(
    (t) => t === "Files" || t === "text/plain" || t === "text/uri-list"
  );

/**
 * <AjOrb /> — the floating orb, its radial drop menu, right-click menu and the
 * activity panel. Pure presentation + interaction: ALL data comes in through
 * props and ALL side effects leave through `callbacks` (see ./types.ts).
 */
export function AjOrb({
  items,
  messages,
  assistantBusy = false,
  connection,
  connectionLabel,
  capabilities,
  callbacks,
  initialPosition,
  size = 104,
  assistantName = "AJ",
}: AjOrbProps) {
  const cb = useRef(callbacks);
  cb.current = callbacks;

  /* ---------------- UI state ---------------- */
  const [moveMode, setMoveMode] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuMode, setMenuMode] = useState<"hover" | "drag">("hover");
  const [hovered, setHovered] = useState<OrbIntent | null>(null);
  const [rejected, setRejected] = useState<OrbIntent | null>(null);
  const [attention, setAttention] = useState(false);
  const [panelOpen, setPanelOpenState] = useState(false);
  const [ctx, setCtx] = useState<{ x: number; y: number } | null>(null);
  const [noteOpen, setNoteOpen] = useState(false);
  const [toasts, setToasts] = useState<ToastData[]>([]);
  const [acked, setAcked] = useState<Set<string>>(new Set());
  const [flash, setFlash] = useState(false);
  const [submitting, setSubmitting] = useState(0);
  const [vp, setVp] = useState({ w: window.innerWidth, h: window.innerHeight });

  const openTimer = useRef<number | null>(null);
  const closeTimer = useRef<number | null>(null);
  const dragLeaveTimer = useRef<number | null>(null);
  const rejectTimer = useRef<number | null>(null);
  const flashTimer = useRef<number | null>(null);
  const toastId = useRef(1);
  const fileInput = useRef<HTMLInputElement>(null);
  const pickIntent = useRef<OrbIntent>("add-file");
  const dropIntent = useRef<OrbIntent>("add-file");

  const motion = useOrbMotion({
    size,
    initial: initialPosition,
    enabled: moveMode,
    onCommit: (p) => cb.current.onPositionChange?.(p),
  });

  /* ---------------- helpers ---------------- */
  const clearTimers = () => {
    for (const t of [openTimer, closeTimer, dragLeaveTimer]) {
      if (t.current !== null) window.clearTimeout(t.current);
      t.current = null;
    }
  };

  const pushToast = useCallback((kind: ToastKind, title: string, body?: string) => {
    const id = toastId.current++;
    setToasts((t) => [...t.slice(-3), { id, kind, title, body }]);
  }, []);
  const dismissToast = useCallback(
    (id: number) => setToasts((t) => t.filter((x) => x.id !== id)),
    []
  );

  const errText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");

  /** Run a host callback, surfacing any failure as an error toast. */
  const guarded = useCallback(
    async (label: string, fn: () => void | Promise<void>) => {
      try {
        await fn();
      } catch (e) {
        pushToast("error", label, errText(e));
      }
    },
    [pushToast]
  );

  const closeMenu = useCallback(() => {
    clearTimers();
    setMenuOpen(false);
    setHovered(null);
    setRejected(null);
  }, []);

  const setPanelOpen = useCallback((open: boolean) => {
    setPanelOpenState(open);
    cb.current.onPanelVisibilityChange?.(open);
  }, []);

  /** Throws on failure (used where the caller shows inline errors). */
  const submitRaw = useCallback(async (payload: SubmitPayload, intent: OrbIntent) => {
    setSubmitting((n) => n + 1);
    try {
      await cb.current.onSubmit(payload, intent);
    } finally {
      setSubmitting((n) => n - 1);
    }
  }, []);

  const submit = useCallback(
    (payload: SubmitPayload, intent: OrbIntent) =>
      guarded("Couldn’t add to AJ", () => submitRaw(payload, intent)),
    [guarded, submitRaw]
  );

  const flashRejected = useCallback((intent: OrbIntent) => {
    setRejected(intent);
    if (rejectTimer.current !== null) window.clearTimeout(rejectTimer.current);
    rejectTimer.current = window.setTimeout(() => setRejected(null), 700);
  }, []);

  /** Validate + dispatch a payload that came from a drop / picker. */
  const processPayload = useCallback(
    (raw: SubmitPayload, intent: OrbIntent) => {
      const action = actionFor(intent);
      const { accepted, rejected: bad } = validatePayload(raw, action);
      const has = accepted.files.length > 0 || accepted.uris.length > 0 || !!accepted.text;
      if (bad.length > 0) {
        flashRejected(intent);
        const lines = bad.slice(0, 3).map((r) => `${r.name}: ${r.reason}`);
        if (bad.length > 3) lines.push(`+${bad.length - 3} more`);
        pushToast(has ? "warning" : "error", has ? "Some items were skipped" : "Nothing was added", lines.join("\n"));
      } else if (!has) {
        pushToast("warning", "Nothing to add", "The dropped item contained no files or text.");
      }
      if (has) void submit(accepted, intent);
    },
    [flashRejected, pushToast, submit]
  );

  const handleDrop = useCallback(
    (dt: DataTransfer, intent: OrbIntent) => {
      processPayload(extractDrop(dt), intent);
      closeMenu();
    },
    [closeMenu, processPayload]
  );

  const openPicker = useCallback((intent: OrbIntent) => {
    const a = actionFor(intent);
    const el = fileInput.current;
    if (!el || !a.picker) return;
    el.accept = a.picker.accept;
    el.multiple = a.picker.multiple;
    el.value = "";
    pickIntent.current = intent;
    el.click();
  }, []);

  const activate = useCallback(
    (intent: OrbIntent) => {
      closeMenu();
      switch (intent) {
        case "recent":
          setPanelOpen(true);
          break;
        case "add-text":
          setNoteOpen(true);
          break;
        case "paste-clipboard":
          void (async () => {
            try {
              const payload = await readClipboardPayload();
              await submit(payload, "paste-clipboard");
            } catch (e) {
              pushToast("error", "Couldn’t paste", errText(e));
            }
          })();
          break;
        default:
          openPicker(intent);
      }
    },
    [closeMenu, openPicker, pushToast, setPanelOpen, submit]
  );

  /* ---------------- derived state ---------------- */
  const unseenErrorIds = useMemo(
    () => new Set(items.filter((i) => i.status === "error" && !acked.has(i.id)).map((i) => i.id)),
    [items, acked]
  );
  const derived = deriveOrbState({ items, unseenErrorIds, successFlash: flash, submitting: submitting > 0 });

  /* ---------------- effects ---------------- */

  // Viewport tracking.
  useEffect(() => {
    const on = () => setVp({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);

  // Acknowledge errors while the panel is open (the user is looking at them).
  useEffect(() => {
    if (!panelOpen) return;
    const ids = items.filter((i) => i.status === "error").map((i) => i.id);
    setAcked((prev) => (ids.every((id) => prev.has(id)) ? prev : new Set([...prev, ...ids])));
  }, [panelOpen, items]);

  // Event-driven notifications from REAL status transitions.
  const prevStatus = useRef<Map<string, ActivityStatus> | null>(null);
  useEffect(() => {
    const prev = prevStatus.current;
    if (prev) {
      for (const it of items) {
        const p = prev.get(it.id);
        if (!p || p === it.status) continue;
        if (it.status === "completed") {
          pushToast("success", "Added to AJ", it.name);
          setFlash(true);
          if (flashTimer.current !== null) window.clearTimeout(flashTimer.current);
          flashTimer.current = window.setTimeout(() => setFlash(false), 1800);
        } else if (it.status === "error") {
          pushToast("error", `Failed: ${it.name}`, it.errorMessage);
        }
        if (p === "error") {
          setAcked((a) => {
            if (!a.has(it.id)) return a;
            const n = new Set(a);
            n.delete(it.id);
            return n;
          });
        }
      }
    }
    prevStatus.current = new Map(items.map((i) => [i.id, i.status]));
  }, [items, pushToast]);

  // Connection loss notification.
  const prevConn = useRef<ConnectionState | null>(null);
  useEffect(() => {
    if (prevConn.current && prevConn.current !== connection && connection === "disconnected") {
      pushToast("warning", "AJ is not connected", "New items can’t be processed until the connection returns.");
    }
    prevConn.current = connection;
  }, [connection, pushToast]);

  // Window-level: orb "perks up" while a file is dragged anywhere; block browser navigation on stray drops.
  useEffect(() => {
    let depth = 0;
    const files = (e: globalThis.DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes("Files");
    const enter = (e: globalThis.DragEvent) => {
      if (!files(e)) return;
      depth++;
      setAttention(true);
    };
    const leave = (e: globalThis.DragEvent) => {
      if (!files(e)) return;
      depth = Math.max(0, depth - 1);
      if (depth === 0) setAttention(false);
    };
    const over = (e: globalThis.DragEvent) => {
      if (files(e)) e.preventDefault();
    };
    const end = (e: globalThis.DragEvent) => {
      if (files(e)) e.preventDefault();
      depth = 0;
      setAttention(false);
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", end);
    window.addEventListener("dragend", end);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", end);
      window.removeEventListener("dragend", end);
    };
  }, []);

  // Desktop host: real drops and drag hover arrive from GTK (file URIs), not
  // from the browser DataTransfer (which cannot expose host paths).
  useEffect(() => {
    window.__AJ_EXTERNAL_DROP = (payload) => {
      const intent = (payload.intent as OrbIntent) || dropIntent.current || "add-file";
      processPayload(
        { files: [], uris: [`ajdrop:${payload.dropId}`], text: payload.text ?? null, rejected: [] },
        intent
      );
      closeMenu();
    };
    window.__AJ_DRAG_MOVE = (x, y) => {
      const cx = motion.pos.x + size / 2;
      const cy = motion.pos.y + size / 2;
      const dx = x - cx;
      const dy = y - cy;
      const r = Math.hypot(dx, dy);
      clearTimers();
      setMenuMode("drag");
      setMenuOpen(true);
      if (r < 58 || r > 196) {
        setHovered(null);
        return;
      }
      const deg = (Math.atan2(dx, -dy) * 180) / Math.PI;
      const norm = (deg + 360) % 360;
      let best: OrbIntent | null = null;
      let bestDelta = 999;
      for (const a of RADIAL_ACTIONS) {
        const d = Math.abs(((norm - a.angle + 540) % 360) - 180);
        if (d < 22.5 && d < bestDelta) {
          bestDelta = d;
          best = a.intent;
        }
      }
      if (best) dropIntent.current = best;
      setHovered(best);
    };
    window.__AJ_DRAG_LEAVE = () => {
      if (dragLeaveTimer.current !== null) window.clearTimeout(dragLeaveTimer.current);
      dragLeaveTimer.current = window.setTimeout(closeMenu, 160);
    };
    return () => {
      delete window.__AJ_EXTERNAL_DROP;
      delete window.__AJ_DRAG_MOVE;
      delete window.__AJ_DRAG_LEAVE;
    };
  }, [closeMenu, motion.pos.x, motion.pos.y, processPayload, size]);

  // Host-pushed toasts (capture failures, storage problems, rejected items).
  useEffect(() => {
    window.__AJ_TOAST = (t) => pushToast(t.kind, t.title, t.body);
    return () => {
      delete window.__AJ_TOAST;
    };
  }, [pushToast]);

  // Tell the desktop host exactly which screen regions should accept input so
  // the transparent full-screen host passes clicks through everywhere else.
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const regions: { x: number; y: number; w: number; h: number }[] = [];
      const add = (el: Element | null, pad = 0) => {
        if (!el) return;
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) return;
        regions.push({ x: r.left - pad, y: r.top - pad, w: r.width + pad * 2, h: r.height + pad * 2 });
      };
      add(document.querySelector(".aj-orbwrap"), 26);
      add(document.querySelector(".aj-menu[data-open]"), 6);
      add(document.querySelector(".aj-panel"), 6);
      add(document.querySelector(".aj-ctx"), 6);
      add(document.querySelector(".aj-note"), 6);
      add(document.querySelector(".aj-toasts"), 4);
      post({ type: "regions", regions });
    });
    return () => cancelAnimationFrame(frame);
  }, [menuOpen, panelOpen, ctx, noteOpen, toasts, motion.pos.x, motion.pos.y, vp.w, vp.h, size]);

  // Escape: leave move mode → close menu → close panel.
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key !== "Escape" || ctx || noteOpen) return;
      if (moveMode) setMoveMode(false);
      else if (menuOpen) closeMenu();
      else if (panelOpen) setPanelOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeMenu, ctx, menuOpen, moveMode, noteOpen, panelOpen, setPanelOpen]);

  useEffect(() => () => {
    clearTimers();
    for (const t of [rejectTimer, flashTimer]) if (t.current !== null) window.clearTimeout(t.current);
  }, []);

  /* ---------------- orb pointer / drag handlers ---------------- */
  const onPointerEnter = (e: React.PointerEvent) => {
    if (moveMode || e.pointerType === "touch" || motion.dragging) return;
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
    if (menuOpen || openTimer.current !== null) return;
    openTimer.current = window.setTimeout(() => {
      openTimer.current = null;
      setMenuMode("hover");
      setMenuOpen(true);
    }, 140);
  };

  const onPointerLeave = () => {
    if (openTimer.current !== null) {
      window.clearTimeout(openTimer.current);
      openTimer.current = null;
    }
    if (menuOpen && menuMode === "hover") {
      closeTimer.current = window.setTimeout(closeMenu, 260);
    }
  };

  const onOrbClick = () => {
    if (motion.consumeDidDrag() || moveMode) return;
    if (!menuOpen) {
      setMenuMode("hover");
      setMenuOpen(true);
    }
  };

  const onOrbDoubleClick = () => {
    closeMenu();
    setCtx(null);
    setMoveMode((m) => !m);
  };

  const onOrbContextMenu = (e: MouseEvent) => {
    e.preventDefault();
    closeMenu();
    setCtx({ x: e.clientX, y: e.clientY });
  };

  const onOrbKeyDown = (e: KeyboardEvent) => {
    if (e.target !== e.currentTarget) return;
    if (moveMode && e.key.startsWith("Arrow")) {
      e.preventDefault();
      const step = e.shiftKey ? 48 : 12;
      const dx = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
      const dy = e.key === "ArrowUp" ? -step : e.key === "ArrowDown" ? step : 0;
      motion.setPosition({
        x: Math.max(4, Math.min(motion.pos.x + dx, vp.w - size - 4)),
        y: Math.max(4, Math.min(motion.pos.y + dy, vp.h - size - 4)),
      });
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (!moveMode) {
        setMenuMode("hover");
        setMenuOpen(true);
      }
    } else if (e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey)) {
      e.preventDefault();
      setCtx({ x: motion.pos.x + size / 2, y: motion.pos.y + size / 2 });
    }
  };

  const onOrbDragOver = (e: DragEvent) => {
    if (!hasDragPayload(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    clearTimers();
    if (moveMode) return;
    if (!menuOpen || menuMode !== "drag") {
      setMenuMode("drag");
      setMenuOpen(true);
    }
  };

  const onOrbDragLeave = () => {
    if (dragLeaveTimer.current !== null) window.clearTimeout(dragLeaveTimer.current);
    dragLeaveTimer.current = window.setTimeout(closeMenu, 160);
  };

  const onOrbDrop = (e: DragEvent) => {
    if (!hasDragPayload(e)) return;
    e.preventDefault();
    handleDrop(e.dataTransfer, "add-file"); // dropping on the centre = default intent
  };

  const onSegmentDragOver = (e: DragEvent, intent: OrbIntent) => {
    if (!hasDragPayload(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    setHovered(intent);
    setRejected(previewDrop(e.dataTransfer, actionFor(intent)) === "reject" ? intent : null);
  };

  const onSegmentDrop = (e: DragEvent, intent: OrbIntent) => {
    if (!hasDragPayload(e)) return;
    e.preventDefault();
    e.stopPropagation();
    handleDrop(e.dataTransfer, intent);
  };

  /* ---------------- centre text of the radial menu ---------------- */
  let centerText = "Select an action";
  let centerTone: "neutral" | "accent" | "danger" = "neutral";
  if (menuMode === "drag") {
    if (rejected) {
      centerText = "Not accepted";
      centerTone = "danger";
    } else if (hovered) {
      centerText = actionFor(hovered).dropLabel;
      centerTone = "accent";
    } else {
      centerText = "Release to Select";
    }
  } else if (hovered) {
    centerText = actionFor(hovered).label;
  }

  const disabledIntents = new Set<OrbIntent>();
  if (!capabilities.clipboard || !navigator.clipboard) disabledIntents.add("paste-clipboard");

  /* ---------------- context menu ---------------- */
  const runningCount = items.filter((i) => i.status === "uploading" || i.status === "queued").length;
  const finishedCount = items.filter(isFinished).length;
  const resumeMode = derived.anyPaused && !derived.anyRunning;
  const canBulk = capabilities.pause && (resumeMode ? !!callbacks.onResumeAll : !!callbacks.onPauseAll);

  const ctxItems: MenuItem[] = [
    {
      id: "progress",
      label: panelOpen ? "Hide progress" : "Show progress",
      hint: derived.activeCount > 0 ? `${derived.activeCount} active` : undefined,
      icon: <IconPanel size={16} />,
      onSelect: () => setPanelOpen(!panelOpen),
    },
    {
      id: "add",
      label: "Add files…",
      icon: <IconFileUpload size={16} />,
      onSelect: () => openPicker("add-file"),
    },
    ...(callbacks.onOpenInbox
      ? [{
          id: "inbox",
          label: "Open inbox folder",
          icon: <IconPanel size={16} />,
          onSelect: () => cb.current.onOpenInbox?.(),
        }]
      : []),
    ...(callbacks.onOpenStorage
      ? [{
          id: "storage",
          label: "Storage location…",
          icon: <IconPanel size={16} />,
          onSelect: () => cb.current.onOpenStorage?.(),
        }]
      : []),
    {
      id: "paste",
      label: "Paste from clipboard",
      icon: <IconPaste size={16} />,
      disabled: disabledIntents.has("paste-clipboard"),
      onSelect: () => activate("paste-clipboard"),
    },
    {
      id: "bulk",
      label: resumeMode ? "Resume all" : "Pause all",
      icon: resumeMode ? <IconPlay size={16} /> : <IconPause size={16} />,
      dividerBefore: true,
      disabled: !canBulk || (!resumeMode && runningCount === 0),
      onSelect: () =>
        void guarded(resumeMode ? "Couldn’t resume" : "Couldn’t pause", () =>
          resumeMode ? cb.current.onResumeAll?.() : cb.current.onPauseAll?.()
        ),
    },
    {
      id: "clear",
      label: "Clear finished",
      icon: <IconTrash size={16} />,
      disabled: !callbacks.onClearFinished || finishedCount === 0,
      onSelect: () => void guarded("Couldn’t clear", () => cb.current.onClearFinished?.()),
    },
    {
      id: "move",
      label: moveMode ? "Stop moving orb" : "Move orb",
      hint: moveMode ? "Esc" : "Double-click",
      icon: <IconMove size={16} />,
      dividerBefore: true,
      onSelect: () => {
        setMoveMode((m) => !m);
        closeMenu();
      },
    },
    ...(callbacks.onQuit
      ? [{
          id: "quit",
          label: "Quit AJ Orb",
          danger: true,
          dividerBefore: true,
          onSelect: () => cb.current.onQuit?.(),
        }]
      : []),
  ];

  /* ---------------- panel geometry ---------------- */
  const narrow = vp.w < 760;
  const panelW = narrow ? Math.min(vp.w - 24, 440) : 700;
  const panelH = Math.min(narrow ? 580 : 540, vp.h - 24);
  const placed = placeBeside({ x: motion.pos.x, y: motion.pos.y, size }, { w: panelW, h: panelH }, vp);
  const panelLeft = narrow ? (vp.w - panelW) / 2 : placed.left;
  const moving = motion.dragging || motion.flying;

  const orbLabel =
    `AJ Orb. ${derived.activeCount} active transfer${derived.activeCount === 1 ? "" : "s"}. ` +
    "Hover for actions, drop files to add, double-click to move, right-click for options.";

  const noteLeft = Math.max(10, Math.min(motion.pos.x + size / 2 - 150, vp.w - 310));
  const noteTop = motion.pos.y + size / 2 > vp.h / 2 ? Math.max(10, motion.pos.y - 190) : motion.pos.y + size + 16;

  return (
    <div className="aj-root">
      <input
        ref={fileInput}
        type="file"
        multiple
        hidden
        tabIndex={-1}
        aria-hidden="true"
        onChange={(e) => {
          const payload = extractFromFileList(e.target.files);
          if (payload.files.length > 0) processPayload(payload, pickIntent.current);
        }}
      />

      <div
        ref={motion.elRef}
        className="aj-orbwrap"
        style={{ width: size, height: size }}
        role="button"
        tabIndex={0}
        aria-label={orbLabel}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        data-move={moveMode || undefined}
        data-dragging={motion.dragging || undefined}
        onPointerEnter={onPointerEnter}
        onPointerLeave={onPointerLeave}
        onClick={onOrbClick}
        onDoubleClick={onOrbDoubleClick}
        onContextMenu={onOrbContextMenu}
        onKeyDown={onOrbKeyDown}
        onDragEnter={onOrbDragOver}
        onDragOver={onOrbDragOver}
        onDragLeave={onOrbDragLeave}
        onDrop={onOrbDrop}
        {...motion.handlers}
      >
        <RadialMenu
          open={menuOpen && !moveMode}
          mode={menuMode}
          orbSize={size}
          hovered={hovered}
          rejected={rejected}
          disabled={disabledIntents}
          centerText={centerText}
          centerTone={centerTone}
          onHover={setHovered}
          onActivate={activate}
          onSegmentDragOver={onSegmentDragOver}
          onSegmentDragLeave={(i) => {
            setHovered((h) => (h === i ? null : h));
            setRejected((r) => (r === i ? null : r));
          }}
          onSegmentDrop={onSegmentDrop}
        />
        <div className="aj-orbwrap__body">
          <OrbBody
            state={derived.state}
            dragOver={menuOpen && menuMode === "drag"}
            rejected={rejected !== null}
            moveMode={moveMode}
            dragging={motion.dragging}
            menuOpen={menuOpen}
            attention={attention && !menuOpen}
            disconnected={connection === "disconnected"}
            activeCount={derived.activeCount}
            errorCount={derived.unseenErrorCount}
          />
        </div>
        {moveMode && (
          <span
            className="aj-movehint"
            data-flip={motion.pos.y > vp.h - 90 || undefined}
            role="status"
          >
            {motion.dragging ? "Release to throw" : "Drag to move · double-click to finish"}
          </span>
        )}
      </div>

      {panelOpen && (
        <ProgressPanel
          box={{ left: panelLeft, top: placed.top, w: panelW, h: panelH }}
          narrow={narrow}
          hidden={moving}
          orbState={derived.state}
          assistantName={assistantName}
          connection={connection}
          connectionLabel={connectionLabel}
          capabilities={capabilities}
          items={items}
          messages={messages}
          assistantBusy={assistantBusy}
          actions={{
            cancel: callbacks.onCancel
              ? (id) => guarded("Couldn’t cancel", () => cb.current.onCancel?.(id))
              : undefined,
            retry: callbacks.onRetry
              ? (id) => guarded("Couldn’t retry", () => cb.current.onRetry?.(id))
              : undefined,
            pause: callbacks.onPause
              ? (id) => guarded("Couldn’t pause", () => cb.current.onPause?.(id))
              : undefined,
            resume: callbacks.onResume
              ? (id) => guarded("Couldn’t resume", () => cb.current.onResume?.(id))
              : undefined,
          }}
          onClearFinished={
            callbacks.onClearFinished
              ? () => guarded("Couldn’t clear", () => cb.current.onClearFinished?.())
              : undefined
          }
          onSend={
            callbacks.onSendMessage
              ? async (text) => {
                  await cb.current.onSendMessage?.(text); // throws → inline error in the chat card
                }
              : undefined
          }
          onRetryMessage={
            callbacks.onRetryMessage
              ? (id) => guarded("Couldn’t resend", () => cb.current.onRetryMessage?.(id))
              : undefined
          }
          onClose={() => setPanelOpen(false)}
          onDropData={(dt) => handleDrop(dt, "add-file")}
        />
      )}

      {noteOpen && (
        <NoteComposer
          left={noteLeft}
          top={noteTop}
          onClose={() => setNoteOpen(false)}
          onSubmit={(text) =>
            submitRaw({ files: [], uris: [], text, rejected: [] }, "add-text")
          }
        />
      )}

      <Toasts toasts={toasts} onDismiss={dismissToast} orb={{ x: motion.pos.x, y: motion.pos.y, size }} />

      {ctx && <ContextMenu x={ctx.x} y={ctx.y} items={ctxItems} onClose={() => setCtx(null)} />}
    </div>
  );
}

