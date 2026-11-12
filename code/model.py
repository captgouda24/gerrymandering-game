"""Dynamic gerrymandering game, 2028-2056 (15 House elections), simulated over K shock paths.

Each election on each path: whoever controls a state's redistricting picks a congressional map from that state's
pre-drawn menu (precinct-based; design margin 4/8/12/16, plain or demographically hedged) and redraws both legislative
chambers in its own favor; then national, state-drift, group (Hispanic/Black/Asian) and district shocks are drawn and the
House, governors and legislatures are elected.  Objective: discounted share of Congresses with a House majority.
All margins are R minus D in pct points."""
import json, csv, os, numpy as np
from drawmaps import SEATS, TARGETS, CHAMBERS
ST = sorted(SEATS); S = len(ST); NS = np.array([SEATS[s] for s in ST]); OFF = np.concatenate([[0], np.cumsum(NS)]); ND = int(NS.sum())
T = 15; YEARS = 2028 + 2 * np.arange(T); MID = (YEARS % 4 == 2); CENSUS = np.isin(YEARS, [2032, 2042, 2052])
TG = np.array(TARGETS, float); J = len(TG); SIDX = np.repeat(np.arange(S), NS)
SD_GROUP = np.array([12.0, 4.0, 6.0])   # per-election random-walk sd of each group's margin relative to everyone else (see groups.py)

# ---- institutions after the 2026 elections (+1 R, -1 D, 0 split) ------------------------------------------------------
GOV_R = 'AL AR FL ID IN LA MS MO MT NE NH ND OK SC SD TN UT VT WV WY AK'.split()
LEG_R = 'AL AR FL ID IN IA KS KY LA MS MO MT NE ND OH OK SC SD TN UT WV WY'.split()
LEG_SPLIT = 'GA NC TX AK'.split()
GOV0 = np.array([1 if s in GOV_R else -1 for s in ST]); LEG0 = np.array([1 if s in LEG_R else 0 if s in LEG_SPLIT else -1 for s in ST])
NOVETO = np.isin(ST, ['NC', 'KY'])                       # governor cannot block a map (no veto / simple-majority override)
GOV_PRES_YEAR = np.isin(ST, 'DE IN MO MT NC ND UT WA WV'.split()); GOV_EVERY = np.isin(ST, ['NH', 'VT'])
BAN_ALWAYS = 'AZ CO MI WA ID MT NJ HI NY UT IA PA'.split()  # commissions or court-enforced anti-gerrymandering rules
BAN_FROM_2032 = ['CA', 'VA']                              # Prop 50 and the Virginia amendment expire with the 2030 census
DREW_R = 'AL AR FL GA IN KS KY LA MS MO NE NH NC ND OH OK SC SD TN TX UT WV WY'.split()   # who drew today's legislative maps
DREW_D = 'IL MD MA NV NM OR CT RI DE NY'.split()
LEGMAP0 = np.array([1 if s in DREW_R else -1 if s in DREW_D else 0 for s in ST])

def ban_matrix(kind='status_quo', extra=(), lift=()):    # kind: status_quo | none | national_ban
    b = np.zeros((T, S), bool)
    if kind == 'status_quo':
        b[:, np.isin(ST, BAN_ALWAYS)] = True; b[np.ix_(YEARS >= 2032, np.isin(ST, BAN_FROM_2032))] = True
    elif kind == 'national_ban': b[:] = True
    b[:, np.isin(ST, list(extra))] = True; b[:, np.isin(ST, list(lift))] = False
    return b

def load_inputs(maps_dir='data/maps', enacted_floor=True, alt_dir=None):
    """enacted_floor: where today's enacted map carries more seats at a design margin than our drawn map does, the party's
    menu uses the enacted map instead, so the menu never understates what has already been done."""
    with open('data/smm_fit.json') as fh: th = json.load(fh)['theta']
    nm = NS.max(); menus = np.zeros((S, 2, 2, J, nm)); msh = np.zeros((S, 2, 2, J, nm, 3)); neutral = np.zeros((S, nm)); nsh = np.zeros((S, nm, 3))
    lean = np.zeros(S); ssh = np.zeros((S, 3)); tip = np.zeros((S, 2, 3)); tipsh = np.zeros((S, 2, 3, 3)); missing = []
    for i, s in enumerate(ST):
        n = NS[i]; f = f'{maps_dir}/{s}.json'
        if not os.path.exists(f): missing.append(s); continue
        with open(f) as fh: m = json.load(fh)
        lean[i] = m['statewide']; ssh[i] = m['state_shares']
        if n == 1: neutral[i, 0] = lean[i]; nsh[i, 0] = ssh[i]
        else:
            neutral[i, :n] = m['neutral_one'][0]; nsh[i, :n] = m['neutral_one'][1]
            for p, name in enumerate(('R', 'D')):
                for h, suf in enumerate(('', '_h')):
                    for j, t in enumerate(TARGETS): menus[i, p, h, j, :n] = m[name + suf][str(t)][0]; msh[i, p, h, j, :n] = m[name + suf][str(t)][1]
        for c, ch in enumerate(('upper', 'lower')):     # chamber tipping seats under a neutral, R-drawn, D-drawn map
            tip[i, c] = [m[ch]['neutral_tip'], m[ch]['R_tip'], m[ch]['D_tip']]
            tipsh[i, c] = [m[ch]['neutral_tip_shares'], m[ch]['R_tip_shares'], m[ch]['D_tip_shares']]
    nalt = 0
    if alt_dir:                                           # a second set of drawn maps: keep whichever carries more seats at each design margin
        for i, s in enumerate(ST):
            n = NS[i]; f = f'{alt_dir}/{s}.json'
            if n == 1 or not os.path.exists(f): continue
            with open(f) as fh: m = json.load(fh)
            for p, (name, sg) in enumerate((('R', 1), ('D', -1))):
                for h, suf in enumerate(('', '_h')):
                    for j, t in enumerate(TARGETS):
                        al = np.array(m[name + suf][str(t)][0])
                        if (sg * al >= t).sum() > (sg * menus[i, p, h, j, :n] >= t).sum(): menus[i, p, h, j, :n] = al; msh[i, p, h, j, :n] = m[name + suf][str(t)][1]; nalt += 1
    cur = np.zeros(ND); inc = np.zeros(ND)                # enacted 2026 maps (Cook PVI is in vote-share points -> margin = 2*PVI) and incumbents
    with open('data/house2026_final.csv') as fh: rows = list(csv.DictReader(fh))
    for i, s in enumerate(ST):
        r = sorted([x for x in rows if x['state'] == s], key=lambda x: -float(x['pvi']))
        cur[OFF[i]:OFF[i+1]] = [2 * float(x['pvi']) for x in r]; inc[OFF[i]:OFF[i+1]] = [1 if x['call'] == 'R' else -1 for x in r]
    nfloor = 0
    if enacted_floor:
        for i in range(S):
            n = NS[i]; e = cur[OFF[i]:OFF[i+1]]
            if n == 1 or abs(e.mean() - lean[i]) > 6: continue      # skip if the map set is on a different footing (e.g. rescaled votes)
            for p, sg in ((0, 1), (1, -1)):
                for j, t in enumerate(TARGETS):
                    if (sg * e >= t).sum() > (sg * menus[i, p, 0, j, :n] >= t).sum():
                        for h in (0, 1): menus[i, p, h, j, :n] = e; msh[i, p, h, j, :n] = ssh[i]
                        nfloor += 1
    natsh = (ssh * NS[:, None]).sum(0) / NS.sum()   # seat-weighted ~ population-weighted national shares
    return dict(theta=th, menus=menus, msh=msh, neutral=neutral, nsh=nsh, lean=lean, ssh=ssh, natsh=natsh, cur=cur, inc=inc,
                missing=missing, tip=tip, tipsh=tipsh, n_enacted_floor=nfloor, n_alt=nalt)

def simulate(inp, A, B, H, ban, K=2000, seed=0, mid_decade=True, lam=0.5, sd_gov=8.0, beta=0.95, retire=0.115, group_scale=1.0, abstain=0, clean_start=False, even_start=False, phi=0.8, sd_persist=6.0, detail=False):
    """abstain: +1 / -1 makes that party (R / D) draw neutral maps wherever it controls redistricting; 0 = nobody abstains.
    A (target margin), B (slope on expected adverse swing), H (0 plain / 1 hedged menu): arrays [2 parties (R, D), S].
    A controlling party p targets an effective margin A + B*adv, where adv is the swing against p expected at the coming
    election, and picks the menu map whose design margin, adjusted for the state's drift since the data, is closest."""
    th = inp['theta']; rng = np.random.default_rng(seed); H = H.astype(int)
    sd_nat, mid_pen, pres_pen, rho, sd_dist, incumb, sd_drift, sd_state = (th[k] for k in ('sd_nat', 'mid_pen', 'pres_pen', 'rho', 'sd_dist', 'incumb', 'sd_drift', 'sd_state'))
    pres = np.ones(K); x = np.full(K, -13.4 + pres_pen + mid_pen)             # 2026: R president, D+13.4 House vote
    drift = np.zeros((K, S)); fg = np.zeros((K, 3)); gov = np.tile(GOV0, (K, 1)).astype(float); leg = np.tile(LEG0, (K, 1)).astype(float)
    legmap = np.tile(LEGMAP0, (K, 1)).astype(float)
    off = np.tile(inp['cur'] - inp['lean'][SIDX], (K, 1))                     # district lean minus state lean
    sh = np.tile(inp['ssh'][SIDX] - inp['natsh'], (K, 1, 1))                  # district group shares minus national shares
    inc = np.tile(inp['inc'], (K, 1)); incw = np.ones((K, ND))                # incumbency weight (lam right after a redraw)
    pd_ = np.zeros((K, ND)); sd_iid = np.sqrt(max(sd_dist ** 2 - sd_persist ** 2 * (1 - phi), 1.0))   # persistent + one-off district shocks, same swing variance
    if clean_start or even_start:                                            # symmetric start: coin-flip president, no carried-over wave, no incumbents
        pres = np.where(rng.random(K) < 0.5, 1.0, -1.0); x = np.zeros(K); inc[:] = 0
    if even_start:                                                           # also: neutral maps everywhere and coin-flip state governments
        off = np.tile((inp['neutral'] - inp['lean'][:, None])[SIDX, np.arange(ND) - OFF[:-1][SIDX]], (K, 1)); sh = np.tile((inp['nsh'] - inp['natsh'])[SIDX, np.arange(ND) - OFF[:-1][SIDX]], (K, 1, 1))
        gov = np.where(rng.random((K, S)) < 0.5, 1.0, -1.0); leg = np.where(rng.random((K, S)) < 0.5, 1.0, -1.0); legmap[:] = 0
    drawn = np.zeros((K, S)); cur_j = -2 * np.ones((K, S), int)                 # -2 = today's enacted map, -1 = neutral map
    leg_path = np.zeros((K, T, S), np.int8) if detail else None; gov_path = np.zeros((K, T, S), np.int8) if detail else None; env_path = np.zeros((K, T, S), np.float32) if detail else None
    pres_path = np.zeros((K, T)); rseats = np.zeros((K, T)); ctrl_log = np.zeros((T, S, 2)); disc = beta ** np.arange(T)
    own_seats = np.zeros((2, S)); own_time = np.zeros((2, S)); lockout = []
    rel_menu = inp['menus'] - inp['lean'][:, None, None, None, None]; rel_neu = inp['neutral'] - inp['lean'][:, None]
    msh = inp['msh'] - inp['natsh']; nsh = inp['nsh'] - inp['natsh']; ssh = inp['ssh'] - inp['natsh']
    tipsh = inp['tipsh'] - inp['ssh'][:, None, None, :]; sidx = np.arange(S)[None, :]
    for t in range(T):
        en = -pres * (pres_pen + mid_pen * MID[t]) + rho * x                    # expected national environment
        ctrl = np.where((leg != 0) & ((gov == leg) | NOVETO[None, :]), leg, 0.0); ctrl[:, ban[t]] = 0
        fair = (ctrl == abstain) & (abstain != 0)                                # an abstaining party draws neutral maps when it holds the pen
        ctrl = np.where(fair, 0.0, ctrl)
        legmap = np.where(ctrl != 0, ctrl, legmap); legmap[:, ban[t]] = 0        # whoever holds the pen redraws the legislature too
        legmap = np.where(fair, 0.0, legmap)
        if CENSUS[t]: legmap = np.where(ctrl == 0, 0.0, legmap)
        for s in range(S):
            n = NS[s]
            if n == 1: continue
            sl = slice(OFF[s], OFF[s+1]); c = ctrl[:, s]; p = (c < 0).astype(int)   # party index 0=R, 1=D
            tgt = A[p, s] + B[p, s] * (-c * en)
            j = np.abs(TG[None, :] + (c * drift[:, s])[:, None] - tgt[:, None]).argmin(1)
            can = (c != 0) & (mid_decade | CENSUS[t] | (t == 0))
            redo = can & ((drawn[:, s] != c) | (cur_j[:, s] != j) | CENSUS[t])
            neu = (c == 0) & (CENSUS[t] | (ban[t, s] & (t > 0) & ~ban[t-1, s]) | (fair[:, s] & (cur_j[:, s] != -1)))
            if redo.any():
                hh = H[p[redo], s]
                off[redo, sl] = rel_menu[s, p[redo], hh, j[redo], :n]; sh[redo, sl] = msh[s, p[redo], hh, j[redo], :n]
                drawn[redo, s] = c[redo]; cur_j[redo, s] = j[redo]
            if neu.any():
                off[neu, sl] = rel_neu[s, :n]; sh[neu, sl] = nsh[s, :n]; drawn[neu, s] = 0; cur_j[neu, s] = -1
            ch = redo | neu
            if ch.any():
                inc[ch, sl] = -np.sort(-inc[ch, sl], axis=1); incw[ch, sl] = lam; pd_[ch, sl] = 0   # new lines: local drift is reset   # incumbents keep the friendliest seats, lose some bonus
        x = rho * x + rng.normal(0, sd_nat, K); nat = -pres * (pres_pen + mid_pen * MID[t]) + x
        drift += rng.normal(0, sd_drift, (K, S)); fg += rng.normal(0, 1, (K, 3)) * SD_GROUP * group_scale
        env = inp['lean'][None, :] + drift + nat[:, None] + rng.normal(0, max(sd_state, 1e-9), (K, S)) + fg @ ssh.T   # statewide R margin
        m = env[:, SIDX] - (fg @ ssh.T)[:, SIDX] + off + np.einsum('kdg,kg->kd', sh, fg) + incumb * inc * incw + pd_ + rng.normal(0, sd_iid, (K, ND))
        pd_ = phi * pd_ + rng.normal(0, sd_persist * np.sqrt(1 - phi ** 2), (K, ND))
        win = np.where(m > 0, 1.0, -1.0); rseats[:, t] = (win > 0).sum(1)
        seats_s = np.add.reduceat((win > 0), OFF[:-1], axis=1)
        for pi, sg in ((0, 1), (1, -1)):
            mask = (drawn == sg); own = seats_s if sg == 1 else NS[None, :] - seats_s
            own_seats[pi] += disc[t] * (mask * own).sum(0); own_time[pi] += disc[t] * mask.sum(0); ctrl_log[t, :, pi] = (ctrl == sg).mean(0)
        inc = np.where(rng.random((K, ND)) < retire, 0.0, win); incw[:] = 1.0
        if not MID[t]: pres = np.where(nat + rng.normal(0, 2, K) > 0, 1.0, -1.0)
        pres_path[:, t] = pres                                                   # president serving alongside the House just elected
        gyr = (MID[t] & ~GOV_PRES_YEAR) | (~MID[t] & GOV_PRES_YEAR) | GOV_EVERY
        gov = np.where(gyr[None, :], np.where(env + rng.normal(0, sd_gov, (K, S)) > 0, 1.0, -1.0), gov)
        bi = np.where(legmap > 0, 1, np.where(legmap < 0, 2, 0)); common = rng.normal(0, 2, (K, S))   # each chamber is decided by its tipping seat
        up = env + inp['tip'][sidx, 0, bi] + np.einsum('ksg,kg->ks', tipsh[sidx, 0, bi], fg) + common + rng.normal(0, 2, (K, S)) > 0
        lo = env + inp['tip'][sidx, 1, bi] + np.einsum('ksg,kg->ks', tipsh[sidx, 1, bi], fg) + common + rng.normal(0, 2, (K, S)) > 0
        leg = np.where(up & lo, 1.0, np.where(~up & ~lo, -1.0, 0.0))
        if detail: leg_path[:, t] = leg; gov_path[:, t] = gov; env_path[:, t] = env    # legislature and governor after this election; statewide R margin
    rmaj = rseats >= 218; w = disc / disc.sum()
    out = dict(R_time=float((rmaj * w).sum(1).mean()), D_time=float(((~rmaj) * w).sum(1).mean()), R_seats=float(rseats.mean()),
               sd_seats=float(rseats.std()), flips=float((np.diff(rmaj.astype(int), axis=1) != 0).sum(1).mean()),
               D_time_se=float(((~rmaj) * w).sum(1).std() / np.sqrt(K)),
               R_maj_by_year=rmaj.mean(0), own_seats=own_seats / np.maximum(own_time, 1e-9), own_time=own_time / (K * disc.sum()), ctrl=ctrl_log)
    if detail: out.update(rseats=rseats, pres=pres_path, leg=leg_path, gov=gov_path, env=env_path)
    return out

def const_policy(aR, bR, hR, aD, bD, hD):
    A = np.zeros((2, S)); B = np.zeros((2, S)); H = np.zeros((2, S), int); A[0] = aR; A[1] = aD; B[0] = bR; B[1] = bD; H[0] = hR; H[1] = hD
    return A, B, H
