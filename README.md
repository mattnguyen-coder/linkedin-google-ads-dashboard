# LinkedIn + Google Ads Weekly Dashboard

Pipeline that merges a week's LinkedIn Ads CSV exports with Google Ads
connector data into a single dashboard.

## Scripts

1. `merge.py` — parses the LinkedIn CSVs (campaign performance, creative
   performance, demographics), the Google Ads raw JSON exports (campaign,
   ad group, keyword, geographic, search term) and, optionally, the ChatGPT
   Ads CSVs (`openaiads_ads_*`, `openaiads_adgroups_*`), aggregates Google Ads
   from daily to weekly, and writes `unified.json`. Optional trailing
   arguments: `<chatgpt_ads.csv> <chatgpt_adgroups.csv> <previous_snapshot.json>`
   (the previous snapshot fills ChatGPT week-over-week).
2. `history.py` — reads/updates `google-ads-history.json` (a running
   per-campaign, per-week history) and back-fills `wow_spend_change_pct`
   onto the Google Ads records in `unified.json`, since Google Ads has no
   built-in week-over-week comparison like LinkedIn does.
3. `generate_dashboard.py` — renders `unified.json` + `google-ads-history.json`
   into `dashboard.html`.

## Distribution — Claude Artifacts only

`dashboard.html` is published exclusively via Claude Artifacts. It is
**never** uploaded to Google Drive — Drive does not render raw `.html`
files as live pages, so a Drive copy would just be a static, non-functional
download.

Every weekly refresh (and any manual refresh) must **update this same
existing artifact**, not publish a new one:

https://claude.ai/code/artifact/3c3c7aed-53c7-48ec-9a36-96a41257c3c2

`google-ads-history.json` is unaffected by this — it still lives in the
"Dashboard Specs" Google Drive folder, since it's a small JSON file the
pipeline reads back in each week for WoW tracking, not a rendered page.

## Weekly refresh steps

1. Confirm all required LinkedIn CSVs are present in the "LinkedIn Ads"
   Drive folder for the reporting week.
2. Pull Google Ads data for the same week via the Google Ads connector.
3. Run `merge.py`, then `history.py`, then `generate_dashboard.py` to
   produce this week's `dashboard.html`.
4. Publish `dashboard.html` to the Claude Artifact URL above (update in
   place — do not create a new artifact).
5. Upload the updated `google-ads-history.json` back to the "Dashboard
   Specs" Drive folder, replacing the previous version.

## ChatGPT Ads

ChatGPT Ads is the third channel (first tracked week: 2026-10-07). See
`docs/WEEKLY_UPDATE_RUNBOOK.md` for the weekly steps and QA checklist,
`docs/CHATGPT_ADS_DATA_DICTIONARY.md` for the field mapping, and
`docs/GUIDE_UPDATES.md` for text to paste into the three Google guide docs.
`dashboard_artifact.html` is a copy of the HTML published to the artifact
(the artifact itself is the source the dashboard serves; `generate_dashboard.py`
does not yet render the ChatGPT tab or the Trends tab).
