import re, pickle

STATE_ABBR = {
 'Alabama':'AL','Alaska':'AK','Arizona':'AZ','Arkansas':'AR','California':'CA','Colorado':'CO',
 'Connecticut':'CT','Delaware':'DE','Florida':'FL','Georgia':'GA','Hawaii':'HI','Idaho':'ID',
 'Illinois':'IL','Indiana':'IN','Iowa':'IA','Kansas':'KS','Kentucky':'KY','Louisiana':'LA',
 'Maine':'ME','Maryland':'MD','Massachusetts':'MA','Michigan':'MI','Minnesota':'MN','Mississippi':'MS',
 'Missouri':'MO','Montana':'MT','Nebraska':'NE','Nevada':'NV','New Hampshire':'NH','New Jersey':'NJ',
 'New Mexico':'NM','New York':'NY','North Carolina':'NC','North Dakota':'ND','Ohio':'OH','Oklahoma':'OK',
 'Oregon':'OR','Pennsylvania':'PA','Rhode Island':'RI','South Carolina':'SC','South Dakota':'SD',
 'Tennessee':'TN','Texas':'TX','Utah':'UT','Vermont':'VT','Virginia':'VA','Washington':'WA',
 'West Virginia':'WV','Wisconsin':'WI','Wyoming':'WY','District of Columbia':'DC','Puerto Rico':'PR'}

def norm_state(s):
    if not s: return ''
    s = str(s).strip()
    if len(s) == 2: return s.upper()
    return STATE_ABBR.get(s.title(), STATE_ABBR.get(s, s.upper()[:2]))

def norm_phone(p):
    if not p: return ''
    d = re.sub(r'\D', '', str(p))
    if len(d) == 11 and d.startswith('1'): d = d[1:]
    return d if len(d) == 10 else ''

STOPWORDS = {'the','a','an','of','and','&','at','in','on','for','llc','inc','pc','pa','pllc','llp',
 'ltd','corp','co','dvm','dr','veterinary','vet','animal','pet','pets','hospital','clinic','center',
 'centre','care','health','medical','practice','group','services','service','hosp','clin'}

def norm_name(n):
    if not n: return '', set()
    n = str(n).lower()
    n = re.sub(r'\(.*?\)', ' ', n)
    n = re.sub(r'[^a-z0-9 ]', ' ', n)
    toks = [t for t in n.split() if t]
    core = [t for t in toks if t not in STOPWORDS and len(t) > 1]
    return ' '.join(toks), set(core if core else toks)

def name_sim(a_toks, b_toks):
    if not a_toks or not b_toks: return 0.0
    inter = a_toks & b_toks
    return len(inter) / max(1, min(len(a_toks), len(b_toks)))

def zip5(z):
    if z is None: return ''
    z = re.sub(r'\D', '', str(z))
    return z[:5].zfill(5) if len(z) >= 4 else ''

def street_key(s):
    """first street number + first word of street name"""
    if not s: return ''
    s = str(s).lower().strip()
    m = re.match(r'(\d+)\s+([a-z0-9]+)', re.sub(r'[^a-z0-9 ]',' ',s).strip())
    return f'{m.group(1)} {m.group(2)}' if m else ''
