---
type: regex
target: { source: file, path: lesson/study.md }
pattern: '^## Step \d+:'
flags: m
match: 'not_contains'
---
