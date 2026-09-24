#!/usr/bin/env python3
"""
Normalize BoB input into the canonical raw schema.

Two input modes, same output (canonical CSV):

  report  A Salesforce report export (.csv or .xlsx), one row per line item.
          Headers are matched by closest text, not exact string.
  soql    One or more JSON files holding run_soql results (a list of rows, or
          {"rows": [...]}) from the query in references/salesforce_query.md.

Usage:
  python normalize.py report <export.xlsx|csv> <out.csv>
  python normalize.py soql <page1.json> [page2.json ...] <out.csv>

Prints a JSON header report: matched, fuzzy-matched, and unmatched columns.
Fuzzy and unmatched columns MUST be shown to the user before building.
"""
import csv, json, re, sys, difflib
from pathlib import Path

# canonical key -> expected report header
SCHEMA = {
    "opp_name": "Opportunity Name",
    "close_date": "Close Date",
    "commence": "Contract Commence Date",
    "end": "Contract End Date",
    "orig_commence": "Original Contract Commence Date",
    "orig_end": "Original Contract End Date (new)",
    "cust_total_monthly": "Customer Total Monthly Amount",
    "t1_payments": "1st Tier - # of Payments",
    "t1_monthly": "1st Tier - Customer Total Monthly Amount",
    "t2_payments": "2nd Tier - # of Payments",
    "t2_monthly": "2nd Tier - Customer Total Monthly Amount",
    "contract_no": "Finance Partner Contract #",
    "finance_co": "Finance Company: Account Name",
    "orig_opp_cust_monthly": "Originating Opp - Customer Total Monthly",
    "originating_contract": "Originating Contract",
    "orig_opp_name": "Originating Opportunity: Opportunity Name",
    "asset_name": "Connected Asset: Asset Name",
    "go_live": "Connected Asset: Equipment Go-Live Date",
    "serial": "Connected Asset: Serial Number",
    "product_link": "Product Link",
    "product_name": "Price Book Entry: Product: Product Name",
    "net_sales_price": "Net Sales Price",
    "tier1_price": "Tier 1 Price",
    "tier1_dur": "Tier 1 Duration",
    "tier2_price": "Tier 2 Price",
    "tier2_dur": "Tier 2 Duration",
    "item_net_price": "Item Net Price",
    "type": "Type",
    "account_name": "Account Name: Account Name",
}
# provisional headers: absence is flagged, not fatal
PROVISIONAL = {"orig_commence", "orig_end"}
# extra keys available only from SOQL mode
EXTRA = ["opp_id", "orig_opp_id", "account_id", "stage"]
CANON = list(SCHEMA) + EXTRA


def norm(s):
    return re.sub(r"[^a-z0-9#]", "", str(s).lower())


def match_headers(headers):
    report = {"exact": {}, "fuzzy": {}, "unmatched_expected": [], "unused_input": []}
    used, mapping = set(), {}
    nh = {h: norm(h) for h in headers}
    for key, want in SCHEMA.items():
        w = norm(want)
        hit = next((h for h, n in nh.items() if n == w and h not in used), None)
        if hit:
            mapping[key] = hit; used.add(hit); report["exact"][key] = hit
    for key, want in SCHEMA.items():
        if key in mapping:
            continue
        w = norm(want)
        best, score = None, 0.0
        for h, n in nh.items():
            if h in used:
                continue
            r = difflib.SequenceMatcher(None, w, n).ratio()
            if r > score:
                best, score = h, r
        if best and score >= 0.85:
            mapping[key] = best; used.add(best)
            report["fuzzy"][key] = {"expected": want, "matched": best, "score": round(score, 2)}
        else:
            report["unmatched_expected"].append(
                {"key": key, "expected": want, "provisional": key in PROVISIONAL,
                 "closest": best, "score": round(score, 2)})
    report["unused_input"] = [h for h in headers if h not in used]
    return mapping, report


def read_report(path):
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
        ws = wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        # header row = first row that contains "Opportunity Name"-like text
        hi = next((i for i, r in enumerate(rows[:30])
                   if any(norm(c) == norm("Opportunity Name") for c in r if c)), 0)
        headers = [str(c).strip() if c is not None else f"col{j}" for j, c in enumerate(rows[hi])]
        data = [dict(zip(headers, r)) for r in rows[hi + 1:]]
    else:
        with open(p, newline="", encoding="utf-8-sig") as f:
            rdr = csv.DictReader(f)
            headers = rdr.fieldnames
            data = list(rdr)
    return headers, data


def g(d, *path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s).replace("&amp;", "&") if isinstance(s, str) else s


def soql_row(r):
    o = r.get("Opportunity") or {}
    ca = r.get("Connected_Asset__r") or {}
    return {
        "opp_name": o.get("Name"),
        "close_date": o.get("CloseDate"),
        "commence": o.get("Contract_Start_Date__c"),
        "end": o.get("Contract_End_Date__c"),
        "orig_commence": o.get("Originating_Oppty_Contract_Start_Date__c"),
        "orig_end": o.get("Originating_Oppty_Contract_End_Date__c"),
        "cust_total_monthly": o.get("Customer_Total_Monthly_Amount__c"),
        # NOTE: 2nd-tier API names are swapped vs. their labels in this org
        "t1_payments": o.get("X1st_Tier_of_Payments__c"),
        "t1_monthly": o.get("X1st_Ti__c"),
        "t2_payments": o.get("X2nd_Tier_Customer_Total_Monthly_Amount__c"),
        "t2_monthly": o.get("X2nd_Tier_of_monthly__c"),
        "contract_no": o.get("Contract__c"),
        "finance_co": g(o, "Finance_Company__r", "Name"),
        "orig_opp_cust_monthly": o.get("Originating_Opp_Customer_Total_Monthly__c"),
        "originating_contract": r.get("Originating_Contract__c") or o.get("Originating_Opp_Contract_Number__c"),
        "orig_opp_name": g(o, "Originating_Opportunity__r", "Name"),
        "asset_name": ca.get("Name"),
        "go_live": ca.get("InstallDate"),
        "serial": ca.get("SerialNumber"),
        "product_link": strip_html(r.get("Product_Link__c")),
        "product_name": g(r, "PricebookEntry", "Product2", "Name"),
        "net_sales_price": r.get("Net_Sales_Price__c"),
        "tier1_price": r.get("Tier_1_Price__c"),
        "tier1_dur": r.get("Tier_1_Duration__c"),
        "tier2_price": r.get("Tier_2_Price__c"),
        "tier2_dur": r.get("Tier_2_Duration__c"),
        "item_net_price": r.get("Item_Net_Price__c"),
        "type": o.get("Type"),
        "account_name": g(o, "Account", "Name"),
        "opp_id": r.get("OpportunityId") or o.get("Id"),
        "orig_opp_id": o.get("Originating_Opportunity__c"),
        "account_id": o.get("AccountId"),
        "stage": o.get("StageName"),
    }


def write(rows, out):
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CANON)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in CANON})


def main():
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(1)
    mode, *ins, out = sys.argv[1:]
    if mode == "report":
        headers, data = read_report(ins[0])
        mapping, rep = match_headers(headers)
        rows = [{k: d.get(h) for k, h in mapping.items()} for d in data]
        # drop fully empty trailing rows
        rows = [r for r in rows if any(v not in (None, "") for v in r.values())]
        write(rows, out)
        rep["rows"] = len(rows)
        print(json.dumps({"mode": "report", "header_check": rep}, indent=2, default=str))
    elif mode == "soql":
        rows, seen = [], set()
        for p in ins:
            d = json.load(open(p))
            d = d.get("rows", d) if isinstance(d, dict) else d
            for r in d:
                if r.get("Id") in seen:
                    continue
                seen.add(r.get("Id")); rows.append(soql_row(r))
        write(rows, out)
        print(json.dumps({"mode": "soql", "rows": len(rows),
                          "note": "Original contract dates mapped from Originating Oppty Contract Start/End Date (confirm)."},
                         indent=2))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
