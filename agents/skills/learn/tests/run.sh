#!/usr/bin/env bash
# Run the learn builder tests.
set -euo pipefail
cd "$(dirname "$0")/.."
node --test "tests/*.test.mjs" "$@"
