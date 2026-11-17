# Refund Policy Sweep: Effect of `beta`

## Purpose

The proposal describes `beta` as a railway refund intended to encourage
release of redundant tickets. This experiment varies `beta` while holding the
market, traveller beliefs, and Eq. (3) decision rule fixed.

## Controlled profile

- A has one berth. The confirmed A-ticket holder has plan-change probability
  `0.25` at each of times 1 and 2.
- A redundant traveller has a confirmed, better B ticket and an A waitlist
  ticket. A follower waits behind her for A.
- The rule-based traveller believes `q1 = 0.10`, `q2 = 0`, and has
  `epsilon = 1`. Under Eq. (3), `beta = 0` produces no release; `beta >= 1`
  produces a release at time 1 if the A ticket remains waitlisted.
- Chart time is 3. There is no resale. Results use 10,000 runs, seed 7.

## Results

| `beta` | Eq. (3) release? | Mean releases | Mean refunds | Mean empty berths | Mean travellers who travel | Mean traveller payoff | Mean Eq. (4) welfare | Eq. (4) population SD |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | No | 0.0000 | 0.0000 | 0.4398 | 1.5602 | 33.4866 | 55.4866 | 16.3800 |
| 1 | Yes | 0.7397 | 0.7397 | 0.2603 | 1.7397 | 37.9741 | 59.7729 | 13.6343 |
| 2 | Yes | 0.7397 | 1.4794 | 0.2603 | 1.7397 | 38.7138 | 59.0332 | 13.1997 |

## Interpretation

In this profile, the first refund large enough to change the Eq. (3) decision
improves allocation: the follower moves forward in the queue, fewer berths
are empty, and more travellers travel. Increasing `beta` from 1 to 2 does not
change the release rate because the binary release threshold was already met.
It raises traveller payoff through larger transfers, but Eq. (4) welfare falls
because that objective explicitly deducts refunds paid.

This distinction responds to the TA feedback: refunds are shown as transfers
and separately included in the railway's stated objective. The numbers are a
controlled simulation result, not a recommended real-world refund amount.
The population standard deviations describe per-run outcome variability; they
are not confidence intervals for a real-world railway parameter.

## Reproduce

```bash
python3 -m waitlist_sim --refund-policy-sweep --runs 10000 --seed 7
```
