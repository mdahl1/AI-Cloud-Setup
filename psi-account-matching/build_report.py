"""Match PSIvet member list against Salesforce accounts and build result rows."""
import json, pickle, sys
import re
sys.path.insert(0, '.')
from matchlib import norm_phone, norm_name, norm_state, zip5

accounts = pickle.load(open('psi_accounts.pkl','rb'))        # all SFDC accounts w/ PSI ID (dict by Id)
members  = pickle.load(open('members.pkl','rb'))

# candidate pools from fallback queries
zip_hits = []
for i in ('0','1a','1b'):
    zip_hits += json.load(open(f'zip_hits_{i}.json'))
phone_hits = json.load(open('phone_hits.json'))

# shipping-address enrichment for all candidates
ship = {}
for i in (0,1,2):
    for r in json.load(open(f'ship_hits_{i}.json')):
        ship[r['Id']] = r
def enrich(a):
    s = ship.get(a['Id'], {})
    a = dict(a)
    a['ShippingCity'] = s.get('ShippingCity'); a['ShippingState'] = s.get('ShippingState')
    a['ShippingPostalCode'] = s.get('ShippingPostalCode')
    if not a.get('BillingCity'): a['BillingCity'] = s.get('BillingCity')
    return a
zip_hits = [enrich(a) for a in zip_hits]
phone_hits = [enrich(a) for a in phone_hits]

by_psi = {str(a['PSI_Unique_ID__c']).strip(): a for a in accounts.values()}

BAD_TYPES = {'Out of Business', 'Deactivated'}

def geo(r, a):
    mzips = {z for z in (zip5(r.get('Billing zip')), zip5(r.get('Ship zip'))) if z}
    azips = {z for z in (zip5(a.get('BillingPostalCode')), zip5(a.get('ShippingPostalCode'))) if z}
    zip_ok = bool(mzips & azips)
    mcities = {str(c).strip().lower() for c in (r.get('Billing city'), r.get('Ship city'), r.get('Ship citiy')) if c}
    acities = {str(c).strip().lower() for c in (a.get('BillingCity'), a.get('ShippingCity')) if c}
    city_ok = bool(mcities & acities)
    mst = norm_state(r.get('Billing State') or r.get('Billing state'))
    asts = {norm_state(s) for s in (a.get('BillingState'), a.get('ShippingState')) if s}
    state_ok = bool(mst) and mst in asts
    return zip_ok, city_ok, state_ok

def name_score(r, a):
    _, mtoks = norm_name(r['Account name'])
    _, atoks = norm_name(a['Name'])
    if not mtoks or not atoks: return 0.0, set()
    inter = mtoks & atoks
    return len(inter) / max(len(mtoks), len(atoks)), inter

def score_candidate(r, a, phone_matched):
    ns, inter = name_score(r, a)
    zip_ok, city_ok, state_ok = geo(r, a)
    s = ns
    if phone_matched: s += 0.6
    if zip_ok: s += 0.35
    if city_ok: s += 0.2
    if state_ok: s += 0.1
    if a.get('Type') in BAD_TYPES: s -= 0.25
    return s, ns, inter, zip_ok, city_ok, state_ok

def accept(r, ns, inter, zip_ok, city_ok, state_ok, phone_matched):
    """Return confidence label or None."""
    # a name overlap consisting only of the member's own city/state words is
    # geography, not identity (e.g. "Spokane Veterinary Clinic" vs "PharMerica - Spokane")
    geo_words = set()
    for v in (r.get('Billing city'), r.get('Ship city'), r.get('Ship citiy'),
              r.get('Billing State'), r.get('Billing state')):
        if v: geo_words |= set(re.sub(r'[^a-z0-9 ]',' ',str(v).lower()).split())
    identity_tokens = inter - geo_words
    if not phone_matched and not identity_tokens:
        # identical name cores (e.g. "Hemet Animal Hospital" in Hemet) still count,
        # but a partial overlap that is only the city word does not
        if ns >= 1.0 and zip_ok and (city_ok or state_ok):
            return 'high'
        return None
    distinctive = any(len(t) >= 3 for t in identity_tokens)
    if phone_matched:
        return 'high' if (ns >= 0.6 or zip_ok or city_ok) else 'medium'
    if ns >= 0.8 and (zip_ok or (city_ok and state_ok)): return 'high'
    if ns >= 0.6 and (zip_ok or city_ok or state_ok): return 'medium'
    if ns >= 0.4 and distinctive and zip_ok and (city_ok or state_ok): return 'medium'
    if inter and distinctive and zip_ok and city_ok: return 'medium (review)'
    return None

from collections import defaultdict
phone_by = defaultdict(list)
for a in phone_hits:
    p = norm_phone(a.get('Phone'))
    if p: phone_by[p].append(a)

def resolve(r):
    """Best fallback match for a member row without a PSI ID match."""
    mphone = norm_phone(r.get('Phone'))
    cands = [(a, True) for a in phone_by.get(mphone, [])] if mphone else []
    cands += [(a, False) for a in zip_hits]
    best = None
    for a, pm in cands:
        s, ns, inter, z, c, st = score_candidate(r, a, pm)
        conf = accept(r, ns, inter, z, c, st, pm)
        if conf and (best is None or s > best[0]):
            method = 'Phone' if pm else 'Name+Geo'
            note = f'name_sim={ns:.2f}, zip={z}, city={c}, state={st}'
            if a.get('Type') in BAD_TYPES: note += f"; WARNING account Type={a.get('Type')}"
            best = (s, a, method, conf, note)
    if best: return best[1], best[2], best[3], best[4]
    return None, 'No match', None, None

def full_rows(src_rows, src, id_field='PSI ID'):
    out = []
    for r in src_rows:
        pid = str(r[id_field])
        row = {'PSI ID': pid, 'Member Name': r['Account name'],
               'City': r.get('Billing city'),
               'State': norm_state(r.get('Billing State') or r.get('Billing state')),
               'Zip': zip5(r.get('Billing zip')),
               'Active Date': r.get('Active date')}
        if 'Cancel date' in r: row['Cancel Date'] = r.get('Cancel date')
        if pid in by_psi:
            a = by_psi[pid]; method, conf, note = 'PSI ID', 'exact', ''
        else:
            a, method, conf, note = resolve(r)
        if a:
            row.update({'SFDC Account ID': a['Id'], 'SFDC Account Name': a['Name'],
                        'SFDC Type': a.get('Type'), 'SFDC State': a.get('BillingState'),
                        'SFDC PSI ID': a.get('PSI_Unique_ID__c'),
                        'SFDC PSI Join Date': a.get('PSI_Join_Date__c'),
                        'SFDC PSI Termination Date': a.get('PSI_Termination_Date__c')})
        else:
            row.update({'SFDC Account ID': None, 'SFDC Account Name': None, 'SFDC Type': None,
                        'SFDC State': None, 'SFDC PSI ID': None, 'SFDC PSI Join Date': None,
                        'SFDC PSI Termination Date': None})
        row['Match Method'] = method
        row['Confidence'] = conf
        row['Note'] = note or ''
        actions = []
        if a is None:
            actions.append('No SFDC account found: create account or match manually')
        else:
            if not a.get('PSI_Unique_ID__c'):
                actions.append('Set PSI_Unique_ID__c')
            elif str(a.get('PSI_Unique_ID__c')).strip() != pid:
                actions.append(f"PSI ID mismatch (SFDC has {a.get('PSI_Unique_ID__c')})")
            if src != 'cancelled' and a.get('PSI_Termination_Date__c'):
                actions.append('Clear PSI_Termination_Date__c (member is active)')
            if src == 'cancelled' and not a.get('PSI_Termination_Date__c'):
                actions.append('Set PSI_Termination_Date__c')
            if not a.get('PSI_Join_Date__c'):
                actions.append('Set PSI_Join_Date__c')
        row['Action Needed'] = '; '.join(actions)
        out.append(row)
    return out

active_rows = full_rows(members['active'], 'active')
new_rows = full_rows(members['new'], 'new')
cancelled_rows = full_rows(members['cancelled'], 'cancelled', id_field='PSIvet account ID')

# reverse check: SFDC says active PSI member, but PSI ID not on current full list
active_ids = set(str(r['PSI ID']) for r in members['active'])
cancelled_ids = set(str(r['PSIvet account ID']) for r in members['cancelled'])
stale = []
for a in accounts.values():
    pid = str(a['PSI_Unique_ID__c']).strip()
    if not a.get('PSI_Termination_Date__c') and pid not in active_ids:
        stale.append({'SFDC Account ID': a['Id'], 'SFDC Account Name': a['Name'],
                      'SFDC Type': a.get('Type'), 'SFDC State': a.get('BillingState'),
                      'SFDC PSI ID': pid, 'SFDC PSI Join Date': a.get('PSI_Join_Date__c'),
                      'On This Month Cancelled Sheet': 'Yes' if pid in cancelled_ids else 'No',
                      'Action Needed': 'Not on current PSI member list: verify and set PSI_Termination_Date__c'})
stale.sort(key=lambda x: (x['On This Month Cancelled Sheet'] == 'No', x['SFDC Account Name'] or ''))

pickle.dump({'active':active_rows,'new':new_rows,'cancelled':cancelled_rows,'stale':stale},
            open('report_rows.pkl','wb'))

from collections import Counter
for label, rows in (('ACTIVE',active_rows),('NEW',new_rows),('CANCELLED',cancelled_rows)):
    print(label, dict(Counter((r['Match Method'], r['Confidence']) for r in rows)))
print('stale:', len(stale), '| on cancelled sheet:', sum(1 for s in stale if s['On This Month Cancelled Sheet']=='Yes'))
