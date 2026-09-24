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

Do not select `Account_Type__c` on Account (it returns HTTP 400). It lives on Opportunity.

## 2. Size check (always run first)

```sql
SELECT COUNT(Id) n FROM OpportunityLineItem
WHERE <HIERARCHY> AND <STAGE> AND <ACTIVE>
```

- `<HIERARCHY>` = `(Opportunity.AccountId = '<HQ>' OR Opportunity.Account.ParentId = '<HQ>' OR Opportunity.Account.Parent.ParentId = '<HQ>')`
- `<STAGE>` = `Opportunity.StageName IN ('Closed Won','Closed Won - Deferred')`
- `<ACTIVE>` = `(Opportunity.Contract_End_Date__c >= TODAY OR Opportunity.Contract_End_Date__c = null)`

Filtering to active contracts is safe: renewal rows carry the original term themselves
(`Originating_Oppty_Contract_Start_Date__c` / `_End_Date__c`), and an original whose renewal has
not started yet is still active, so it is still pulled for the price rule.

**If n > 250, stop and ask for the report export instead.** Every row returned by `run_soql`
passes through the conversation twice (once as the result, once written to disk), so large pulls
are slow and can exceed context. `run_soql_to_file` saves to the connector's server, not this
sandbox, so it does not help here.

## 3. Pull the rows

Page with `ORDER BY Id` and `AND Id > '<last Id>'`, `LIMIT 200` per page. Save each page verbatim
as JSON to `/home/claude/bob/page_N.json`.

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
WHERE <HIERARCHY> AND <STAGE> AND <ACTIVE>
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
