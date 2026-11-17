# C2: Fixed Beliefs Versus Capacity-Coupled Outcomes

## Purpose

This controlled experiment checks the concern in the TA feedback: Eq. (2)
uses fixed, independent confirmation probabilities, while the simulator makes
confirmation outcomes depend on other travellers' bookings.

## Design

All strategic travellers have the same values for two trains and use the same
Eq. (2) strategy with a fixed confirmation belief of `p_A = p_B = 0.70` and
expected ticket cost of `1.0` per train. The rule therefore books both trains.
There are no plan changes, releases, refunds, or resale events. Each train has
the same capacity. The only changes between profiles are capacity and the
number of travellers.

| Profile | Capacity per train | Strategic travellers | Runs |
|---|---:|---:|---:|
| Light | 8 | 6 | 1,000 |
| Balanced | 4 | 10 | 1,000 |
| Congested | 2 | 14 | 1,000 |

The runs are deterministic in this particular experiment because all plan
change and resale probabilities are zero. Repetition is retained so the same
runner can be used once stochastic events are added.

## Results

| Profile | Fixed belief | Observed `p_A` | Observed `p_B` | Observed joint `P(A and B)` | Independent product `p_A p_B` | Joint minus product |
|---|---:|---:|---:|---:|---:|---:|
| Light | 0.700 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| Balanced | 0.700 | 0.400 | 0.400 | 0.400 | 0.160 | 0.240 |
| Congested | 0.700 | 0.143 | 0.143 | 0.143 | 0.020 | 0.122 |

## Interpretation

The same fixed belief is wrong in opposite directions as congestion changes:
it understates confirmation in the light profile and overstates it in the
balanced and congested profiles. This directly demonstrates that a constant
`p_k` cannot represent confirmation without conditioning on the market state.

The trains are not independent in this profile. Each traveller books both
trains at the same time, with the same input-order tie break on both trains.
The early travellers therefore tend to be confirmed on both, so the observed
joint confirmation probability is larger than the product of marginal rates.

These are controlled simulation results, not empirical estimates of railway
behavior. The assumptions that create them, including FIFO queues and input
order for simultaneous bookings, are in [DECISIONS.md](../DECISIONS.md).

## Reproduce

```bash
python3 -m waitlist_sim --c2-congestion-experiment --runs 1000 --seed 7
```

The experiment is implemented in `waitlist_sim/experiments.py`.
