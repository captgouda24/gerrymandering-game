"""Check every saved congressional map: each district contiguous, population within tolerance, and seats carried as claimed."""
import sys, os, json, numpy as np, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, 'code')
import drawhq, flip
from drawmaps import SEATS, TARGETS
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
bad = 0; nmaps = 0; worst = 0
for st in sorted(s for s in SEATS if SEATS[s] > 1):
    az = np.load(f'data/assign/{st}.npz', allow_pickle=True); z, V, ip, ix = drawhq.raw(st); N = SEATS[st]; n = len(V)
    A = csr_matrix((np.ones(len(ix)), ix, ip), shape=(n, n)); rows = np.repeat(np.arange(n), np.diff(ip)); js = json.load(open(f'data/maps_hq/{st}.json'))
    for k in az.files:
        if k in ('ids', 'matches_final_run'): continue
        a = az[k].astype(np.int64); nmaps += 1; keep = a[rows] == a[ix]
        B = csr_matrix((np.ones(keep.sum()), (rows[keep], ix[keep])), shape=(n, n)); nc = connected_components(B, directed=False)[0]
        s = flip.district_sums(a, V, N); dev = np.abs(s[:, 4] / (V[:, 4].sum() / N) - 1).max(); worst = max(worst, dev); msg = []
        if nc != N: msg.append(f'{nc} pieces for {N} districts')
        if dev > js['pop_tolerance'] + 1e-6: msg.append(f'pop dev {dev:.3f} > {js["pop_tolerance"]}')
        if k != 'neutral':
            p, m = k.rsplit('_', 1); l = np.sort(flip.leans_of(s))[::-1]
            if not np.allclose(l, js[p][m][0], atol=0.02): msg.append('leans differ from the menu the model uses')
        if msg: bad += 1; print(st, k, '; '.join(msg), flush=True)
print('maps checked', nmaps, 'with problems', bad, 'worst population deviation', round(float(worst), 4))
