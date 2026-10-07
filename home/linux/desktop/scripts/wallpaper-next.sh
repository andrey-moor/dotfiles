# Cycle the wallpapers in @DIR@ over awww's IPC. --first sets the first one.
#
# writeShellApplication already sets errexit, nounset and pipefail.
state="${XDG_RUNTIME_DIR:-/tmp}/desktop-wallpaper.idx"

# The store directory holds symlinks, so -type l matters as much as -type f.
mapfile -t files < <(find @DIR@ -maxdepth 1 -type f,l | sort)
[ "${#files[@]}" -gt 0 ] || exit 0

idx=0
if [ "${1:-}" != "--first" ] && [ -f "$state" ]; then
  idx=$(( ($(cat "$state") + 1) % ${#files[@]} ))
fi
echo "$idx" > "$state"

# The oneshot unit is only ordered after the daemon, so wait for its socket.
for _ in 1 2 3 4 5 6 7 8 9 10; do
  awww query >/dev/null 2>&1 && break
  sleep 0.5
done

awww img --transition-type fade --transition-duration 1 "${files[$idx]}"
