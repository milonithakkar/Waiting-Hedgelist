# C2: Eq. (3) Release Belief Versus Observed `q1` and `q2`

## Purpose

Eq. (3) says a redundant waitlisted ticket should be released when the avoided
expected cancellation cost plus refund is greater than the release friction.
Its critical inputs are `q1` (confirmation before chart) and `q2`
(confirmation at chart). This experiment checks whether a fixed belief about
those rates matches the capacity-coupled event model.

## Controlled profile

- Train A has one berth. One holder has the confirmed A ticket.
- The holder has plan-change probability `eta = 0.25` at each of times 1 and 2.
- A second traveller has a confirmed, better B ticket and is waitlisted for A.
  She deliberately keeps the redundant A ticket for this measurement.
- Chart time is 3. No refund, resale, or voluntary release occurs.
- `cW = 1`, `fC = 4`, `F = 10`, and `epsilon = 1`.

This is a keep-ticket counterfactual: it estimates the outcomes Eq. (3) asks
the traveller to weigh before choosing whether to release.

## Result from 10,000 runs, seed 7

| Quantity | Value |
|---|---:|
| Observed `q1`: confirmation before chart | 0.4521 |
| Observed `q2`: confirmation at chart | 0.0000 |
| Chart cancellation rate | 0.5479 |

For comparison, a fixed belief `q1 = 0.10`, `q2 = 0.00` gives Eq. (3) release
gain `0.30`, below friction `1.00`, so the rule says **hold**. Substituting the
observed rates gives release gain `1.3563`, above friction `1.00`, so the rule
says **release**.

## Interpretation

The release rule can change its recommendation when fixed probability beliefs
are replaced by outcomes from the interacting simulator. This is a controlled
demonstration rather than a calibrated railway prediction. The q1/q2
estimates depend on the discrete plan-change timing and FIFO convention
recorded in [DECISIONS.md](../DECISIONS.md).

## Reproduce

```bash
python3 -m waitlist_sim --c2-release-experiment --runs 10000 --seed 7
```
