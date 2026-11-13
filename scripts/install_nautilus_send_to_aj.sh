#!/usr/bin/env bash
set -euo pipefail
# Install/uninstall a Nautilus script: right-click file(s) -> Scripts -> Send to AJ Inbox
# Explicit user action required. Uses AJ canonical inbox CLI/config resolution.

AJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/nautilus/scripts"
NAME="Send to AJ Inbox"
TARGET="$DEST/$NAME"
MODE="install"
DRY_RUN=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [--install|--uninstall] [--dry-run] [--dest DIR]
Installs/removes Nautilus script "$NAME" for the current user.
Respects AJ_CONFIG/AJ_INBOX_ROOT at capture time.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --install) MODE=install; shift;;
    --uninstall|--remove) MODE=uninstall; shift;;
    --dry-run) DRY_RUN=1; shift;;
    --dest) DEST="$2"; TARGET="$DEST/$NAME"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

run() { if [ "$DRY_RUN" -eq 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

if [ "$MODE" = "uninstall" ]; then
  if [ -e "$TARGET" ]; then
    run rm -f "$TARGET"
    echo "Removed: $TARGET"
  else
    echo "Not installed: $TARGET"
  fi
  exit 0
fi

run mkdir -p "$DEST"
TMP="$TARGET.tmp.$$"
write_script() {
  cat > "$TMP" <<EOF
#!/usr/bin/env bash
AJ_ROOT="$AJ_ROOT"
PY="\$AJ_ROOT/.venv/bin/python"
if [ ! -x "\$PY" ]; then PY="\$(command -v python3 || echo python3)"; fi
export PYTHONPATH="\$AJ_ROOT\${PYTHONPATH:+:\$PYTHONPATH}"
# Nautilus provides selected paths/URIs (newline-separated). Batch into one call.
items=()
if [ -n "\${NAUTILUS_SCRIPT_SELECTED_FILE_PATHS:-}" ]; then
  while IFS= read -r p; do [ -n "\$p" ] && items+=("\$p"); done <<< "\$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS"
fi
if [ \${#items[@]} -eq 0 ] && [ -n "\${NAUTILUS_SCRIPT_SELECTED_URIS:-}" ]; then
  while IFS= read -r u; do [ -n "\$u" ] && items+=("\$u"); done <<< "\$NAUTILUS_SCRIPT_SELECTED_URIS"
fi
if [ \${#items[@]} -eq 0 ] && [ \$# -gt 0 ]; then
  items=("\$@")
fi
if [ \${#items[@]} -eq 0 ]; then
  notify-send "AJ Inbox" "No files selected" 2>/dev/null || true
  exit 0
fi
"\$PY" "\$AJ_ROOT/scripts/send_to_aj.py" "\${items[@]}"
EOF
  chmod +x "$TMP"
  mv -f "$TMP" "$TARGET"
}

if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] would install Nautilus script: $TARGET"
  echo "[dry-run] AJ_ROOT=$AJ_ROOT"
else
  write_script
  echo "Installed Nautilus script: $TARGET"
fi
echo "In Nautilus: right-click file(s) -> Scripts -> $NAME"
echo "You may need to restart Nautilus (nautilus -q) for it to appear."
echo "Uninstall: bash \"$AJ_ROOT/scripts/install_nautilus_send_to_aj.sh\" --uninstall"
