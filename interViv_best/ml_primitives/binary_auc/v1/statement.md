Implement `binary_auc(y_true, y_score)`.

The score is the probability that a randomly chosen positive example is
ranked strictly above a randomly chosen negative example, plus half the
probability that they tie.

The result always lies in `[0, 1]`. A ranking that perfectly separates
positives above negatives is `1`. The inverted ranking is `0`. If every
score is identical, the result is `1/2`. A strictly increasing transform
of the scores must not change the value.
