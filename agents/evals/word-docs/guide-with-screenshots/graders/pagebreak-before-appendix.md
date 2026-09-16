---
type: regex
target: { source: file, path: build/routine-guide.md }
pattern: '<!--\s*pagebreak\s*-->\s*\n+#{1,2} [^\n]*appendix'
flags: i
---
