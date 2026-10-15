# ChatGPT Ads Data Dictionary

Source: ChatGPT Ads Manager exports `openaiads_ads_<start>-<end>.csv` and `openaiads_adgroups_<start>-<end>.csv`. Grain: one row per ad (ads file) or per ad group (ad groups file) for one Wednesday–Tuesday week. Currency: USD. The export has no date column; the week comes from the file name.

## Ads file → `chatgpt_ad` record

| Export column | Record field | Type | Notes |
|---|---|---|---|
| campaign_name | campaign_name | text | |
| ad_group_name | ad_group_name | text | With ad_name, identifies an ad for week-over-week matching |
| ad_name | ad_name | text | |
| ad_status | ad_status | text | `active`, `paused` |
| review_status | review_status | text | e.g. `approved` |
| ad_title | ad_title | text | Shown as "Headline" in the dashboard |
| ad_copy | ad_copy | text | |
| ad_url | ad_url | text | Includes UTM parameters (`utm_source=openai`) |
| impressions | impressions | number | |
| clicks | clicks | number | |
| conversions | conversions | number | 0 for every ad so far; tracking status unconfirmed |
| spend | spend | USD | |
| ctr | ctr | % | Recomputed: clicks ÷ impressions × 100. Export value is a fraction (0.0077) or a string ("0.98%") depending on export version, so it is not used |
| cpc | cpc | USD | Recomputed: spend ÷ clicks |
| cpm | cpm | USD | Recomputed: spend ÷ impressions × 1000 |
| (derived) | `*_prior_period`, wow_spend_change_pct | number | Filled from the previous week's snapshot; null in the first tracked week (2026-10-07) |

## Ad groups file → `chatgpt_adgroup` record

Same metric columns as above, plus:

| Export column | Record field | Notes |
|---|---|---|
| ad_group_status | ad_group_status | `active`, `paused` |
| billing_event_type | billing_event_type | `click` so far |
| max_bid | max_bid | USD |
| context_hints | not stored | Targeting prompt text; not shown on the dashboard |

## Metric mapping to the unified dashboard metrics

| Dashboard metric | ChatGPT source | Comparable to Google Ads / LinkedIn? |
|---|---|---|
| Spend | spend | Yes |
| Impressions | impressions | **Unconfirmed.** ChatGPT's impression definition is not documented; may not equal a search or feed impression |
| Clicks | clicks | **Unconfirmed.** Definition and click-filtering not documented |
| CTR, CPC, CPM | derived | Same formulas, but depend on the two rows above |
| Conversions | conversions | Not comparable until tracking and the attribution window are confirmed. Currently 0 |
| Cost / Conversion | spend ÷ conversions | Shown as "—" while conversions are 0; ChatGPT spend is excluded from Combined Cost / Conversion until conversions are reported |
| Engagements, Cost / Engagement | not provided | LinkedIn only (unchanged) |
| ROAS, conversion value | not provided | Not available for any channel on the dashboard |

## Known data issues

1. **Export CPC/CPM do not reconcile.** In the 2026-09-28 sample, CPM differed from spend ÷ impressions × 1000 on all six rows, and CPC differed from spend ÷ clicks on four of six. Raise with ChatGPT; until resolved the dashboard derives all ratios.
2. **First export had no date range.** The 2026-09-28 sample sheet (Drive: ChatGPT / Reporting) is not used by the dashboard.
3. **Export format varies.** That sample was a Google Sheet with percent strings; the current files are CSV with fractional ctr. The parser reads only counts and spend, so this does not affect results.

## Snapshot placement

Records are added to the normal weekly snapshot (`snapshot_<start>-<end>.json`) next to the Google Ads and LinkedIn records, with `platform: "chatgpt"`. `meta.counts` includes `chatgpt_ad` and `chatgpt_adgroup`. Earlier snapshots have none and are not modified; the dashboard shows "No ChatGPT Ads data for this week" for them.
