# Select a region or a window, then annotate in satty.
#
# writeShellApplication already sets errexit, nounset and pipefail.
region="$(slurp -d)" || exit 0
grim -g "$region" - | satty --filename -
