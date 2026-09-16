#!/usr/bin/env bash
# Copy this case's fixture files into the run's empty workspace, so the paths in the prompt exist.
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cp -R "$here/resources" ./resources
