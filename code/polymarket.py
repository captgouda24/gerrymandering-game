"""Pull Polymarket 'XX-NN House Election Winner' prices for all 435 districts; merge with Wikipedia calls."""
import json, urllib.request, urllib.parse, csv, concurrent.futures as cf
def get(u):
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
    for _ in range(3):
        try: return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e: err = e
    return {}
rows = list(csv.DictReader(open('data/house2026.csv')))
def fetch(r):
    d = r['district']; key = f"{r['state']}-{'AL' if d == 'AL' else d.zfill(2)}"
    title = f"{key} House Election Winner"
    res = get('https://gamma-api.polymarket.com/public-search?' + urllib.parse.urlencode({'q': title, 'limit_per_type': 5}))
    pr = pd = None; closed = None
    for ev in res.get('events') or []:
        if ev.get('title', '').strip() != title: continue
        for m in ev.get('markets', []):
            q = m.get('question', ''); p = m.get('outcomePrices')
            if not p: continue
            p = float(json.loads(p)[0]) if isinstance(p, str) else float(p[0])
            if 'Republican Party' in q: pr = p; closed = m.get('closed')
            if 'Democratic Party' in q: pd = p
    return key, pr, pd, closed
with cf.ThreadPoolExecutor(6) as ex: res = list(ex.map(fetch, rows))
for r, (key, pr, pd, closed) in zip(rows, res):
    r['key'] = key; r['pm_R'] = pr; r['pm_D'] = pd; r['pm_closed'] = closed
    w = r['winner']; w = 'Democratic' if w == 'DFL' else w
    r['winner'] = w
    # final call: Wikipedia/AP call if present, else Polymarket favourite
    if w: r['call'] = w[0]; r['source'] = 'AP'
    elif pr is not None and pd is not None: r['call'] = 'R' if pr > pd else 'D'; r['source'] = 'PM'
    else: r['call'] = ''; r['source'] = ''
    r['p_R'] = (1.0 if w == 'Republican' else 0.0) if w else (pr / (pr + pd) if pr is not None and pd and pr + pd > 0 else (pr if pr is not None else ''))
wr = csv.DictWriter(open('data/house2026_final.csv', 'w', newline=''), fieldnames=rows[0].keys()); wr.writeheader(); wr.writerows(rows)
print('no PM market:', sum(r['pm_R'] is None for r in rows))
print('uncalled by AP ->')
for r in rows:
    if r['source'] != 'AP': print(' ', r['key'], 'PVI', r['pvi'], 'inc', r['inc_party'], 'PM R/D', r['pm_R'], r['pm_D'])
print('AP call vs PM disagree ->')
for r in rows:
    if r['source'] == 'AP' and r['pm_R'] is not None and r['pm_D'] is not None and ((r['pm_R'] > .5) != (r['call'] == 'R')) and abs(r['pm_R']-.5) < .49:
        print(' ', r['key'], r['call'], r['pm_R'], r['pm_D'])
from collections import Counter
print(Counter(r['call'] for r in rows), 'E[R seats]=', round(sum(float(r['p_R']) for r in rows if r['p_R'] != ''), 2))
