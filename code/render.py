"""Render every congressional map: one page per state for the plain maps (neutral + each party at 4 design margins) and one
for the hedged maps.  Precincts are coloured by the lean of the district they belong to; black lines are district borders.
Output: data/maps_png/{ST}_plain.png, {ST}_hedged.png and data/all_maps.pdf.  Shapes: Census TIGER 2020 VTDs / block groups."""
import sys, os, io, json, zipfile, urllib.request, numpy as np, shapefile, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, 'code')
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, LineCollection
from matplotlib.backends.backend_pdf import PdfPages
from shapely.geometry import shape
from shapely.ops import unary_union
from drawmaps import SEATS, TARGETS
import flip, drawhq
FIPS = dict(AL='01', AK='02', AZ='04', AR='05', CA='06', CO='08', CT='09', DE='10', FL='12', GA='13', HI='15', ID='16', IL='17', IN='18', IA='19',
            KS='20', KY='21', LA='22', ME='23', MD='24', MA='25', MI='26', MN='27', MS='28', MO='29', MT='30', NE='31', NV='32', NH='33', NJ='34',
            NM='35', NY='36', NC='37', ND='38', OH='39', OK='40', OR='41', PA='42', RI='44', SC='45', SD='46', TN='47', TX='48', UT='49', VT='50',
            VA='51', WA='53', WV='54', WI='55', WY='56')
NAMES = dict(TX='Texas', CA='California', FL='Florida', NY='New York', PA='Pennsylvania', IL='Illinois', OH='Ohio', GA='Georgia', NC='North Carolina', MI='Michigan')
BG = ('CA', 'HI', 'OR', 'WV')

def shapes(st):
    path = f'data/shp/{st}.zip'
    if not os.path.exists(path):
        f = FIPS[st]; url = (f'https://www2.census.gov/geo/tiger/TIGER2020/BG/tl_2020_{f}_bg.zip' if st in BG else f'https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/VTD/2020/tl_2020_{f}_vtd20.zip')
        os.makedirs('data/shp', exist_ok=True); open(path, 'wb').write(urllib.request.urlopen(url, timeout=600).read())
    r = shapefile.Reader(path); key = 'GEOID' if st in BG else 'GEOID20'; out = {}
    for sr in r.iterShapeRecords():
        try: out[sr.record[key]] = shape(sr.shape.__geo_interface__).simplify(0.002)
        except Exception: pass
    return out

def rings(g):
    if g.is_empty: return []
    gs = g.geoms if hasattr(g, 'geoms') else [g]
    return [np.asarray(p.exterior.coords) for p in gs if p.geom_type == 'Polygon' and not p.is_empty]

def panel(ax, geoms, assign, V, N, title, sign=None, m=None):
    sums = flip.district_sums(assign, V, N); lean = flip.leans_of(sums); polys = []; cols = []
    for i, g in enumerate(geoms):
        if g is None: continue
        for r in rings(g): polys.append(r); cols.append(lean[assign[i]])
    ax.add_collection(PolyCollection(polys, array=np.clip(cols, -30, 30), cmap='RdBu_r', clim=(-30, 30), edgecolors='none', rasterized=True))
    lines = []
    for d in range(N):
        mem = [geoms[i] for i in np.where(assign == d)[0] if geoms[i] is not None]
        if mem:
            u = unary_union(mem); us = u.geoms if hasattr(u, 'geoms') else [u]
            lines += [np.asarray(p.exterior.coords) for p in us if p.geom_type == 'Polygon']
    ax.add_collection(LineCollection(lines, colors='k', linewidths=0.35))
    ax.autoscale(); ax.set_aspect(1.25); ax.axis('off')
    r_seats = int((lean > 0).sum()); sub = f'{r_seats} R-leaning, {N - r_seats} D-leaning'
    if sign: sub += f'; {int((sign * lean >= m).sum())} carried by {m}+ pts'
    ax.set_title(f'{title}\n{sub}', fontsize=7)

def render(st, pdf):
    az = np.load(f'data/assign/{st}.npz', allow_pickle=True); ids = az['ids']; N = SEATS[st]; _, V, _, _ = drawhq.raw(st); sh = shapes(st)
    geoms = [sh.get(i) for i in ids]; found = sum(g is not None for g in geoms) / len(ids)
    note = '' if bool(az['matches_final_run']) else '  [regenerated map differs slightly from the one used in the results]'
    for kind, suf in (('plain', ''), ('hedged against group swings', '_h')):
        keys = [('Neutral (random contiguous map)', 'neutral', None, None)] if not suf else []
        keys += [(f'{pn} draw, {m}-pt design', f'{p}{suf}_{m}', sg, m) for p, pn, sg in (('R', 'Republican', 1), ('D', 'Democratic', -1)) for m in TARGETS]
        fig, axes = plt.subplots(3, 3, figsize=(11, 8.5)); axes = axes.ravel()
        for ax in axes: ax.axis('off')
        for ax, (title, k, sg, m) in zip(axes, keys): panel(ax, geoms, az[k].astype(np.int64), V, N, title, sg, m)
        fig.suptitle(f'{st}: {N} districts, {kind} maps. Colour = district lean (red Republican, blue Democratic, relative to nation; saturates at 30 pts).{note}', fontsize=8)
        fig.tight_layout(rect=(0, 0, 1, 0.96)); os.makedirs('data/maps_png', exist_ok=True)
        fig.savefig(f'data/maps_png/{st}_{"hedged" if suf else "plain"}.png', dpi=110); pdf.savefig(fig, dpi=110); plt.close(fig)
    return found

if __name__ == '__main__':
    states = sys.argv[1:] or sorted([s for s in SEATS if SEATS[s] > 1 and os.path.exists(f'data/assign/{s}.npz')], key=lambda s: -SEATS[s])
    with PdfPages('data/all_maps.pdf' if len(states) > 3 else 'data/test_maps.pdf') as pdf:
        for st in states:
            try: print(st, 'shapes matched for', round(100 * render(st, pdf)), '% of precincts', flush=True)
            except Exception as e: print(st, 'ERR', repr(e), flush=True)
