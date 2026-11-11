"""Download Dave's Redistricting precinct (VTD) data for every state: census population, election results, adjacency graph.
Output: data/vtd/{ST}.npz with pop, votes and an edge list."""
import re, io, json, zipfile, urllib.request, numpy as np, pandas as pd, concurrent.futures as cf, sys, os
files = open('data/vtd_files.txt').read().split()
BASE = 'https://raw.githubusercontent.com/dra2020/vtd_data/master/'
def latest(st, kind):
    c = [f for f in files if re.fullmatch(rf'2020_VTD/{st}/{kind}_{st}\.v\d+\.zip', f)]
    return sorted(c, key=lambda f: int(re.search(r'v(\d+)', f).group(1)))[-1]
def fetch(path):
    for _ in range(4):
        try: return urllib.request.urlopen(BASE + path, timeout=180).read()
        except Exception as e: err = e
    raise err
def one(st):
    out = f'data/vtd/{st}.npz'
    if os.path.exists(out): return st, 'cached'
    ze = zipfile.ZipFile(io.BytesIO(fetch(latest(st, 'Election_Data'))))
    zd = zipfile.ZipFile(io.BytesIO(fetch(latest(st, 'Demographic_Data'))))
    zg = zipfile.ZipFile(io.BytesIO(fetch(latest(st, 'Geojson'))))
    e = pd.read_csv(ze.open([n for n in ze.namelist() if n.endswith('.csv')][0]), dtype={'GEOID20': str}).set_index('GEOID20')
    d = pd.read_csv(zd.open([n for n in zd.namelist() if n.endswith('.csv')][0]), dtype={'GEOID20': str}).set_index('GEOID20')
    g = json.load(zg.open([n for n in zg.namelist() if n.endswith('graph.json')][0]))
    ids = [i for i in d.index if i in g]
    idx = {v: i for i, v in enumerate(ids)}
    edges = sorted({(min(idx[a], idx[b]), max(idx[a], idx[b])) for a in ids for b in g[a] if b in idx and b != a})
    e = e.reindex(ids).fillna(0); d = d.reindex(ids).fillna(0)
    arr = dict(pop=d['T_20_CENS_Total'].values.astype(float), edges=np.array(edges, dtype=np.int32), ids=np.array(ids))
    for c in ('T_20_CENS_White', 'T_20_CENS_Hispanic', 'T_20_CENS_Black', 'T_20_CENS_Asian'):
        if c in d: arr[c[10:].lower()] = d[c].values.astype(float)
    have = []
    for tag in ('E_24_PRES', 'E_20_PRES', 'E_16_PRES', 'E_20-24_COMP', 'E_16-22_COMP', 'E_16-20_COMP'):
        if tag + '_Dem' in e:
            k = tag[2:].replace('-', '_').lower(); arr[k + '_d'] = e[tag + '_Dem'].values.astype(float); arr[k + '_r'] = e[tag + '_Rep'].values.astype(float); have.append(k)
    np.savez_compressed(out, **arr)
    return st, f"{len(ids)} units, {len(edges)} edges, pop {arr['pop'].sum():,.0f}, elections {have}"
if __name__ == '__main__':
    states = sorted({f.split('/')[1] for f in files if f.startswith('2020_VTD/') and f.count('/') == 2})
    states = [s for s in states if len(s) == 2 and s not in ('DC', 'PR')]
    with cf.ThreadPoolExecutor(6) as ex:
        for st, msg in ex.map(lambda s: (lambda: one(s))() if True else None, states): print(st, msg, flush=True)
