import type { SubmitPayload } from "../types";

/**
 * Read the system clipboard into a SubmitPayload.
 * Browser reference only: in the GTK port use Gtk.Clipboard
 * (wait_for_text / wait_for_image / wait_for_uris) asynchronously.
 * Throws a user-readable Error when unavailable, denied or empty.
 */
export async function readClipboardPayload(): Promise<SubmitPayload> {
  const payload: SubmitPayload = { files: [], uris: [], text: null, rejected: [] };
  if (!navigator.clipboard) {
    throw new Error("Clipboard access is not available here.");
  }
  try {
    if (navigator.clipboard.read) {
      const entries = await navigator.clipboard.read();
      for (const entry of entries) {
        const imageType = entry.types.find((t) => t.startsWith("image/"));
        if (imageType) {
          const blob = await entry.getType(imageType);
          const ext = imageType.split("/")[1] ?? "png";
          payload.files.push(
            new File([blob], `clipboard-image-${Date.now()}.${ext}`, { type: imageType })
          );
        } else if (entry.types.includes("text/plain")) {
          const blob = await entry.getType("text/plain");
          const text = (await blob.text()).trim();
          if (text) payload.text = text;
        }
      }
    } else {
      const text = (await navigator.clipboard.readText()).trim();
      if (text) payload.text = text;
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === "NotAllowedError") {
      throw new Error("Clipboard permission was denied.");
    }
    throw err instanceof Error ? err : new Error("Could not read the clipboard.");
  }
  if (payload.files.length === 0 && !payload.text) {
    throw new Error("The clipboard is empty.");
  }
  return payload;
}
