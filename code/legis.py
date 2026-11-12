"""Control of state legislatures over time, by world and scenario.  A party "holds the legislature" when it wins both
chambers.  Writes data/legislatures.json."""
import sys, json, numpy as np
sys.path.insert(0, 'code')
from model import *
import run
K = 6000; YEARS = [2028 + 2 * t for t in range(T)]
inp = load_inputs('data/maps_hq', alt_dir='data/maps')
WORLDS = [('actual', inp, {}), ('every_state_5050', load_inputs('data/maps_hq_even', enacted_floor=False), dict(even_start=True))]
SCEN = [('national_ban', 'national_ban', 0), ('current_bans', 'status_quo', 0), ('no_bans', 'none', 0), ('R_all_out_D_abstains_no_bans', 'none', -1), ('D_all_out_R_abstains_no_bans', 'none', 1)]
def spells(a):                                       # a: [K, T] in {-1, 0, 1}; mean length of unbroken spells of one party holding the legislature
    out = []
    for sg in (1, -1):
        h = (a == sg).astype(np.int8); p = np.concatenate([np.zeros((len(h), 1), np.int8), h, np.zeros((len(h), 1), np.int8)], 1); d = np.diff(p, axis=1)
        n = (d == 1).sum(); out.append(float(h.sum() / max(n, 1)))
    return out
out = dict(years=YEARS, states=list(ST), worlds={})
for wname, wi, kw in WORLDS:
    Pu, _ = run.uncoordinated(wi, **kw); W = {}
    for sname, law, ab in SCEN:
        o = simulate(wi, *Pu, ban_matrix(law), K=K, seed=1, abstain=ab, detail=True, **kw); leg = o['leg']; gov = o['gov']; rv = o['env'] > 0
        R = leg == 1; D = leg == -1; wrong = (R & ~rv) | (D & rv)        # the party holding the legislature lost the statewide vote that year
        keepR = (R[:, 1:] & R[:, :-1]).sum((0, 1)) / np.maximum(R[:, :-1].sum((0, 1)), 1); keepD = (D[:, 1:] & D[:, :-1]).sum((0, 1)) / np.maximum(D[:, :-1].sum((0, 1)), 1)
        st = {}
        for i, s in enumerate(ST):
            sp = spells(leg[:, :, i])
            st[s] = dict(R=round(float(R[:, :, i].mean()), 3), D=round(float(D[:, :, i].mean()), 3), wrong=round(float(wrong[:, :, i].mean()), 3),
                         R_trifecta=round(float((R[:, :, i] & (gov[:, :, i] == 1)).mean()), 3), D_trifecta=round(float((D[:, :, i] & (gov[:, :, i] == -1)).mean()), 3),
                         keep_R=round(float(keepR[i]), 3), keep_D=round(float(keepD[i]), 3), spell_R=round(sp[0], 2), spell_D=round(sp[1], 2),
                         whole_period=round(float((R[:, :, i].all(1) | D[:, :, i].all(1)).mean()), 3), R_by_year=R[:, :, i].mean(0).round(3).tolist(), D_by_year=D[:, :, i].mean(0).round(3).tolist())
        W[sname] = dict(states=st, n_R=R.sum(2).mean(0).round(1).tolist(), n_D=D.sum(2).mean(0).round(1).tolist(), wrong=round(float(wrong.mean()), 3),
                        wrong_R=round(float((R & ~rv).mean()), 3), wrong_D=round(float((D & rv).mean()), 3),
                        keep=round(float(((R[:, 1:] & R[:, :-1]) | (D[:, 1:] & D[:, :-1])).sum() / (R | D)[:, :-1].sum()), 3),
                        whole_period=round(float((R.all(1) | D.all(1)).mean()), 3))
        print(wname, sname, 'legislatures R', W[sname]['n_R'][::3], 'D', W[sname]['n_D'][::3], 'wrong-winner', W[sname]['wrong'], W[sname]['wrong_R'], W[sname]['wrong_D'], 'keep', W[sname]['keep'], 'whole', W[sname]['whole_period'], flush=True)
    out['worlds'][wname] = W
with open('data/legislatures.json', 'w') as f: json.dump(out, f)
