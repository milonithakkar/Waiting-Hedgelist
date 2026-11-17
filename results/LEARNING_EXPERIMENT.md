# Repeated Belief Learning Benchmark

## Purpose

The proposal states that travellers do not know true confirmation chances and
learn them from experience. This benchmark implements that behavior for Eq.
(2) booking decisions.

## Learning rule

Eight agents repeatedly book in the same two-train market. Each keeps a
private Beta posterior for each train, initialized at `Beta(4, 1)` with mean
0.80. In every episode, an agent uses each posterior mean as Eq. (2)'s `p_k`.
For every ticket the agent booked, an ever-confirmed outcome increments alpha;
a chart-cancelled ticket increments beta. Agents see only their own tickets.

Both trains have capacity 3. Train A has higher value, so all agents initially
book A. B is considered as an additional hedge only when the Eq. (2) marginal
benefit exceeds its expected cost.

## 10-episode result, seed 7

| Episode | A bookings | B bookings | Mean A belief before booking | Mean A belief after update | Observed A confirmation |
|---:|---:|---:|---:|---:|---:|
| 1 | 8 | 0 | 0.8000 | 0.7292 | 0.3750 |
| 6 | 8 | 0 | 0.5875 | 0.5682 | 0.3750 |
| 7 | 8 | 5 | 0.5682 | 0.5521 | 0.3750 |
| 10 | 8 | 3 | 0.5268 | 0.5167 | 0.3750 |

Agents who received different A outcomes have different posterior beliefs, so
they begin to make different B-booking decisions even though they started with
the same prior and values.

## Limits

This is an intentionally small learning benchmark. It treats each booked
ticket outcome as an independent posterior observation, does not learn
`q1`/`q2`, and does not yet combine learning with release decisions or the
type-equilibrium solver. It demonstrates the proposal's information-learning
mechanism without claiming a statistically calibrated learning model.

## Reproduce

```bash
python3 -m waitlist_sim --learning-experiment --runs 10 --seed 7
```
