#!/usr/bin/env bash
# Run the doc-diagrams script tests. Template tests skip when the diagram-design plugin is missing.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -p 'test_*.py' "$@"
