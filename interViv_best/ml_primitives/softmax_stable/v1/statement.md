Implement `softmax(logits)` for a batch of class scores.

Each row is an independent example. Convert the row into a discrete
distribution over classes: every entry is at least zero, and the row
sums to one.

Large positive scores overflow a naive `exp`. Subtract the row maximum
before the exponential so the same input still yields a finite
distribution. Adding a constant to a whole row must not change the
result.

The batch axis is the first axis. Keep that axis vectorized.
