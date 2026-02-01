#!/bin/bash
# VM keyboard input testing script
# Tests both key codes (-k) and scancodes (-s) methods

VM="${VM:-ArchBase-Template}"
DELAY=100

echo "=== Parallels send-key-event Testing ==="
echo "VM: $VM"
echo ""

# Test function using key codes (-k)
test_keycode() {
    local desc="$1"
    local code="$2"
    echo -n "Testing keycode $code ($desc)... "
    prlctl send-key-event "$VM" --key "$code" --delay "$DELAY"
    echo "sent"
    sleep 0.2
}

# Test function using scancodes (-s)
test_scancode() {
    local desc="$1"
    local code="$2"
    echo -n "Testing scancode $code ($desc)... "
    prlctl send-key-event "$VM" --scancode "$code" --delay "$DELAY"
    echo "sent"
    sleep 0.2
}

# Test modifier + key using JSON
test_modifier_json() {
    local desc="$1"
    local mod_code="$2"
    local key_code="$3"
    echo -n "Testing $desc via JSON... "
    echo "[{\"key\":$mod_code,\"event\":\"press\",\"delay\":$DELAY},{\"key\":$key_code,\"delay\":$DELAY},{\"key\":$mod_code,\"event\":\"release\"}]" | prlctl send-key-event "$VM" --json
    echo "sent"
    sleep 0.3
}

case "${1:-help}" in
    letters-keycode)
        echo "=== Testing Letters with Key Codes ==="
        echo "Expected: qwertyuiopasdfghjklzxcvbnm"
        # QWERTY row: Q=24 to P=33
        for code in 24 25 26 27 28 29 30 31 32 33; do
            prlctl send-key-event "$VM" --key "$code" --delay "$DELAY"
            sleep 0.1
        done
        # ASDF row: A=38 to L=46
        for code in 38 39 40 41 42 43 44 45 46; do
            prlctl send-key-event "$VM" --key "$code" --delay "$DELAY"
            sleep 0.1
        done
        # ZXCV row: Z=52 to M=58
        for code in 52 53 54 55 56 57 58; do
            prlctl send-key-event "$VM" --key "$code" --delay "$DELAY"
            sleep 0.1
        done
        echo ""
        echo "Done - check VM screen"
        ;;

    letters-scancode)
        echo "=== Testing Letters with Scancodes (PS/2 Set 1) ==="
        echo "Expected: qwertyuiopasdfghjklzxcvbnm"
        # PS/2 Set 1 scancodes for letters
        # q=16, w=17, e=18, r=19, t=20, y=21, u=22, i=23, o=24, p=25
        for code in 16 17 18 19 20 21 22 23 24 25; do
            prlctl send-key-event "$VM" --scancode "$code" --delay "$DELAY"
            sleep 0.1
        done
        # a=30, s=31, d=32, f=33, g=34, h=35, j=36, k=37, l=38
        for code in 30 31 32 33 34 35 36 37 38; do
            prlctl send-key-event "$VM" --scancode "$code" --delay "$DELAY"
            sleep 0.1
        done
        # z=44, x=45, c=46, v=47, b=48, n=49, m=50
        for code in 44 45 46 47 48 49 50; do
            prlctl send-key-event "$VM" --scancode "$code" --delay "$DELAY"
            sleep 0.1
        done
        echo ""
        echo "Done - check VM screen"
        ;;

    numbers-keycode)
        echo "=== Testing Numbers with Key Codes ==="
        echo "Expected: 1234567890"
        # 1=10, 2=11, ..., 9=18, 0=19
        for code in 10 11 12 13 14 15 16 17 18 19; do
            prlctl send-key-event "$VM" --key "$code" --delay "$DELAY"
            sleep 0.1
        done
        echo ""
        ;;

    numbers-scancode)
        echo "=== Testing Numbers with Scancodes ==="
        echo "Expected: 1234567890"
        # PS/2: 1=2, 2=3, ..., 9=10, 0=11
        for code in 2 3 4 5 6 7 8 9 10 11; do
            prlctl send-key-event "$VM" --scancode "$code" --delay "$DELAY"
            sleep 0.1
        done
        echo ""
        ;;

    special-keycode)
        echo "=== Testing Special Chars with Key Codes ==="
        echo "Expected: space, period, slash, minus, enter"
        test_keycode "space" 65
        test_keycode "period" 60      # . key
        test_keycode "slash" 61       # / key
        test_keycode "minus" 20       # - key
        test_keycode "enter" 36
        ;;

    special-scancode)
        echo "=== Testing Special Chars with Scancodes ==="
        echo "Expected: space, period, slash, minus, enter"
        test_scancode "space" 57
        test_scancode "period" 52
        test_scancode "slash" 53
        test_scancode "minus" 12
        test_scancode "enter" 28
        ;;

    modifiers)
        echo "=== Testing Modifier Keys ==="
        echo "Ctrl+U to clear line, then Ctrl+C"
        echo ""
        echo "Ctrl+U (clear line):"
        test_modifier_json "Ctrl+U" 37 30   # Ctrl=37, U=30 (keycodes)
        sleep 1
        echo "Ctrl+C:"
        test_modifier_json "Ctrl+C" 37 54   # Ctrl=37, C=54 (keycodes)
        ;;

    arrows)
        echo "=== Testing Arrow Keys ==="
        test_keycode "Up" 98
        test_keycode "Down" 104
        test_keycode "Left" 100
        test_keycode "Right" 102
        ;;

    enter)
        echo "=== Testing Enter Key ==="
        echo "Keycode method:"
        test_keycode "Enter" 36
        sleep 0.5
        echo "Scancode method:"
        test_scancode "Enter" 28
        ;;

    json-test)
        echo "=== Testing JSON batch input ==="
        echo "Typing 'test' via JSON..."
        # Using keycodes: t=28, e=26, s=39, t=28
        echo '[{"key":28,"delay":100},{"key":26,"delay":100},{"key":39,"delay":100},{"key":28,"delay":100}]' | prlctl send-key-event "$VM" --json
        echo "Done"
        ;;

    clear)
        echo "=== Clearing line with Ctrl+U ==="
        # Using keycodes via JSON
        echo '[{"key":37,"event":"press","delay":50},{"key":30,"delay":100},{"key":37,"event":"release"}]' | prlctl send-key-event "$VM" --json
        echo "Sent Ctrl+U"
        ;;

    help|*)
        echo "Usage: $0 <test>"
        echo ""
        echo "Tests:"
        echo "  letters-keycode   - Test a-z using Parallels key codes"
        echo "  letters-scancode  - Test a-z using PS/2 scancodes"
        echo "  numbers-keycode   - Test 0-9 using key codes"
        echo "  numbers-scancode  - Test 0-9 using scancodes"
        echo "  special-keycode   - Test special chars with key codes"
        echo "  special-scancode  - Test special chars with scancodes"
        echo "  modifiers         - Test Ctrl+U, Ctrl+C"
        echo "  arrows            - Test arrow keys"
        echo "  enter             - Test Enter key"
        echo "  json-test         - Test JSON batch input"
        echo "  clear             - Send Ctrl+U to clear line"
        echo ""
        echo "Env vars: VM=<name> DELAY=<ms>"
        ;;
esac
