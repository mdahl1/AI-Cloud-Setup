# PSI Member List → Salesforce Account Matching

Matches the monthly PSIvet EOM membership list (xlsx) against Salesforce
Accounts and produces a results workbook plus Data Loader CSVs. Built for the
August 2026 run; reusable for future months.

## What it produces

`PSI_Member_SFDC_Match_<month>.xlsx` with five sheets:

- **Summary**: match counts and methodology.
- **Active Members**: every row of the full membership list with the matched
  SFDC account, match method, confidence, and an Action Needed column.
- **New Members** / **Cancelled Members**: the month's adds and cancels,
  same columns.
- **Stale PSI in SFDC**: accounts holding an active `PSI_Unique_ID__c` that is
  not on the current member list (candidates for termination dates).

Plus two Data Loader CSVs:

- `psi_updates_set_fields.csv`: matched accounts needing `PSI_Unique_ID__c`,
  `PSI_Join_Date__c`, or a cleared termination date (exact/high confidence only).
- `psi_updates_terminations.csv`: this month's cancels needing
  `PSI_Termination_Date__c`.

## Matching tiers

1. **PSI ID**: member PSI ID equals `Account.PSI_Unique_ID__c` (exact).
2. **Phone**: normalized 10-digit phone equality, best candidate chosen by
   name token similarity, zip, city, and state agreement.
3. **Name+Geo**: name token similarity with zip/city/state confirmation.
   A name overlap consisting only of the member's own city or state words is
   rejected unless the name cores are identical.

Candidates typed Out of Business or Deactivated are penalized in scoring and
flagged in the Note column when matched.

## Files

- `matchlib.py`: normalization helpers (state, phone, zip, name tokens).
- `build_report.py`: runs the three tiers and the reverse check, writes
  `report_rows.pkl`. Expects local input files produced by the extraction and
  query steps (see below).
- `make_workbook.py`: renders the workbook from `report_rows.pkl`.
- `salvage.py`: recovers complete JSON rows from Salesforce connector
  responses truncated at the connector's ~50k character cap, and paginates
  into `psi_accounts.pkl`.

## Monthly workflow

1. Extract the three sheets of the member list to `members.pkl`
   (header row is row 6 on each sheet).
2. Export all accounts where `PSI_Unique_ID__c != null` (Id, Name, Type,
   BillingState, PSI fields) via paginated `run_soql` calls, salvaging each
   truncated response with `salvage.py` and resuming from the last complete Id.
3. For member rows without a PSI ID match: query accounts by phone-format
   variants (`+1 (XXX) XXX-XXXX`, `(XXX) XXX-XXXX`, `XXX-XXX-XXXX`, bare
   10-digit), save to `phone_hits.json`; then query accounts by the remaining
   members' billing/ship zips, save to `zip_hits_*.json`; then fetch
   Shipping City/State/PostalCode for all candidates into `ship_hits_*.json`.
4. Run `build_report.py`, review the fallback matches it prints, then
   `make_workbook.py`, and recalculate the workbook (LibreOffice must have
   the Calc component installed: `apt-get install libreoffice-calc`).

Notes for the operator: review all `medium` confidence matches before loading
updates; the Stale PSI sheet rows that are not on the month's cancelled sheet
need verification against PSIvet before setting termination dates. The
connector caps every response at ~50k characters, so keep per-query result
sizes under that or salvage.
