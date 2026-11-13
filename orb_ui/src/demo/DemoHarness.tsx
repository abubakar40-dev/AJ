import { useState } from "react";
import type { ConnectionState, SubmitPayload } from "../aj/types";
import type { DemoSettings } from "./useDemoAdapter";

interface Props {
  settings: DemoSettings;
  onSettings: (s: DemoSettings) => void;
  connection: ConnectionState;
  onConnection: (c: ConnectionState) => void;
  onSubmit: (p: SubmitPayload) => Promise<void>;
  onResetPosition: () => void;
}

const MAKERS: { label: string; name: string; type: string; kb: number }[] = [
  { label: "PDF", name: "Test-document.pdf", type: "application/pdf", kb: 300 },
  { label: "CSV", name: "Test-table.csv", type: "text/csv", kb: 200 },
  { label: "PNG", name: "Test-image.png", type: "image/png", kb: 400 },
];

/**
 * Developer-only panel (NOT part of AJ). Lets reviewers exercise every state
 * without needing real files: generated test files are real File objects that
 * go through exactly the same onSubmit path as dropped files.
 */
export function DemoHarness({
  settings,
  onSettings,
  connection,
  onConnection,
  onSubmit,
  onResetPosition,
}: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="fixed bottom-4 left-4 z-20 text-[12px] text-white">
      {open ? (
        <div className="w-[280px] rounded-2xl bg-black/55 p-4 shadow-2xl ring-1 ring-white/15 backdrop-blur-md">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-[13px] font-semibold">Demo harness</h2>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-md px-2 py-0.5 text-white/70 hover:bg-white/10"
              aria-label="Close demo harness"
            >
              ✕
            </button>
          </div>
          <p className="mb-3 leading-snug text-white/65">
            Browser-only test controls. Not part of AJ. Transfers are throttled reads of real files — there is
            no AJ backend here.
          </p>

          <label className="mb-3 block">
            <span className="mb-1 flex justify-between text-white/80">
              <span>Simulated speed</span>
              <span className="tabular-nums">{settings.kbps} KB/s</span>
            </span>
            <input
              type="range"
              min={32}
              max={2048}
              step={32}
              value={settings.kbps}
              onChange={(e) => onSettings({ ...settings, kbps: Number(e.target.value) })}
              className="w-full accent-cyan-300"
            />
          </label>

          <label className="mb-3 flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.failNext}
              onChange={(e) => onSettings({ ...settings, failNext: e.target.checked })}
              className="accent-cyan-300"
            />
            Fail next transfer at 50%
          </label>

          <label className="mb-3 flex items-center justify-between gap-2">
            <span>Connection</span>
            <select
              value={connection}
              onChange={(e) => onConnection(e.target.value as ConnectionState)}
              className="rounded-md bg-white/15 px-2 py-1 text-white outline-none"
            >
              <option className="text-black" value="connected">connected</option>
              <option className="text-black" value="connecting">connecting</option>
              <option className="text-black" value="disconnected">disconnected</option>
            </select>
          </label>

          <p className="mb-1 text-white/80">Add generated test file</p>
          <div className="mb-3 flex gap-2">
            {MAKERS.map((m) => (
              <button
                key={m.label}
                type="button"
                className="flex-1 rounded-lg bg-white/15 px-2 py-1.5 font-semibold hover:bg-white/25"
                onClick={() =>
                  void onSubmit({
                    files: [new File([new Uint8Array(m.kb * 1024)], m.name, { type: m.type })],
                    uris: [],
                    text: null,
                    rejected: [],
                  })
                }
              >
                {m.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={onResetPosition}
            className="mb-3 w-full rounded-lg bg-white/15 px-2 py-1.5 hover:bg-white/25"
          >
            Reset orb position
          </button>

          <ul className="list-disc space-y-0.5 pl-4 text-white/70">
            <li>Hover the orb → radial menu</li>
            <li>Drag a file onto it → “Release to Select”</li>
            <li>Double-click → move &amp; throw mode</li>
            <li>Right-click → Show progress, pause…</li>
          </ul>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-full bg-black/45 px-3.5 py-2 font-semibold shadow-lg ring-1 ring-white/15 backdrop-blur-md hover:bg-black/60"
        >
          Demo harness
        </button>
      )}
    </div>
  );
}
