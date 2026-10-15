# Weekly Update Runbook: Google Ads + LinkedIn Ads + ChatGPT Ads

Target time: under 15 minutes of hands-on work. Run it on Wednesday for the Wednesday–Tuesday week that just ended.

This extends the existing "Weekly Dashboard Update Guide". The LinkedIn and Google Ads steps are unchanged. ChatGPT Ads follows the same method: weekly export files in Drive, one unified snapshot per week, an entry added to `index.json`, and the existing artifact updated in place.

## Key locations

| What | Where |
|---|---|
| Dashboard (update in place, never publish a new one) | https://claude.ai/code/artifact/3c3c7aed-53c7-48ec-9a36-96a41257c3c2 |
| LinkedIn CSVs | Drive: Claude - Paid Ads Project / Weekly Report Files / LinkedIn Ads |
| ChatGPT Ads CSVs | Drive: Claude - Paid Ads Project / Weekly Report Files / ChatGPT Ads (folder ID `1hkEiZM03DP0HSDtQlLcLoflvDhhVSD8E`) |
| Snapshots and `index.json` | Drive: LinkedIn Ads / history (folder ID `115AKkNbkEc1OjrrAcdA8hpYZbRq2x7N9`) |
| `google-ads-history.json` | Drive: Dashboard Specs (folder ID `17YUKKHX6Zs9R2ImV8t8oES2YpxenjIKG`) |
| Google Ads account | Customer ID `4071709382` (via the Google Ads connector) |
| Pipeline code | github.com/mattnguyen-coder/linkedin-google-ads-dashboard (`merge.py`, `history.py`) |

## Before you start

- Claude Code with the Google Ads and Google Drive connectors connected in your own session (connections do not transfer between people).
- Know the reporting week: start (Wednesday) and end (Tuesday), for example 2026-10-07 and 2026-10-13.

## Steps

### 1. Export LinkedIn (3 reports)
Campaign Performance, Creative Performance and Demographics from LinkedIn Campaign Manager, for the week. Unchanged from the current guide.

### 2. Export ChatGPT Ads (2 reports)
In ChatGPT Ads Manager, export two reports for exactly the same Wednesday–Tuesday range:

1. **Ads** (ad level)
2. **Ad groups**

> **TO FILL IN (owner: whoever runs ChatGPT Ads Manager):** the exact menu path and date-range setting. This runbook's author could not see Ads Manager. Add screenshots or the click path here after the first run. Also confirm the export covers only the chosen week and is not cumulative since launch.

Required columns (the export currently provides all of them; if ChatGPT renames or drops one, stop and see Troubleshooting):

- Ads: `campaign_name, ad_group_name, ad_name, ad_status, review_status, ad_title, ad_copy, ad_url, impressions, clicks, conversions, spend, ctr, cpc, cpm`
- Ad groups: `campaign_name, ad_group_name, ad_group_status, impressions, clicks, conversions, spend, ctr, cpc, cpm, context_hints, billing_event_type, max_bid`

### 3. Name the files
Exactly this pattern, with ISO dates (the same style the LinkedIn files use today):

```
openaiads_ads_YYYY-MM-DD-YYYY-MM-DD.csv
openaiads_adgroups_YYYY-MM-DD-YYYY-MM-DD.csv
```

Example: `openaiads_ads_2026-10-07-2026-10-13.csv`. The first date is the Wednesday start, so files sort chronologically.

### 4. Upload to Drive
Upload both CSVs to the **ChatGPT Ads** folder (table above). Upload the LinkedIn CSVs to **LinkedIn Ads** as usual.

### 5. Run the refresh in Claude Code
Open Claude Code (desktop app), confirm Google Ads and Google Drive show as connected, and paste:

```
Please refresh the weekly dashboard for the reporting week of
[YYYY-MM-DD] – [YYYY-MM-DD]:

1. Check the "LinkedIn Ads" Google Drive folder for:
   - linkedinads_campaignperformance_[start]-[end].csv
   - linkedinads_creativeperformance_[start]-[end].csv
   - linkedinads_demographic_[start]-[end].csv
   and the "ChatGPT Ads" Drive folder for:
   - openaiads_ads_[start]-[end].csv
   - openaiads_adgroups_[start]-[end].csv
2. If any is missing, stop and tell me which one(s).
3. If all present: pull Google Ads data for this date range (customer
   4071709382), merge per data-mapping.md using merge.py (pass the previous
   week's snapshot so ChatGPT week-over-week is filled in), run history.py,
   write this week's snapshot file, update history/index.json, and update the
   existing artifact (do not create a new artifact):
   https://claude.ai/code/artifact/3c3c7aed-53c7-48ec-9a36-96a41257c3c2
4. Run the QA checklist in WEEKLY_UPDATE_RUNBOOK.md and report each result.
```

### 6. Get the new files into Drive
Claude stages the output files in `~/ads-dashboard-upload/<week>/`. The Drive connector cannot write large files or change an existing file's contents, so:

1. **Snapshot** (`snapshot_<start>-<end>.json`): drag into Drive `LinkedIn Ads/history`. New file, no prompt.
2. **`google-ads-history.json`**: in Drive `Dashboard Specs`, right-click the existing file, **File information → Manage versions → Upload new version**. Do not choose "Keep both"; two copies make the dashboard pick one at random.
3. **`index.json`**: either upload as a new version the same way, or ask Claude to replace it (Claude trashes the old file, which stays recoverable for 30 days, and creates the updated one). Do this last, so the dashboard never points at a missing snapshot.

### 7. Verify
Open the artifact. Check the header shows the new week and "Data through <Tuesday>", the week appears in the dropdown, and Combined, Google Ads, LinkedIn Ads and ChatGPT Ads tabs all show the new numbers.

## Pre-publish QA checklist

- [ ] All five CSVs present with the exact date range in the name; the LinkedIn report header shows the same dates.
- [ ] ChatGPT ads total spend equals ad-group total spend (Claude warns if not).
- [ ] ChatGPT totals equal the sum of the rows in the CSV (spend, impressions, clicks).
- [ ] LinkedIn spend in the dashboard equals the sum of Total Spent in the campaign CSV.
- [ ] Google Ads spend is identical across the campaign, ad group, keyword and location reports.
- [ ] Combined spend = Google Ads + LinkedIn + ChatGPT.
- [ ] No duplicate week: `index.json` lists the week once, and `google-ads-history.json` has one set of rows for the week.
- [ ] Week start is a Wednesday and the end is the following Tuesday, matching the previous week plus 7 days.
- [ ] Everything is USD (no currency conversion is applied anywhere).
- [ ] Google Ads prior week in `google-ads-history.json` is the immediately preceding week (no gap).
- [ ] The Trends tab has a row for the week (it is a hardcoded list in the artifact and is updated on every refresh).

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Claude says a file is missing | Name differs from the pattern, or it is in the wrong folder. Rename and re-run; do not run with a partial set. |
| ChatGPT tab says "No ChatGPT Ads data for this week" | The snapshot lacks `chatgpt_ad` records. Re-run with the two CSVs present. Older weeks always show this. |
| ChatGPT week-over-week is blank | Normal in the first tracked week. Later it means the previous snapshot was not passed to `merge.py`. |
| ChatGPT CPC or CPM looks different from Ads Manager | Expected. The dashboard derives CTR, CPC and CPM from spend, impressions and clicks because the export's own cpc/cpm columns do not reconcile with them. |
| ChatGPT conversions are 0 | Expected until ChatGPT conversion tracking is set up. Cost / Conversion for ChatGPT shows "—" and Combined Cost / Conversion excludes ChatGPT spend. |
| ChatGPT export columns changed | Stop. Update `parse_chatgpt_ads` / `parse_chatgpt_adgroups` in `merge.py` and the data dictionary before running. |
| Google Ads week-over-week compares the wrong week | `google-ads-history.json` is missing the previous week's rows. Add them (history.py does this each run) and upload the file. |
| LinkedIn numbers of $1,000+ are blank or low | The old parser dropped values with thousands separators. Fixed in `merge.py`; make sure you are running the current version. |
| Dashboard shows an error banner after a refresh | `index.json` points to a snapshot that is not in Drive. Upload the snapshot, or restore the previous `index.json`. |
| Two files with the same name in a Drive folder | A re-upload used "Keep both". Delete the older copy (keep the one with the latest modified time). |

## Optional phase 2 (not built)

An API pull for ChatGPT Ads and a scheduled Claude Code task for the whole refresh. Only worth doing once the manual process has been stable for a month.
