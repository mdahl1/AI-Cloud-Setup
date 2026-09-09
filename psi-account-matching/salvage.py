import json, sys, glob, os, pickle

def salvage(path):
    txt = open(path).read()
    start = txt.index('[')
    body = txt[start+1:]
    # cut to last complete object
    depth=0; last_end=-1; in_str=False; esc=False
    for i,ch in enumerate(body):
        if esc: esc=False; continue
        if ch=='\\': esc=True; continue
        if ch=='"': in_str = not in_str; continue
        if in_str: continue
        if ch=='{': depth+=1
        elif ch=='}':
            depth-=1
            if depth==0: last_end=i
    if last_end<0: return []
    frag = '['+body[:last_end+1]+']'
    return json.loads(frag)

if __name__ == '__main__':
    store_path = 'psi_accounts.pkl'
    store = pickle.load(open(store_path,'rb')) if os.path.exists(store_path) else {}
    rows = salvage(sys.argv[1])
    for r in rows: store[r['Id']] = r
    pickle.dump(store, open(store_path,'wb'))
    print('salvaged', len(rows), 'rows; total', len(store), '; last Id:', rows[-1]['Id'] if rows else None)
