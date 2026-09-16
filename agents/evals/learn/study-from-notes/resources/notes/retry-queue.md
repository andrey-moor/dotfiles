# Settlement retry queue

source: code:payments/settlement
scope: how a failed settlement message is retried and when it is dead-lettered
read: 2026-09-15

## In this system

- [verified] A settlement message that fails is retried up to 3 times. (settlement/worker.py:88)
- [verified] Attempts wait 30 seconds, then 60, then 120, doubling each time. (settlement/backoff.py:14)
- [verified] After the third failed retry the worker moves the message to the dead-letter queue. (settlement/worker.py:102)
- [verified] Each message carries an attempt counter in its header. (settlement/message.py:41)
- [verified] A replay job moves dead-lettered messages back to the main queue when an operator starts it. (settlement/replay.py:20)
- [doc] The ledger team owns the dead-letter queue. (docs/ownership.md:12)

## Terms

- **Dead-letter queue**: a queue that holds messages the worker gave up on, so they can be inspected or replayed. (settlement/worker.py:100)
- **Backoff**: the wait between attempts, which grows after each failure. (settlement/backoff.py:10)
- **Attempt counter**: a header field that records how many times a message was tried. (settlement/message.py:41)

## Open questions

- Whether replay resets the attempt counter. Searched settlement/replay.py, not found.
