"""Benchmark: seats at each design margin in (a) the enacted 2026 map, (b) the rough ReCom menu, (c) the precinct-flip menu."""
import sys, json, csv, time, numpy as np
sys.path.insert(0, 'code')
import drawhq
from drawmaps import SEATS, TARGETS
def enacted(st):
    with open('data/house2026_final.csv') as f: return np.array([2 * float(r['pvi']) for r in csv.DictReader(f) if r['state'] == st])
def count(l, sign): return [int((sign * np.asarray(l) >= m).sum()) for m in TARGETS]
for st in sys.argv[1:]:
    t = time.time(); z, V, ip, ix = drawhq.raw(st); res = drawhq.congress(st, V, ip, ix, False)
    with open(f'data/maps/{st}.json') as f: old = json.load(f)
    print(f'{st} ({SEATS[st]} seats, {time.time()-t:.0f}s, tol {res["pop_tolerance"]}) seats carried by >= 4/8/12/16 pts')
    for name, sign in (('R', 1), ('D', -1)):
        print(f'  {name}: enacted {count(enacted(st), sign)}  rough {[count(old[name][str(m)][0], sign)[i] for i, m in enumerate(TARGETS)]}'
              f'  flips {[count(res[name][str(m)][0], sign)[i] for i, m in enumerate(TARGETS)]}  hedged {[count(res[name+"_h"][str(m)][0], sign)[i] for i, m in enumerate(TARGETS)]}', flush=True)
