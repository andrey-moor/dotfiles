# Trainer: one training step

source: code:trainer
scope: what happens inside one optimizer step of the trainer
read: 2026-09-15

## In this system

- [verified] Each training step loads one batch of 512 examples. (trainer/loop.py:40)
- [verified] The forward pass computes the loss for the batch. (trainer/loop.py:52)
- [verified] The backward pass computes gradients for every parameter. (trainer/loop.py:58)
- [verified] Gradients are clipped to a global norm of 1.0. (trainer/loop.py:61)
- [verified] The optimizer updates the parameters and increments the step counter. (trainer/loop.py:66)
- [verified] Every 1000 steps the trainer writes a checkpoint. (trainer/loop.py:80)

## Terms

- **Training step**: one optimizer update over one batch. (trainer/loop.py:38)
- **Gradient clipping**: scaling gradients down when their combined norm passes a limit. (trainer/loop.py:60)
- **Checkpoint**: a saved copy of parameters and optimizer state. (trainer/loop.py:78)

## Open questions

- Whether the learning rate schedule changes per step. Not found in trainer/loop.py.
