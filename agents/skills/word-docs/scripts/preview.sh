#!/usr/bin/env bash
# Render a .docx to page images so the result can be inspected. The PDF comes from export-pdf.mjs, so its
# fonts are the closest this machine has to Word's.
# Usage: preview.sh file.docx [outdir]
# outdir defaults to a new temporary folder, so previews never land next to the document.
set -euo pipefail
if [ $# -lt 1 ]; then echo "usage: preview.sh file.docx [outdir]" >&2; exit 2; fi
DOCX=$1
[ -f "$DOCX" ] || { echo "preview.sh: not found: $DOCX" >&2; exit 2; }
command -v pdftoppm >/dev/null || { echo "preview.sh: pdftoppm (poppler) not found" >&2; exit 1; }
OUTDIR=${2:-$(mktemp -d "${TMPDIR:-/tmp}/word-docs-preview.XXXXXX")}
mkdir -p "$OUTDIR"
BASE=$(basename "$DOCX"); BASE=${BASE%.[dD][oO][cC][xX]}
status=0
node "$(dirname "$0")/export-pdf.mjs" "$DOCX" -o "$OUTDIR/$BASE.pdf" || status=$?
[ -f "$OUTDIR/$BASE.pdf" ] || { echo "preview.sh: PDF export failed" >&2; exit 1; }
rm -f "$OUTDIR"/page-*.jpg
pdftoppm -jpeg -r 80 "$OUTDIR/$BASE.pdf" "$OUTDIR/page"
echo "preview.sh: pages are in $OUTDIR" >&2
ls "$OUTDIR"/page-*.jpg
exit "$status"
