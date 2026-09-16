#!/usr/bin/env bash
# One-time setup: install the builder's Node dependencies and check the PDF and preview tools.
set -euo pipefail
cd "$(dirname "$0")"
command -v node >/dev/null || { echo "setup: node is required" >&2; exit 1; }
npm install --silent --no-audit --no-fund
command -v soffice >/dev/null || [ -x /Applications/LibreOffice.app/Contents/MacOS/soffice ] || echo "setup: warning: LibreOffice not found; export-pdf.mjs and preview.sh will not work" >&2
command -v pdffonts >/dev/null || echo "setup: warning: pdffonts (poppler) not found; export-pdf.mjs cannot check PDF fonts" >&2
command -v pdftoppm >/dev/null || echo "setup: warning: pdftoppm (poppler) not found; preview.sh will not work" >&2
if [ "$(uname)" = Linux ]; then
  if ! command -v fc-list >/dev/null; then
    echo "setup: warning: fc-list (fontconfig) not found; export-pdf.mjs cannot pick fonts" >&2
  elif ! fc-list : family | grep -qi '^aptos'; then
    echo "setup: note: Aptos is not installed, so PDFs use a similar sans font and line breaks can differ from Word" >&2
  fi
fi
echo "word-docs ready: node $(node --version), docx $(node -p "JSON.parse(require('fs').readFileSync('node_modules/docx/package.json', 'utf8')).version")"
