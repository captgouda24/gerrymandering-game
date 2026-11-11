"""Draw maps on real precinct data (Dave's Redistricting VTD files): contiguous districts of near-equal population.
Congress:      neutral ensemble + for each party a menu of gerrymanders at design margins 4/8/12/16 (short-burst ReCom
               maximizing the number of seats carried by at least that margin).  Population within 1% of ideal.
Legislatures:  for each chamber, neutral ensemble + each party's gerrymander maximizing the lean of the TIPPING seat (the
               seat that decides the majority), i.e. the statewide swing the majority can survive.  Within 5% of ideal.
Leans are R minus D, pct points, relative to the nation, averaging the 2020 and 2024 presidential results.
Output: data/maps/{ST}.json"""
import sys, json, time, os, random, functools, numpy as np, networkx as nx
from gerrychain import Graph, Partition, MarkovChain, constraints, accept
from gerrychain.updaters import Tally
from gerrychain.proposals import recom
from gerrychain.tree import recursive_tree_part
from gerrychain.optimization import SingleMetricOptimizer

NAT = {'24': 1.5, '20': -4.5}          # national two-party presidential margin, R minus D
SEATS = dict(AL=7, AK=1, AZ=9, AR=4, CA=52, CO=8, CT=5, DE=1, FL=28, GA=14, HI=2, ID=2, IL=17, IN=9, IA=4, KS=4, KY=6, LA=6,
             ME=2, MD=8, MA=9, MI=13, MN=8, MS=4, MO=8, MT=2, NE=3, NV=4, NH=2, NJ=12, NM=3, NY=26, NC=14, ND=1, OH=15, OK=5,
             OR=6, PA=17, RI=2, SC=7, SD=1, TN=9, TX=38, UT=4, VT=1, VA=11, WA=10, WV=2, WI=8, WY=1)
# (upper, lower) chamber districts. Where the lower house is elected from the senate districts (multi-member), both use that map.
CHAMBERS = dict(AL=(35, 105), AK=(20, 40), AZ=(30, 30), AR=(35, 100), CA=(40, 80), CO=(35, 65), CT=(36, 151), DE=(21, 41), FL=(40, 120),
                GA=(56, 180), HI=(25, 51), ID=(35, 35), IL=(59, 118), IN=(50, 100), IA=(50, 100), KS=(40, 125), KY=(38, 100), LA=(39, 105),
                ME=(35, 151), MD=(47, 47), MA=(40, 160), MI=(38, 110), MN=(67, 134), MS=(52, 122), MO=(34, 163), MT=(50, 100), NE=(49, 49),
                NV=(21, 42), NH=(24, 400), NJ=(40, 40), NM=(42, 70), NY=(63, 150), NC=(50, 120), ND=(47, 47), OH=(33, 99), OK=(48, 101),
                OR=(30, 60), PA=(50, 203), RI=(38, 75), SC=(46, 124), SD=(35, 35), TN=(33, 99), TX=(31, 150), UT=(29, 75), VT=(30, 150),
                VA=(40, 100), WA=(49, 49), WV=(34, 100), WI=(33, 99), WY=(31, 62))
TARGETS = (4, 8, 12, 16)                # congressional design margins on the seats-vs-safety frontier
MIN_UNITS = 6                           # a chamber is drawn with at most (precincts / 6) districts (binds for NH, VT, ME, ... lower houses)

def load_graph(st, ndist, units_per_district):
    """Precinct adjacency graph, with precincts merged into contiguous within-county blocks of about
    1/units_per_district of a district (breadth-first growth up to a population cap). Rough but fast."""
    z = np.load(f'data/vtd/{st}.npz', allow_pickle=True)
    n = len(z['pop']); g = nx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(map(tuple, z['edges']))
    comps = sorted(nx.connected_components(g), key=len, reverse=True)   # stitch islands to the nearest-index mainland unit
    main = np.array(sorted(comps[0]))
    for c in comps[1:]:
        a = min(c); g.add_edge(a, int(main[np.argmin(np.abs(main - a))]))
    cols = dict(pop=z['pop'], d24=z['24_pres_d'], r24=z['24_pres_r'], d20=z['20_pres_d'], r20=z['20_pres_r'],
                hisp=z['hispanic'], black=z['black'], asian=z['asian'])
    cap = z['pop'].sum() / ndist / units_per_district; county = np.array([i[:5] for i in z['ids']]); label = -np.ones(n, int); nxt = 0
    for v in sorted(range(n), key=lambda v: g.degree[v]):
        if label[v] >= 0: continue
        label[v] = nxt; tot = z['pop'][v]; frontier = [v]
        while frontier and tot < cap:
            u = frontier.pop(0)
            for w in g[u]:
                if label[w] < 0 and county[w] == county[v] and tot + z['pop'][w] <= 1.3 * cap:
                    label[w] = nxt; tot += z['pop'][w]; frontier.append(w)
        nxt += 1
    k = label.max() + 1; h = nx.Graph(); h.add_nodes_from(range(k))
    le = label[np.array(g.edges)]; h.add_edges_from({(int(a), int(b)) for a, b in le if a != b})
    agg = {c: np.bincount(label, weights=v, minlength=k) for c, v in cols.items()}
    for i in range(k): h.nodes[i].update({c: float(agg[c][i]) for c in agg})
    return Graph.from_networkx(h), z, n

def leans(part):
    out = []
    for k in part.parts:
        l24 = 100 * (part['r24'][k] - part['d24'][k]) / max(part['r24'][k] + part['d24'][k], 1) - NAT['24']
        l20 = 100 * (part['r20'][k] - part['d20'][k]) / max(part['r20'][k] + part['d20'][k], 1) - NAT['20']
        out.append(0.5 * (l24 + l20))
    return np.array(out)

GROUPS = ('hisp', 'black', 'asian'); HEDGE = np.array([15.0, 6.0, 8.0])   # adverse group swings a hedged map must survive (pct pts)

def shares(part):
    """District population shares of each group, in the same order as leans(part)."""
    return np.array([[part[g][k] / max(part['pop'][k], 1) for g in GROUPS] for k in part.parts])

def sorted_map(part):
    l = leans(part); o = np.argsort(-l); return l[o].round(2).tolist(), shares(part)[o].round(3).tolist()

def statewide(z):
    f = lambda y: (z[f'{y}_pres_r'].sum() - z[f'{y}_pres_d'].sum()) / (z[f'{y}_pres_r'].sum() + z[f'{y}_pres_d'].sum()) * 100 - NAT[y]
    return float(0.5 * (f('24') + f('20')))

def seats_score(sign, m):               # congressional: seats carried by >= m, with partial credit for the next one
    def score(part):
        l = np.sort(sign * leans(part))[::-1]; won = int((l >= m).sum()); nxt = l[won] if won < len(l) else m
        return won + float(np.clip((nxt - (m - 30)) / 30, 0, 0.999))
    return score

def hedged_score(sign, m):              # like seats_score, but a seat only counts if it survives the worst single-group swing
    def score(part):
        l = np.sort(sign * leans(part) - (shares(part) * HEDGE).max(1))[::-1]; won = int((l >= m).sum()); nxt = l[won] if won < len(l) else m
        return won + float(np.clip((nxt - (m - 30)) / 30, 0, 0.999))
    return score

def tipping(l, sign):                   # lean (for party `sign`) of the seat that delivers a majority
    return float(np.sort(sign * l)[::-1][len(l) // 2])

def tipping_score(sign):                # legislative: the tipping seat, with a little weight on the two seats behind it
    def score(part):
        l = np.sort(sign * leans(part))[::-1]; k = len(l) // 2
        return float(l[k] + 0.05 * l[min(k + 1, len(l) - 1)] + 0.02 * l[min(k + 2, len(l) - 1)])
    return score

def setup(st, ndist, eps, upd_units):
    g, z, nprec = load_graph(st, ndist, upd_units); ideal = z['pop'].sum() / ndist
    upd = {k: Tally(k) for k in ('pop', 'd24', 'r24', 'd20', 'r20', 'hisp', 'black', 'asian')}
    init = Partition(g, recursive_tree_part(g, range(ndist), ideal, 'pop', eps * 0.9), upd)
    prop = functools.partial(recom, pop_col='pop', pop_target=ideal, epsilon=eps, node_repeats=1)
    return z, init, prop, [constraints.within_percent_of_ideal_population(init, eps, 'pop')], len(g.nodes)

def neutral_chain(init, prop, cons, steps):
    samp = []; last = init
    for i, p in enumerate(MarkovChain(prop, cons, accept.always_accept, init, steps)):
        if i >= steps // 3 and i % 4 == 0: samp.append(np.sort(leans(p))[::-1])
        last = p
    return samp, last

def optimize(prop, cons, start, score, bursts, burst_len=10):
    opt = SingleMetricOptimizer(prop, cons, start, score, maximize=True)
    for _ in opt.short_bursts(burst_len, bursts): pass
    return opt.best_part

def run_congress(st, verbose=False):
    N = SEATS[st]; t0 = time.time()
    if N == 1:
        z = np.load(f'data/vtd/{st}.npz', allow_pickle=True); return dict(seats=1, neutral=[statewide(z)], R={}, D={}, R_h={}, D_h={})
    z, init, prop, cons, nn = setup(st, N, 0.01, 150)
    samp, last = neutral_chain(init, prop, cons, 300)
    res = dict(seats=N, nodes=nn, neutral=np.mean(samp, axis=0).round(2).tolist(), R={}, D={}, R_h={}, D_h={})
    res['neutral_one'] = sorted_map(last)                 # one representative neutral map with its demographics
    for name, sign in (('R', 1), ('D', -1)):
        start = last
        for m in TARGETS:
            start = optimize(prop, cons, start, seats_score(sign, m), bursts=int(min(150, max(100, 12 * N))))
            res[name][str(m)] = sorted_map(start); l = np.array(res[name][str(m)][0])
            hed = optimize(prop, cons, start, hedged_score(sign, m), bursts=int(min(100, max(60, 8 * N))))
            res[name + '_h'][str(m)] = sorted_map(hed)
            if verbose: print(st, name, m, int((sign * l >= m).sum()), '/', N, 'hedged', int((sign * np.array(res[name + '_h'][str(m)][0]) >= m).sum()), f'{time.time()-t0:.0f}s', flush=True)
    res['seconds'] = round(time.time() - t0); return res

def run_chamber(st, ndist_true, verbose=False):
    """If no balanced cut is found, retry with finer building blocks; only as a last resort draw 30% fewer districts."""
    nprec = len(np.load(f'data/vtd/{st}.npz', allow_pickle=True)['pop']); N = int(min(ndist_true, nprec // MIN_UNITS))
    while True:
        for units in (40, 80, 160):
            try: return _run_chamber(st, ndist_true, N, units, verbose)
            except RuntimeError: pass
        N = int(N * 0.7)

def _run_chamber(st, ndist_true, N, units=40, verbose=False):
    t0 = time.time()
    z, init, prop, cons, nn = setup(st, N, 0.05, units); sw = statewide(z)
    samp, last = neutral_chain(init, prop, cons, int(min(600, max(200, 4 * N))))
    def tipsh(p, sign):
        l = sign * leans(p); return shares(p)[np.argsort(-l)[len(l) // 2]].round(3).tolist()
    res = dict(districts_true=ndist_true, districts_drawn=N, nodes=nn, neutral_tip_shares=tipsh(last, 1),
               neutral_tip=float(np.mean([tipping(s, 1) for s in samp]) - sw))       # tipping-seat R lean minus statewide R lean
    for name, sign in (('R', 1), ('D', -1)):
        best = optimize(prop, cons, last, tipping_score(sign), bursts=int(min(800, max(150, 6 * N))))
        res[name + '_tip'] = sign * tipping(leans(best), sign) - sw              # stored as R-lean offset
        res[name + '_tip_shares'] = tipsh(best, sign)
    res['seconds'] = round(time.time() - t0)
    if verbose: print(st, ndist_true, res, flush=True)
    return res

def run_state(st, verbose=False):
    random.seed(0); np.random.seed(0)
    z = np.load(f'data/vtd/{st}.npz', allow_pickle=True)
    pop = z['pop'].sum(); res = dict(state=st, statewide=statewide(z), state_shares=[float(z[g].sum() / pop) for g in ('hispanic', 'black', 'asian')])
    res.update(run_congress(st, verbose))
    up, lo = CHAMBERS[st]; res['upper'] = run_chamber(st, up, verbose)
    res['lower'] = dict(res['upper']) if lo == up else run_chamber(st, lo, verbose)
    os.makedirs('data/maps', exist_ok=True)
    with open(f'data/maps/{st}.json', 'w') as f: json.dump(res, f)
    return res

if __name__ == '__main__':
    t = time.time(); r = run_state(sys.argv[1], verbose=True)
    print('neutral', np.round(r['neutral'], 0).astype(int).tolist()); print('upper', r['upper']); print('lower', r['lower']); print('total', round(time.time() - t), 's')
