"""Precinct-by-precinct gerrymandering search (compiled).  Districts must be contiguous and near-equal in population;
there is NO compactness requirement, so tentacles, pie slices and narrow connectors are all allowed -- the automated
analogue of a consultant trading precincts between districts by hand.  Simulated annealing over single-precinct moves."""
import numpy as np, numba as nb

@nb.njit(cache=True)
def _lean(s):                           # R minus D, pct pts, relative to the nation (2020 and 2024 presidential, averaged)
    return 0.5 * (100.0 * (s[0] - s[1]) / max(s[0] + s[1], 1.0) - 1.5 + 100.0 * (s[2] - s[3]) / max(s[2] + s[3], 1.0) + 4.5)

@nb.njit(cache=True)
def _val(s, sign, x, scale, hedge):     # smooth "is this seat carried by at least x" for the party `sign`
    l = sign * _lean(s)
    if hedge[0] + hedge[1] + hedge[2] > 0:       # hedged maps: subtract the worst single-group adverse swing
        p = max(s[4], 1.0); l -= max(hedge[0] * s[5] / p, max(hedge[1] * s[6] / p, hedge[2] * s[7] / p))
    return 1.0 / (1.0 + np.exp(-(l - x) / scale))

@nb.njit(cache=True)
def _connected_without(u, a, assign, indptr, indices, stamp, tick, queue):
    """Does district a stay connected if precinct u leaves?  Breadth-first search among a's precincts from one of u's
    neighbours until all of u's other neighbours in a are reached."""
    need = 0; start = -1
    for e in range(indptr[u], indptr[u + 1]):
        w = indices[e]
        if assign[w] == a:
            need += 1
            if start < 0: start = w
    if need <= 1: return need == 1                # need == 0 would empty or strand the district
    stamp[u] = tick; stamp[start] = tick; queue[0] = start; head = 0; tail = 1; found = 1
    isnb = False
    while head < tail:
        v = queue[head]; head += 1
        for e in range(indptr[v], indptr[v + 1]):
            w = indices[e]
            if assign[w] == a and stamp[w] != tick:
                stamp[w] = tick; queue[tail] = w; tail += 1
                isnb = False
                for f in range(indptr[u], indptr[u + 1]):
                    if indices[f] == w: isnb = True; break
                if isnb:
                    found += 1
                    if found == need: return True
    return False

@nb.njit(cache=True)
def anneal(assign, sums, V, indptr, indices, lo, hi, sign, x, hedge, iters, t0, t1, s0, s1, mode, seed):
    """mode 0: repair population (minimize out-of-band population); mode 1: maximize seats carried by >= x.
    assign/sums are updated in place.  Returns the number of accepted moves."""
    np.random.seed(seed); n = len(assign); stamp = np.zeros(n, np.int64); queue = np.zeros(n, np.int64); tick = 0; acc = 0
    for it in range(iters):
        frac = it / iters; T = t0 * (t1 / t0) ** frac; sc = s0 * (s1 / s0) ** frac
        u = np.random.randint(n); deg = indptr[u + 1] - indptr[u]
        if deg == 0: continue
        v = indices[indptr[u] + np.random.randint(deg)]; a = assign[u]; b = assign[v]
        if a == b: continue
        pa = sums[a, 4] - V[u, 4]; pb = sums[b, 4] + V[u, 4]
        if mode == 1:
            if pa < lo or pb > hi: continue
            d = -_val(sums[a], sign, x, sc, hedge) - _val(sums[b], sign, x, sc, hedge)
            na = sums[a] - V[u]; nb_ = sums[b] + V[u]
            d += _val(na, sign, x, sc, hedge) + _val(nb_, sign, x, sc, hedge)
        else:
            old = max(lo - sums[a, 4], 0.0) + max(sums[a, 4] - hi, 0.0) + max(lo - sums[b, 4], 0.0) + max(sums[b, 4] - hi, 0.0)
            new = max(lo - pa, 0.0) + max(pa - hi, 0.0) + max(lo - pb, 0.0) + max(pb - hi, 0.0)
            d = (old - new) / hi
            if d == 0.0: d = ((sums[a, 4] - sums[b, 4]) - (pa - pb)) / hi * 1e-3 if sums[a, 4] > sums[b, 4] else -1e-9   # drift toward balance
        if d < 0 and np.random.random() >= np.exp(d / T): continue
        tick += 1
        if not _connected_without(u, a, assign, indptr, indices, stamp, tick, queue): continue
        assign[u] = b
        for k in range(V.shape[1]): sums[a, k] -= V[u, k]; sums[b, k] += V[u, k]
        acc += 1
    return acc

def district_sums(assign, V, N):
    s = np.zeros((N, V.shape[1]))
    for k in range(V.shape[1]): s[:, k] = np.bincount(assign, weights=V[:, k], minlength=N)
    return s

def leans_of(sums): return np.array([_lean(s) for s in sums])
def shares_of(sums): return sums[:, 5:8] / np.maximum(sums[:, 4:5], 1)
