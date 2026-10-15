#!/usr/bin/env python3
"""
Parse LinkedIn Ads CSVs + Google Ads raw daily export into the unified
schema from data-mapping.md, and aggregate Google Ads to weekly grain.

Usage:
    python3 merge.py <csv_dir> <google_ads_raw.json> <week_start> <week_end> <out_unified.json>

<csv_dir> must contain these 3 files named:
    linkedinads_campaignperformance.csv
    linkedinads_creativeperformance.csv
    linkedinads_demographic.csv
plus an optional linkedinads_creativeplacement.csv (parsed if present, but
no longer shown on the dashboard, so not required).
(already decoded from LinkedIn's UTF-16LE export to UTF-8)
"""
import csv
import json
import os
import sys


_NA_VALUES = {"", "n/a", "N/A", "NA", "-", "--"}


def pct_to_float(s):
    if s is None or s in _NA_VALUES:
        return None
    try:
        return float(s.rstrip("%"))
    except ValueError:
        return None


def num(s):
    if s is None or s in _NA_VALUES:
        return None
    try:
        # LinkedIn exports can contain thousands separators ("1,420.80"); without
        # stripping them, values >= 1000 silently parse to None.
        return float(s.replace(",", ""))
    except ValueError:
        return None


def read_csv_rows(path):
    """Read a tab-delimited file as proper CSV rows (respects quoted fields
    that contain embedded newlines/tabs -- LinkedIn's ad-copy columns do)."""
    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.reader(f, delimiter="\t"))


def find_header_row(rows, required_tokens):
    """Find the first row containing all required_tokens as cells."""
    for i, row in enumerate(rows):
        if all(tok in row for tok in required_tokens):
            return i, row
    raise ValueError(f"Could not find header row containing {required_tokens}")


def parse_ad_set_or_creative_file(path, required_tokens, table_type, week_start, week_end, warnings):
    """Shared parser for campaignperformance / creativeperformance / creativeplacement."""
    rows = read_csv_rows(path)
    header_idx, header = find_header_row(rows, required_tokens)
    col = {name: i for i, name in enumerate(header)}

    records = []
    for cells in rows[header_idx + 1:]:
        if not cells or not any(cells):
            continue
        if len(cells) < len(header):
            cells = cells + [""] * (len(header) - len(cells))

        def c(name):
            return cells[col[name]] if name in col else None

        rec = {
            "table_type": table_type,
            "platform": "linkedin",
            "date_range_start": week_start,
            "date_range_end": week_end,
            "campaign_id": c("Campaign ID"),
            "campaign_name": c("Campaign Name"),
            "campaign_status": c("Campaign Status"),
            "ad_set_id": c("Ad Set ID"),
            "ad_set_name": c("Ad Set Name"),
            "ad_id": c("Ad ID"),
            "ad_name": c("Ad Name"),
            "ad_headline": c("Ad Headline"),
            "ad_intro_text": c("Ad Introduction Text"),
            "video_length_sec": num(c("Video Length (in Seconds)")),
            "placement": c("Placement"),
            "spend": num(c("Total Spent")),
            "spend_prior_period": num(c("Total Spent Compare Time Range")),
            "wow_spend_change_pct": pct_to_float(c("Total Spent Percentage Difference")),
            "impressions": num(c("Impressions")),
            "impressions_prior_period": num(c("Impressions Compare Time Range")),
            "clicks": num(c("Clicks")),
            "clicks_prior_period": num(c("Clicks Compare Time Range")),
            "ctr": pct_to_float(c("Click Through Rate")),
            "cpm": num(c("Average CPM")),
            "cpc": num(c("Average CPC")),
            "reactions": num(c("Reactions")),
            "comments": num(c("Comments")),
            "shares": num(c("Shares")),
            "follows": num(c("Follows")),
            "engagement_total": num(c("Total Engagements")),
            "engagement_total_prior_period": num(c("Total Engagements Compare Time Range")),
            "engagement_rate": pct_to_float(c("Engagement Rate")),
            "conversions": num(c("Conversions")),
            "conversions_prior_period": num(c("Conversions Compare Time Range")),
            "conversion_value": num(c("Total Conversion Value")),
        }
        records.append(rec)
    return records


def parse_demographics(path, week_start, week_end, warnings):
    all_rows = read_csv_rows(path)
    # Find first block header: a row whose first cell ends with " Segment"
    # and which has an "Impressions" column.
    blocks = []
    i = 0
    n = len(all_rows)
    while i < n:
        cells = all_rows[i]
        if cells and cells[0].endswith(" Segment") and "Impressions" in cells:
            break
        i += 1
    if i == n:
        raise ValueError("No segment header found in demographics file")

    while i < n:
        cells = all_rows[i]
        if not (cells and cells[0].endswith(" Segment") and "Impressions" in cells):
            i += 1
            continue
        header = cells
        col = {name: idx for idx, name in enumerate(header)}
        segment_type = header[0][: -len(" Segment")]
        i += 1
        data_rows = []
        while i < n and all_rows[i] and any(all_rows[i]):
            dcells = all_rows[i]
            if len(dcells) < len(header):
                dcells = dcells + [""] * (len(header) - len(dcells))

            def c(name):
                return dcells[col[name]] if name in col else None

            data_rows.append({
                "table_type": "linkedin_demographic",
                "platform": "linkedin",
                "date_range_start": week_start,
                "date_range_end": week_end,
                "segment_type": segment_type,
                "segment_value": c(header[0]),
                "impressions": num(c("Impressions")),
                "clicks": num(c("Clicks")),
                "ctr": pct_to_float(c("Click Through Rate")),
                "conversions": num(c("Conversions")),
                "conversion_rate": pct_to_float(c("Conversion Rate")),
            })
            i += 1
        blocks.append((segment_type, data_rows))
        i += 1  # skip blank separator line

    warnings.append(
        f"Demographics: found {len(blocks)} segment blocks: "
        + ", ".join(b[0] for b in blocks)
    )
    for seg_type, rows in blocks:
        if seg_type == "Job Title" and rows:
            sample = rows[0]["segment_value"]
            if sample in ("Engineering", "Information Technology", "Sales", "Operations"):
                warnings.append(
                    "Demographics: block header says 'Job Title Segment' but its values "
                    f"(e.g. '{sample}') look like job FUNCTIONS, not titles. This is how "
                    "LinkedIn labeled it in the source export -- tagged as-is, not corrected."
                )
    return [r for _, rows in blocks for r in rows]


def aggregate_google_ads(raw_path, week_start, week_end):
    with open(raw_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    rows = raw["result"] if isinstance(raw, dict) and "result" in raw else raw

    by_campaign = {}
    for r in rows:
        cid = r["campaign.id"]
        b = by_campaign.setdefault(cid, {
            "campaign_id": cid,
            "campaign_name": r["campaign.name"],
            "campaign_status": r["campaign.status"],
            "channel_type": r["campaign.advertising_channel_type"],
            "impressions": 0.0,
            "clicks": 0.0,
            "spend": 0.0,
            "conversions": 0.0,
            "conversion_value": 0.0,
        })
        b["impressions"] += r.get("metrics.impressions", 0) or 0
        b["clicks"] += r.get("metrics.clicks", 0) or 0
        b["spend"] += (r.get("metrics.cost_micros", 0) or 0) / 1_000_000
        b["conversions"] += r.get("metrics.conversions", 0) or 0
        b["conversion_value"] += r.get("metrics.conversions_value", 0) or 0

    records = []
    for b in by_campaign.values():
        ctr = (b["clicks"] / b["impressions"] * 100) if b["impressions"] else 0.0
        cpc = (b["spend"] / b["clicks"]) if b["clicks"] else 0.0
        records.append({
            "table_type": "google_ads_campaign",
            "platform": "google_ads",
            "date_range_start": week_start,
            "date_range_end": week_end,
            "campaign_id": b["campaign_id"],
            "campaign_name": b["campaign_name"],
            "campaign_status": b["campaign_status"],
            "channel_type": b["channel_type"],
            "spend": round(b["spend"], 2),
            "impressions": b["impressions"],
            "clicks": b["clicks"],
            "ctr": round(ctr, 4),
            "cpc": round(cpc, 4),
            "conversions": b["conversions"],
            "conversion_value": b["conversion_value"],
            "wow_spend_change_pct": None,  # filled in by history.py
        })
    return records


# Google Ads country-criterion IDs follow "2" + ISO 3166-1 numeric code.
_COUNTRY_CRITERION_NAMES = {
    2036: "Australia", 2076: "Brazil", 2124: "Canada", 2156: "China", 2208: "Denmark",
    2246: "Finland", 2250: "France", 2276: "Germany", 2344: "Hong Kong", 2352: "Iceland",
    2356: "India", 2372: "Ireland", 2380: "Italy", 2392: "Japan", 2410: "South Korea",
    2458: "Malaysia", 2484: "Mexico", 2528: "Netherlands", 2554: "New Zealand",
    2578: "Norway", 2608: "Philippines", 2620: "Portugal", 2702: "Singapore",
    2710: "South Africa", 2724: "Spain", 2752: "Sweden", 2756: "Switzerland",
    2764: "Thailand", 2784: "United Arab Emirates", 2826: "United Kingdom",
    2840: "United States", 2158: "Taiwan", 2818: "Egypt", 2032: "Argentina",
}


def _aggregate_daily_to_weekly(rows, key_fn, base_fields_fn, sum_fields, week_start, week_end, table_type):
    """Generic daily-rows -> one-row-per-key weekly aggregator for Google Ads views."""
    buckets = {}
    for r in rows:
        key = key_fn(r)
        b = buckets.setdefault(key, {**base_fields_fn(r), **{f: 0.0 for f in sum_fields}})
        for f in sum_fields:
            b[f] += r.get(f, 0) or 0
    records = []
    for b in buckets.values():
        impressions = b.get("metrics.impressions", 0)
        clicks = b.get("metrics.clicks", 0)
        spend = b.get("metrics.cost_micros", 0) / 1_000_000
        conversions = b.get("metrics.conversions", 0)
        rec = {
            "table_type": table_type,
            "platform": "google_ads",
            "date_range_start": week_start,
            "date_range_end": week_end,
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round((clicks / impressions * 100) if impressions else 0.0, 4),
            "cpc": round((spend / clicks) if clicks else 0.0, 4),
            "conversions": conversions,
            "conversion_value": b.get("metrics.conversions_value", 0),
        }
        for k, v in b.items():
            if not k.startswith("metrics."):
                rec[k] = v
        records.append(rec)
    return records


def aggregate_ga_ad_groups(raw_path, week_start, week_end):
    rows = json.load(open(raw_path, encoding="utf-8"))
    rows = rows["result"] if isinstance(rows, dict) else rows
    return _aggregate_daily_to_weekly(
        rows,
        key_fn=lambda r: r["ad_group.id"],
        base_fields_fn=lambda r: {
            "campaign_id": r["campaign.id"], "campaign_name": r["campaign.name"],
            "ad_group_id": r["ad_group.id"], "ad_group_name": r["ad_group.name"],
            "ad_group_status": r["ad_group.status"],
        },
        sum_fields=["metrics.impressions", "metrics.clicks", "metrics.cost_micros",
                    "metrics.conversions", "metrics.conversions_value"],
        week_start=week_start, week_end=week_end, table_type="google_ads_adgroup",
    )


def aggregate_ga_keywords(raw_path, week_start, week_end):
    rows = json.load(open(raw_path, encoding="utf-8"))
    rows = rows["result"] if isinstance(rows, dict) else rows
    return _aggregate_daily_to_weekly(
        rows,
        key_fn=lambda r: (r["campaign.id"], r["ad_group.name"], r["ad_group_criterion.criterion_id"]),  # criterion_id alone repeats across ad groups
        base_fields_fn=lambda r: {
            "campaign_id": r["campaign.id"], "campaign_name": r["campaign.name"],
            "ad_group_name": r["ad_group.name"],
            "keyword_text": r["ad_group_criterion.keyword.text"],
            "match_type": r["ad_group_criterion.keyword.match_type"],
        },
        sum_fields=["metrics.impressions", "metrics.clicks", "metrics.cost_micros",
                    "metrics.conversions", "metrics.conversions_value"],
        week_start=week_start, week_end=week_end, table_type="google_ads_keyword",
    )


def aggregate_ga_geo(raw_path, week_start, week_end):
    rows = json.load(open(raw_path, encoding="utf-8"))
    rows = rows["result"] if isinstance(rows, dict) else rows
    return _aggregate_daily_to_weekly(
        rows,
        key_fn=lambda r: (r["campaign.id"], r["geographic_view.country_criterion_id"]),
        base_fields_fn=lambda r: {
            "campaign_id": r["campaign.id"], "campaign_name": r["campaign.name"],
            "country_criterion_id": r["geographic_view.country_criterion_id"],
            "country_name": _COUNTRY_CRITERION_NAMES.get(
                r["geographic_view.country_criterion_id"],
                f"Criterion {r['geographic_view.country_criterion_id']}",
            ),
            "location_type": r["geographic_view.location_type"],
        },
        sum_fields=["metrics.impressions", "metrics.clicks", "metrics.cost_micros",
                    "metrics.conversions", "metrics.conversions_value"],
        week_start=week_start, week_end=week_end, table_type="google_ads_geo",
    )


def aggregate_ga_search_terms(raw_path, week_start, week_end):
    rows = json.load(open(raw_path, encoding="utf-8"))
    rows = rows["result"] if isinstance(rows, dict) else rows
    return _aggregate_daily_to_weekly(
        rows,
        key_fn=lambda r: (r["ad_group.id"], r["search_term_view.search_term"]),
        base_fields_fn=lambda r: {
            "campaign_id": r["campaign.id"], "campaign_name": r["campaign.name"],
            "ad_group_name": r["ad_group.name"],
            "search_term": r["search_term_view.search_term"],
            "search_term_status": r["search_term_view.status"],
        },
        sum_fields=["metrics.impressions", "metrics.clicks", "metrics.cost_micros",
                    "metrics.conversions", "metrics.conversions_value"],
        week_start=week_start, week_end=week_end, table_type="google_ads_searchterm",
    )


def _ratios(spend, impressions, clicks):
    """Derive CTR (%), CPC and CPM from raw totals. ChatGPT's own cpc/cpm columns
    don't reconcile with spend/clicks and spend/impressions, so they're not used."""
    ctr = round(clicks / impressions * 100, 4) if impressions else 0.0
    cpc = round(spend / clicks, 4) if clicks else 0.0
    cpm = round(spend / impressions * 1000, 4) if impressions else 0.0
    return ctr, cpc, cpm


def _read_utf8_csv(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def parse_chatgpt_ads(path, week_start, week_end, warnings):
    """ChatGPT Ads ad-level export (openaiads_ads_*.csv) -> chatgpt_ad records."""
    records = []
    for r in _read_utf8_csv(path):
        spend, impressions, clicks = num(r["spend"]) or 0.0, num(r["impressions"]) or 0.0, num(r["clicks"]) or 0.0
        ctr, cpc, cpm = _ratios(spend, impressions, clicks)
        records.append({
            "table_type": "chatgpt_ad",
            "platform": "chatgpt",
            "date_range_start": week_start,
            "date_range_end": week_end,
            "campaign_name": r["campaign_name"],
            "ad_group_name": r["ad_group_name"],
            "ad_name": r["ad_name"],
            "ad_status": r["ad_status"],
            "review_status": r["review_status"],
            "ad_title": r["ad_title"],
            "ad_copy": r["ad_copy"],
            "ad_url": r["ad_url"],
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": num(r["conversions"]) or 0.0,
            "ctr": ctr, "cpc": cpc, "cpm": cpm,
            # No ChatGPT history yet (first tracked week) -- WoW stays blank.
            "spend_prior_period": None, "impressions_prior_period": None,
            "clicks_prior_period": None, "conversions_prior_period": None,
            "wow_spend_change_pct": None,
        })
    return records


def parse_chatgpt_adgroups(path, week_start, week_end, warnings):
    """ChatGPT Ads ad-group export (openaiads_adgroups_*.csv) -> chatgpt_adgroup records."""
    records = []
    for r in _read_utf8_csv(path):
        spend, impressions, clicks = num(r["spend"]) or 0.0, num(r["impressions"]) or 0.0, num(r["clicks"]) or 0.0
        ctr, cpc, cpm = _ratios(spend, impressions, clicks)
        records.append({
            "table_type": "chatgpt_adgroup",
            "platform": "chatgpt",
            "date_range_start": week_start,
            "date_range_end": week_end,
            "campaign_name": r["campaign_name"],
            "ad_group_name": r["ad_group_name"],
            "ad_group_status": r["ad_group_status"],
            "billing_event_type": r.get("billing_event_type"),
            "max_bid": num(r.get("max_bid")),
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": num(r["conversions"]) or 0.0,
            "ctr": ctr, "cpc": cpc, "cpm": cpm,
            "spend_prior_period": None, "impressions_prior_period": None,
            "clicks_prior_period": None, "conversions_prior_period": None,
            "wow_spend_change_pct": None,
        })
    return records


def apply_chatgpt_prior(records, prior_snapshot_path, warnings):
    """Fill *_prior_period and wow_spend_change_pct on ChatGPT records from the previous
    week's snapshot (ChatGPT exports carry no compare columns, unlike LinkedIn)."""
    if not prior_snapshot_path or not os.path.exists(prior_snapshot_path):
        return
    with open(prior_snapshot_path, "r", encoding="utf-8") as f:
        prior = json.load(f)
    key = {"chatgpt_ad": lambda r: (r["ad_group_name"], r["ad_name"]),
           "chatgpt_adgroup": lambda r: (r["ad_group_name"],)}
    prior_by = {}
    for r in prior["records"]:
        if r["table_type"] in key:
            prior_by[(r["table_type"], key[r["table_type"]](r))] = r
    if not prior_by:
        warnings.append("ChatGPT Ads: prior snapshot has no ChatGPT records -- WoW left blank.")
        return
    for r in records:
        p = prior_by.get((r["table_type"], key[r["table_type"]](r)))
        # An ad that did not exist last week counts as 0 prior spend (WoW stays blank, totals stay comparable).
        r["spend_prior_period"] = p["spend"] if p else 0.0
        r["impressions_prior_period"] = p["impressions"] if p else 0.0
        r["clicks_prior_period"] = p["clicks"] if p else 0.0
        r["conversions_prior_period"] = p["conversions"] if p else 0.0
        r["wow_spend_change_pct"] = (
            round((r["spend"] - p["spend"]) / p["spend"] * 100, 2) if p and p["spend"] else None
        )


def main():
    (csv_dir, ga_raw_path, ga_adgroup_path, ga_keyword_path, ga_geo_path,
     ga_searchterm_path, week_start, week_end, out_path) = sys.argv[1:10]
    # Optional: ChatGPT Ads exports (openaiads_ads_*.csv, openaiads_adgroups_*.csv)
    chatgpt_ads_path = sys.argv[10] if len(sys.argv) > 10 else None
    chatgpt_adgroups_path = sys.argv[11] if len(sys.argv) > 11 else None
    # Optional: previous week's snapshot_*.json, used to fill ChatGPT prior-period values.
    prior_snapshot_path = sys.argv[12] if len(sys.argv) > 12 else None
    warnings = []

    campaign_perf = parse_ad_set_or_creative_file(
        f"{csv_dir}/linkedinads_campaignperformance.csv",
        ["Campaign ID", "Ad Set ID", "Total Spent"],
        "linkedin_campaign", week_start, week_end, warnings,
    )
    creative_perf = parse_ad_set_or_creative_file(
        f"{csv_dir}/linkedinads_creativeperformance.csv",
        ["Campaign ID", "Ad ID", "Total Spent"],
        "linkedin_creative", week_start, week_end, warnings,
    )
    placement_path = f"{csv_dir}/linkedinads_creativeplacement.csv"
    if os.path.exists(placement_path):
        creative_placement = parse_ad_set_or_creative_file(
            placement_path,
            ["Campaign ID", "Ad ID", "Placement", "Total Spent"],
            "linkedin_placement", week_start, week_end, warnings,
        )
    else:
        creative_placement = []
        warnings.append(
            "linkedinads_creativeplacement.csv not provided this week -- "
            "skipped (Creative Placement is no longer shown on the dashboard)."
        )
    demographics = parse_demographics(
        f"{csv_dir}/linkedinads_demographic.csv", week_start, week_end, warnings,
    )
    google_ads = aggregate_google_ads(ga_raw_path, week_start, week_end)
    google_ads_adgroup = aggregate_ga_ad_groups(ga_adgroup_path, week_start, week_end)
    google_ads_keyword = aggregate_ga_keywords(ga_keyword_path, week_start, week_end)
    google_ads_geo = aggregate_ga_geo(ga_geo_path, week_start, week_end)
    google_ads_searchterm = aggregate_ga_search_terms(ga_searchterm_path, week_start, week_end)

    # The dashboard only ever shows the top N search terms by spend (dashboard-spec.md).
    # Trim here so the per-week snapshot stored in Drive stays small -- most raw search
    # term rows are near-zero spend and would otherwise dominate the file.
    SEARCH_TERM_TOP_N = 50
    search_term_total = len(google_ads_searchterm)
    google_ads_searchterm.sort(key=lambda r: r["spend"], reverse=True)
    search_term_omitted = max(0, search_term_total - SEARCH_TERM_TOP_N)
    google_ads_searchterm = google_ads_searchterm[:SEARCH_TERM_TOP_N]
    if search_term_omitted:
        warnings.append(
            f"Search Term Performance: kept top {SEARCH_TERM_TOP_N} of "
            f"{search_term_total} rows by spend ({search_term_omitted} omitted)."
        )

    # Creative Placement is parsed (when the optional CSV is present) only to report a
    # row count -- it isn't rendered anywhere on the dashboard, so it's excluded from
    # the stored records to keep the per-week snapshot small.
    chatgpt_ads = parse_chatgpt_ads(chatgpt_ads_path, week_start, week_end, warnings) if chatgpt_ads_path else []
    chatgpt_adgroups = (
        parse_chatgpt_adgroups(chatgpt_adgroups_path, week_start, week_end, warnings)
        if chatgpt_adgroups_path else []
    )
    if chatgpt_ads or chatgpt_adgroups:
        apply_chatgpt_prior(chatgpt_ads + chatgpt_adgroups, prior_snapshot_path, warnings)
        if not prior_snapshot_path:
            warnings.append(
                "ChatGPT Ads: first tracked week -- no prior-week data, so ChatGPT week-over-week is blank."
            )
        warnings.append(
            "ChatGPT Ads: CTR/CPC/CPM are derived from spend, impressions and clicks (export's cpc/cpm columns not used)."
        )
        if chatgpt_ads and chatgpt_adgroups:
            ad_spend = round(sum(r["spend"] for r in chatgpt_ads), 2)
            grp_spend = round(sum(r["spend"] for r in chatgpt_adgroups), 2)
            if abs(ad_spend - grp_spend) > 0.01:
                warnings.append(
                    f"ChatGPT Ads: ad-level spend ${ad_spend:,.2f} does not match ad-group spend ${grp_spend:,.2f}."
                )

    all_records = (
        campaign_perf + creative_perf + demographics + google_ads
        + google_ads_adgroup + google_ads_keyword + google_ads_geo + google_ads_searchterm
        + chatgpt_ads + chatgpt_adgroups
    )

    out = {
        "meta": {
            "week_start": week_start,
            "week_end": week_end,
            "counts": {
                "linkedin_campaign": len(campaign_perf),
                "linkedin_creative": len(creative_perf),
                "linkedin_placement": len(creative_placement),
                "linkedin_demographic": len(demographics),
                "google_ads_campaign": len(google_ads),
                "google_ads_adgroup": len(google_ads_adgroup),
                "google_ads_keyword": len(google_ads_keyword),
                "google_ads_geo": len(google_ads_geo),
                "google_ads_searchterm": len(google_ads_searchterm),
                "chatgpt_ad": len(chatgpt_ads),
                "chatgpt_adgroup": len(chatgpt_adgroups),
            },
            "warnings": warnings,
        },
        "records": all_records,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(json.dumps(out["meta"], indent=2))


if __name__ == "__main__":
    main()
