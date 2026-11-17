# Waitlist Hedging and Refund Incentives: Multi-Agent Simulation Study

## Abstract

We study a railway waitlist system in which travellers can book multiple
trains, later release redundant tickets, and learn confirmation probabilities
from experience. The project implements the proposal's traveller utility and
decision rules, a multi-train event simulator, a small type-based equilibrium
benchmark, and controlled policy experiments. Results show that fixed,
independent confirmation beliefs can differ sharply from capacity-coupled
outcomes. A release refund can improve seat use when it causes redundant
waitlisted tickets to be released, but refund payments must be reported as
transfers separately from the railway's stated objective.

## Research questions

1. Do the independent fixed-probability assumptions in Eqs. (2) and (3)
   match outcomes in an interacting waitlist market?
2. Can a refund `beta` induce earlier release of redundant tickets and reduce
   empty berths?
3. What does a tractable type-based equilibrium predict, and where does it
   differ from detailed queue dynamics?

## Model

The multi-train simulator implements:

- per-train berth capacity and capped FIFO waitlists;
- booking, confirmation, refusal, plan changes, releases, chart-time waitlist
  cancellation, and post-chart resale;
- Eq. (1) traveller payoff accounting and Eq. (4) railway welfare accounting;
- Eq. (2) fixed-belief booking choices and Eq. (3) fixed-belief release
  choices;
- repeated private Beta-belief updates from observed ticket outcomes.

All choices that were not specified in the proposal, including discrete time,
same-time event order, FIFO allocation, and probability estimators, are listed
in [DECISIONS.md](DECISIONS.md).

## Main findings

### Fixed probabilities and independence fail under congestion

With a constant Eq. (2) belief of `p_A = p_B = 0.70`, observed confirmation
rates were 1.000 in a light profile, 0.400 in a balanced profile, and 0.143 in
a congested profile. In the balanced profile, observed joint confirmation was
0.400 while the product of marginals was 0.160. Shared capacity and aligned
booking order therefore violate both the fixed-probability and independence
assumptions. Full results: [C2 congestion experiment](results/C2_CONGESTION_EXPERIMENT.md).

### Observed `q1` can change the release decision

In a kept-ticket counterfactual, observed `q1` was 0.4521, versus a fixed
belief of 0.10. With the configured costs, the fixed belief led Eq. (3) to
hold the ticket; the observed rate led it to release. Full results:
[C2 release timing experiment](results/C2_RELEASE_TIMING_EXPERIMENT.md).

### Refunds can improve allocation, but larger refunds are not automatically better

In the controlled refund sweep, `beta=1` triggered release, reduced mean empty
berths from 0.4398 to 0.2603, and increased mean Eq. (4) welfare from 55.4866
to 59.7729. Increasing `beta` to 2 did not increase releases but reduced Eq.
(4) welfare to 59.0332 because Eq. (4) subtracts paid refunds. Refunds remain
separate transfers in traveller accounting. Full results:
[refund policy sweep](results/REFUND_POLICY_SWEEP.md).

The beta=1 allocation effect persists across the tested plan-change rates:
the Eq. (4) improvement was +1.5671 at `eta=0.10`, +4.2863 at `eta=0.25`, and
+6.3696 at `eta=0.50`. Full results:
[eta sensitivity](results/REFUND_ETA_SENSITIVITY.md).

### Type grouping makes equilibrium tractable but misses FIFO inequality

The pure type-based solver checks all profiles of a small set of traveller
types. The supplied example checks 16 profiles and finds three equilibria.
When one equilibrium is replayed in the event simulator, the aggregate A
confirmation rate matches the mean-field value 0.4, yet high-value travellers
receive A with probability 1.0 and price-sensitive travellers with probability
0.0 due to FIFO/input order. The aggregate hides this allocation difference.
Full results: [C3 type equilibrium](results/C3_TYPE_EQUILIBRIUM.md).

### Learning changes booking behavior

In a repeated congested market, agents start with the same 0.80 confirmation
belief. Their mean A belief falls to about 0.52 after private observations;
agents begin making different B-booking choices because their own ticket
histories differ. Full results: [learning experiment](results/LEARNING_EXPERIMENT.md).

## Limitations

The experiments are controlled simulations, not calibrated estimates of a
real railway. The type equilibrium is a static mean-field approximation with
independent confirmations; it does not solve the full dynamic learning and
release game. The learning benchmark does not yet learn `q1` or `q2`, and
resale buyers are not modeled as traveller agents.

## Reproduce

```bash
python3 -m unittest discover -s tests -v
python3 -m waitlist_sim --c2-congestion-experiment --runs 1000 --seed 7
python3 -m waitlist_sim --c2-release-experiment --runs 10000 --seed 7
python3 -m waitlist_sim --equilibrium-config examples/type_equilibrium.json
python3 -m waitlist_sim --refund-policy-sweep --runs 10000 --seed 7
python3 -m waitlist_sim --refund-eta-sensitivity --runs 10000 --seed 7
python3 -m waitlist_sim --learning-experiment --runs 10 --seed 7
```
