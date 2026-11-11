"""Solve the gerrymandering game and run the counterfactuals.  Writes data/results.json."""
import sys, json, time, itertools, numpy as np
from scipy.stats import norm
sys.path.insert(0, 'code')
from model import *
from drawmaps import HEDGE
K = 3000; AG = (0, 4, 8, 12, 16, 20); BG = (0.0, 0.5, 1.0); HG = (0, 1)
GRID = list(itertools.product(AG, BG, HG)); t00 = time.time(); NEVAL = [0]
def sim(inp, P, ban, **kw):
    NEVAL[0] += 1; return simulate(inp, *P, ban, K=kw.pop('K', K), seed=kw.pop('seed', 0), **kw)

def uncoordinated(inp, **kw):
    """Each state party picks the rule that maximizes its own state's expected discounted seats while it holds the pen.
    Seats add up across states and control does not depend on the congressional map, so one run per grid point
    (everyone playing that point) recovers every state's own best choice."""
    ban = ban_matrix('none'); pay = np.zeros((len(GRID), 2, S))
    for g, (a, b, h) in enumerate(GRID): pay[g] = sim(inp, const_policy(a, b, h, a, b, h), ban, **kw)['own_seats']
    G = np.array(GRID)[pay.argmax(0)]; return (G[..., 0].astype(float), G[..., 1].astype(float), G[..., 2].astype(int)), pay

def coordinated(inp, ban, P0, who=(0, 1), rounds=4, **kw):
    """National planners: each coordinated party picks one rule for all its states to maximize its own discounted time in
    the majority; iterate best responses to a Nash equilibrium.  Parties not in `who` keep their uncoordinated maps."""
    P = [x.copy() for x in P0]; pol = {}
    for r in range(rounds):
        old = dict(pol)
        for p in who:
            res = []
            for a, b, h in GRID:
                Q = [x.copy() for x in P]; Q[0][p] = a; Q[1][p] = b; Q[2][p] = h; res.append(sim(inp, Q, ban, **kw)['R_time' if p == 0 else 'D_time'])
            a, b, h = GRID[int(np.argmax(res))]; P[0][p] = a; P[1][p] = b; P[2][p] = h; pol[p] = (a, b, h)
        if pol == old: break
    return P, {('R', 'D')[p]: v for p, v in pol.items()}

def summ(o): return dict(D_time=round(o['D_time'], 4), se=round(o['D_time_se'], 4), R_seats=round(o['R_seats'], 1), sd=round(o['sd_seats'], 1), flips=round(o['flips'], 2))

def stress(inp):
    """Static test of the menus: if a party drew every multi-seat state at a given design margin, how many seats would it
    expect to hold in a neutral year, and after a uniform or group-specific swing against it?"""
    sd = inp['theta']['sd_dist']; rows = []
    shocks = dict(none=(0, np.zeros(3)), uniform_5=(5, np.zeros(3)), uniform_10=(10, np.zeros(3)),
                  hispanic=(0, np.array([HEDGE[0], 0, 0])), black=(0, np.array([0, HEDGE[1], 0])), asian=(0, np.array([0, 0, HEDGE[2]])))
    for p, (name, sign) in enumerate((('R', 1), ('D', -1))):
        for h in (0, 1):
            for j, m in enumerate(TARGETS):
                r = dict(party=name, hedged=bool(h), design_margin=m)
                for k, (u, g) in shocks.items():
                    tot = 0.0
                    for s in range(S):
                        n = NS[s]
                        if n > 1: tot += norm.cdf((sign * inp['menus'][s, p, h, j, :n] - u - (inp['msh'][s, p, h, j, :n] - inp['natsh']) @ g * 1.0) / sd).sum()
                    r[k] = round(tot, 1)
                rows.append(r)
    return rows

if __name__ == '__main__':
    inp = load_inputs(); assert not inp['missing'], inp['missing']
    R = dict(theta=inp['theta'], stress=stress(inp))
    Pu, pay = uncoordinated(inp)
    R['uncoordinated_policy'] = {s: dict(R=[Pu[0][0, i], Pu[1][0, i], int(Pu[2][0, i])], D=[Pu[0][1, i], Pu[1][1, i], int(Pu[2][1, i])]) for i, s in enumerate(ST) if NS[i] > 1}
    print('uncoordinated seat-weighted mean design margin: R %.1f  D %.1f; hedged share R %.2f D %.2f' % tuple(
        [(Pu[0][p] * NS).sum() / NS.sum() for p in (0, 1)] + [(Pu[2][p] * NS).sum() / NS.sum() for p in (0, 1)]), flush=True)
    scen = {}; eq = {}
    for name, kind, kw in (('status_quo', 'status_quo', {}), ('unlimited', 'none', {}), ('national_ban', 'national_ban', {}),
                           ('status_quo_decennial', 'status_quo', dict(mid_decade=False)), ('status_quo_no_group_shocks', 'status_quo', dict(group_scale=0.0))):
        ban = ban_matrix(kind); e = {}
        o = sim(inp, Pu, ban, seed=1, **kw); e['uncoordinated'] = summ(o); e['R_maj_by_year'] = o['R_maj_by_year'].round(3).tolist()
        if kind != 'national_ban':
            for label, who in (('both_coordinated', (0, 1)), ('only_R_coordinated', (0,)), ('only_D_coordinated', (1,))):
                P, pol = coordinated(inp, ban, Pu, who, **kw); e[label] = summ(sim(inp, P, ban, seed=1, **kw)); e[label]['policy'] = pol
                if label == 'both_coordinated': eq[name] = P
        scen[name] = e; print(name, json.dumps(e)[:1000], f'[{time.time()-t00:.0f}s]', flush=True)
    # lopsided worlds: one party goes all-out wherever it holds the pen (no bans bind it), the other draws neutral maps
    for name, ab, who in (('R_all_out_D_abstains', -1, 0), ('D_all_out_R_abstains', 1, 1)):
        for law in ('none', 'status_quo'):
            ban = ban_matrix(law); e = dict(uncoordinated=summ(sim(inp, Pu, ban, seed=1, abstain=ab)))
            P, pol = coordinated(inp, ban, Pu, (who,), abstain=ab); e['trying_party_coordinated'] = summ(sim(inp, P, ban, seed=1, abstain=ab)); e['policy'] = pol
            scen[name + ('' if law == 'none' else '_under_current_bans')] = e; print(name, law, json.dumps(e), f'[{time.time()-t00:.0f}s]', flush=True)
    R['scenarios'] = scen
    # single-state reforms relative to the status quo (uncoordinated play): add a ban where there is none, lift it where there is one
    b0 = ban_matrix('status_quo'); base = sim(inp, Pu, b0, K=8000); rows = []
    for i, s in enumerate(ST):
        if NS[i] == 1: continue
        banned = b0[:, i].all()
        o = sim(inp, Pu, ban_matrix('status_quo', lift=[s]) if banned else ban_matrix('status_quo', extra=[s]), K=8000)
        rows.append(dict(state=s, seats=int(NS[i]), change='lift ban' if banned else 'add ban', dD_time=round(o['D_time'] - base['D_time'], 4), dR_seats=round(o['R_seats'] - base['R_seats'], 2)))
    R['state_reforms'] = rows; print('state reforms done', f'[{time.time()-t00:.0f}s]', flush=True)
    # value of seats beyond the threshold: majority in the next three Congresses as a function of today's seat count
    o = sim(inp, Pu, b0, K=8000, detail=True); rs = o['rseats']; val = []
    fut = np.stack([(rs[:, t+1:t+4] >= 218).mean(1) for t in range(T - 3)], 1); now = rs[:, :T-3]
    for lo in range(170, 266, 8):
        m = (now >= lo) & (now < lo + 8)
        if m.sum() > 200: val.append(dict(R_seats=f'{lo}-{lo+7}', n=int(m.sum()), P_R_majority_next3=round(float(fut[m].mean()), 3)))
    R['value_of_margin'] = val
    R['control'] = {s: dict(R=round(float(o['ctrl'][:, i, 0].mean()), 2), D=round(float(o['ctrl'][:, i, 1].mean()), 2)) for i, s in enumerate(ST) if NS[i] > 1}
    R['legislature_tips'] = {s: dict(upper=inp['tip'][i, 0].round(1).tolist(), lower=inp['tip'][i, 1].round(1).tolist()) for i, s in enumerate(ST)}
    # robustness to the questionable parameters, and bootstrap bands from re-estimated shock parameters (policies held fixed)
    rob = {}
    for label, mod in (('incumbency=0', dict(incumb=0.0)), ('incumbency x2', dict(incumb=2 * inp['theta']['incumb'])),
                       ('state drift halved', dict(sd_drift=inp['theta']['sd_drift'] / 2)), ('national sd x0.7', dict(sd_nat=0.7 * inp['theta']['sd_nat']))):
        i2 = dict(inp); i2['theta'] = dict(inp['theta'], **mod)
        P, pol = coordinated(i2, b0, Pu, (0, 1), rounds=3)
        rob[label] = dict(uncoordinated=summ(sim(i2, Pu, b0, seed=1)), both_coordinated=summ(sim(i2, P, b0, seed=1)), policy=pol); print(label, rob[label], flush=True)
    R['robustness'] = rob
    try:
        with open('data/bootstrap_theta.json') as f: draws = json.load(f)
        bs = {k: [] for k in ('status_quo_unc', 'status_quo_coord', 'unlimited_unc', 'national_ban')}
        for d in draws:
            i2 = dict(inp); i2['theta'] = d
            bs['status_quo_unc'].append(sim(i2, Pu, b0, K=1500)['D_time']); bs['status_quo_coord'].append(sim(i2, eq['status_quo'], b0, K=1500)['D_time'])
            bs['unlimited_unc'].append(sim(i2, Pu, ban_matrix('none'), K=1500)['D_time']); bs['national_ban'].append(sim(i2, Pu, ban_matrix('national_ban'), K=1500)['D_time'])
        R['bootstrap'] = {k: dict(mean=round(float(np.mean(v)), 4), se=round(float(np.std(v)), 4)) for k, v in bs.items()}
        a = np.array(bs['status_quo_coord']) - np.array(bs['status_quo_unc']); R['bootstrap']['coord_minus_unc'] = dict(mean=round(float(a.mean()), 4), se=round(float(a.std()), 4))
        a = np.array(bs['unlimited_unc']) - np.array(bs['national_ban']); R['bootstrap']['unlimited_minus_ban'] = dict(mean=round(float(a.mean()), 4), se=round(float(a.std()), 4))
        R['bootstrap']['n_draws'] = len(draws); print('bootstrap', R['bootstrap'], flush=True)
    except FileNotFoundError: pass
    R['n_evals'] = NEVAL[0]; R['seconds'] = time.time() - t00
    with open('data/results.json', 'w') as f: json.dump(R, f, indent=1, default=lambda v: v.tolist() if hasattr(v, 'tolist') else str(v))
    print('evaluations', NEVAL[0], 'seconds', round(time.time() - t00))
