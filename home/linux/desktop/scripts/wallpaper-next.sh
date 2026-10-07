# Cycle the wallpapers in @DIR@ over awww's IPC. --first sets the first one.
#
# writeShellApplication already sets errexit, nounset and pipefail.
state="${XDG_RUNTIME_DIR:-/tmp}/desktop-wallpaper.idx"

# The store directory holds symlinks, so -type l matters as much as -type f.
# A user wallpaperDir may hold other files, so only images are candidates.
# Subdirectories are deliberately not scanned.
mapfile -t files < <(find @DIR@ -maxdepth 1 \( -type f -o -type l \) \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' \) | sort)
[ "${#files[@]}" -gt 0 ] || exit 0

idx=0
if [ "${1:-}" != "--first" ] && [ -f "$state" ]; then
  idx=$(( ($(cat "$state") + 1) % ${#files[@]} ))
fi

# The oneshot unit is only ordered after the daemon, so wait for its socket.
# 30 s outlasts one awww restart, whose RestartSec is 10.
for _ in {1..60}; do
  awww query >/dev/null 2>&1 && break
  sleep 0.5
done

awww img --transition-type fade --transition-duration 1 "${files[$idx]}"

# Written only after a successful set, so a failure does not skip a wallpaper.
echo "$idx" > "$state"
