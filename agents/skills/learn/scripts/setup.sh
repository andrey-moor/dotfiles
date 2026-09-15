#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v node >/dev/null || { echo "setup: node is required" >&2; exit 1; }
npm install --silent --no-audit --no-fund
echo "learn ready: node $(node --version)"
