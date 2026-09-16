---
description: A flow figure for a Word document is drawn at the doc-inline width and type sizes, with the profile marker in place.
tags: [doc-diagrams, capability]
max_turns: 24
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
plugins: ["../../..", "../../../.eval-deps/diagram-design"]
---

I need a diagram for a design doc that goes out as a Word file. it should show how an export request flows: the client app calls the API gateway, the gateway hands it to the export service, the export service puts a job on the queue, a worker takes the job, and the worker writes the file to object storage. draw it as build/export-flow.html next to the doc source in build/. I'll render the PNG myself.
