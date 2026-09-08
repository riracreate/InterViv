Implement `minmax(x)`.

For each slice along the last axis, map the smallest value to `0` and the
largest value to `1` with an affine stretch. Values in between keep their
order.

A slice whose maximum equals its minimum has no range. Write zeros for
that slice; do not divide by zero and do not emit NaN.

The output has the same shape and dtype as a float64 view of `x`.
