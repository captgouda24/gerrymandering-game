# Results (third run, finished 2026-11-12)

Illustrative simulation, not a forecast. Every number is the Democratic share of discounted time holding the U.S. House
majority over the 15 elections 2028-2056 (the Republican share is one minus it). Simulation error is about 0.3 points;
re-estimating the shock parameters 40 times gives standard errors of 2-3 points on levels. Full output: `data/results.json`.

Every map behind these numbers is saved precinct by precinct: congressional maps in `data/assign/` (pictures in
`data/maps_img/`), legislative chambers in `data/assign_chambers/`, and the every-state-50-50 maps in `data/assign_even/`.
The first run's maps were not saved; its results are kept in `data/results_v1.json` and differ by 1-2 points, because
its Republican congressional maps were slightly stronger (see the benchmark table). Election-by-election paths are in
`data/timeline.json` and charted in `data/timeline.html`.

## Time in majority by scenario

| Scenario | Actual start | National 50-50, clean start | Every state 50-50 |
|---|---|---|---|
| National ban (neutral maps everywhere) | 42% | 40% | 42% |
| Today's bans, both parties gerrymander | 26% | 24% | 41% |
| No bans anywhere, both gerrymander | 32% | 32% | 39% |
| Republicans all-out, Democrats abstain (no bans) | 17% | 17% | 26% |
| Republicans all-out, Democrats abstain (today's bans) | 20% | 19% | 32% |
| Democrats all-out, Republicans abstain (no bans) | 65% | 65% | 57% |
| Democrats all-out, Republicans abstain (today's bans) | 51% | 49% | 52% |

- **Actual start**: 2026 results, incumbents, maps and state governments as they stand.
- **National 50-50, clean start**: same states, but a coin-flip president, no carried-over 2026 wave and no incumbents.
  (State leans are measured relative to the nation, so the expected national vote is even in both columns.)
- **Every state 50-50**: every precinct in a state is shifted by a uniform swing so the state votes like the nation; maps
  are redrawn on that basis; state governments start as coin flips.

## Findings

1. **Who gerrymanders matters enormously.** Unilateral effort moves the outcome from 17% to 65%.
2. **Mutual gerrymandering under today's rules costs Democrats about 16 points** against a national ban (26% vs 42%).
3. **Today's bans hurt Democrats.** With no bans anywhere they hold the majority 32% of the time, against 26% now.
4. **When every state is 50-50, mutual gerrymandering is close to a wash** (39-41% vs 42% under a ban). The real-world
   asymmetry therefore comes from which states each party holds and where the bans are, not from map-drawing skill.
5. **Neutral maps still favor Republicans** (about 42% Democratic), including when every state is 50-50. See caveats.
6. **National coordination barely matters.** Coordinated play by either or both parties moves the result by at most
   about 2 points, against state-by-state seat maximizing.
7. **The majority threshold is where the value is.** The chance Republicans hold the next three Congresses rises from 59%
   with 170-177 seats to 74% just under 218, then only to 80% at 258-265.
8. **Mid-decade redistricting costs Democrats about 2 points** (26% vs 28% if maps could only change after a census).
9. **Group swings matter little in aggregate.** A 15-point swing among Hispanic voters against the party that drew every
   state costs Republicans about 1 expected seat and Democrats about 5 at thin margins. Hedged maps cost seats (259 vs
   263 expected Republican seats at an 8-point design); state parties choose them for a third to a half of seats.
10. **Thin maps break in waves.** Republicans drawing every state at a 4-point design expect 266 seats in a neutral
    year, 238 after a 5-point swing against them and 190 after 10; at a 16-point design, 237, 232 and 224.

## Single-state reforms (change in Democratic time in majority, today's bans otherwise)

| Reform | Change |
|---|---|
| Ban in Texas | +3.6 |
| Ban in Florida | +2.1 |
| Ban in North Carolina | +1.9 |
| Lift New York's ban | +1.8 |
| Ban in Indiana | +1.7 |
| Ban in Ohio | +1.6 |
| Ban in Missouri | +1.6 |
| Ban in South Carolina | +1.3 |
| Ban in Illinois | -1.3 |
| Ban in Georgia | +1.2 |
| Lift New Jersey's ban | +1.2 |
| Lift Colorado's ban | +1.1 |

## Control of the pen

Averaged over states, the seat that decides a legislative chamber sits 2 points more Republican than the state under a
neutral map, about 15 points more Republican under a Republican-drawn map, and about 12 points more Democratic under a
Democratic-drawn one. Share of 2028-2056 in which each party controls redistricting, under today's bans:

| State | Republicans | Democrats |
|---|---|---|
| North Carolina | 88% | 4% |
| Florida | 74% | 7% |
| Ohio | 67% | 4% |
| Texas | 60% | 9% |
| Georgia | 45% | 14% |
| Wisconsin | 40% | 33% |
| Nevada | 25% | 41% |
| Minnesota | 18% | 56% |
| Illinois | 4% | 81% |
| Maryland | 0% | 98% |

House control changes hands often: under today's bans the average unbroken spell is 2.7 elections, and one party holds
all 15 in 4% of futures (13% when only Republicans gerrymander). State-level lock-out durations were not computed.

## Drawn maps against enacted maps (seats carried by at least 4 / 8 / 12 / 16 points)

| State, party | Enacted 2026 | First-pass search | Tentacle search, first run | Tentacle search, this run |
|---|---|---|---|---|
| Texas, R (38) | 30 / 28 / 27 / 25 | 27 / 27 / 23 / 21 | 29 / 29 / 29 / 29 | 28 / 28 / 28 / 28 |
| Florida, R (28) | 24 / 23 / 19 / 12 | 21 / 22 / 19 / 17 | 24 / 24 / 22 / 20 | 23 / 23 / 21 / 20 |
| North Carolina, R (14) | 11 / 11 / 9 / 7 | 11 / 11 / 9 / 8 | 10 / 10 / 10 / 9 | 10 / 10 / 10 / 10 |
| Ohio, R (15) | 11 / 11 / 7 / 7 | 13 / 13 / 12 / 11 | 13 / 13 / 13 / 12 | 13 / 13 / 13 / 12 |
| Georgia, R (14) | 9 / 9 / 9 / 8 | 11 / 11 / 10 / 9 | 11 / 11 / 11 / 10 | 10 / 10 / 10 / 10 |
| Tennessee, R (9) | 9 / 9 / 9 / 9 | 8 / 8 / 8 / 8 | 9 / 8 / 8 / 8 | 9 / 8 / 8 / 8 |
| Illinois, D (17) | 14 / 11 / 9 / 8 | 12 / 12 / 11 / 10 | 13 / 12 / 12 / 12 | 12 / 12 / 12 / 12 |
| Maryland, D (8) | 7 / 6 / 6 / 6 | 8 / 8 / 8 / 8 | 8 / 8 / 8 / 8 | 8 / 8 / 8 / 8 |
| California, D (52) | 47 / 44 / 41 / 32 | 45 / 40 / 40 / 37 | 48 / 47 / 45 / 42 | 47 / 46 / 45 / 43 |
| New York, D (26) | 17 / 15 / 14 / 13 | 20 / 18 / 17 / 16 | 22 / 21 / 20 / 20 | 21 / 21 / 19 / 19 |

The model uses, at each safety level, whichever of enacted, first-pass and this run's tentacle map carries the most
seats. The search is not reproducible from its seeds, and this run is a seat weaker for Republicans in Texas, Florida and
Georgia and two weaker in Pennsylvania (11 seats against 13).

## Caveats

- **Levels are less reliable than differences.** The neutral-map baseline (about 60% Republican) is the number to doubt
  most. State lean is measured from votes while districts are built from population, which may inflate it. Kenny,
  McCartan, Imai and coauthors (PNAS 2023) find enacted gerrymanders mostly cancel nationally; this model does not, and
  the two have not been reconciled.
- **Shock sizes are calibrated to look plausible**, matched to 1998-2026 House returns. Halving state drift moves the
  today's-bans figure from 26% to 21%. Group-shock sizes (12 / 4 / 6 points per election for Hispanic / Black / Asian
  voters) are set by judgment from two precinct-level swings.
- **Map quality is uneven.** All congressional maps in this run were drawn at a quarter of full search effort (the first
  run drew Texas, Florida, New York and Pennsylvania at full effort). Legislative chambers are true single-member maps within 5% of equal population where
  precincts allow, within 10% in some states, and whole-precinct approximations in others. The legislative search is noisy:
  redrawing with the same settings moves a chamber's tipping seat by about 5 points (standard deviation), so
  single-state pen-control figures are rough. The Texas Senate (+3 for Republicans) and Florida House (+4) draws look
  under-optimized.
- **Checks on the saved congressional maps** (`code/validate.py`): all 748 are contiguous and match the menus the model
  uses; Ohio's 16 partisan maps deviate up to 2% from equal population instead of 1%. Chamber maps were not checked this
  way. The Maine picture is mostly blank (34% of precincts matched Census shapes).
- **"Enacted" leans** come from the 2026 Cook index as listed on Wikipedia and may reflect superseded maps in a few states.
- Population is fixed at the 2020 census; no reapportionment. State courts and the Voting Rights Act are ignored.
- "Uncoordinated" means each state party maximizes its own state's expected seats; "coordinated" means one national rule
  per party maximizing time in the majority.
