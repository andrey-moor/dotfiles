---
type: regex
target: { source: file, path: lesson/study.md }
pattern: '(^## Q:[\s\S]*){11}'
flags: m
match: 'not_contains'
---
