---
description: UI steps for a new teammate follow the procedure form. One action per step, bold UI labels, and the result stated. Graded by code, because a judge model failed compliant outputs.
tags: [plain-prose, regression]
max_turns: 8
timeout_seconds: 300
allowed_tools: [Read, Skill]
---

can you write up the steps for setting up the nightly export routine in our Scheduler app? it's for a new teammate, save it as setup-steps.md.

from memory: open Scheduler, go to Routines in the left menu and hit New routine, type a name, set the schedule to every day at 02:00 UTC, then the output folder exports/nightly (that folder has to exist already or it errors), click Create routine. after that the routine shows in the Routines list with status Active.
