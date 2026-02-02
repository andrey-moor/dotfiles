#!/bin/bash
# Fast VM text input via prlctl JSON batch mode
# Uses PS/2 Set 1 scancodes for maximum compatibility
#
# Usage: ./prl-type.sh "text to type"
#        VM=MyVM ./prl-type.sh "text"
#        DELAY=50 ./prl-type.sh "text"  # slower, more reliable
#
# Testing:
#   1. Start a VM with a shell prompt visible
#   2. Run: ./prl-type.sh "echo hello"
#   3. Verify with screenshot: prlctl capture <VM> --file /tmp/test.png
#   4. Test shifted chars: ./prl-type.sh "TEST: @#$"
#
# See VM-KEYBOARD.md for scancode reference

set -euo pipefail

VM="${VM:-ArchBase-Template}"
TEXT="${1:-}"
DELAY="${DELAY:-30}"  # ms between press/release

if [[ -z "$TEXT" ]]; then
    echo "Usage: $0 \"text to type\"" >&2
    echo "Env: VM=<name> DELAY=<ms>" >&2
    exit 1
fi

# PS/2 Set 1 Scancodes
SHIFT=42

# Get scancode for character (returns empty if unknown)
get_scancode() {
    case "$1" in
        # Letters (qwerty layout)
        q|Q) echo 16;; w|W) echo 17;; e|E) echo 18;; r|R) echo 19;; t|T) echo 20;;
        y|Y) echo 21;; u|U) echo 22;; i|I) echo 23;; o|O) echo 24;; p|P) echo 25;;
        a|A) echo 30;; s|S) echo 31;; d|D) echo 32;; f|F) echo 33;; g|G) echo 34;;
        h|H) echo 35;; j|J) echo 36;; k|K) echo 37;; l|L) echo 38;;
        z|Z) echo 44;; x|X) echo 45;; c|C) echo 46;; v|V) echo 47;; b|B) echo 48;;
        n|N) echo 49;; m|M) echo 50;;
        # Numbers and their shifted variants
        1|'!') echo 2;; 2|'@') echo 3;; 3|'#') echo 4;; 4|'$') echo 5;; 5|'%') echo 6;;
        6|'^') echo 7;; 7|'&') echo 8;; 8|'*') echo 9;; 9|'(') echo 10;; 0|')') echo 11;;
        # Control characters
        $'\n') echo 28;;         # Enter/Return
        $'\t') echo 15;;         # Tab
        # Special characters
        ' ') echo 57;;           # space
        '-'|'_') echo 12;;       # minus/underscore
        '='|'+') echo 13;;       # equal/plus
        '['|'{') echo 26;;       # brackets
        ']'|'}') echo 27;;
        ';'|':') echo 39;;       # semicolon/colon
        "'"|'"') echo 40;;       # quotes
        ','|'<') echo 51;;       # comma/less
        '.'|'>') echo 52;;       # period/greater
        '/'|'?') echo 53;;       # slash/question
        '`'|'~') echo 41;;       # grave/tilde
        '\') echo 43;;           # backslash
        '|') echo 43;;           # pipe (shifted backslash)
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

# Build JSON array of key events
build_json() {
    local json="["
    local first=true

    for (( i=0; i<${#TEXT}; i++ )); do
        char="${TEXT:$i:1}"
        code=$(get_scancode "$char")

        if [[ -z "$code" ]]; then
            continue  # Skip unknown characters
        fi

        if needs_shift "$char"; then
            # Shift + key sequence
            if [[ "$first" != true ]]; then json+=","; fi
            json+="{\"scancode\":$SHIFT,\"event\":\"press\"}"
            json+=",{\"scancode\":$code,\"delay\":$DELAY}"
            json+=",{\"scancode\":$SHIFT,\"event\":\"release\"}"
            first=false
        else
            # Regular key
            if [[ "$first" != true ]]; then json+=","; fi
            json+="{\"scancode\":$code,\"delay\":$DELAY}"
            first=false
        fi
    done

    json+="]"
    echo "$json"
}

# Build and send JSON
json=$(build_json)
echo "$json" | prlctl send-key-event "$VM" --json
