import { extensionOf } from "./format";

export type FileKind =
  | "image"
  | "table"
  | "document"
  | "text"
  | "other"
  /** Neither name nor MIME known (browsers hide names during dragover). */
  | "unknown";

const IMAGE_EXT = new Set([
  "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "tif", "tiff", "heic", "avif", "ico",
]);
const TABLE_EXT = new Set(["csv", "tsv", "xlsx", "xls", "xlsm", "ods", "numbers"]);
const DOC_EXT = new Set([
  "pdf", "doc", "docx", "odt", "rtf", "ppt", "pptx", "odp", "epub", "pages", "key",
]);
const TEXT_EXT = new Set([
  "txt", "md", "markdown", "log", "json", "yaml", "yml", "xml", "html", "htm", "rst", "tex",
]);

const TABLE_MIME = [
  "text/csv",
  "text/tab-separated-values",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml",
  "application/vnd.oasis.opendocument.spreadsheet",
];
const DOC_MIME = [
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml",
  "application/vnd.openxmlformats-officedocument.presentationml",
  "application/vnd.ms-powerpoint",
  "application/vnd.oasis.opendocument.text",
  "application/rtf",
  "application/epub+zip",
];

export function classifyFile(name: string, mime: string): FileKind {
  const ext = extensionOf(name);
  const type = (mime || "").toLowerCase();
  if (!ext && !type) return "unknown";
  if (type.startsWith("image/") || IMAGE_EXT.has(ext)) return "image";
  if (TABLE_MIME.some((m) => type.startsWith(m)) || TABLE_EXT.has(ext)) return "table";
  if (DOC_MIME.some((m) => type.startsWith(m)) || DOC_EXT.has(ext)) return "document";
  if (type.startsWith("text/") || TEXT_EXT.has(ext)) return "text";
  return "other";
}

/** Badge colour/label for the little document icon in the activity list. */
export function badgeFor(name: string, mime?: string): { label: string; color: string } {
  const ext = extensionOf(name);
  const kind = classifyFile(name, mime ?? "");
  const label = (ext || "FILE").slice(0, 4).toUpperCase();
  if (ext === "pdf") return { label: "PDF", color: "#e0245e" };
  switch (kind) {
    case "image":
      return { label, color: "#0ea5a4" };
    case "table":
      return { label, color: "#1f9d55" };
    case "document":
      return { label, color: "#2f6fe4" };
    case "text":
      return { label, color: "#6b7280" };
    default:
      return { label, color: "#7c5cd6" };
  }
}
