"""Simulated method of moments for the shock process.
theta = (sd_nat, mid_pen, pres_pen, rho, sd_state, sd_dist, incumb, sd_drift).  Margins are R minus D in pct points.
  national environment  n_t = -pres_t*(pres_pen + mid_pen*1[midterm]) + x_t,  x_t = rho*x_{t-1} + N(0, sd_nat)
  district margin       = state lean + district offset + n_t + state shock + incumb*inc + district shock"""
import json, sys, numpy as np
from scipy.optimize import minimize
sys.path.insert(0, 'code')
from moments import moments, data_moments
from drawmaps import SEATS
NAMES = ['sd_nat', 'mid_pen', 'pres_pen', 'rho', 'sd_state', 'sd_dist', 'incumb', 'sd_drift']
KEYS = ['pres_party_margin_midterm', 'pres_party_margin_presyear', 'sd_national_margin', 'sd_national_swing',
        'sd_state_swing_dev', 'sd_district_swing_resid', 'incumbency_coef', 'seat_flip_rate', 'sd_state_drift_4cycles']
RETIRE, SD_MAP, T = 0.115, 31.6, 14
sizes = np.array([SEATS[s] for s in sorted(SEATS)]); sidx0 = np.repeat(np.arange(50), sizes); D = sizes.sum()
DEC = np.array([0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3])      # map-decade of each of the 14 cycles 1998..2024

def sim_national(th, rng, K=400, Tn=15):
    sd_nat, mid_pen, pres_pen, rho = th[:4]
    nat = np.zeros((K, Tn)); pres = np.zeros((K, Tn)); x = rng.normal(0, sd_nat / np.sqrt(max(1 - rho**2, 1e-6)), K)
    p = np.where(rng.random(K) < .5, 1., -1.)
    mid = np.arange(Tn) % 2 == 0                                    # series starts in a midterm (1998)
    for t in range(Tn):
        x = rho * x + rng.normal(0, sd_nat, K)
        nat[:, t] = -p * (pres_pen + mid_pen * mid[t]) + x; pres[:, t] = p
        if not mid[t]: p = np.where(nat[:, t] + rng.normal(0, 2, K) > 0, 1., -1.)   # presidential year picks the next president
    return nat, pres, mid

def sim_moments(th, seed=1, reps=6):
    rng = np.random.default_rng(seed); sd_state, sd_dist, incumb, sd_drift = th[4:]
    nat, pres, mid = sim_national(th, rng)
    pn = pres * nat
    out = dict(pres_party_margin_midterm=pn[:, mid].mean(), pres_party_margin_presyear=pn[:, ~mid].mean(),
               sd_national_margin=nat.std(axis=1, ddof=1).mean(), sd_national_swing=np.diff(nat, axis=1).std(axis=1, ddof=1).mean())
    acc = {k: [] for k in KEYS[4:]}
    for r in range(reps):
        L = rng.normal(0, 18, 50); inc = np.zeros(D); M = np.full((T, D * 4), np.nan); W = np.full_like(M, np.nan); I = np.full_like(M, np.nan)
        for t in range(T):
            if t == 0 or DEC[t] != DEC[t - 1]:
                off = rng.normal(0, SD_MAP, D); off -= (np.bincount(sidx0, weights=off) / sizes)[sidx0]; fresh = True   # redraws keep the state mean
            L = L + rng.normal(0, sd_drift, 50)
            m = L[sidx0] + off + nat[r, t] + rng.normal(0, sd_state, 50)[sidx0] + incumb * inc + rng.normal(0, sd_dist, D)
            cols = DEC[t] * D + np.arange(D); M[t, cols] = m; W[t, cols] = np.sign(m); I[t, cols] = np.nan if fresh else inc
            fresh = False
            inc = np.where(rng.random(D) < RETIRE, 0., np.sign(m))
        mm = moments(M, W, I, np.tile(sidx0, 4), nat[r, :T], pres[r, :T], mid[:T])
        for k in acc: acc[k].append(mm[k])
    out.update({k: float(np.mean(v)) for k, v in acc.items()})
    return out

def fit_to(dm, maxiter=700):
    target = np.array([dm[k] for k in KEYS]); scale = np.maximum(np.abs(target), 0.5)
    def loss(th):
        th = np.array(th)
        if (th[[0, 4, 5, 7]] <= 0).any() or not (-0.9 < th[3] < 0.9): return 1e6
        sm = sim_moments(th); return float((((np.array([sm[k] for k in KEYS]) - target) / scale) ** 2).sum())
    x0 = np.array([5.0, 3.0, 2.0, 0.2, 3.0, 5.5, 2.0, 2.0])
    return minimize(loss, x0, method='Nelder-Mead', options=dict(maxiter=maxiter, xatol=0.02, fatol=1e-4, adaptive=True))

def fit():
    dm, _ = data_moments(); r = fit_to(dm)
    th = r.x; sm = sim_moments(th, seed=2, reps=12)
    print('loss', round(r.fun, 4), 'evals', r.nfev)
    for n, v in zip(NAMES, th): print(f'  {n:10s} {v:7.3f}')
    print(f"{'moment':32s} {'data':>8s} {'model':>8s}")
    for k in KEYS: print(f'{k:32s} {dm[k]:8.3f} {sm[k]:8.3f}')
    with open('data/smm_fit.json', 'w') as f: json.dump(dict(theta=dict(zip(NAMES, map(float, th))), data=dm, model=sm, retire=RETIRE), f, indent=1)

if __name__ == '__main__': fit()
