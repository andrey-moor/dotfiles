#!/usr/bin/env bash
# Run every skill's script tests. Usage: ./run-tests.sh [skill...]
# Each skill keeps its tests in skills/<name>/tests/run.sh. Tests that need LibreOffice, poppler or the
# diagram-design plugin skip themselves when the tool is missing, so read the skip counts.
set -uo pipefail
cd "$(dirname "$0")/skills"
failed=()
[ $# -gt 0 ] || set -- */tests/run.sh
for arg in "$@"; do
  skill=${arg%%/*}
  runner=$skill/tests/run.sh
  [ -f "$runner" ] || { echo "run-tests: no tests for $skill"; failed+=("$skill"); continue; }
  echo "== $skill"
  if ! bash "$runner"; then failed+=("$skill"); fi
done
if [ ${#failed[@]} -gt 0 ]; then echo "run-tests: failed: ${failed[*]}"; exit 1; fi
echo "run-tests: all passed"
