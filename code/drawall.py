"""Run the map drawer for all 50 states on 4 cores (largest first; resumable)."""
import os, sys, warnings, multiprocessing as mp, time
warnings.filterwarnings('ignore'); sys.path.insert(0, 'code')
from drawmaps import run_state, SEATS, CHAMBERS
def work(st):
    if os.path.exists(f'data/maps/{st}.json'): return st, 0
    t = time.time()
    try: run_state(st)
    except Exception as e: return st, f'ERR {e!r}'
    return st, round(time.time() - t)
if __name__ == '__main__':
    order = sorted(SEATS, key=lambda s: -(SEATS[s] * 4 + sum(CHAMBERS[s])))
    with mp.Pool(4) as pool:
        for st, sec in pool.imap_unordered(work, order, chunksize=1): print(st, sec, flush=True)
