Implement `layer_norm(x, eps=1e-5)`.

This is the distinct zero-variance case: unlike min-max scaling, a
constant slice still has to produce a finite vector. Subtract the last-axis
mean, divide by the square root of the last-axis population variance plus
`eps`, and return the same shape.

On a slice whose values actually vary, the output mean is near zero and
the output variance is near one. Adding a constant to a whole slice must
not change the result. Omitting `eps` yields NaN on a constant slice.
