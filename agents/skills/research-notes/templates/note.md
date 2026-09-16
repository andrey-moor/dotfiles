# <Subsystem or source name>

source: code:/path/to/repo | web | doc:/path/to/document
scope: <one sentence: what this note covers and what it leaves out>
read: 2026-09-14

## In general

- [web] <claim>. (https://example.com/docs/page , read 2026-09-14)

## In this system

- [verified] <claim>. (path/to/file.py:123)
- [doc] <claim>. (docs/design.md:40)
- [inferred] <claim>. (from path/to/file.py:123 and path/to/other.go:45)
- [thin] <claim>. (<why it is thin>)
- [doc] <claim that spans lines, such as a commit subject and body>. (path/to/commit.txt:12-20)
- [verified] <person> said <what they said> on 2026-09-14. (sources/chat-export.md:14)
- [doc] <what they said, as a fact about the system>. (sources/chat-export.md:14)
- [verified] As of 2026-09-15, <state a live check observed>. (evidence/2026-09-15-access-check.txt:7)

## Terms

- **Term**: definition. (path/to/file.py:10)

## Open questions

- <what you could not find, and where you looked>
- Conflict: <the point>. docs/design.md:40 says <one value>, and path/to/file.py:123 says <another>.
