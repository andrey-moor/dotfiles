#!/usr/bin/env bash
# Run the word-docs tests. Layout and PDF tests skip themselves when LibreOffice or poppler is missing.
set -euo pipefail
cd "$(dirname "$0")/.."
node --test "tests/*.test.mjs" "$@"
