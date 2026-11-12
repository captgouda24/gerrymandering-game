"""Lower houses whose districts are smaller than (or comparable to) precincts: NH, VT, ME, CT.
These are built directly from the raw precincts (towns and wards) as multi-member districts: a district is a contiguous
group of precincts electing seats in proportion to its population, with a cap on district size, and the party that
carries the district takes its seats (bloc voting).  'Neutral' is every precinct on its own.  A partisan draw groups
towns to maximize the lean of the tipping seat; it is found by an intensive local search (millions of proposals)."""
import sys, json, time, numpy as np
sys.path.insert(0, 'code')
from drawmaps import CHAMBERS, NAT, statewide
CAP = dict(NH=8.0, VT=2.0, ME=1.3, CT=1.3)             # largest district, in seats (single precincts above the cap stand alone)

def chamber(st, nseats=None, cap_seats=None, seed=0, proposals=600_000, rounds=8, verbose=True):
    rng = np.random.default_rng(seed); z = np.load(f'data/vtd/{st}.npz', allow_pickle=True); n = len(z['pop']); nseats = nseats or CHAMBERS[st][1]
    pop = z['pop'].astype(float); ideal = pop.sum() / nseats; cap = (cap_seats or CAP[st]) * ideal; sw = statewide(z)
    V = np.stack([z['24_pres_r'], z['24_pres_d'], z['20_pres_r'], z['20_pres_d'], pop, z['hispanic'], z['black'], z['asian']], 1).astype(float)
    nbr = [[] for _ in range(n)]
    for a, b in z['edges']: nbr[a].append(int(b)); nbr[b].append(int(a))
    edges = np.array(z['edges'])
    def lean(v):
        return 0.5 * (100 * (v[0] - v[1]) / max(v[0] + v[1], 1) - NAT['24'] + 100 * (v[2] - v[3]) / max(v[2] + v[3], 1) - NAT['20'])
    def tip(sums, alive, sign):
        ids = np.where(alive)[0]; l = np.array([sign * lean(sums[i]) for i in ids]); w = sums[ids, 4] / pop.sum()
        o = np.argsort(-l); k = o[np.searchsorted(np.cumsum(w[o]), 0.5)]; return float(l[k]), int(ids[k])
    def connected(members, drop):
        rest = members - {drop}
        if not rest: return True
        start = next(iter(rest)); seen = {start}; stack = [start]
        while stack:
            u = stack.pop()
            for w_ in nbr[u]:
                if w_ in rest and w_ not in seen: seen.add(w_); stack.append(w_)
        return len(seen) == len(rest)
    out = dict(districts_true=nseats, method='population-weighted districts built from whole precincts', precincts=n)
    sums0 = V.copy(); t0, k0 = tip(sums0, np.ones(n, bool), 1)
    out['neutral_tip'] = t0 - sw; out['neutral_tip_shares'] = (sums0[k0, 5:8] / max(sums0[k0, 4], 1)).round(3).tolist()
    for name, sign in (('R', 1), ('D', -1)):
        t1 = time.time(); label = np.arange(n); sums = V.copy(); members = [{i} for i in range(n)]; alive = np.ones(n, bool)
        f = lambda v, x: v[4] / pop.sum() / (1 + np.exp(-(sign * lean(v) - x) / 1.5))
        best = tip(sums, alive, sign)[0]
        for r in range(rounds):
            x = tip(sums, alive, sign)[0] + 1.0; pick = rng.integers(0, len(edges), proposals); flip = rng.random(proposals) < 0.5; sec = rng.random(proposals) < 0.05
            for i in range(proposals):
                u, v = edges[pick[i]]
                if flip[i]: u, v = v, u
                a, b = label[u], label[v]
                if a == b and not sec[i]: continue
                if not connected(members[a], u): continue
                if sec[i] or a == b:                         # u secedes into a district of its own
                    if len(members[a]) == 1: continue
                    b = int(np.where(~alive)[0][0]); new_b = V[u].copy()
                else:
                    new_b = sums[b] + V[u]
                    if new_b[4] > cap: continue
                new_a = sums[a] - V[u]
                d = f(new_b, x) + (f(new_a, x) if len(members[a]) > 1 else 0) - f(sums[a], x) - (f(sums[b], x) if alive[b] and b != a and not (sec[i] or label[v] == a) else 0)
                if d >= 0:
                    members[a].discard(u); sums[a] = new_a; alive[a] = len(members[a]) > 0
                    if not alive[b]: members[b] = set(); sums[b] = 0
                    members[b].add(u); sums[b] = new_b; alive[b] = True; label[u] = b
            best = tip(sums, alive, sign)[0]
            if verbose: print(st, name, 'round', r, 'districts', int(alive.sum()), 'tipping lean for drawer', round(best, 2), f'{time.time()-t1:.0f}s', flush=True)
        tl, k = tip(sums, alive, sign)
        out[name + '_tip'] = sign * tl - sw; out[name + '_tip_shares'] = (sums[k, 5:8] / max(sums[k, 4], 1)).round(3).tolist()
        out[name + '_districts'] = int(alive.sum()); out[name + '_assign'] = label.copy()
    out['districts_drawn'] = out['R_districts']; return out

def best_of(st, nseats=None, cap_seats=None, seeds=3, proposals=300_000, rounds=6):
    """Several independent searches; keep each party's best."""
    runs = [chamber(st, nseats, cap_seats, seed=sd, proposals=proposals, rounds=rounds, verbose=False) for sd in range(seeds)]
    res = dict(runs[0]); br = max(runs, key=lambda r: r['R_tip']); bd = min(runs, key=lambda r: r['D_tip'])
    for k in ('R_tip', 'R_tip_shares', 'R_districts', 'R_assign'): res[k] = br[k]
    for k in ('D_tip', 'D_tip_shares', 'D_districts', 'D_assign'): res[k] = bd[k]
    return res

if __name__ == '__main__':
    for st in sys.argv[1:]:
        res = best_of(st, seeds=4, proposals=600_000, rounds=8); print(st, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in res.items()}, flush=True)
        try:
            with open(f'data/maps/{st}.json') as f: mp = json.load(f)
            mp['lower'] = res
            with open(f'data/maps/{st}.json', 'w') as f: json.dump(mp, f)
        except FileNotFoundError: print(st, 'state file not ready; result not saved')
