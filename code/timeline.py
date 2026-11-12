"""Who is in charge over time: for every world and scenario, the chance each party holds the House, the presidency and
both, election by election, plus who holds the redistricting pen in each state.  Writes data/timeline.json."""
import sys, json, numpy as np
sys.path.insert(0, 'code')
from model import *
import run
K = 8000; YEARS = [2028 + 2 * t for t in range(T)]
inp = load_inputs('data/maps_hq', alt_dir='data/maps')
WORLDS = [('actual', inp, {}), ('national_5050_clean_start', inp, dict(clean_start=True)),
          ('every_state_5050', load_inputs('data/maps_hq_even', enacted_floor=False), dict(even_start=True))]
SCEN = [('national_ban', 'national_ban', 0), ('current_bans', 'status_quo', 0), ('no_bans', 'none', 0),
        ('R_all_out_D_abstains_no_bans', 'none', -1), ('D_all_out_R_abstains_no_bans', 'none', 1),
        ('R_all_out_D_abstains_current_bans', 'status_quo', -1), ('D_all_out_R_abstains_current_bans', 'status_quo', 1)]
out = dict(years=YEARS, states=[s for s in ST], seats=[int(n) for n in NS], worlds={})
for wname, wi, kw in WORLDS:
    Pu, _ = run.uncoordinated(wi, **kw); W = {}
    for sname, law, ab in SCEN:
        o = simulate(wi, *Pu, ban_matrix(law), K=K, seed=1, abstain=ab, detail=True, **kw); rs = o['rseats']; rm = rs >= 218; rp = o['pres'] > 0
        run_len = []                                  # length of each unbroken spell of one party holding the House
        for k in range(K):
            cut = np.flatnonzero(np.diff(rm[k].astype(int))) + 1; run_len += np.diff(np.concatenate([[0], cut, [T]])).tolist()
        W[sname] = dict(R_house=rm.mean(0).round(3).tolist(), R_pres=rp.mean(0).round(3).tolist(), R_both=(rm & rp).mean(0).round(3).tolist(),
                        D_both=(~rm & ~rp).mean(0).round(3).tolist(), R_seats_mean=rs.mean(0).round(1).tolist(),
                        R_seats_p10=np.percentile(rs, 10, 0).tolist(), R_seats_p90=np.percentile(rs, 90, 0).tolist(),
                        mean_spell_elections=round(float(np.mean(run_len)), 2), share_paths_one_party_whole_period=round(float((rm.all(1) | (~rm).all(1)).mean()), 3),
                        pen_seats_R=(o['ctrl'][:, :, 0] * NS * (NS > 1)).sum(1).round(1).tolist(), pen_seats_D=(o['ctrl'][:, :, 1] * NS * (NS > 1)).sum(1).round(1).tolist(),
                        pen_R=o['ctrl'][:, :, 0].round(2).T.tolist(), pen_D=o['ctrl'][:, :, 1].round(2).T.tolist())
        print(wname, sname, 'R House by year', W[sname]['R_house'], flush=True)
    out['worlds'][wname] = W
with open('data/timeline.json', 'w') as f: json.dump(out, f)
