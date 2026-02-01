# VM Keyboard Input via prlctl

Documentation for sending keyboard input to Parallels VMs using `prlctl send-key-event`.

## Command Syntax

```bash
prlctl send-key-event <VM_NAME> [options]
```

### Options

| Option | Description |
|--------|-------------|
| `-k, --key <code>` | Parallels virtual key code (X11-style) |
| `-s, --scancode <code>` | PS/2 Set 1 hardware scancode |
| `-e, --event <press\|release>` | Key event type (default: both) |
| `-d, --delay <ms>` | Delay between press and release |
| `-j, --json` | Read JSON array from stdin |

**Recommendation**: Use **scancodes** (`-s`) for reliability.

## PS/2 Set 1 Scancodes

### Letters (lowercase)
```
q=16  w=17  e=18  r=19  t=20  y=21  u=22  i=23  o=24  p=25
a=30  s=31  d=32  f=33  g=34  h=35  j=36  k=37  l=38
z=44  x=45  c=46  v=47  b=48  n=49  m=50
```

### Numbers
```
1=2  2=3  3=4  4=5  5=6  6=7  7=8  8=9  9=10  0=11
```

### Special Characters (unshifted)
```
space=57  minus=12  equal=13  backslash=43  backspace=14
tab=15    bracketL=26  bracketR=27  semicolon=39  quote=40
comma=51  period=52  slash=53  grave=41
```

### Modifier Keys
```
Shift_L=42  Shift_R=54  Ctrl_L=29  Ctrl_R=97  Alt_L=56  Alt_R=100
```

### Control Keys
```
Enter=28  Escape=1  Backspace=14  Tab=15  Space=57
```

### Arrow & Navigation Keys
```
Up=72  Down=80  Left=75  Right=77
Home=71  End=79  PageUp=73  PageDown=81
Insert=82  Delete=83
```

### Function Keys
```
F1=59  F2=60  F3=61  F4=62  F5=63  F6=64
F7=65  F8=66  F9=67  F10=68  F11=87  F12=88
```

## Shifted Characters

Hold Shift (scancode 42), press key, release Shift:

| Char | Shift + Scancode |
|------|------------------|
| A-Z | Shift + letter scancode |
| ! | Shift + 2 (1 key) |
| @ | Shift + 3 |
| # | Shift + 4 |
| $ | Shift + 5 |
| % | Shift + 6 |
| ^ | Shift + 7 |
| & | Shift + 8 |
| * | Shift + 9 |
| ( | Shift + 10 |
| ) | Shift + 11 |
| _ | Shift + 12 (minus) |
| + | Shift + 13 (equal) |
| : | Shift + 39 (semicolon) |
| " | Shift + 40 (quote) |
| < | Shift + 51 (comma) |
| > | Shift + 52 (period) |
| ? | Shift + 53 (slash) |
| \| | Shift + 43 (backslash) |
| { | Shift + 26 (bracketL) |
| } | Shift + 27 (bracketR) |
| ~ | Shift + 41 (grave) |

## Usage Examples

### Simple key press
```bash
# Type 'a' with 100ms delay between press/release
prlctl send-key-event "MyVM" --scancode 30 --delay 100
```

### Modifier combination (Ctrl+U to clear line)
```bash
prlctl send-key-event "MyVM" --scancode 29 --event press   # Ctrl down
prlctl send-key-event "MyVM" --scancode 22 --delay 100     # U press+release
prlctl send-key-event "MyVM" --scancode 29 --event release # Ctrl up
```

### Shifted character (uppercase or symbol)
```bash
prlctl send-key-event "MyVM" --scancode 42 --event press   # Shift down
prlctl send-key-event "MyVM" --scancode 30 --delay 100     # a -> A
prlctl send-key-event "MyVM" --scancode 42 --event release # Shift up
```

### JSON batch input
```bash
echo '[
  {"scancode": 29, "event": "press"},
  {"scancode": 22, "delay": 100},
  {"scancode": 29, "event": "release"}
]' | prlctl send-key-event "MyVM" --json
```

## Timing Recommendations

| Speed | DELAY (ms) | Sleep (sec) | ~Time/100 chars |
|-------|------------|-------------|-----------------|
| Aggressive | 15 | 0.01 | ~60s |
| Fast (default) | 30 | 0.03 | ~110s |
| Medium | 50 | 0.05 | ~160s |
| Safe | 100 | 0.1 | ~200s |

**Note**: Bottleneck is prlctl process startup (~0.5s/call), not delays.

## Troubleshooting

### Key repeat / stuck keys
- Always explicitly release modifier keys
- Use `--delay` instead of separate press/release for regular keys
- Send release event for any stuck key: `--scancode X --event release`

### Characters getting dropped
- Increase delay and sleep values
- Reduce typing speed
- Check VM is not CPU-bound

## References

- [Parallels send-key-event docs](https://docs.parallels.com/parallels-desktop-developers-guide/command-line-interface-utility/manage-virtual-machines-from-cli/general-virtual-machine-management/send-a-keyboard-event-to-a-virtual-machine)
- [List of key codes](https://docs.parallels.com/parallels-desktop-developers-guide/command-line-interface-utility/manage-virtual-machines-from-cli/general-virtual-machine-management/send-a-keyboard-event-to-a-virtual-machine/list-of-parallels-keyboard-key-codes)
