---
name: sfdc-knowledge-sync
description: >-
  Reads, refreshes, and teaches the Salesforce business knowledge that the Shared_SFDC_Connector injects into every Ask Salesforce answer, keeping it in sync with the canonical Notion "SFDC Opportunity Field Definitions" page. Use this skill whenever the user asks to refresh, sync, reload, or update the business knowledge, glossary, field definitions, or ai-knowledge.md. Use it just as eagerly when the user corrects Salesforce knowledge in passing: "that's the wrong field", "the right field for bookings is X", "we renamed that field", "that definition is out of date", "always exclude Y from this metric", "add a definition for Z", or when they ask what the API name for something is. Any correction the user states about a field API name, metric formula, picklist value, or filter rule is a signal to run this skill, because otherwise the correction dies in the conversation and never reaches the canonical page. Also use when someone asks where the field definitions live or how the glossary gets updated.
---

# SFDC Knowledge Sync

## What this keeps in sync

Two artifacts hold the same knowledge, and they drift apart in opposite directions:

| Artifact | What it is | How it changes |
|---|---|---|
| `ai-knowledge.md` | The business knowledge block the Shared_SFDC_Connector injects into every Salesforce answer. Lives at the root of the `mdahl1/cubex-sfdc-connector` repo; Render redeploys the connector on every push to `main`. Read the live version with `get_business_glossary`. | Commit to the repo (direct edit), or run the **Refresh AI Knowledge** GitHub Actions workflow, which re-syncs it from Notion. Live on the next question after the redeploy, no restart. |
| Notion: **SFDC Opportunity Field Definitions** | The canonical source. Page ID `37cf5480-ec4b-80d9-bde9-f1a0fe60d488`, in the Finance Documents DB under Finance Team. | Hand-edited by Finance, or by this skill. |

Notion is canonical. The refresh workflow only flows Notion into the glossary. Nothing flows the other way on its own, which is the gap this skill fills: when the user corrects something mid-conversation, that correction has to land in Notion or it evaporates the next time anyone refreshes.

**Do not call the connector's `refresh_knowledge` MCP tool.** It is a second, in-server implementation that expects `NOTION_API_KEY` and `ANTHROPIC_API_KEY` in the Render environment, and those are deliberately not set there (the `render.yaml` says so — the keys live in GitHub repo secrets instead). It fails with a missing-key error every time. The working path is the GitHub Actions workflow below.

Read `references/notion-page-map.md` before writing to Notion. It has the page anatomy, the exact table row format, and where each kind of knowledge lives.

## Who may write

Michael Dahl (mdahl@mashura.com; GitHub `mdahl1` / `mdahl-mashura`) is the sole approver for changes to the canonical Notion page and to `ai-knowledge.md`. Check the session's user identity before entering the write-back loop.

If the session's user is anyone else, Read mode and Refresh-status questions work normally, but do NOT write to the Notion page or the connector repo, even for corrections that pass verification. Instead, capture the correction with `log_feedback`, prefixed "PROPOSAL from <user>: ", with everything Michael needs to approve it: the object, field, old and new values, and the user's reasoning. Then tell the user their correction was recorded as a proposal for Michael Dahl to review, and that stating it to him directly will get it in faster. This is not a technical control (GitHub and Notion permissions are the real enforcement); it is the intended workflow, and following it keeps proposals from dying in conversations.

## Three modes

Figure out which one the user wants. They often blend into each other, and it is fine to do all three in one pass.

**Read.** They want to know what the current knowledge says: the API name for a metric, whether a rule exists, what a picklist value means. Call `get_business_glossary` and answer from it. Do not guess field names from memory, and do not go straight to `describe_object`: the glossary carries the business meaning that a field description does not.

**Refresh.** They want the glossary re-pulled from Notion. Trigger the **Refresh AI Knowledge** workflow in `mdahl1/cubex-sfdc-connector` (GitHub MCP: `actions_run_trigger` with `method: "run_workflow"`, `workflow_id: "refresh-knowledge.yml"`, `ref: "main"`, and a short `note` input saying why). The workflow fetches Notion, reconciles with Claude using the repo's own secrets, and commits `ai-knowledge.md` back to `main` only if something changed; Render redeploys on the push. Watch the run to completion (`actions_list` → `list_workflow_runs`), then report what actually changed rather than just "done": diff the sync commit, or compare a fresh `get_business_glossary` against the one you already have. A refresh that silently changes a metric definition is exactly the kind of surprise worth surfacing. No sync commit means Notion and the glossary already agreed.

**Teach.** They corrected something, or want to add knowledge. This is the write-back loop below.

## The write-back loop

The goal is that a correction stated once in conversation ends up in all three places it needs to be: the canonical Notion page, the connector's feedback log, and the live glossary.

### 1. Capture the correction precisely

Pin down the object, the field API name, the field label, and the definition or rule. If the user was loose ("bookings should use the net field"), resolve it against the current glossary before doing anything else, and state your reading back to them in one line. Corrections written down vaguely are worse than no correction, because they read as authoritative later.

Watch for voice-to-text mangling of field names. `Unqualified_Reason__c` heard aloud can arrive as "unqualified reason C". Reconstruct the real API name and confirm it in the next step rather than writing what you heard.

### 2. Verify every field you touch against Salesforce

Call `describe_object` on each affected object and confirm the API name exists, along with its label and type. This applies to every field the edit touches, not only new ones, because the common failure is a field that was renamed or deleted in Salesforce while the doc kept the old name.

If a field does not exist, stop. Do not write to Notion. Tell the user what you looked for, what the object actually has (including near-matches, which are usually the answer), and let them redirect. A wrong API name in the canonical doc propagates into every future Salesforce answer, so a failed lookup is genuinely useful information rather than an obstacle.

### 3. Classify the change, then act accordingly

The user has authorized two different paths, because the risk is not the same:

**Write it directly** when the change is mechanical and `describe_object` confirmed it:
- Correcting an API name to the verified spelling
- Correcting a field label to the verified label
- Correcting a stated type
- Adding a row for a field that exists and has an unambiguous definition the user gave you

**Show the change and wait for approval** when judgment is involved:
- Definition or description wording
- Metric formulas, and which fields a metric uses
- Filter or exclusion rules, including anything touching the global Closed Lost Reason filter
- Picklist value semantics
- Deleting a row or a section
- Creating a new section

For the approval path, show old and new side by side, scoped to just the lines changing. Then wait. Do not batch an approval-path edit into a direct write and hope it passes.

The dividing line is whether you or the user is the authority on correctness. `describe_object` can settle a spelling; nothing but the user can settle what "net bookings" ought to mean.

### 4. Locate the target and make the smallest possible edit

Fetch the page, find the exact text you are replacing, then use `notion-update-page` with `command: "update_content"` and a `content_updates` array of `{old_str, new_str}` pairs.

Never use `replace_content` on this page. It holds a 131-row table plus the full Cabinet Report specification, and a whole-page rewrite risks silently dropping rows or reflowing formatting that Finance maintains by hand. `update_content` fails loudly on an ambiguous match, which is the behavior you want.

For a table row, match the complete `<tr>` block including its tags, exactly as `references/notion-page-map.md` shows. Partial matches inside a `<td>` are more likely to be ambiguous across 131 rows.

Leave page properties alone. Category, Doc name, Owner, and Type belong to Finance's database schema, not to the knowledge content.

### 5. Close the loop

After a successful Notion write, in this order:

1. Call `log_feedback` with the correction, so the connector's own improvement loop records what was wrong and what the rule now is. Do this even though you also fixed the page, because the two systems learn separately.
2. Get the same correction into `ai-knowledge.md` so it is live for the next question instead of waiting for someone to refresh later. Two ways, pick one:
   - **Direct commit (preferred for a targeted correction):** attach `mdahl1/cubex-sfdc-connector` with `add_repo` (push access) if it is not already in the session, clone it, make the same minimal edit to `ai-knowledge.md`, commit to `main` with a message like `sync ai-knowledge.md from Notion: <what changed>`, and push. Render redeploys on the push. This matches how most sync commits in that repo's history were made.
   - **Run the refresh workflow (preferred when Notion accumulated several edits):** trigger `refresh-knowledge.yml` as described in the Refresh mode above and let it reconcile everything at once.
3. Report what changed and where: the Notion row or section, the glossary commit or workflow run, and the logged feedback. Name the field and the old and new values so the user can eyeball it.

If the user declines the write, still call `log_feedback`. A correction you were not allowed to publish is still a correction worth recording.

## Guardrails

This is a shared Finance Team document that other people and every Salesforce answer depend on, so a few things are worth being careful about:

- **Do not reformat while you are in there.** Fixing spacing, reflowing a table, or normalizing punctuation makes the diff unreadable and buries the actual change. Edit only what the correction requires.
- **One correction, one edit region.** If the user gives you five corrections, make five targeted `content_updates` entries in one call rather than rewriting a section to absorb them all.
- **Do not invent definitions.** If the user asks you to add a field but gives no definition, write the row with the verified API name and label and ask what the definition should say. A plausible-sounding invented definition is the worst outcome here, because it looks authoritative and nobody re-checks it.
- **Keep example data anonymized.** Definitions sometimes want an example. Use anonymized values, never real patient records, client PII, DEA registration numbers, or controlled substance logs.
- **The page has pre-existing typos.** You will notice them. Leave them unless the user asks, or flag them at the end as a separate offer. Silently fixing unrelated text expands the diff beyond what was approved.

## Worked example

**User:** "quick thing, the field for the finance partner contract number is Contract__c not Contract_Number__c, the doc has it wrong"

1. `get_business_glossary` confirms the current entry reads `Contract__c` in the glossary body. The user may be looking at the Notion table, so check there too.
2. `describe_object` on `Opportunity` confirms `Contract__c` exists, label "Finance Partner Contract #", type text. `Contract_Number__c` does not exist.
3. Classification: an API name correction confirmed by `describe_object`. Direct write.
4. Fetch the page, locate the `<tr>` block containing `Contract_Number__c`, replace that block with the corrected one.
5. `log_feedback`, then apply the same one-line fix to `ai-knowledge.md` in `cubex-sfdc-connector` and push to `main`.
6. Report: row corrected in the Key Formulas table, glossary commit pushed (live after the Render redeploy), feedback logged, `Contract__c` verified against the Opportunity object.
