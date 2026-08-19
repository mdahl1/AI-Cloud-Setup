# Notion page map: SFDC Opportunity Field Definitions

Read this before writing to the page, so the edit lands in the right place and in the right format.

**Page ID:** `37cf5480-ec4b-80d9-bde9-f1a0fe60d488`
**URL:** https://app.notion.com/p/37cf5480ec4b80d9bde9f1a0fe60d488
**Location:** Finance Documents DB → Finance databases → Finance Team
**Page properties (do not edit):** Category, Created time, Doc name, Owner, Text, Type

Verified as of August 18, 2026. If the structure below no longer matches what `notion-fetch` returns, trust the fetch and update this file.

## Structure

The page is two parts:

1. **Key Formulas** table. One bold line reading `**Key Formulas**`, then a single `<table>` holding the field dictionary.
2. **Prose sections** below the table: metric definitions, win rate definitions, quota and forecast notes, then `## Cabinet Report — Full Instructions`.

## Part 1: the Key Formulas table

131 field rows plus a header row. Four columns:

| Column | Content |
|---|---|
| Object | `Opportunity`, `Account`, `Asset`, or `Pre-Implementation Task` |
| API Name | Salesforce API name, e.g. `Net_Bookings__c` |
| Field Name | The Salesforce label, e.g. `Net Bookings` |
| Definition | Business meaning, free text |

Current row counts by object, useful as a sanity check that an edit did not drop rows:

- Opportunity: 58
- Account: 48
- Asset: 16
- Pre-Implementation Task: 9

### Exact row format

Rows are Notion-flavored markdown HTML. A row is five lines:

```
<tr>
<td>Opportunity</td>
<td>OwnerId</td>
<td>Opportunity Owner</td>
<td>AE, Bookings/Quota owner; individual who closed the deal</td>
</tr>
```

When editing, match the complete `<tr>` block including both tags as `old_str`. Matching only the inner text risks an ambiguous match across 131 rows, and `update_content` fails rather than guessing.

The header row uses bold: `<td>**Object**</td>` and so on. Do not touch it.

Long definitions use `<br>` for line breaks inside a `<td>`. Preserve them.

### Adding a row

Anchor on the row that should precede the new one: make `old_str` that row's full `<tr>` block, and `new_str` that same block followed by the new block. Keep rows grouped with their object rather than appending to the end of the table.

### Removing a row

Removal is judgment, not mechanical, so it needs approval even when `describe_object` confirms the field is gone from Salesforce. A field missing from `describe_object` might be deprecated, renamed, or simply not visible to the connector's permission set.

## Part 2: prose sections

Below the table, in order:

- Booking measures and what each field means
- Booked vs funded
- Dimensions and their exact picklist values
- Metric definitions: bookings total, new doors, ASP, margin, amount up for renewal, net and gross renewal rate, churn, contraction, expansion, sales cycle
- Win rate definitions: overall, MQL, SQL, proposal
- Quota and forecast notes: `ForecastingQuota` fields, the 2026 `ForecastingTypeId` values, manager rollup quota exclusions, `Vet_Forecast_Category__c` values, and the note that `QuotaOwner.Name` traversal returns a 400
- `## Cabinet Report — Full Instructions`, with `#### TRIGGER`, `#### REPORT STRUCTURE`, `### TABLES 1 & 2 — ACCOUNT-LEVEL`, `### TABLE 3 — ASSET-LEVEL`, and their step and column definitions

Headings use `##`, `###`, and `####`. Sections are separated by `---`. Emphasis-only lines like `**Table 1 — All Sites**` act as sub-labels inside a section, so do not promote them to headings.

### Which part gets the edit

- A field's API name, label, or one-line meaning → the table.
- A metric formula, a filter rule, a picklist's business semantics, or anything with SOQL in it → the prose section that already covers that metric.

Both, when a correction changes a field name that a formula also references. Search the whole page for the old API name before deciding the edit is done: a renamed field usually appears in a metric definition and sometimes in the Cabinet Report queries too.

### New sections

Add a new section only when the knowledge fits nowhere existing, and get approval first. Place it with related content rather than at the end, match the surrounding heading level, and separate it with `---` the way its neighbors are.

## Related pages

- **Sales & Marketing Metric Definitions** (`335f5480-ec4b-8071-a7c3-c109a3911eb0`) covers sales and marketing metrics and is a separate document with its own owner. If a correction really belongs there, say so rather than writing it into this page.
