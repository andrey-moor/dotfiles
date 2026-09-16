---
type: regex
target: { source: file, path: message.md }
pattern: '(4821[^\n]{0,80}(request ID|audit log))|((request ID|audit log)[^\n]{0,80}4821)'
flags: i
---
