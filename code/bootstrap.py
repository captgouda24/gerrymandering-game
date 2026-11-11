"""Bootstrap the shock-process estimates: resample states (district moments) and election years (national moments)
with replacement, re-estimate, and save the draws.  The forward simulation is then re-run under each draw."""
import sys, json, numpy as np
sys.path.insert(0, 'code')
from moments import build_panel, panel_to_arrays, moments, NAT, PRES
from smm import fit_to, NAMES
Bn = int(sys.argv[1]) if len(sys.argv) > 1 else 40
p = build_panel(); M, W, I, sidx = panel_to_arrays(p); ns = sidx.max() + 1
yrs = np.array(sorted(NAT)); nat = np.array([NAT[y] for y in yrs]); pres = np.array([PRES[y] for y in yrs]); mid = yrs % 4 == 2
rng = np.random.default_rng(7); draws = []
for b in range(Bn):
    pick = rng.integers(0, ns, ns); cols = np.concatenate([np.where(sidx == s)[0] for s in pick])
    lab = np.concatenate([np.full((sidx == s).sum(), i) for i, s in enumerate(pick)])
    iy = np.where(mid, rng.choice(np.where(mid)[0], len(yrs)), rng.choice(np.where(~mid)[0], len(yrs)))
    dm = moments(M[:, cols], W[:, cols], I[:, cols], lab, nat[iy], pres[iy], mid)
    d = np.diff(nat); dm['sd_national_swing'] = float(rng.choice(d, len(d)).std(ddof=1))
    th = fit_to(dm, maxiter=450).x; draws.append(dict(zip(NAMES, map(float, th)))); print(b, np.round(th, 2).tolist(), flush=True)
    with open('data/bootstrap_theta.json', 'w') as f: json.dump(draws, f)
arr = np.array([[d[k] for k in NAMES] for d in draws])
for k, m_, s_ in zip(NAMES, arr.mean(0), arr.std(0)): print(f'{k:10s} mean {m_:6.2f}  se {s_:5.2f}')
