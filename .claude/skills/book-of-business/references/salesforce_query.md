# Salesforce live pull

Uses the Shared SFDC Connector, read-only. Allowed tools: `run_soql` and `describe_object`. Load them
with `tool_search` ("salesforce soql") if not loaded. Never load or call `update_record`, `log_feedback`,
or `refresh_knowledge`. Every query is a single `SELECT`.

## 1. Resolve the corporate customer

```sql
SELECT Id, Name, ParentId FROM Account WHERE Name LIKE '%<customer>%' LIMIT 50
```

Pick the Corporate HQ account: usually the one other matches point to via `ParentId`, often
named with "HQ". Corporate hierarchies nest (a customer HQ can sit under another parent), so
use the customer's own HQ, not the top of the tree.

Always confirm with the user before pulling when any of these are true:
- More than one plausible HQ (for example a veterinary group and a dental group with the same name).
- Accounts whose names match the customer but have no ParentId, or a ParentId outside the HQ's tree.
  List them and ask whether to include them. They will not be pulled by the hierarchy filter.
  If the user says to include one, add its Id to `<HIERARCHY>` as an extra clause.

Do not select `Account_Type__c` on Account (it returns HTTP 400). It lives on Opportunity.

## 2. Walk the account tree (any depth)

Hierarchies can nest to any depth, and a fixed `Account.Parent.Parent...` filter cannot follow
them, so collect every account under the HQ first, one level at a time:

```bash
python scripts/hierarchy.py <HQ Id>
```

It prints `next_parent_clauses`. For each clause, run and save the result (page with
`AND Id > '<last Id>'` if a level returns 2,000 rows) to `/home/claude/bob/level_<next_level>.json`
(`level_<N>_2.json` and so on for extra pages or clauses):

```sql
SELECT Id, Name, ParentId FROM Account WHERE <parent clause> ORDER BY Id
```

Re-run with all level files until it prints `"done": true`:

```bash
python scripts/hierarchy.py <HQ Id> /home/claude/bob/level_*.json > /home/claude/bob/accounts.json
```

Report any `problems`. Tell the user the account count and deepest level. `account_clauses` is a
list of `Opportunity.AccountId IN (...)` filters, split so each query stays short.

## 3. Size check (always run first)

```sql
SELECT COUNT(Id) n FROM OpportunityLineItem
WHERE <HIERARCHY> AND <STAGE>
```

- `<HIERARCHY>` = one clause from `account_clauses`. With more than one clause, run the size
  check once per clause; `n` is the sum.
- `<STAGE>` = `Opportunity.StageName IN ('Closed Won','Closed Won - Deferred')`

Do not filter on contract end date. Ended contracts are kept and flagged by the builder
(`references/rules.md`), and the report export route includes them, so filtering here would make
the two routes give different workbooks. Superseded originals are also needed for the renewal
chain and price rules.

There is no row limit. `n` sets how many rows the pull must return. Every row returned by
`run_soql` passes through the conversation twice (once as the result, once written to disk), so
large pulls are slow. For large `n`, tell the user the count and the number of pages, mention that a
report export (Route A) is faster, and continue paging unless they choose to send one.
`run_soql_to_file` saves to the connector's server, not this sandbox, so it does not help here.

## 4. Pull the rows

Run the pull once per clause in `account_clauses`. Page with `ORDER BY Id` and
`AND Id > '<last Id>'`, `LIMIT 200` per page. Save each page verbatim as JSON to
`/home/claude/bob/page_<clause>_<N>.json` as soon as it returns, before running the next query, so
a long pull survives context compaction. `<last Id>` is the `Id` of the last row in the most recent
page on disk for that clause.

Stop when the running total reaches `n` or a page returns no rows. Do not stop just because a page
returned fewer than 200 rows; the connector may cap page size. Then run `normalize.py soql` with
`--expect <n>`. If it reports `"complete": false`, page again from the last Id on disk. Rows added
in Salesforce during the pull can push the count slightly above `n`; that is fine.

```sql
SELECT Id, OpportunityId, Opportunity.Name, Opportunity.CloseDate, Opportunity.StageName,
  Opportunity.Type, Opportunity.Contract_Start_Date__c, Opportunity.Contract_End_Date__c,
  Opportunity.Originating_Oppty_Contract_Start_Date__c, Opportunity.Originating_Oppty_Contract_End_Date__c,
  Opportunity.Customer_Total_Monthly_Amount__c,
  Opportunity.X1st_Tier_of_Payments__c, Opportunity.X1st_Ti__c,
  Opportunity.X2nd_Tier_Customer_Total_Monthly_Amount__c, Opportunity.X2nd_Tier_of_monthly__c,
  Opportunity.Contract__c, Opportunity.Finance_Company__r.Name,
  Opportunity.Originating_Opp_Customer_Total_Monthly__c, Opportunity.Originating_Opp_Contract_Number__c,
  Opportunity.Originating_Opportunity__c, Opportunity.Originating_Opportunity__r.Name,
  Opportunity.Account.Name, Opportunity.AccountId,
  Originating_Contract__c, Connected_Asset__r.Name, Connected_Asset__r.InstallDate,
  Connected_Asset__r.SerialNumber, Product_Link__c, PricebookEntry.Product2.Name,
  Net_Sales_Price__c, Tier_1_Price__c, Tier_1_Duration__c, Tier_2_Price__c, Tier_2_Duration__c,
  Item_Net_Price__c
FROM OpportunityLineItem
WHERE <HIERARCHY> AND <STAGE>
ORDER BY Id LIMIT 200
```

## Field map (report column to API field)

| Report column | API field |
|---|---|
| Contract Commence / End Date | `Opportunity.Contract_Start_Date__c` / `Contract_End_Date__c` |
| Original Contract Commence / End Date | `Opportunity.Originating_Oppty_Contract_Start_Date__c` / `_End_Date__c` (closest match; no field with the report's label exists) |
| 1st Tier # of Payments / Monthly | `X1st_Tier_of_Payments__c` / `X1st_Ti__c` |
| 2nd Tier # of Payments / Monthly | `X2nd_Tier_Customer_Total_Monthly_Amount__c` / `X2nd_Tier_of_monthly__c` (**API names are swapped against their labels**) |
| Finance Partner Contract # | `Opportunity.Contract__c` |
| Originating Contract | line `Originating_Contract__c`, falling back to `Opportunity.Originating_Opp_Contract_Number__c` |
| Equipment Go-Live Date | `Connected_Asset__r.InstallDate` |

`normalize.py soql` applies this map.

## Data patterns seen in the org

- Tier 1/Tier 2 prices are often populated with duration 0. The builder treats duration 0 as
  "no tier data" and uses Net Sales Price, which is what ties to Customer Total Monthly Amount.
- Older Greenfield rows often have no Connected Asset, so renewal matching falls back to
  Originating Contract / Originating Opportunity.
- Expansion opportunities frequently carry real serials (not occasional). The builder keeps any
  Expansion opportunity with a serial not found on another row and flags it.
- Line items such as "Finance Gross & PV Discount" carry no price. They appear as fee rows with a blank price and are flagged.
