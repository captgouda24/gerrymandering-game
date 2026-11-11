"""Parse 2026 governor results and post-election state legislative chamber control from Wikipedia."""
import re, json
g = open('data/2026_United_States_gubernatorial_elections.txt').read()
g = g[g.index('== Race summary =='):g.index('=== Territories and federal district ===')]
gov = {}
for blk in g.split('\n|-\n! [[')[1:]:
    st = re.search(r'\|([^\]]+)\]\]', blk).group(1)
    c = re.findall(r"\*\{\{Party stripe[^\n]*", blk)
    res = []
    for ln in c:
        p = re.findall(r"\((Republican|Democratic|Independent|DFL|[A-Z][A-Za-z\- ]+)\)", ln); pc = re.search(r"([\d.]+)%", ln)
        res.append((p[-1] if p else '?', bool(re.search(r'\{\{aye\}\}', ln, re.I)), float(pc.group(1)) if pc else None))
    win = [r[0] for r in res if r[1]]
    d = sum(r[2] or 0 for r in res if r[0] in ('Democratic', 'DFL')); r_ = sum(r[2] or 0 for r in res if r[0] == 'Republican')
    gov[st] = dict(winner=win[0] if win else None, D=d, R=r_, raw=[(a, b, c_) for a, b, c_ in res][:4])
for k, v in gov.items(): print(k, v['winner'], v['D'], v['R'], '' if v['winner'] else v['raw'])
l = open('data/2026_United_States_state_legislative_elections.txt').read()
l = l[l.index('== State summaries =='):]
leg = {}
for sec in re.split(r'\n===\s*([A-Za-z ]+?)\s*===\n', l)[1:]:
    pass
parts = re.split(r'\n===\s*([A-Za-z ]+?)\s*===\n', l)
for i in range(1, len(parts), 2):
    st, sec = parts[i], parts[i+1]
    ch = {}
    for tb in sec.split('{| class="wikitable"')[1:]:
        cap = re.search(r'\|\+[^|]*\|\s*([^\n]+)', tb); cap = cap.group(1).strip() if cap else '?'
        seats = {}
        for row in tb.split('\n|-'):
            pm = re.search(r'\[\[[^\]]*\|(Republican|Democratic|Independent|Democratic \(DFL\)|DFL|Coalition|[A-Za-z\-– ]+)\]\]', row)
            cells = [x.strip() for x in row.split('\n') if x.startswith('|')]
            nums = [re.sub(r'\{\{[^}]*\}\}\s*\|?', '', x.lstrip('|')).strip() for x in cells]
            nums = [n for n in nums if re.fullmatch(r"'*\d+'*", n)]
            if pm and len(nums) >= 2: seats[pm.group(1)] = (int(nums[0].strip("'")), int(nums[1].strip("'")))
            elif pm and len(nums) == 1: seats[pm.group(1)] = (int(nums[0].strip("'")), None)
        ch[cap] = seats
    leg[st] = ch
    print(st, {k: {p: v for p, v in s.items()} for k, s in ch.items()})
json.dump(dict(gov=gov, leg=leg), open('data/states2026.json', 'w'), indent=1)
