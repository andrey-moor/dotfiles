---
type: regex
target: { source: file, path: notes/access.md }
pattern: '\bwrite access\b[^\n]*\[verified\]|\[verified\][^\n]*\bcan write\b'
flags: i
match: 'not_contains'
---
