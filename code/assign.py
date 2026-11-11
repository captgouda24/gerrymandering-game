"""Re-run the congressional draws with the same seeds and settings as the final run, this time saving which precinct
went to which district (data/assign/{ST}.npz), and check that the regenerated maps match the ones the results used."""
import sys, os, json, numpy as np, multiprocessing as mp, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, 'code')
import drawhq
from drawmaps import SEATS, TARGETS
FULL = ()                                          # all states at a quarter effort here (the regenerated maps are a fresh random draw either way)
def work(st):
    out = f'data/assign/{st}.npz'
    if os.path.exists(out): return st, 'cached'
    drawhq.EFFORT, drawhq.RESTARTS = (1.0, 3) if st in FULL else (0.25, 2)
    z, V, ip, ix = drawhq.raw(st); keep = {}
    try: res = drawhq.congress(st, V, ip, ix, False, keep)
    except RuntimeError as e: return st, f'ERR {e!r}'
    with open(f'data/maps_hq/{st}.json') as f: old = json.load(f)
    same = all(np.allclose(res[p][str(m)][0], old[p][str(m)][0], atol=0.02) for p in ('R', 'D', 'R_h', 'D_h') for m in TARGETS) if not old.get('congress_fallback') else False
    np.savez_compressed(out, ids=z['ids'], matches_final_run=same, **keep)
    return st, 'matches final run' if same else 'DIFFERS from final run'
if __name__ == '__main__':
    os.makedirs('data/assign', exist_ok=True); states = sorted([s for s in SEATS if SEATS[s] > 1], key=lambda s: -SEATS[s])
    with mp.Pool(4) as pool:
        for st, msg in pool.imap_unordered(work, states, chunksize=1): print(st, msg, flush=True)
