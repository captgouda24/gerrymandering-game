"""Build the 1998-2024 district panel from FiveThirtyEight House returns and define the moment function
shared by data and simulation (the core of the simulated method of moments)."""
import numpy as np, pandas as pd

# National House popular-vote margin, R minus D, pct points (2026 from the Cook tracker via Wikipedia).
NAT = {1998: 1.1, 2000: 0.5, 2002: 4.8, 2004: 2.6, 2006: -8.0, 2008: -10.6, 2010: 6.8, 2012: -1.2,
       2014: 5.7, 2016: 1.1, 2018: -8.6, 2020: -3.1, 2022: 2.8, 2024: 2.6, 2026: -13.4}
# Party of the sitting president at each election (+1 R, -1 D).
PRES = {1998: -1, 2000: -1, 2002: 1, 2004: 1, 2006: 1, 2008: 1, 2010: -1, 2012: -1, 2014: -1, 2016: -1,
        2018: 1, 2020: 1, 2022: -1, 2024: -1, 2026: 1}
YEARS = list(range(1998, 2026, 2))
def decade(y): return (y - 2) // 10          # 2002-2010 share a map, 2012-2020, 2022-2024, 1998-2000

def build_panel(path='data/fte_house.csv'):
    d = pd.read_csv(path, low_memory=False)
    d = d[(d.stage == 'general') & (~d.special) & d.cycle.isin(YEARS) & d.candidate_id.notna()]
    d = d[~d.state_abbrev.isin(['DC', 'PR', 'GU', 'VI', 'AS', 'MP'])]
    top = d.sort_values('votes').groupby(['cycle', 'state_abbrev', 'office_seat_name', 'candidate_id']).agg(
        votes=('votes', 'sum'), party=('ballot_party', 'last'), pol=('politician_id', 'last'), win=('winner', 'max')).reset_index()
    rows = []
    for (cy, st, seat), g in top.groupby(['cycle', 'state_abbrev', 'office_seat_name']):
        r = g[g.party == 'REP'].votes.max() if (g.party == 'REP').any() else 0.0
        dm = g[g.party == 'DEM'].votes.max() if (g.party == 'DEM').any() else 0.0
        w = g.sort_values('votes').iloc[-1]
        rows.append((cy, st, seat, r, dm, w.party, w.pol))
    p = pd.DataFrame(rows, columns=['year', 'state', 'seat', 'R', 'D', 'wparty', 'wpol'])
    p['contested'] = (p.R > 0) & (p.D > 0)
    p['margin'] = 100 * (p.R - p.D) / (p.R + p.D).replace(0, np.nan)
    p['win'] = np.where(p.wparty == 'REP', 1, np.where(p.wparty == 'DEM', -1, 0))
    # incumbency: did last cycle's winner in this state (any district) win/run here? proxy = same politician won again,
    # so define inc going INTO year t as: the winner of this unit at t-2 appears as a candidate in this state at t.
    cand = d.groupby(['cycle', 'state_abbrev'])['politician_id'].apply(set).to_dict()
    prev = p.set_index(['year', 'state', 'seat'])
    inc = []
    for r_ in p.itertuples():
        key = (r_.year - 2, r_.state, r_.seat)
        if key in prev.index and decade(r_.year) == decade(r_.year - 2):
            pw = prev.loc[key]
            inc.append(int(pw.win) if pw.wpol in cand.get((r_.year, r_.state), ()) else 0)
        else:
            inc.append(np.nan)
    p['inc'] = inc
    return p

def panel_to_arrays(p):
    """Wide arrays [T, units]; a unit is (state, seat, decade) so swings never cross a redistricting."""
    p = p.copy(); p['unit'] = p.state + '|' + p.seat + '|' + p.year.map(decade).astype(str)
    units = sorted(p.unit.unique()); ui = {u: i for i, u in enumerate(units)}; T = len(YEARS)
    M = np.full((T, len(units)), np.nan); W = np.full_like(M, np.nan); I = np.full_like(M, np.nan)
    for r in p.itertuples():
        t = YEARS.index(r.year); j = ui[r.unit]
        if r.contested and abs(r.margin) < 90: M[t, j] = r.margin
        W[t, j] = r.win; I[t, j] = r.inc
    st = np.array([u.split('|')[0] for u in units]); _, sidx = np.unique(st, return_inverse=True)
    return M, W, I, sidx

def moments(M, W, I, sidx, nat, pres, mid):
    """M margins [T,U] (nan = missing), W winners, I incumbency going in (+1 R, -1 D, 0 open), sidx state index,
    nat [T'] national margins, pres [T'] president's party, mid [T'] midterm flag. Returns dict of moments."""
    out = {}
    pn = pres * nat
    out['pres_party_margin_midterm'] = pn[mid].mean()
    out['pres_party_margin_presyear'] = pn[~mid].mean()
    out['sd_national_margin'] = nat.std(ddof=1)
    out['sd_national_swing'] = np.diff(nat).std(ddof=1)
    S = M[1:] - M[:-1]                                  # within-map swings
    dI = I[1:] - np.where(np.isnan(I[:-1]), 0, I[:-1])  # change in incumbency status (prior unknown -> open)
    ok = ~np.isnan(S) & ~np.isnan(I[1:])
    st_dev, resid, dinc = [], [], []
    ns = sidx.max() + 1
    for t in range(S.shape[0]):
        o = ok[t]
        if o.sum() < 50: continue
        s = S[t] - np.mean(S[t][o])
        cnt = np.bincount(sidx[o], minlength=ns); sm = np.bincount(sidx[o], weights=s[o], minlength=ns) / np.maximum(cnt, 1)
        big = cnt >= 5
        st_dev.append(sm[big])
        r = (s - sm[sidx])[o & big[sidx]]; resid.append(r); dinc.append(dI[t][o & big[sidx]])
    st_dev = np.concatenate(st_dev); resid = np.concatenate(resid); dinc = np.concatenate(dinc)
    keep = np.abs(resid) < 35; resid, dinc = resid[keep], dinc[keep]
    out['sd_state_swing_dev'] = st_dev.std()
    out['sd_district_swing_resid'] = resid.std()
    out['incumbency_coef'] = (resid * (dinc - dinc.mean())).sum() / ((dinc - dinc.mean()) ** 2).sum()
    both = ~np.isnan(W[1:]) & ~np.isnan(W[:-1]) & (W[1:] != 0) & (W[:-1] != 0)
    out['seat_flip_rate'] = (W[1:][both] != W[:-1][both]).mean()
    out['open_seat_rate'] = np.nanmean(I[1:] == 0) / np.mean(~np.isnan(I[1:]))
    # state-level long-run drift: change over 4 cycles in (state mean margin - national mean of state means)
    T = M.shape[0]; sm = np.full((T, ns), np.nan)
    for t in range(T):
        o = ~np.isnan(M[t]); cnt = np.bincount(sidx[o], minlength=ns)
        v = np.bincount(sidx[o], weights=M[t][o], minlength=ns) / np.maximum(cnt, 1)
        v[cnt < 5] = np.nan; sm[t] = v - np.nanmean(v)
    out['sd_state_drift_4cycles'] = np.nanstd(sm[4:] - sm[:-4])
    # dispersion of district margins within state
    dev = M - sm[:, sidx] - np.nanmean(M, axis=1, keepdims=True) * 0
    out['sd_district_within_state'] = np.nanstd(M - np.where(np.isnan(sm), np.nan, 1)[:, sidx] * np.array(
        [np.bincount(sidx[~np.isnan(M[t])], weights=M[t][~np.isnan(M[t])], minlength=ns) / np.maximum(np.bincount(sidx[~np.isnan(M[t])], minlength=ns), 1) for t in range(T)])[:, sidx])
    return out

def data_moments():
    p = build_panel(); M, W, I, sidx = panel_to_arrays(p)
    yrs = np.array(sorted(NAT)); nat = np.array([NAT[y] for y in yrs]); pres = np.array([PRES[y] for y in yrs]); mid = (yrs % 4 == 2)
    return moments(M, W, I, sidx, nat, pres, mid), p

if __name__ == '__main__':
    m, p = data_moments()
    print('panel rows', len(p), 'contested share', p.contested.mean().round(3))
    for k, v in m.items(): print(f'{k:32s} {v:8.3f}')
    import json; json.dump(m, open('data/data_moments.json', 'w'), indent=1)
