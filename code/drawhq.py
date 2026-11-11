"""High-quality maps: precinct-by-precinct search with tentacles allowed (flip.py), started from random contiguous
partitions.  Same output format as drawmaps.py, written to data/maps_hq/{ST}.json.
Congress: population within 1% of ideal; legislative chambers within 5% (wider only if precincts make that impossible)."""
import sys, json, time, os, random, functools, numpy as np, networkx as nx, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, 'code')
from gerrychain import Graph
from gerrychain.tree import recursive_tree_part, bipartition_tree
from drawmaps import SEATS, CHAMBERS, TARGETS, HEDGE, MIN_UNITS, statewide, load_graph
import flip, multimember
RESTARTS = int(os.environ.get('RESTARTS', 3)); EFFORT = float(os.environ.get('EFFORT', 1.0)); EVEN = os.environ.get('EVEN') == '1'
OUT = 'data/maps_hq_even' if EVEN else 'data/maps_hq'

def raw(st):
    z = np.load(f'data/vtd/{st}.npz', allow_pickle=True); n = len(z['pop'])
    g = nx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(map(tuple, z['edges']))
    comps = sorted(nx.connected_components(g), key=len, reverse=True); main = np.array(sorted(comps[0]))
    for c in comps[1:]: a = min(c); g.add_edge(a, int(main[np.argmin(np.abs(main - a))]))
    V = np.stack([z['24_pres_r'], z['24_pres_d'], z['20_pres_r'], z['20_pres_d'], z['pop'], z['hispanic'], z['black'], z['asian']], 1).astype(float)
    if EVEN:                                   # rescale every precinct by a uniform swing so the state's vote matches the nation's (a 50-50 state)
        for r, d, nat in ((0, 1, 1.5), (2, 3, -4.5)):
            t = V[:, r] + V[:, d]; delta = (V[:, r].sum() - V[:, d].sum()) / max(t.sum(), 1) - nat / 100
            V[:, r] = np.clip(V[:, r] - delta * t / 2, 0, t); V[:, d] = t - V[:, r]
    A = nx.to_scipy_sparse_array(g, nodelist=range(n), format='csr')
    return z, V, A.indptr.astype(np.int64), A.indices.astype(np.int64)

def start_partition(st, N, V, indptr, indices, eps, seed):
    """Random contiguous partition: tree-partition a coarsened graph at a loose tolerance, expand to precincts, then let
    the precinct search repair population to within eps (or as close as the precincts allow)."""
    random.seed(seed); np.random.seed(seed); ideal = V[:, 4].sum() / N; assign = None
    for units, loose in ((60, 0.03), (60, 0.10), (25, 0.25), (12, 0.45)):
        try:
            g, z, _, label = load_graph(st, N, units, return_label=True)
            part = recursive_tree_part(g, range(N), ideal, 'pop', loose, method=functools.partial(bipartition_tree, max_attempts=3000))
            assign = np.array([part[b] for b in label], dtype=np.int64); break
        except RuntimeError: continue
    if assign is None: raise RuntimeError('no starting partition')
    sums = flip.district_sums(assign, V, N); none = np.zeros(3); n = len(assign); tol = eps
    for tol in (eps, eps * 2, eps * 4, 0.25):
        lo, hi = ideal * (1 - tol), ideal * (1 + tol)
        flip.anneal(assign, sums, V, indptr, indices, lo, hi, 1.0, 0.0, none, int(60 * n * EFFORT) + 200000, 1e-3, 1e-5, 1.0, 1.0, 0, seed)
        if (sums[:, 4] >= lo - 1).all() and (sums[:, 4] <= hi + 1).all(): break
    return assign, sums, tol

def smap(sums):
    l = flip.leans_of(sums); o = np.argsort(-l); return l[o].round(2).tolist(), flip.shares_of(sums)[o].round(3).tolist()

def congress(st, V, indptr, indices, verbose, keep=None):
    """keep: optional dict that receives the precinct-to-district assignment of every map drawn."""
    N = SEATS[st]; n = len(V); ideal = V[:, 4].sum() / N; none = np.zeros(3)
    starts = [start_partition(st, N, V, indptr, indices, 0.01, sd) for sd in range(RESTARTS)]
    tol = max(s[2] for s in starts); lo, hi = ideal * (1 - tol), ideal * (1 + tol)
    res = dict(seats=N, pop_tolerance=tol, method='precinct flips, contiguity only', neutral_one=smap(starts[0][1]),
               neutral=np.mean([np.sort(flip.leans_of(s[1]))[::-1] for s in starts], 0).round(2).tolist(), R={}, D={}, R_h={}, D_h={})
    iters = int(min(4e7, max(4e6, 3000 * n)) * EFFORT)
    if keep is not None: keep['neutral'] = starts[0][0].copy()
    for name, sign in (('R', 1.0), ('D', -1.0)):
        cur = [(a.copy(), s.copy()) for a, s, _ in starts]
        for m in TARGETS:
            best = None
            for r, (a, s) in enumerate(cur):
                flip.anneal(a, s, V, indptr, indices, lo, hi, sign, float(m) + 0.3, none, iters, 0.03, 0.0005, 4.0, 0.7, 1, 100 * r + m)
                c = (int((sign * flip.leans_of(s) >= m).sum()), a, s)
                if best is None or c[0] > best[0]: best = c
            res[name][str(m)] = smap(best[2])
            if keep is not None: keep[f'{name}_{m}'] = best[1].copy()
            ah, sh = best[1].copy(), best[2].copy()
            flip.anneal(ah, sh, V, indptr, indices, lo, hi, sign, float(m) + 0.3, HEDGE, iters, 0.03, 0.0005, 4.0, 0.7, 1, 7 + m)
            res[name + '_h'][str(m)] = smap(sh)
            if keep is not None: keep[f'{name}_h_{m}'] = ah.copy()
            if verbose: print(st, name, m, 'seats>=m', best[0], '/', N, 'hedged', int((sign * flip.leans_of(sh) >= m).sum()), flush=True)
    return res

def tip_of(sums, sign): l = sign * flip.leans_of(sums); k = np.argsort(-l)[len(l) // 2]; return float(l[k]), k

def chamber(st, ndist, V, indptr, indices, sw, verbose):
    n = len(V)
    if n < MIN_UNITS * ndist: return multimember.best_of(st, ndist, multimember.CAP.get(st, 1.3))
    ideal = V[:, 4].sum() / ndist; none = np.zeros(3)
    try: starts = [start_partition(st, ndist, V, indptr, indices, 0.05, sd) for sd in range(2)]
    except RuntimeError: return multimember.best_of(st, ndist, multimember.CAP.get(st, 1.3))
    tol = max(s[2] for s in starts)
    if tol > 0.11: return multimember.best_of(st, ndist, multimember.CAP.get(st, 1.3))    # precincts too coarse for real districts
    lo, hi = ideal * (1 - tol), ideal * (1 + tol)
    res = dict(districts_true=ndist, districts_drawn=ndist, pop_tolerance=tol, method='precinct flips, contiguity only')
    t0, k0 = tip_of(starts[0][1], 1); res['neutral_tip'] = float(np.mean([tip_of(s[1], 1)[0] for s in starts]) - sw)
    res['neutral_tip_shares'] = flip.shares_of(starts[0][1])[k0].round(3).tolist()
    iters = int(min(1.5e7, max(2e6, 1000 * n)) * EFFORT)
    for name, sign in (('R', 1.0), ('D', -1.0)):
        best = None
        for a0, s0, _ in starts:
            a, s = a0.copy(), s0.copy()
            for rnd in range(6):                         # ratchet: aim a little above the current tipping seat, repeat
                x = tip_of(s, sign)[0] + 1.5
                flip.anneal(a, s, V, indptr, indices, lo, hi, sign, x, none, iters, 0.02, 0.0005, 3.0, 0.7, 1, 31 * rnd + 5)
            t, k = tip_of(s, sign)
            if best is None or t > best[0]: best = (t, flip.shares_of(s)[k].round(3).tolist())
        res[name + '_tip'] = sign * best[0] - sw; res[name + '_tip_shares'] = best[1]
    if verbose: print(st, ndist, {k: round(v, 1) for k, v in res.items() if k.endswith('_tip')}, 'tol', tol, flush=True)
    return res

def run_state(st, out=None, verbose=False):
    out = out or OUT; t0 = time.time(); z, V, indptr, indices = raw(st); pop = z['pop'].sum(); sw = 0.0 if EVEN else statewide(z)
    res = dict(state=st, statewide=sw, state_shares=[float(z[g].sum() / pop) for g in ('hispanic', 'black', 'asian')])
    if SEATS[st] == 1: res.update(seats=1, neutral=[sw], R={}, D={}, R_h={}, D_h={})
    else:
        try: res.update(congress(st, V, indptr, indices, verbose))
        except RuntimeError:
            N = SEATS[st]; flat = [[sw] * N, [res['state_shares']] * N]; menu = {str(t): flat for t in TARGETS}
            res.update(seats=N, congress_fallback=True, neutral=flat[0], neutral_one=flat, R=menu, D=menu, R_h=menu, D_h=menu)
    up, lo = CHAMBERS[st]; res['upper'] = chamber(st, up, V, indptr, indices, sw, verbose)
    res['lower'] = dict(res['upper']) if lo == up else chamber(st, lo, V, indptr, indices, sw, verbose)
    res['seconds'] = round(time.time() - t0); os.makedirs(out, exist_ok=True)
    with open(f'{out}/{st}.json', 'w') as f: json.dump(res, f)
    return res

if __name__ == '__main__':
    import multiprocessing as mp
    if len(sys.argv) > 1 and sys.argv[1] != 'all':
        r = run_state(sys.argv[1], out=sys.argv[2] if len(sys.argv) > 2 else OUT, verbose=True); print('seconds', r['seconds'])
    else:
        def work(st):
            if os.path.exists(f'{OUT}/{st}.json'): return st, 0
            try: return st, run_state(st)['seconds']
            except Exception as e: return st, f'ERR {e!r}'
        with mp.Pool(4) as pool:
            for st, sec in pool.imap_unordered(work, sorted(SEATS, key=lambda s: -SEATS[s]), chunksize=1): print(st, sec, flush=True)
