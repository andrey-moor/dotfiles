---
description: A design doc for a team follows a design-doc outline and is framed for the team, not as a request to the manager who asked for it.
tags: [word-docs, capability]
max_turns: 12
timeout_seconds: 420
allowed_tools: [Read, Glob, Skill]
---

my manager Dana asked me to write a design doc for the team about replacing our nightly export cron with an event-driven pipeline. it goes out as a Word doc. write the Markdown source as build/export-pipeline.md and I'll run the build myself.

facts: the cron job runs for 4 hours and fails about twice a month. finance needs the data by 06:00. the proposal is to publish one event per transaction, consume them with a pool of 8 workers, retry 3 times, then move the message to a dead-letter queue. we considered a bigger batch machine and splitting the job by region. still open: who owns the dead-letter queue.
