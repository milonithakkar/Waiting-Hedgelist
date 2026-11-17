# C3: Type-Based Booking Equilibrium

## What is implemented

`waitlist_sim/equilibrium.py` finds pure booking equilibria for a small number
of traveller types. Each type has a count, values for each train, an outside
option, and expected ticket costs. Every member of a type chooses the same set
of trains. The solver enumerates all type-action profiles and retains profiles
where every type's chosen action is a best response.

For a candidate profile, its mean-field confirmation probability is:

`p_k = min(1, capacity_k / expected demand_k)`.

Expected utility enumerates independent confirmation outcomes and subtracts the
configured expected ticket costs. This is intentionally a tractable
approximation; it is not an exact equilibrium of the full dynamic simulator.

## Example

Run the supplied two-train, two-type case:

```bash
python3 -m waitlist_sim --equilibrium-config examples/type_equilibrium.json
```

It checks 16 profiles and finds three pure equilibria. Multiple equilibria are
expected in a coordination setting, so the solver returns all of them rather
than silently selecting one.

## Replay against the event simulator

Each equilibrium can be replayed with fixed actions in the detailed event
simulator:

```bash
python3 -m waitlist_sim --equilibrium-config examples/type_equilibrium.json \
  --equilibrium-compare --equilibrium-index 2 --runs 1000 --seed 7
```

For equilibrium 2, the mean-field model gives `p_A = 0.4` and `p_B = 1.0`.
The event simulator has the same aggregate rates. But FIFO and input order make
the rates unequal by type: high-value travellers have observed A confirmation
rate 1.0, while price-sensitive travellers have rate 0.0. The aggregate hides
this split.

## Interpretation

Grouping travellers by type makes equilibrium computation manageable, exactly
as the TA suggested. It also creates a new modeling limit: a single
type-level rate cannot represent priority or queue-position differences that
the event simulator creates. The final analysis should report both aggregate
and type-level outcomes, and should treat this equilibrium as a benchmark.
