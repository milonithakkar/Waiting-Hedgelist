# Waitlist Hedging and Confirmation: Multi-Agent Project

The current submission narrative is in [REPORT_DRAFT.md](REPORT_DRAFT.md). All
modeling decisions are in [DECISIONS.md](DECISIONS.md), with alternatives and
rationale in [DECISION_ALTERNATIVES.md](DECISION_ALTERNATIVES.md).

This project studies railway waitlists with a multi-agent simulator. Travellers choose sets of trains to book and when to release redundant tickets; each train has its own berth capacity and waitlist. Because allocations interact through shared capacity, one traveller's confirmation chance depends on the other travellers' choices.

## What we are building

The main deliverable is an experimental simulator, not a production booking system. It will compare:

1. The proposal's independent-probability rules (Eqs. 2–3).
2. A capacity-coupled, multi-train event simulation with waitlists, cancellations, releases, charting, and resale.
3. A compact type-based equilibrium calculation to compare predicted choices with simulated behavior.

We will report traveller outcomes, railway accounting, refunds/transfers, and real social/resource costs separately. A refund is money moving between railway and traveller; it is not by itself a destroyed social resource.

## Checkpoints

- [x] **C0 — Project framing:** define the course deliverable, main comparison, and accounting distinction.
- [x] **C1 — Baseline simulator:** implement traveller types, shared capacity, configurable policies, seeded runs, and transparent outcome metrics.
- [x] **C2 — Proposal-rule comparison:** encode Eqs. 2–3 and demonstrate fixed-belief and independence gaps in controlled interacting simulations.
- [x] **C3 — Type-based equilibrium:** compute a tractable pure type equilibrium and replay it in the event simulator.
- [ ] **C4 — Experiments and report:** initial policy and learning experiments are documented; expand sensitivity analysis and prepare the final course report.

## Initial modeling choices (provisional)

All modeling assumptions and their rationale are recorded in [DECISIONS.md](DECISIONS.md). Proposal-backed rules are separated there from implementation choices that still need validation.

## Run the baseline

Requires Python 3.10+ and uses only the standard library:

```bash
python3 -m waitlist_sim --runs 1000 --seed 7
```

Run a multi-type scenario from JSON with:

```bash
python3 -m waitlist_sim --config examples/two_types.json --policy hedgers_first --runs 1000
```

Available provisional allocation policies are `hedgers_first` and `lottery`. The first prioritizes travellers who hedged; the second ignores hedge choice. They exist to exercise the simulator's policy seam and are not asserted to match the railway mechanism. Use `--help` for options. Output is JSON so experiments can be saved and analyzed reproducibly.

To evaluate proposal Eqs. (2) and (3) on explicit probability/payoff inputs, run:

```bash
python3 -m waitlist_sim --rule-config examples/proposal_rule_cases.json
```

Eq. (2) multiplies `p_k` by the product of non-confirmation probabilities for higher-value held trains, then compares the incremental value over the fallback with the expected unused-ticket cost. Eq. (3) compares release friction `epsilon` with the two cancellation-cost terms and the refund bonus; the bonus is included only when `refund_eligible` is true. The sample numbers are illustrative, not estimates from railway data.

To check fixed confirmation probabilities against the simulator's conditional confirmation rates, supply both assumed probabilities:

```bash
python3 -m waitlist_sim --config examples/two_types.json --runs 1000 \
  --benchmark-hedged-probability 0.75 \
  --benchmark-unhedged-probability 0.25
```

The diagnostic reports the observed-minus-assumed gap for hedged and unhedged travellers in the simple C1 model. Those example probabilities are illustrative inputs only.

The proposal's multi-train process is available through a separate event-simulator config:

```bash
python3 -m waitlist_sim --network-config examples/multi_train_market.json --runs 1000 --seed 7
```

This engine has separate train capacities and waitlist caps, FIFO berth promotion, chart-time waitlist cancellation, per-time-step plan-change hazards, scheduled redundant-ticket release, post-chart resale, and Eq. (4) welfare accounting. The output includes per-train confirmation estimates, observed q1/q2 timing rates among uncensored initially waitlisted tickets, and pairwise joint-versus-independent confirmation diagnostics for travellers who requested both trains. Rates exclude tickets censored by plan changes or voluntary release before their confirmation outcome; they remain conditional on the configured booking/release profile and are not universal probabilities. Booking plans may be supplied directly or generated from Eqs. (2)–(3); the engine does not yet solve the agents' strategic equilibrium.

To let an agent generate its booking set and release schedule from the independent-probability rules, add a `strategy` object with `confirmation_probabilities`, `expected_ticket_costs`, and optional per-train `release_inputs`. See `examples/equation_strategy_market.json`. At a scheduled Eq. (3) release, the engine executes only if that train is still waitlisted and another confirmed train is better. This is the fixed-probability benchmark policy; the event simulator's observed probabilities can differ.

## Accounting conventions

- **Traveller utility:** follows Eq. (1), including the best trip net of fare, unused-ticket costs, release bonuses, and release friction.
- **Refund transfer:** total release bonuses paid to travellers are reported separately.
- **Railway objective:** Eq. (4) is reported as written, including its explicit refund penalty and empty-berth penalty.
- **Resource interpretation:** a refund is a transfer between railway and traveller, not by itself a destroyed social resource. The railway objective's refund penalty is a policy/accounting choice and is kept distinct from the physical empty-berth count.

These are bookkeeping definitions for the model; final definitions should match the proposal's intended objective.

## Checkpoint status

C1 remains available as a simple single-pool baseline. Proposal Eqs. (1)--(3) are encoded in `proposal_rules.py`; Eq. (2) and Eq. (3) can generate agent booking and release actions in a network config. `network.py` provides a first multi-train event simulation plus conditional and joint confirmation diagnostics. Eleven hand-calculated tests pass for the main event and accounting paths. C2 remains open: probabilities and expected ticket costs must be supplied as beliefs for rule-based agents, assumptions need validation against intended railway timing, and agents do not yet learn beliefs. The railway objective (4) is reported per run, including empty berths and refunds paid. See [DECISIONS.md](DECISIONS.md) for test coverage and unresolved assumptions.

The first controlled C2 congestion experiment is implemented and documented in [results/C2_CONGESTION_EXPERIMENT.md](results/C2_CONGESTION_EXPERIMENT.md). It demonstrates that confirmation and joint confirmation vary with congestion under an unchanged fixed-belief Eq. (2) strategy.

The controlled Eq. (3) keep-ticket experiment is in [results/C2_RELEASE_TIMING_EXPERIMENT.md](results/C2_RELEASE_TIMING_EXPERIMENT.md). It estimates `q1`/`q2` from cancellations and shows that replacing a fixed `q1` belief with the observed rate can reverse the release decision.

C3's type-based pure equilibrium benchmark and its event-simulator replay are documented in [results/C3_TYPE_EQUILIBRIUM.md](results/C3_TYPE_EQUILIBRIUM.md). The replay reports type-level rates because aggregate capacity averages can hide FIFO allocation differences.

The first policy sweep is in [results/REFUND_POLICY_SWEEP.md](results/REFUND_POLICY_SWEEP.md). It varies `beta` under Eq. (3), reports refunds separately, and evaluates the stated Eq. (4) railway objective.

The refund effect is also tested across cancellation rates in [results/REFUND_ETA_SENSITIVITY.md](results/REFUND_ETA_SENSITIVITY.md).

A repeated private-belief learning benchmark is documented in [results/LEARNING_EXPERIMENT.md](results/LEARNING_EXPERIMENT.md). It lets agents update Eq. (2) confirmation beliefs from their own outcomes.
