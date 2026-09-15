#!/usr/bin/env bash
# Render a .docx to PDF and page images so the result can be inspected.
# Usage: preview.sh file.docx [outdir]
set -euo pipefail
if [ $# -lt 1 ]; then echo "usage: preview.sh file.docx [outdir]" >&2; exit 2; fi
DOCX=$(realpath "$1")
OUTDIR=${2:-$(dirname "$DOCX")/preview}
mkdir -p "$OUTDIR"
SOFFICE=$(command -v soffice || true)
for candidate in "/Applications/LibreOffice.app/Contents/MacOS/soffice" "$HOME/Applications/LibreOffice.app/Contents/MacOS/soffice"; do
  [ -z "$SOFFICE" ] && [ -x "$candidate" ] && SOFFICE="$candidate"
done
[ -n "$SOFFICE" ] || { echo "preview.sh: LibreOffice (soffice) not found" >&2; exit 1; }
command -v pdftoppm >/dev/null || { echo "preview.sh: pdftoppm (poppler) not found" >&2; exit 1; }
"$SOFFICE" --headless --convert-to pdf --outdir "$OUTDIR" "$DOCX" >/dev/null 2>&1
BASE=$(basename "$DOCX"); BASE=${BASE%.[dD][oO][cC][xX]}
PDF="$OUTDIR/$BASE.pdf"
[ -f "$PDF" ] || { echo "preview.sh: PDF conversion failed" >&2; exit 1; }
rm -f "$OUTDIR"/page-*.jpg
pdftoppm -jpeg -r 80 "$PDF" "$OUTDIR/page"
echo "Fonts on this machine substitute for Aptos; check layout and styles, not glyph shapes." >&2
ls "$OUTDIR"/page-*.jpg
