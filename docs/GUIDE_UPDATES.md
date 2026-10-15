# Paste-ready updates for the three Google guide docs

The Google Docs could not be edited from the session that built the ChatGPT Ads feature (only the Drive connector was available). Paste each block into the matching doc. Each block says where it goes.

---

## 1. data-mapping (Drive: Dashboard Specs) — append as section 10

**10. ChatGPT Ads — Ads and Ad Groups → Unified Dashboard Schema**

Files: `openaiads_ads_{start}-{end}.csv` and `openaiads_adgroups_{start}-{end}.csv`, in the "ChatGPT Ads" Drive folder. Standard UTF-8 CSV with a header row (unlike LinkedIn: no metadata lines, not UTF-16). One row per ad / ad group for the whole Wednesday–Tuesday week; there is no date column, the dates come from the file name. USD.

Ads → `table_type: chatgpt_ad`, `platform: chatgpt`:
campaign_name, ad_group_name, ad_name, ad_status, review_status, ad_title, ad_copy, ad_url, impressions, clicks, conversions, spend map to fields of the same name.

Ad groups → `table_type: chatgpt_adgroup`: campaign_name, ad_group_name, ad_group_status, billing_event_type, max_bid, impressions, clicks, conversions, spend. `context_hints` is not stored.

ctr, cpc and cpm are NOT taken from the export. They are recomputed from spend, impressions and clicks (the export's cpc/cpm do not reconcile). ctr is expressed as a percentage.

Week-over-week: ChatGPT exports have no compare columns. When building a snapshot, read the previous week's snapshot and copy matching records' spend, impressions, clicks and conversions into `spend_prior_period`, `impressions_prior_period`, `clicks_prior_period`, `conversions_prior_period`, and set `wow_spend_change_pct`. Ads match on (ad_group_name, ad_name); ad groups on ad_group_name. An ad with no match last week has prior values of 0 and a blank WoW. First tracked week: 2026-10-07 (all prior fields null).

Also fix in section 2–3: LinkedIn numeric values can contain thousands separators ("1,420.80"); strip commas before converting. Google Ads keyword rows must be grouped by (campaign, ad group, criterion id), not criterion id alone.

---

## 2. dashboard-spec (Drive: Dashboard Specs)

Layout order (replace item 2): Top navigation: Combined | Google Ads | LinkedIn Ads | ChatGPT Ads | Trends.

Header: add "Data through <Tuesday date>" next to the last-updated timestamp.

Combined tab: jump-nav adds "Spend by Channel" and "ChatGPT Ads Totals".
- Combined KPIs now include ChatGPT spend, impressions and clicks; CTR and CPC are recomputed from the blended totals.
- Cost per Conversion excludes ChatGPT spend while ChatGPT reports no conversions (card sub-label says so).
- Week-over-week on Combined is like-for-like: ChatGPT joins the comparison only once it has a prior week.
- Spend by Channel: one stacked bar with legend (LinkedIn, Google Ads, ChatGPT Ads: dollars and share).
- ChatGPT Ads Totals: Spend, Impressions, Clicks, CTR, CPC, CPM, Conversions, Cost / Conversion.

ChatGPT Ads tab (jump-nav: Totals, Ad Group, Ad Performance):
- "Data as of" line.
- Ad Group Performance: Campaign Name | Ad Group Name | Status | Billing Event | Max Bid | Spend | Impressions | Clicks | CTR | CPC | CPM | Conversions | WoW Spend Change %
- Ad Performance (creative-level): Ad Name | Ad Group Name | Status | Review | Headline | Ad Copy | Spend | Impressions | Clicks | CTR | CPC | CPM | Conversions | WoW Spend Change %
- Weeks without ChatGPT data (before 2026-10-07) show "No ChatGPT Ads data for this week".

Trends tab: adds a ChatGPT Ads spend series (stacked chart, table column and KPI card). The TRENDS list in the artifact is hardcoded and gets a new row every refresh.

Known limitation (add): ChatGPT's first tracked week (2026-10-07) has no prior week, so its WoW is blank. Expected, not a bug.

---

## 3. Weekly Dashboard Update Guide (Drive: Claude - Paid Ads Project)

Key Resource Locations: add a row "ChatGPT Ads exports: Drive folder 'ChatGPT Ads' (Weekly Report Files)" and "Runbook: WEEKLY_UPDATE_RUNBOOK.md in the dashboard repo (docs/)".

Replace step 1–3 with: export the 3 LinkedIn reports and the 2 ChatGPT Ads reports (ads, ad groups); name them `linkedinads_{type}_{start}-{end}.csv` (ISO dates, e.g. 2026-10-07-2026-10-13) and `openaiads_ads_{start}-{end}.csv` / `openaiads_adgroups_{start}-{end}.csv`; upload LinkedIn files to "LinkedIn Ads" and ChatGPT files to "ChatGPT Ads".

Replace the refresh prompt with the one in the runbook (checks both folders, passes the previous snapshot for ChatGPT WoW, customer ID 4071709382).

Add after step 5: "Claude stages snapshot, index.json and google-ads-history.json in ~/ads-dashboard-upload/<week>/. Upload the snapshot to LinkedIn Ads/history; replace google-ads-history.json and index.json using Manage versions → Upload new version (never 'Keep both')."

Add to step 7: confirm the ChatGPT Ads tab shows the new week.
