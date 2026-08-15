# Metric sanity and reachability

These controls test whether a metric can move under a fixture constructed to trigger it. They are not model-quality results and are not benchmark claims.

| Metric/check | Capability status | Controlled observation |
| --- | --- | --- |
| Unsupported-feedback rate | `VALIDATED_CAPABLE` | No feedback produces `feedback_claim_count=0` and rate `N/A`; one fabricated unsupported statement produces `unsupported_feedback_claim_count=1`, `feedback_claim_count=1`, rate `1.0`. |
| Off-topic detection/reachability | `VALIDATED_CAPABLE` | The lexical prediction path flags the football/pizza response to a database-isolation question as off-topic; detection rate is `1/1`. |
| Off-topic false-positive calculation | `VALIDATED_CAPABLE` | A controlled erroneous off-topic prediction for a relevant isolation answer produces false-positive rate `1/1`. This tests metric calculation, not the scorer. |
| Macro-F1 fraction rendering | `VALIDATED_CAPABLE` | Macro-F1 has no artificial numerator or denominator; reports render `—` in `n/N`. |

The rate definition is now `unsupported_feedback_claims / total_feedback_claims` only when the denominator is greater than zero. Both counts are exposed as `unsupported_feedback_claim_count` and `feedback_claim_count`.

All controls are synthetic repository-local test fixtures. No network, external model, API, or production behavior change is involved.

