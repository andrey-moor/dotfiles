#!/bin/bash
# Reliable VM text input via prlctl send-key-event
# Uses PS/2 Set 1 scancodes for maximum compatibility
#
# Usage: ./vm-type.sh "text to type"
#        VM=MyVM ./vm-type.sh "text"
#        DELAY=50 SLEEP=0.05 ./vm-type.sh "text"  # adjust speed
#
# See VM-KEYBOARD.md for scancode reference

set -euo pipefail

VM="${VM:-ArchBase-Template}"
TEXT="${1:-}"
DELAY="${DELAY:-30}"       # ms between press/release
SLEEP="${SLEEP:-0.03}"     # seconds between keys

if [[ -z "$TEXT" ]]; then
    echo "Usage: $0 \"text to type\"" >&2
    echo "Env: VM=<name> DELAY=<ms> SLEEP=<sec>" >&2
    exit 1
fi

# PS/2 Set 1 Scancodes
SHIFT=42
CTRL=29
ENTER=28

# Get scancode for lowercase letter or number
get_scancode() {
    case "$1" in
        # Letters (qwerty layout)
        q) echo 16;; w) echo 17;; e) echo 18;; r) echo 19;; t) echo 20;;
        y) echo 21;; u) echo 22;; i) echo 23;; o) echo 24;; p) echo 25;;
        a) echo 30;; s) echo 31;; d) echo 32;; f) echo 33;; g) echo 34;;
        h) echo 35;; j) echo 36;; k) echo 37;; l) echo 38;;
        z) echo 44;; x) echo 45;; c) echo 46;; v) echo 47;; b) echo 48;;
        n) echo 49;; m) echo 50;;
        # Numbers
        1) echo 2;; 2) echo 3;; 3) echo 4;; 4) echo 5;; 5) echo 6;;
        6) echo 7;; 7) echo 8;; 8) echo 9;; 9) echo 10;; 0) echo 11;;
        # Special characters (unshifted)
        ' ') echo 57;;   # space
        '-') echo 12;;   # minus/hyphen
        '=') echo 13;;   # equal
        '[') echo 26;;   # left bracket
        ']') echo 27;;   # right bracket
        ';') echo 39;;   # semicolon
        ',') echo 51;;   # comma
        '.') echo 52;;   # period
        '/') echo 53;;   # slash
        '`') echo 41;;   # grave/backtick
        "\\") echo 43;;  # backslash
        "'") echo 40;;   # single quote
        *) echo "";;
    esac
}

# Check if character needs shift
needs_shift() {
    case "$1" in
        [A-Z]) return 0;;
        '!'|'@'|'#'|'$'|'%'|'^'|'&'|'*'|'('|')') return 0;;
        '_'|'+'|':'|'"'|'<'|'>'|'?'|'|'|'{'|'}'|'~') return 0;;
        *) return 1;;
    esac
}

# Get base scancode for shifted character
get_shifted_scancode() {
    case "$1" in
        # Uppercase letters -> lowercase scancode
        [A-Z])
            lower=$(echo "$1" | tr 'A-Z' 'a-z')
            get_scancode "$lower"
            ;;
        # Shifted number row
        '!') echo 2;;   # Shift+1
        '@') echo 3;;   # Shift+2
        '#') echo 4;;   # Shift+3
        '$') echo 5;;   # Shift+4
        '%') echo 6;;   # Shift+5
        '^') echo 7;;   # Shift+6
        '&') echo 8;;   # Shift+7
        '*') echo 9;;   # Shift+8
        '(') echo 10;;  # Shift+9
        ')') echo 11;;  # Shift+0
        # Shifted special chars
        '_') echo 12;;  # Shift+minus
        '+') echo 13;;  # Shift+equal
        ':') echo 39;;  # Shift+semicolon
        '"') echo 40;;  # Shift+quote
        '<') echo 51;;  # Shift+comma
        '>') echo 52;;  # Shift+period
        '?') echo 53;;  # Shift+slash
        '|') echo 43;;  # Shift+backslash
        '{') echo 26;;  # Shift+[
        '}') echo 27;;  # Shift+]
        '~') echo 41;;  # Shift+grave
        *) echo "";;
    esac
}

# Send a single key with delay
send_key() {
    prlctl send-key-event "$VM" --scancode "$1" --delay "$DELAY"
    sleep "$SLEEP"
}

# Send a shifted key (Shift + key)
send_shifted_key() {
    prlctl send-key-event "$VM" --scancode $SHIFT --event press
    prlctl send-key-event "$VM" --scancode "$1" --delay "$DELAY"
    prlctl send-key-event "$VM" --scancode $SHIFT --event release
    sleep "$SLEEP"
}

# Type each character
for (( i=0; i<${#TEXT}; i++ )); do
    char="${TEXT:$i:1}"

    if needs_shift "$char"; then
        code=$(get_shifted_scancode "$char")
        if [[ -n "$code" ]]; then
            send_shifted_key "$code"
        fi
    else
        code=$(get_scancode "$char")
        if [[ -n "$code" ]]; then
            send_key "$code"
        fi
    fi
done
