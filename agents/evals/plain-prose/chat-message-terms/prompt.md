---
description: A paste-ready chat message defines the acronyms and names it uses, numbers its questions, and keeps pronouns inside their sentence.
tags: [plain-prose, capability]
max_turns: 8
timeout_seconds: 300
allowed_tools: [Read, Skill]
---

draft a message I can paste into the data platform team's chat. save it to message.md.

context: we're chasing why request IDs are missing from about 2% of partner traffic since last Tuesday. background I know: RDF is the row drop filter that removes duplicate rows before storage, IGW is the ingest gateway that writes the audit log, and PR 4821 is the change that adds request IDs to that audit log.

I need to ask them three things: does RDF run before or after IGW writes the audit log, who owns the westus3-batch deployment now, and has PR 4821 shipped to the canary region yet.
