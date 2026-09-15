#!/usr/bin/env bash
# One-time setup: install the builder's Node dependencies and check render tools.
set -euo pipefail
cd "$(dirname "$0")"
command -v node >/dev/null || { echo "setup: node is required" >&2; exit 1; }
npm install --silent --no-audit --no-fund
command -v soffice >/dev/null || [ -x /Applications/LibreOffice.app/Contents/MacOS/soffice ] || echo "setup: warning: LibreOffice not found; preview.sh will not work" >&2
command -v pdftoppm >/dev/null || echo "setup: warning: pdftoppm (poppler) not found; preview.sh will not work" >&2
echo "word-docs ready: node $(node --version), docx $(node -p "require('docx/package.json').version" 2>/dev/null || echo installed)"
