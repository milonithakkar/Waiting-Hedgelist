# Decision Alternatives and Rationale

Read this alongside [DECISIONS.md](DECISIONS.md). Each entry names the option
currently used, other reasonable options, and why the current option was
chosen. “Proposal-backed” means the decision follows text supplied in the
proposal; the alternatives describe ways it could still be implemented.

## Scope decisions

| ID | Current choice | Other reasonable choices | Why this choice |
|---|---|---|---|
| P-01 | Build an experimental simulator and analysis. | Production booking application; purely theoretical paper; only a toy demonstration. | The proposal and TA feedback ask to compare analytical rules with simulated interacting outcomes. |
| P-02 | Compare fixed rules, the event simulator, and a small-type equilibrium. | Only simulation; only equilibrium analysis; train a policy without analytical comparison. | It directly answers each part of the TA feedback while keeping the course project manageable. |
| P-03 | Keep C1 as a simple baseline and make the multi-train event model primary. | Delete C1; keep only C1; merge both models into one. | C1 remains a useful sanity baseline, but it cannot represent the proposal's multi-train mechanics. |
| P-04 | Use individual profiles in the event model and type groups in the equilibrium model. | Individual equilibrium; type groups in both models; aggregate population only. | Individual simulation preserves queue dynamics; types make enumeration tractable. |
| P-05 | Record material assumptions before reporting experiments. | Record only final assumptions; maintain notes outside the repository; no formal log. | It makes results auditable and satisfies the user's requested review process. |
| P-06 | Keep GitHub/repository work out of scope. | Create a repository; commit locally; use a private remote. | The user explicitly redirected effort to implementation. |

## Baseline C1 decisions

| ID | Current choice | Other reasonable choices | Why this choice |
|---|---|---|---|
| C1-01 | One shared capacity with type-level independent hedge probabilities. | Per-train capacity; strategic hedge choice; real booking data. | It is a deliberately minimal baseline used before the proposal's full dynamics were implemented. |
| C1-02 | `hedgers_first` and uniform lottery placeholder policies. | FIFO; value-priority; revenue-maximizing allocation; actual railway policy. | These give simple contrasting baselines and are explicitly not claimed to be proposal rules. |
| C1-03 | Treat refunds as transfers, excluding them from C1 resource cost. | Count refunds as social loss; ignore refunds; include administrative cost. | It responds to TA feedback that money moving from railway to traveller is not itself destroyed welfare. |

## Event simulator and accounting decisions

| ID | Current choice | Other reasonable choices | Why this choice |
|---|---|---|
| M-01 | Discrete time; sample `eta` once per configured active-ticket time step. | Continuous-time hazard; one cancellation draw for the whole trip; time-varying hazard. | The proposal gives `eta` but no time unit. Discrete steps make events reproducible and testable. |
| M-02 | Process bookings, plan changes, releases, then chart cancellation at a common time. | Chart first; releases before plan changes; random ordering; continuous asynchronous events. | This gives a deterministic, documented boundary rule. It lets a chart-time release promote a waiter before chart cleanup. |
| M-03 | FIFO waitlists; config input order breaks simultaneous bookings. | Random priority; booking timestamp with random ties; value or fare priority. | The proposal says “first traveller” for a released berth and does not define ties. FIFO is the closest direct reading. |
| M-04 | Confirm if berth is free, otherwise waitlist below cap, otherwise refuse. | Overbook; reserve part of capacity; allow later booking after chart. | It directly operationalizes the proposal's stated booking rule. |
| M-05 | Release only at planned time, only if another confirmed ticket has strictly higher net value; Eq. (3) release is waitlisted-only. | Release whenever another ticket confirms; allow equal-value release; apply Eq. (3) to confirmed tickets; optimize release continuously. | It makes “redundant” concrete and respects that Eq. (3) is derived for a waitlisted ticket. |
| M-06 | Release times are fixed clock times. | Delay after redundancy; optimal stopping; re-evaluate every time step. | The proposal supplies a release time `r`; fixed times keep the first policy explicit. |
| M-07 | Charge `cW` for waitlist cancellation, `fC(t)` for confirmed cancellation, full fare for unused held confirmed tickets. | No cancellation costs; fixed cost for every status; refund netted directly into cost. | This follows Eq. (1)'s stated status-specific cost structure. |
| M-08 | Independently resell post-chart released berth with probability `psi`; resale buyer is not an agent. | Always resell; model stochastic demand agents; leave berth empty. | It directly implements `psi` while avoiding an additional demand-side model. |
| M-09 | Choose the confirmed train with highest `value - fare`; ties choose outside option. | Choose highest raw value; random ties; choose a train on ties. | It implements the net-surplus term in Eq. (1); the tie rule is conservative and explicit. |
| M-10 | Build Eq. (2) strategies by descending value, with net-surplus fallback and supplied beliefs/costs. | Rank by net value; use outside option only as fallback; solve globally across all subsets; learn costs. | The proposal says order by value; supplied beliefs make the independent-rule benchmark separable from learning. |
| M-11 | Include `beta` in Eq. (3) only for releases at/after refund start. | Always pay it; pay only before cutoff; make it status-dependent. | This follows the supplied condition that eligible releases earn the refund. |
| M-12 | Estimate `q1/q2` on uncensored initially waitlisted tickets. | Treat release/plan-change as failures; include all tickets; use a forced keep counterfactual only. | It avoids conflating a traveller's voluntary action with a confirmation outcome. The dedicated keep-ticket experiment supplies the counterfactual. |
| M-13 | Estimate confirmation on accepted, uncensored tickets; chart non-confirmation is failure. | Count all requests; count only completed trips; count voluntary releases as failures. | This measures the chance relevant to the decision rule without censoring bias from earlier cancellation or release. |
| M-14 | Report refunds separately and also subtract them in Eq. (4). | Treat them only as transfers; treat them only as railway costs; add administrative cost. | The separate reporting addresses TA feedback, while subtracting them in Eq. (4) follows the proposal exactly. |
| M-15 | Use illustrative example parameters. | Calibrate with real railway data; elicit expert values; use synthetic random draws. | No data source was provided; examples make mechanics executable without claiming empirical validity. |
| M-16 | Use seeded Monte Carlo summaries. | One deterministic trace; unseeded runs; analytical expectation only. | Seeds make results reproducible while Monte Carlo covers stochastic cancellations and resale. |

## Experiment decisions

| ID | Current choice | Other reasonable choices | Why this choice |
|---|---|---|
| M-17 | C2 congestion experiment changes only capacity and traveller count. | Vary several parameters simultaneously; use empirical demand; vary booking times. | Isolating congestion makes the fixed-probability failure easy to attribute and explain. |
| M-18 | Estimate Eq. (3) `q1/q2` with a redundant ticket deliberately kept. | Observe the release policy directly; infer rates from aggregate logs; force release. | Eq. (3) compares release with keeping, so the relevant benchmark is the keep-ticket outcome. |
| M-19 | Enumerate pure, type-level mean-field booking equilibria. | Mixed equilibrium; individual-agent equilibrium; reinforcement-learning equilibrium; no equilibrium. | Pure types are transparent and computationally small, matching the TA's type-grouping suggestion. |
| M-20 | Replay equilibrium actions with no dynamic events. | Replay full plan changes and releases; compare only analytical utilities; solve a dynamic equilibrium. | It isolates the static mean-field approximation before adding dynamic strategic complexity. |
| M-21 | Sweep `beta = 0, 1, 2` in one controlled profile. | Large grid search; optimize beta continuously; use different refund thresholds. | It shows the threshold effect and the cost of overpaying with three interpretable policy points. |
| M-22 | Private per-agent Beta posterior learning from own ticket outcomes. | Shared/global learning; Q-learning; Bayesian model with queue position; supervised learning on data. | A Beta update is transparent, matches unknown Bernoulli confirmation outcomes, and implements learning without hiding the mechanism. |
| M-23 | Report per-run population standard deviations. | Standard errors; confidence intervals; no variation metric. | These runs are controlled simulations, so dispersion is informative without making unsupported statistical-inference claims. |
| M-24 | Sensitivity varies `eta` at 0.10, 0.25, and 0.50. | Vary capacity, values, waitlist caps, or all variables jointly. | `eta` directly controls berth-release opportunities and tests the causal mechanism of the refund policy. |
| M-25 | Report draft labels results as controlled simulation findings. | Present results as policy recommendations; omit limitations; wait for real-data calibration. | The model is useful for mechanism analysis but has not been calibrated or validated against railway operations. |

## Rule for future decisions

For every material modeling or experimental decision, add a row to both:

1. [DECISIONS.md](DECISIONS.md): chosen decision, basis, and revision trigger.
2. This file: current option, reasonable alternatives, and selection rationale.

Minor code formatting and test-maintenance decisions do not need entries unless
they change model behavior or reported results.
