---
description: A procedural guide source uses per-image scales for screenshots, a page break before the appendix, and keeps the README snippet verbatim in a fence.
tags: [word-docs, capability]
max_turns: 12
timeout_seconds: 420
allowed_tools: [Read, Glob, Skill]
---

write the Markdown source for a short Word guide that walks a new teammate through creating the nightly export routine, as build/routine-guide.md. I'll build it.

the screenshots are already in build/: shot-new-routine@1x.png is a normal screenshot at native size, and shot-routine-list@2x.png came from a retina display. use one after the steps that open the form and one at the end.

steps: open Scheduler, choose Routines, choose New routine, enter the name "Nightly export", set the schedule to every day at 02:00 UTC, set the output folder to exports/nightly, choose Create routine. the routine then shows as Active.

put an appendix at the end with this README snippet exactly as it is:

```bash
scheduler routines list --status active
```
