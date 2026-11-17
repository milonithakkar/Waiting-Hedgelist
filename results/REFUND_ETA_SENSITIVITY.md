# Refund Incentive Sensitivity to Plan Changes

This extends the refund-policy sweep by varying the plan-change probability
`eta` at each of times 1 and 2. The controlled market and Eq. (3) beliefs are
otherwise unchanged. Results use 10,000 runs with seed 7.

| `eta` per step | Change in empty berths (`beta=1` minus `beta=0`) | Change in travellers who travel | Change in mean Eq. (4) welfare |
|---:|---:|---:|---:|
| 0.10 | -0.0878 | +0.0878 | +1.5671 |
| 0.25 | -0.1795 | +0.1795 | +4.2863 |
| 0.50 | -0.2451 | +0.2451 | +6.3696 |

The refund incentive helps in every tested condition because it removes a
redundant ticket ahead of a follower before a possible berth release. Its
effect becomes larger when plan changes are more likely, since more berth
release opportunities exist. These findings are conditional on the small
controlled profile and its FIFO queue rule; they do not estimate a real
railway elasticity.

Reproduce with:

```bash
python3 -m waitlist_sim --refund-eta-sensitivity --runs 10000 --seed 7
```
