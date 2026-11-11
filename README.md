# Gerrymandering game

How much does it matter, for control of the U.S. House, if one or both parties gerrymander as hard as they can?

This is an illustrative simulation, not a forecast. Shock sizes are calibrated to look plausible, not estimated precisely.

## Pipeline (run from the folder that holds `code/` and `data/`)

| Step | Script | What it does |
|---|---|---|
| 1 | `code/parse_wiki.py`, `code/polymarket.py`, `code/parse_states.py` | 2026 House results by district (AP calls, Polymarket favorites for uncalled seats) and post-election state control |
| 2 | `code/moments.py`, `code/smm.py`, `code/bootstrap.py` | Shock process matched to 1998-2026 House returns; bootstrap draws of the parameters |
| 3 | `code/download_vtd.py` | Precinct data for all 50 states from Dave's Redistricting (`data/vtd/`, not committed; re-downloadable) |
| 4 | `code/drawall.py` (`code/drawmaps.py`), `code/multimember.py` | Pre-drawn menu of maps per state on real precincts: neutral and partisan congressional maps at four safety levels (plain and hedged against group swings), and both legislative chambers |
| 5 | `code/groups.py` | How presidential margins swung with precinct demographics |
| 6 | `code/run.py` (`code/model.py`) | The dynamic game 2028-2056 and all counterfactuals; writes `data/results.json` |

`code/sync.sh "message"` copies code and outputs into this repository and pushes.

Requires Python with `numpy`, `scipy`, `pandas`, `networkx`, `gerrychain`.

## Known rough spots
- Maps are rough optima; the optimizer currently finds fewer seats than real enacted gerrymanders.
- Congressional districts are within 1% of equal population, legislative districts within 5%.
- Lower houses in NH, VT, ME and CT are built from whole towns and wards as multi-member districts.
- Population is held fixed at the 2020 census.
