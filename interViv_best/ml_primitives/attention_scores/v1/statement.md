Implement `attention_weights(query, key)`.

For each batch item, score every query vector against every key vector
with a scaled dot product: divide by the square root of the feature
width. Convert those scores into a distribution over keys with a
numerically stable softmax on the last axis.

The last axis of the result must sum to one. Omitting the scale changes
the distribution whenever the feature width is not one. Large scores
must remain finite.
