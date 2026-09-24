# Book of Business rules (source of truth)

These are the Book of Business Builder project rules. `scripts/build_bob.py` implements them.
If a rule here and the script disagree, the rule wins: fix the script, do not work around it.

## Interpretations the script makes (confirmed or to confirm with Simon)
- Tier duration of 0 or blank = no tier data, so Net Sales Price is used.
- HQ roll-up = Account Name starts with "_", ends in "HQ", or contains "(HQ)".
- A site with several concurrent hardware rows lists all hardware rows first, then fee rows.
- Expansion rows are judged per opportunity: kept if any line carries a serial found on no other row.
- Renewal not yet started: price comes from the original line; Contract # and Financing Partner stay the renewal line's own.
- Rows whose contract has ended are kept and flagged, not dropped: "expired_no_renewal" for a
  non-renewal past its contract end, "expired_renewal" for a renewal past its renewal end. Both
  routes (report export and live pull) include these rows, so they give the same result.

## Output
One sheet, "Master List". Columns: Account Name, Asset Name, Go Live Date, Contract Start Date,
Contract End Date, Renewal Start Date, Renewal End Date, Monthly Price, Serial Number, Contract #,
Financing Partner. Repeating site blocks: main equipment row(s), fee/subscription rows (Account Name,
Go Live Date, Serial Number blank), Total row (SUM formula on Monthly Price), one blank row.
Bold header and Total rows, $#,##0.00, M/D/YYYY, Arial, light borders.
Sort: physical sites A to Z by display name; HQ roll-up blocks last.

## Filtering
Exclude: Expansion rows (after verifying no real asset/serial), superseded renewal-chain rows,
placeholder renewals (Close Date after today, no product/asset/Net Sales Price), rows with no Account Name.
Keep everything else. If the current row in a chain is ambiguous, hold and ask.

## Grouping
Site key: serial-to-site map (hardware rows with a mapped serial), else Account Name normalized
for case and whitespace. HQ fee rows move to a site only on an unambiguous one-to-one contract #
match; otherwise hold and ask. Sites with no main equipment row are left out and listed.

## Renewals
Contract Start/End = Original Contract Commence/End Date. Renewal Start/End = the renewal row's
Contract Commence/End Date. Renewal not started: original price. Started: renewal price. No renewal:
renewal columns blank. Match by serial, then Originating Contract. Same serial at two sites: keep the
site on the newer renewal row.

## Mapping
Asset Name: Connected Asset name, else Product Name. "Cubex Connect" and "CUBEX Connect Lite" to
"Interface Fees"; "PMP Lite" to "CubexPMP Lite"; "Mini" stays "Mini". Financing Partner:
"Mitsubishi HC Capital America" to "Mitsubishi Capital"; "Cubex Direct" as-is; nothing else shortened.
Each fee row shows its own Contract # and Financing Partner. Title-case site names, keeping DTLA, LA,
NOPA, HQ; flag unclear casing. Serial stored as text. Main equipment row = non-blank serial.

## Pricing
Tier in effect today: boundary = Contract Commence Date + Tier 1 Duration months. Before: Tier 1
Price. After: Tier 2 Price. No tier data: Net Sales Price. Flag tier duration that conflicts with term.

## Missing data
Never invent numbers. Missing price, date, or Contract # is left blank with a cell comment and listed.
Missing Go-Live on every row is flagged once at account level.

## Validation (report failures, never silently fix)
Block Total ties to some row's Customer Total Monthly Amount within $0.01 (mismatches expected on
multi-unit contracts). No dropped contract dates or partner. No duplicate serial across sites. Every
mapped serial in exactly one block. Filtered + excluded = raw row count.
