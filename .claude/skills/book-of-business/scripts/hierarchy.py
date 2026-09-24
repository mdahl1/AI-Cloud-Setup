#!/usr/bin/env python3
"""
Walk a corporate account tree to any depth and build the account filter for
the BoB line-item pull. Reads local files only; makes no network calls.

Level files hold run_soql results (a list of rows, {"rows": [...]} or
{"records": [...]}) of:
  SELECT Id, Name, ParentId FROM Account WHERE <parent clause> ORDER BY Id
Name them level_<N>[_<page>].json, where level 1 holds the HQ's direct
children, level 2 their children, and so on. Pages of one level share N.

Usage:
  python hierarchy.py <HQ Id> [level_*.json ...]

Prints JSON. While "done" is false, run the account query once per clause in
"next_parent_clauses" and save the results as level_<next_level>.json. When
"done" is true (the last level returned no accounts), use each clause in
"account_clauses" as <HIERARCHY> in the size check and line-item pull, and
save the full tree to accounts.json for the record.
"""
import json, re, sys
from collections import defaultdict
from pathlib import Path

CHUNK = 300  # Ids per IN clause; keeps each query well under SOQL length limits


def load(path):
    d = json.load(open(path))
    if isinstance(d, dict):
        d = d.get("rows", d.get("records", []))
    return d


def id15(v):
    return str(v or "")[:15]  # 15 and 18 char forms of one Id share the first 15


def clauses(field, ids):
    out = []
    for k in range(0, len(ids), CHUNK):
        quoted = ", ".join("'%s'" % i for i in ids[k:k + CHUNK])
        out.append("%s IN (%s)" % (field, quoted))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    hq, files = sys.argv[1], sys.argv[2:]
    by_level = defaultdict(list)
    for f in files:
        m = re.match(r"level_(\d+)", Path(f).name)
        if not m:
            sys.exit(f"bad level file name: {f}")
        by_level[int(m.group(1))].append(f)
    levels = sorted(by_level)
    if levels and levels != list(range(1, levels[-1] + 1)):
        sys.exit(f"missing level file(s): have levels {levels}")

    tree = [{"Id": hq, "Name": None, "ParentId": None, "level": 0}]
    seen = {id15(hq)}
    frontier, problems = [hq], []
    for n in levels:
        parents = {id15(p) for p in frontier}
        found = []
        for f in by_level[n]:
            for r in load(f):
                rid = r.get("Id")
                if not rid or id15(rid) in seen:
                    continue  # duplicate page row or a cycle in the tree
                if id15(r.get("ParentId")) not in parents:
                    problems.append({"level": n, "id": rid, "name": r.get("Name"),
                                     "detail": "ParentId is not in the previous level; check the query."})
                    continue
                seen.add(id15(rid))
                found.append(rid)
                tree.append({"Id": rid, "Name": r.get("Name"), "ParentId": r.get("ParentId"), "level": n})
        frontier = found

    done = bool(levels) and not frontier
    ids = [a["Id"] for a in tree]
    out = {"hq": hq, "accounts": len(tree), "deepest_level": max(a["level"] for a in tree),
           "done": done, "problems": problems}
    if done:
        out["account_clauses"] = clauses("Opportunity.AccountId", ids)
        out["tree"] = tree
    else:
        out["next_level"] = (levels[-1] + 1) if levels else 1
        out["next_parent_clauses"] = clauses("ParentId", frontier)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
