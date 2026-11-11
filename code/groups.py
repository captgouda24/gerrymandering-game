"""Ecological regression on ~200k precincts: how did the presidential margin swing with a precinct's demographic makeup?
swing(precinct) = state effect + b_H*Hispanic share + b_B*Black share + b_A*Asian share (+ noise), weighted by votes.
The b's are the swing among that group relative to everyone else (R minus D margin, pct pts), for 2016->20 and 2020->24."""
import numpy as np, glob, json
X = {p: [] for p in ('1620', '2024')}; Y = {p: [] for p in X}; Wt = {p: [] for p in X}; FE = {p: [] for p in X}
for si, f in enumerate(sorted(glob.glob('data/vtd/*.npz'))):
    z = np.load(f, allow_pickle=True); pop = np.maximum(z['pop'], 1)
    sh = np.stack([z['hispanic'] / pop, z['black'] / pop, z['asian'] / pop], 1)
    mar = {y: 100 * (z[f'{y}_pres_r'] - z[f'{y}_pres_d']) / np.maximum(z[f'{y}_pres_r'] + z[f'{y}_pres_d'], 1) for y in ('16', '20', '24')}
    tot = {y: z[f'{y}_pres_r'] + z[f'{y}_pres_d'] for y in mar}
    for p, (a, b) in (('1620', ('16', '20')), ('2024', ('20', '24'))):
        ok = (tot[a] > 50) & (tot[b] > 50) & (pop > 50) & (sh.sum(1) <= 1.05)
        X[p].append(sh[ok]); Y[p].append((mar[b] - mar[a])[ok]); Wt[p].append(np.sqrt(tot[b][ok])); FE[p].append(np.full(ok.sum(), si))
out = {}
for p in X:
    x = np.concatenate(X[p]); y = np.concatenate(Y[p]); w = np.concatenate(Wt[p]); fe = np.concatenate(FE[p])
    keep = np.abs(y) < 60; x, y, w, fe = x[keep], y[keep], w[keep], fe[keep]
    for a in (x, y):                                    # absorb state effects (weighted demeaning)
        pass
    sw = np.bincount(fe, weights=w * w); ym = np.bincount(fe, weights=w * w * y) / sw; y = y - ym[fe]
    xm = np.stack([np.bincount(fe, weights=w * w * x[:, j]) / sw for j in range(3)], 1); x = x - xm[fe]
    b = np.linalg.lstsq(x * w[:, None], y * w, rcond=None)[0]; out[p] = dict(n=int(len(y)), hispanic=float(b[0]), black=float(b[1]), asian=float(b[2]))
    print(p, out[p])
sd = {g: float(np.sqrt(np.mean([out[p][g] ** 2 for p in out])) / np.sqrt(2)) for g in ('hispanic', 'black', 'asian')}
print('implied sd per 2-year election (random walk):', sd)
with open('data/group_swings.json', 'w') as f: json.dump(dict(periods=out, sd_per_election=sd), f, indent=1)
