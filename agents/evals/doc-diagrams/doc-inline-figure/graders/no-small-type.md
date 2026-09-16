---
type: regex
target: { source: file, path: build/export-flow.html }
pattern: 'font-size="(6|7|8|9|10)(px)?"'
match: not_contains
---
