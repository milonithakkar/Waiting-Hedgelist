# Modeling Decision Record

This file records project-scope choices and every modeling choice that could
materially change results. Proposal statements and TA feedback are recorded
separately from implementation assumptions. New assumptions should be added
here before they are treated as part of an experiment.

For alternatives considered and selection rationale for each listed decision,
see [DECISION_ALTERNATIVES.md](DECISION_ALTERNATIVES.md).

## Project scope

| ID | Decision | Basis | Status |
|---|---|---|---|
| P-01 | The main deliverable is an experimental multi-agent simulator and analysis, not a production railway booking system. | User's course context and proposal | Active |
| P-02 | The intended comparison is between independent-probability decision rules and capacity-coupled outcomes, followed by a small-type equilibrium and experiments. | Proposal and TA feedback | Active |
| P-03 | C1's single-capacity hedge simulator is retained only as a simple baseline. The multi-train event model is the main implementation path. | Implementation scope choice | Active |
| P-04 | Traveller type grouping is intended to keep equilibrium computation tractable; the current event simulator still takes individual traveller profiles. | TA feedback; current implementation boundary | Active |
| P-05 | `DECISIONS.md` is the source of truth for modeling choices; new material assumptions should be recorded before being used in reported experiments. | User request | Active |
| P-06 | Current work focuses on implementation and modeling; GitHub/repository setup is out of scope per the user's latest direction. | User request | Active |

## Legacy C1 baseline choices

These choices apply only to `model.py`, not to the main multi-train event
engine:

- A single shared seat capacity is used. Each traveller independently hedges
  with the configured type-level probability.
- `hedgers_first` confirms hedgers before unhedged travellers, with uniform
  random tie-breaking within each group. `lottery` ignores hedge status and
  samples uniformly over all travellers. Both are placeholders rather than
  proposal railway rules.
- The same hedge fee is paid by every traveller who hedges; an unconfirmed
  traveller receives the configured refund. The refund is a transfer and is
  excluded from the C1 resource-cost metric.
- C1 `social_resource_cost` is the sum of configured missed-trip costs. It is a
  baseline metric, distinct from the proposal's Eq. (4) railway objective.

## Proposal-backed model statements

These are taken from the proposal text supplied in the conversation:

- Each traveller may book a set of trains; a request is confirmed if a berth is
  available, waitlisted below the queue cap, and refused otherwise.
- Releasing a confirmed berth sends it to the first traveller in that train's
  waitlist.
- A plan change can cancel all of one traveller's tickets with probability
  `eta`.
- At chart time, remaining waitlisted tickets are cancelled. A berth released
  after chart time is resold with probability `psi`, otherwise left empty.
- Traveller utility is Eq. (1); booking and release rules are Eqs. (2) and (3);
  the railway objective is Eq. (4).
- The railway does not know traveller values; travellers do not know true
  confirmation probabilities or other travellers' values/actions.

## Implementation decisions and assumptions

| ID | Decision | Why / effect | Revisit when |
|---|---|---|---|
| M-01 | Simulation time is discrete and supplied as `time_steps`. A traveller's `eta` hazard is sampled once per configured step while that traveller has an active confirmed or waitlisted ticket. A change is terminal and cancels all of their tickets. | The proposal gives a probability but not a sampling interval. The interval changes cumulative cancellation chance. | Confirm intended hazard interval / continuous-time interpretation. |
| M-02 | Same-time order is: bookings in input order; plan-change draws; scheduled releases; then chart-time waitlist cancellations. | The proposal does not define event order for simultaneous events. At exactly chart time, a released confirmed berth can therefore promote a waiter before the remaining queue is cancelled. | Confirm chart-boundary semantics. |
| M-03 | Within-train waitlists are FIFO; same-time booking ties follow traveller order in the config, then each traveller's train order. | Tie-breaks are unspecified and affect who gets a released berth. | Replace if the railway rule or proposal specifies another order. |
| M-04 | A request is immediately confirmed when `confirmed + resold < capacity`; otherwise it joins the queue if its current length is below `waitlist_cap`; otherwise it is refused. Refused requests are excluded from accepted-ticket confirmation-rate denominators. | Direct operationalization of the proposal's berth / queue / refusal rule. | Revisit if caps count a different set of tickets or confirmed reservations. |
| M-05 | A scheduled release happens only at its configured time and only if another confirmed train has strictly higher `value - fare`. The equation-based release rule is applied only when the target ticket is still waitlisted and redundant. | Makes “redundant” operational and keeps Eq. (3)'s waitlisted-ticket derivation from being applied to a confirmed ticket. | Confirm whether equal surplus counts as redundant and how confirmed redundant tickets should be released. |
| M-06 | Release times are absolute configured times; the engine does not automatically reschedule a release if the ticket becomes redundant later than planned. | Keeps the event policy deterministic and explicit. | Change if `r` means a delay after redundancy rather than a clock time. |
| M-07 | Plan changes and ticket cancellations charge `cW` for a waitlisted ticket and `fC(t)` for a confirmed ticket. A flat confirmed-cancellation fee is used unless an exact-time fee schedule is supplied. Confirmed tickets still held but unused at departure cost the full fare. | Implements the status-specific unused-ticket costs in Eq. (1). | Replace the flat fallback with the proposal's actual fee schedule/data. |
| M-08 | Post-chart resale is sampled independently per confirmed berth released after chart. Resale buyers are not represented as traveller agents; a resold berth is counted as occupied for empty-berth accounting. | Implements `psi` while keeping the first model small. | Add resale agents / fares if the project models current-booking demand. |
| M-09 | At departure, each traveller chooses the confirmed train with greatest `value - fare` if it strictly exceeds the outside option; otherwise they take the outside option. Ties favor the outside option. | Operationalizes `k*` and `max(o_i, v_i,k* - F_k*)`; tie behavior is unspecified. | Confirm intended tie rule. |
| M-10 | Eq. (2) strategy generation considers trains in descending value, with lexical train-name tie-break. Its fallback is the maximum of the outside option and net surplus (`value - fare`) of already selected trains. Expected ticket costs and each fixed `p_k` are supplied as agent beliefs. | Applies the stated equation deterministically; the proposal does not define how beliefs or `E[cost_k]` are estimated. | Validate fallback interpretation and derive belief/cost estimation. |
| M-11 | Eq. (3) uses supplied `q1`, `q2`, cancellation costs, fare, `beta`, and `epsilon`. The `beta` term is included only when the planned release time is at or after the configured refund start. | Implements the equation's refund eligibility assumption. | Confirm `tau_r` and whether other refund terms exist. |
| M-12 | `q1`/`q2` output rates use initially waitlisted tickets that were not censored by a plan-change cancellation or voluntary release before their outcome. `q1` is confirmation strictly before chart; `q2` is confirmation exactly at chart. These are profile-specific observations, not counterfactual probabilities under a forced “keep” action. | Makes the empirical denominator explicit and avoids treating a released ticket as a failed confirmation chance. | For Eq. (3), add a dedicated counterfactual “keep ticket” experiment if needed. |
| M-13 | Per-train confirmation probabilities use accepted requests that were not censored before confirmation could be observed: an ever-confirmed ticket is a success even if later canceled; a ticket released or plan-canceled before confirmation is excluded; chart-time non-confirmation is a failure. Refused requests are excluded. Pairwise diagnostics condition on both accepted, uncensored requests and compare observed joint confirmation with the product of marginals from the same paired observations. | A smoke run showed that counting voluntary releases as failures confounds choices with confirmation chance. This revised estimator avoids that error. | Add conditional breakdown by queue position, type, and booking time. |
| M-14 | Refund bonuses are reported separately. Traveller payoff includes bonus receipts and release friction; Eq. (4) is also reported as written, including its explicit refund penalty. | Addresses TA feedback without silently changing the proposal's railway objective. | Clarify whether Eq. (4)'s refund term is intended as railway cost or social loss. |
| M-15 | Example probabilities, values, costs, and train capacities are illustrative only, not empirical estimates. | Prevents example configs from being mistaken for validated data. | Replace with sourced/calibrated parameters for experiments. |
| M-16 | Seeded Monte Carlo runs are the intended way to summarize stochastic outcomes. | Supports repeatable experiments. | Set final run counts and uncertainty reporting in C4. |
| M-17 | The first C2 comparison uses three controlled congestion profiles. All strategic travellers have identical values, beliefs (`p_A = p_B = 0.70`), strategy, and simultaneous booking time; no plan changes, releases, refunds, or resale occur. Only capacity and traveller count vary. | Isolates the effect of shared capacity and aligned booking order on Eq. (2)'s fixed and independent probability assumptions. | Add heterogeneous traveller types, staggered booking, plan changes, and release behavior after this baseline. |
| M-18 | The Eq. (3) timing experiment estimates `q1` and `q2` in a deliberate keep-ticket counterfactual. One confirmed ticket holder faces `eta = 0.25` at times 1 and 2; the redundant waiter holds her ticket to chart time. | Eq. (3) asks whether keeping a redundant ticket risks later cancellation costs. Measuring a policy that releases would censor the outcome the traveller needs to consider. | Add a policy comparison that evaluates release and keep strategies after estimating beliefs. |
| M-19 | C3 uses a finite pure mean-field booking equilibrium. Each traveller type takes one common booking set; `p_k = min(1, capacity_k / expected demand_k)`; confirmations across trains are independent; ticket costs are supplied expected constants. The solver enumerates all type-action profiles and returns every mutual best response. | This makes equilibrium computation tractable and keeps the approximation visible. | Extend to mixed strategies, type-specific queue position, dynamic releases, and learning only if the course scope requires them. |
| M-20 | C3 replay holds equilibrium actions fixed and disables plan changes, releases, refunds, resale, and unused-ticket costs. It reports aggregate and type-level event-simulator confirmation rates. | Isolates the gap between mean-field type probabilities and FIFO/input-order allocation. In the supplied equilibrium 2, aggregate A rate matches 0.4 while high-value and price-sensitive types receive 1.0 and 0.0, respectively. | Add dynamic equilibrium replay after the static benchmark is analyzed. |
| M-21 | The first refund sweep uses `beta ∈ {0, 1, 2}` with one redundant waitlisted ticket and one follower behind it. The Eq. (3) agent uses fixed beliefs `q1 = 0.10`, `q2 = 0`, and `epsilon = 1`; the holder has `eta = 0.25` at times 1 and 2. | Creates a minimal, reproducible test of the intended release incentive while separately reporting transfers and Eq. (4) welfare. | Add policy sweeps over more types, beliefs, capacities, and refund values for final experiments. |
| M-22 | The learning benchmark gives each individual agent independent `Beta(4,1)` posteriors per train. Posterior means enter Eq. (2); every booked ticket increments alpha if ever confirmed and beta otherwise. Agents observe only their own outcomes. | Implements the proposal's learning-from-experience statement while keeping belief updates interpretable. | Add queue-position/context features and q1/q2 release learning if required. |
| M-23 | Stochastic policy-sweep reports include population standard deviations of per-run traveller payoff and Eq. (4) welfare alongside their means. | Makes Monte Carlo variability visible without presenting controlled simulation dispersion as real-world statistical uncertainty. | Add confidence intervals only when an inferential sampling design is defined. |
| M-24 | The first refund sensitivity analysis varies per-step plan-change probability `eta ∈ {0.10, 0.25, 0.50}` and compares `beta = 0` with `beta = 1`, holding all other controlled refund-sweep conditions fixed. | Tests whether the incentive effect depends on the number of berth-release opportunities. | Expand to capacity, waitlist-cap, and value sensitivity in the final report if needed. |
| M-25 | `REPORT_DRAFT.md` consolidates only controlled simulation results and labels them as such. It does not claim calibration or a solved dynamic equilibrium. | Keeps the course narrative aligned with what the implementation actually supports. | Replace draft wording only after adding any further experiments. |

## Current boundaries

- The rule-based strategy is a benchmark under supplied fixed beliefs. Agents do
  not yet learn from experience or update beliefs.
- The event simulator takes a configured strategy profile; it does not yet
  compute a Nash/Bayesian equilibrium.
- The current `eta` implementation is discrete-time and may imply a different
  cancellation probability than a continuous-time model.
- The event engine has passed an initial hand-calculated regression suite, but
  it has not been calibrated against railway data or an authoritative
  operational specification.

## Next checkpoint

**C2 validation pass — first pass complete:** eleven tests in `tests/test_network.py`
cover immediate confirmation, waitlist cap/refusal, FIFO promotion, chart
cancellation, post-chart resale / no-resale, exact-chart promotion, plan-change
cancellation, time-indexed `fC`, Eqs. (1)--(3), and Eq. (4). They pass. The
documented 10-seed example also runs end-to-end. One diagnostic defect found in
that run was corrected by censoring voluntary releases and plan-change
cancellations from confirmation-probability estimates. The example has too few
accepted cases to support substantive probability conclusions.

**Next:** expand C2 experiments across congested profiles and compare the
fixed beliefs with empirical `p_k`, `q1`, `q2`, and joint probabilities. The
first controlled capacity experiment is documented in
`results/C2_CONGESTION_EXPERIMENT.md`: it shows that observed per-train rates
vary from 1.000 to 0.143 under one fixed 0.700 belief and that joint outcomes
can differ from the independent product. The controlled Eq. (3) experiment in
`results/C2_RELEASE_TIMING_EXPERIMENT.md` finds observed `q1 = 0.4521` versus
a fixed `q1 = 0.10`, reversing the release decision in this profile. Next add
heterogeneous types, then begin the type-based equilibrium in C3.

**C3 first pass complete:** a small-type pure booking-equilibrium solver and
event-simulator replay are implemented. The supplied example finds three
equilibria across 16 profiles. Its replay demonstrates that aggregate
mean-field rates can hide large type-level FIFO disparities. The details are
in `results/C3_TYPE_EQUILIBRIUM.md`.

**C4 first policy experiment complete:** `results/REFUND_POLICY_SWEEP.md`
shows that the first refund level that triggers release improves allocation in
the controlled profile, while a higher refund reduces Eq. (4) welfare through
the objective's refund penalty. This is a demonstration, not a calibrated
recommendation.

**Learning benchmark complete:** `results/LEARNING_EXPERIMENT.md` records a
repeated Eq. (2) setting where private ticket outcomes update traveller beliefs
and produce divergent booking choices after initially identical agents face
congestion.
