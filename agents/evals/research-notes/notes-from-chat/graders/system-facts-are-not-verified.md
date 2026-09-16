---
type: regex
target: { source: file, path: notes/retry-policy.md }
pattern: '^\s*- \[verified\](?![^\n]*\b(Dana|Priya|Marco|nobody|no one)\b)'
flags: im
match: not_contains
---
