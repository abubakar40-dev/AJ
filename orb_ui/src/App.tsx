import { useCallback, useState } from "react";
import { AjOrb } from "./aj/AjOrb";
import type { OrbPosition } from "./aj/types";
import { DemoDesktop } from "./demo/DemoDesktop";
import { DemoHarness } from "./demo/DemoHarness";
import { useDemoAdapter } from "./demo/useDemoAdapter";
import { bridgeAvailable } from "./aj/bridge";
import { useAjAdapter } from "./aj/useAjAdapter";

const POS_KEY = "aj-orb-demo-position";

function loadPosition(): OrbPosition | undefined {
  try {
    const raw = localStorage.getItem(POS_KEY);
    if (!raw) return undefined;
    const p = JSON.parse(raw) as OrbPosition;
    return typeof p.x === "number" && typeof p.y === "number" ? p : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Browser demo shell. In the real AJ app, <AjOrb/> is fed by the AJ adapter
 * instead of `useDemoAdapter` (see docs/INTEGRATION.md).
 */
export default function App() {
  const demo = useDemoAdapter();
  const real = useAjAdapter();

  // Running inside the AJ desktop host (WebKitGTK): authoritative state comes
  // from Python/the canonical InboxStore. The browser demo is only a fallback.
  if (bridgeAvailable()) {
    return (
      <AjOrb
        items={real.items}
        messages={real.messages}
        connection={real.connection}
        connectionLabel={real.connectionLabel}
        capabilities={real.capabilities}
        callbacks={real.callbacks}
        initialPosition={real.initialPosition}
      />
    );
  }
  const [resetKey, setResetKey] = useState(0);

  const callbacks = {
    ...demo.callbacks,
    onPositionChange: (p: OrbPosition) => {
      try {
        localStorage.setItem(POS_KEY, JSON.stringify(p));
      } catch {
        /* storage unavailable: position just isn't persisted */
      }
    },
  };

  const resetPosition = useCallback(() => {
    try {
      localStorage.removeItem(POS_KEY);
    } catch {
      /* ignore */
    }
    setResetKey((k) => k + 1);
  }, []);

  return (
    <>
      <DemoDesktop />
      <p className="pointer-events-none fixed left-1/2 top-5 z-10 -translate-x-1/2 rounded-full bg-black/25 px-4 py-1.5 text-[12px] font-medium text-white/85 backdrop-blur-sm">
        AJ Orb — hover · drop a file · double-click to move · right-click for progress
      </p>
      <AjOrb
        key={resetKey}
        items={demo.items}
        messages={demo.messages}
        connection={demo.connection}
        capabilities={demo.capabilities}
        callbacks={callbacks}
        initialPosition={resetKey === 0 ? loadPosition() : undefined}
      />
      <DemoHarness
        settings={demo.settings}
        onSettings={demo.setSettings}
        connection={demo.connection}
        onConnection={demo.setConnection}
        onSubmit={(p) => demo.callbacks.onSubmit(p, "add-file") as Promise<void>}
        onResetPosition={resetPosition}
      />
    </>
  );
}
