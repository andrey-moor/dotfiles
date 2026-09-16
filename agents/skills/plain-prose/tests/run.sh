#!/usr/bin/env bash
# Run the plain-prose script tests.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -p 'test_*.py' "$@"
