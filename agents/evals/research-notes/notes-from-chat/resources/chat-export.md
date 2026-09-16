# Chat export: payments-platform channel

Exported 2026-09-12 14:05 UTC. One message per block. Line numbers are stable.

[2026-09-08 09:12] Dana Reyes: Retries for the settlement worker are capped at 3 today.
[2026-09-08 09:14] Dana Reyes: After the third failure the message goes to the dead-letter queue.
[2026-09-08 09:20] Priya Natarajan: I think we should raise the cap to 5, most failures clear by the fourth try.
[2026-09-08 09:31] Dana Reyes: I'd rather keep 3 and add a 30 second backoff between attempts.
[2026-09-09 16:02] Priya Natarajan: Agreed on 3 with backoff. I'll open the change.
[2026-09-10 11:45] Priya Natarajan: PR 7731 is up: it adds exponential backoff starting at 30 seconds.
[2026-09-11 08:03] Marco Silva: The dead-letter queue is owned by the ledger team, not us.
[2026-09-11 08:10] Dana Reyes: Marco, can you confirm that in the ownership doc? I thought it was ours.
