---
type: regex
target: { source: file, path: setup-steps.md }
pattern: '^\s*\d+\.\s[^\n]*(,? (and|then|and then) (click|select|choose|type|enter|set|open|go|press)\b)'
flags: im
match: not_contains
---
