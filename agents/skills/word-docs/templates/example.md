---
title: Reconciliation Pipeline Design
subtitle: Replacing the nightly batch job with an event-driven pipeline
date: 2026-09-14
status: Draft
toc: true
footer: Company Confidential
---

# Summary

The nightly reconciliation job runs for four hours and fails about twice a month. Each failure delays reconciled data past the SLA. This document proposes an event-driven pipeline that reconciles each transaction within minutes of arrival.

We ask for two engineers for one quarter.

# Background

The job started in 2019 as a single cron task. Transaction volume has grown 6x since then. The job now competes with morning traffic in two regions.

## Current failure modes

| Failure | Frequency | Recovery time |
|---|---|---|
| Upstream write race | 1 per month | 3 hours |
| Timeout at 4 hours | 1 per month | 4 hours |
| Memory pressure | 1 per quarter | 2 hours |

## Constraints

- Finance needs reconciled data by 06:00 local time.
- The ledger service cannot change its write API this year.
- Reconciliation logic must stay in one code path for audit reasons.

# Proposed approach

Each transaction event is published at the point of origin and consumed by a pool of workers. A failed message is retried, then moved to a dead-letter queue. Nothing else is affected.

<!-- A figure goes on its own line; the alt text becomes the caption:
![Event-driven reconciliation pipeline with a dead-letter queue for failed messages](pipeline.png)
-->

The migration has three steps:

1. Run the new pipeline in shadow mode next to the batch job.
   1. Compare outputs daily for two weeks.
   2. Fix any difference before moving on.
2. Cut over one downstream consumer at a time.
3. Retire the cron job.

> Shadow mode is the only step that can slip. Budget three weeks, not two.

Configuration lives in one file:

```yaml
queue: reconciliation-events
workers: 8
retry: 3
```

See the [ledger service runbook](https://example.com/runbook) for the write API details.

<!-- pagebreak -->

# Risks

**Migration stalls.** Each legacy consumer gets a published cut-over date before work starts.

*Capability gaps.* The audit team signs off on the reconciliation-status store before shadow mode begins.
