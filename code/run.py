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


def study(inp, simkw, full=True):
    """Solve one world.  simkw are fixed simulation options for that world (e.g. clean_start, even_start)."""
    def simw(P, ban, **kw): return sim(inp, P, ban, **dict(simkw, **kw))
    def coord(ban, P0, who, **kw): return coordinated(inp, ban, P0, who, **dict(simkw, **kw))
    R = dict(n_enacted_floor=inp['n_enacted_floor'], n_alt=inp['n_alt'])
    Pu, pay = uncoordinated(inp, **simkw)
    R['uncoordinated_policy'] = {s: dict(R=[Pu[0][0, i], Pu[1][0, i], int(Pu[2][0, i])], D=[Pu[0][1, i], Pu[1][1, i], int(Pu[2][1, i])]) for i, s in enumerate(ST) if NS[i] > 1}
    R['mean_design_margin'] = dict(R=float((Pu[0][0] * NS).sum() / NS.sum()), D=float((Pu[0][1] * NS).sum() / NS.sum()),
                                   R_hedged=float((Pu[2][0] * NS).sum() / NS.sum()), D_hedged=float((Pu[2][1] * NS).sum() / NS.sum()))
    scen = {}; eq = {}
    def row(o): return dict(D_time=round(o['D_time'], 4), R_time=round(o['R_time'], 4), se=round(o['D_time_se'], 4), R_seats=round(o['R_seats'], 1), sd=round(o['sd_seats'], 1), flips=round(o['flips'], 2))
    scen['national_ban'] = dict(uncoordinated=row(simw(Pu, ban_matrix('national_ban'), seed=1)))
    for name, kind, kw in (('current_bans', 'status_quo', {}), ('no_bans', 'none', {})) + ((('current_bans_decennial_only', 'status_quo', dict(mid_decade=False)),
                           ('current_bans_no_group_shocks', 'status_quo', dict(group_scale=0.0))) if full else ()):
        ban = ban_matrix(kind); o = simw(Pu, ban, seed=1, **kw); e = dict(uncoordinated=row(o), R_maj_by_year=o['R_maj_by_year'].round(3).tolist())
        for label, who in (('both_coordinated', (0, 1)), ('only_R_coordinated', (0,)), ('only_D_coordinated', (1,))):
            if not full and label != 'both_coordinated': continue
            P, pol = coord(ban, Pu, who, **kw); e[label] = row(simw(P, ban, seed=1, **kw)); e[label]['policy'] = pol
            if label == 'both_coordinated': eq[name] = P
        scen[name] = e; print(' ', name, json.dumps(e)[:700], f'[{time.time()-t00:.0f}s]', flush=True)
    for name, ab, who in (('R_all_out_D_abstains', -1, 0), ('D_all_out_R_abstains', 1, 1)):      # one party tries, the other draws neutral maps
        for law in ('none', 'status_quo'):
            ban = ban_matrix(law); e = dict(uncoordinated=row(simw(Pu, ban, seed=1, abstain=ab)))
            P, pol = coord(ban, Pu, (who,), abstain=ab); e['trying_party_coordinated'] = row(simw(P, ban, seed=1, abstain=ab)); e['policy'] = pol
            scen[name + ('_no_bans' if law == 'none' else '_current_bans')] = e; print(' ', name, law, json.dumps(e), f'[{time.time()-t00:.0f}s]', flush=True)
    R['scenarios'] = scen
    if not full: return R
    R['stress'] = stress(inp); b0 = ban_matrix('status_quo'); base = simw(Pu, b0, K=8000); rows = []
    for i, s in enumerate(ST):                      # single-state reforms: add a ban where there is none, lift it where there is one
        if NS[i] == 1: continue
        banned = b0[:, i].all()
        o = simw(Pu, ban_matrix('status_quo', lift=[s]) if banned else ban_matrix('status_quo', extra=[s]), K=8000)
        rows.append(dict(state=s, seats=int(NS[i]), change='lift ban' if banned else 'add ban', dD_time=round(o['D_time'] - base['D_time'], 4), dR_seats=round(o['R_seats'] - base['R_seats'], 2)))
    R['state_reforms'] = rows
    o = simw(Pu, b0, K=8000, detail=True); rs = o['rseats']; val = []      # value of seats beyond the threshold
    fut = np.stack([(rs[:, t+1:t+4] >= 218).mean(1) for t in range(T - 3)], 1); now = rs[:, :T-3]
    for lo in range(170, 266, 8):
        m = (now >= lo) & (now < lo + 8)
        if m.sum() > 200: val.append(dict(R_seats=f'{lo}-{lo+7}', n=int(m.sum()), P_R_majority_next3=round(float(fut[m].mean()), 3)))
    R['value_of_margin'] = val
    R['control'] = {s: dict(R=round(float(o['ctrl'][:, i, 0].mean()), 2), D=round(float(o['ctrl'][:, i, 1].mean()), 2)) for i, s in enumerate(ST) if NS[i] > 1}
    R['legislature_tips'] = {s: dict(upper=inp['tip'][i, 0].round(1).tolist(), lower=inp['tip'][i, 1].round(1).tolist()) for i, s in enumerate(ST)}
    rob = {}
    for label, mod in (('incumbency=0', dict(incumb=0.0)), ('incumbency x2', dict(incumb=2 * inp['theta']['incumb'])),
                       ('state drift halved', dict(sd_drift=inp['theta']['sd_drift'] / 2)), ('national sd x0.7', dict(sd_nat=0.7 * inp['theta']['sd_nat']))):
        i2 = dict(inp); i2['theta'] = dict(inp['theta'], **mod)
        rob[label] = dict(national_ban=row(sim(i2, Pu, ban_matrix('national_ban'), seed=1, **simkw)), current_bans=row(sim(i2, Pu, b0, seed=1, **simkw)), no_bans=row(sim(i2, Pu, ban_matrix('none'), seed=1, **simkw)))
    R['robustness'] = rob
    try:                                            # bootstrap bands from re-estimated shock parameters (policies held fixed)
        with open('data/bootstrap_theta.json') as f: draws = json.load(f)
        runs = dict(national_ban=(Pu, ban_matrix('national_ban'), {}), current_bans=(Pu, b0, {}), no_bans=(Pu, ban_matrix('none'), {}),
                    R_all_out=(Pu, ban_matrix('none'), dict(abstain=-1)), D_all_out=(Pu, ban_matrix('none'), dict(abstain=1)))
        bs = {k: [] for k in runs}
        for d in draws:
            i2 = dict(inp); i2['theta'] = d
            for k, (P, ban, kw) in runs.items(): bs[k].append(sim(i2, P, ban, K=1500, **dict(simkw, **kw))['D_time'])
        R['bootstrap'] = {k: dict(mean=round(float(np.mean(v)), 4), se=round(float(np.std(v)), 4)) for k, v in bs.items()}; R['bootstrap']['n_draws'] = len(draws)
    except FileNotFoundError: pass
    return R

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'final'; out = {}
    if mode == 'rough':                              # first-pass maps only
        worlds = [('actual', load_inputs('data/maps'), {}, True)]
    else:                                            # tentacle-allowed maps (keeping the better of the two sets), plus the two 50-50 exercises
        inp = load_inputs('data/maps_hq', alt_dir='data/maps')
        worlds = [('actual', inp, {}, True), ('national_5050_clean_start', inp, dict(clean_start=True), False),
                  ('every_state_5050', load_inputs('data/maps_hq_even', enacted_floor=False), dict(even_start=True), False)]
    for name, inp, kw, full in worlds:
        assert not inp['missing'], inp['missing']; print(name, flush=True); out[name] = study(inp, kw, full)
    out['theta'] = worlds[0][1]['theta']; out['n_evals'] = NEVAL[0]; out['seconds'] = time.time() - t00
    with open('data/results_rough.json' if mode == 'rough' else 'data/results.json', 'w') as f: json.dump(out, f, indent=1, default=lambda v: v.tolist() if hasattr(v, 'tolist') else str(v))
    print('evaluations', NEVAL[0], 'seconds', round(time.time() - t00))
