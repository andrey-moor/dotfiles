# Incident chat export

Exported 2026-09-14 10:00 UTC.

[2026-09-13 02:14] On-call: Settlement worker queue depth passed 50000.
[2026-09-13 02:21] On-call: Paged the ledger team. The dead-letter queue is growing too.
[2026-09-13 02:40] Ledger: A schema change deployed at 01:55 rejects messages with no currency field.
[2026-09-13 03:05] Ledger: Rolled back the schema change.
[2026-09-13 03:30] On-call: Queue depth is back under 1000. Replaying the dead-letter queue now.
[2026-09-13 04:10] On-call: Replay finished. Closing the incident. See the roadmap doc for the Q4 plan to add schema checks.
