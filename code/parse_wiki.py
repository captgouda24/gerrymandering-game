"""Parse Wikipedia's 2026 House page: one row per district with Cook PVI, incumbent party, status, winner."""
import re, csv, collections
t = open('data/wiki_house.txt').read()
body = t[t.index('\n==Alabama==\n'):t.index('\n==Non-voting delegates==')]
PARTY = re.compile(r"\((Republican|Democratic|Independent|Libertarian|Green|[A-Z][A-Za-z ]+)\)")
CLEAN = re.compile(r"\{\{[^}]*\}\}|'{2,}|\[\[(?:[^\]|]*\|)?|\]\]|<ref.*")
rows = []
parts = re.split(r'\n!(?:rowspan=\d+ ?\|)?\s*\{\{ushr\|([A-Z]{2})\|(\d+|AL)\|X\}\}', body)
for i in range(1, len(parts), 3):
    st, d, blk = parts[i], parts[i+1], parts[i+2].split('\n|}')[0]
    m = re.search(r'shading PVI\|([RD])\|(\d+)', blk)
    pvi = (int(m.group(2)) * (1 if m.group(1) == 'R' else -1)) if m else 0
    head = blk.split('{{plainlist')[0]
    incs = re.findall(r'\|\s*(Republican|Democratic|Independent)\s*\n', head)
    status = ' / '.join(s.strip() for s in re.findall(r"\|\s*(?:\{\{[^}]*\}\}\s*\|)?\s*((?:Incumbent|New member|New seat|Seat|TBD|Open)[^\n]*)", head))[:160]
    cl = []
    for ln in re.findall(r"\*\{\{Party stripe[^\n]*", blk):
        aye = bool(re.search(r"\{\{aye\}\}", ln, re.I))
        pm = PARTY.findall(ln)
        nm = CLEAN.sub("", ln).lstrip('*').split('(')[0].strip()
        cl.append((nm, pm[-1] if pm else '?', aye))
    win = [c[1] for c in cl if c[2]]
    majors = [c for c in cl if c[1] in ('Republican', 'Democratic', 'Independent')]
    rows.append(dict(state=st, district=d, pvi=pvi, inc_party='/'.join(incs), status=status,
                     winner=win[0] if win else '', n_aye=len(win),
                     cands='; '.join(f"{c[0]} ({c[1][0]})" for c in majors)[:200]))
w = csv.DictWriter(open('data/house2026.csv', 'w', newline=''), fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
print(len(rows), 'districts', collections.Counter(r['winner'] for r in rows))
for r in rows:
    if not r['winner'] or r['n_aye'] > 1:
        print(r['state'], r['district'], r['pvi'], '|', r['inc_party'], '|', r['status'][:50], '|', r['cands'])
print(collections.Counter((r['inc_party'], r['winner']) for r in rows))
