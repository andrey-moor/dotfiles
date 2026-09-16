---
type: regex
target: { source: file, path: notes/retry-policy.md }
pattern: '^\s*- \[doc\][^\n]*\b(Dana|Priya|Marco)\b[^\n]*\b(said|says|wrote|proposed|asked|agreed|announced|confirmed|replied|suggested)\b'
flags: im
match: not_contains
---
