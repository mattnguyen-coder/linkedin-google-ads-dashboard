#!/usr/bin/env python3
"""
Maintain google-ads-history.json (per dashboard-spec.md) and back-fill
wow_spend_change_pct onto the google_ads_campaign records in unified.json.

Format of google-ads-history.json: a flat JSON array, one entry per
(week, campaign):
    {"week_start": "2026-08-05", "campaign_id": ..., "campaign_name": ...,
     "spend": ..., "impressions": ..., "clicks": ..., "conversions": ...}

Usage:
    python3 history.py <unified.json> <history.json>

Mutates both files in place:
  - unified.json: google_ads_campaign records get wow_spend_change_pct filled in
  - history.json: this week's totals appended (or replaced, if re-run for the
    same week), and a "prior_week_totals" / "current_week_totals" summary is
    printed to stdout for the dashboard generator to use directly if desired.
"""
import json
import sys


def main():
    unified_path, history_path = sys.argv[1:3]

    with open(unified_path, "r", encoding="utf-8") as f:
        unified = json.load(f)

    week_start = unified["meta"]["week_start"]
    ga_records = [r for r in unified["records"] if r["table_type"] == "google_ads_campaign"]

    try:
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    except FileNotFoundError:
        history = []

    # Most recent week strictly before this one.
    prior_weeks = sorted({e["week_start"] for e in history if e["week_start"] < week_start})
    prior_week = prior_weeks[-1] if prior_weeks else None
    prior_by_campaign = {}
    if prior_week:
        for e in history:
            if e["week_start"] == prior_week:
                prior_by_campaign[e["campaign_id"]] = e

    for rec in ga_records:
        prior = prior_by_campaign.get(rec["campaign_id"])
        if prior and prior["spend"]:
            rec["wow_spend_change_pct"] = round(
                (rec["spend"] - prior["spend"]) / prior["spend"] * 100, 2
            )
        else:
            rec["wow_spend_change_pct"] = None

    with open(unified_path, "w", encoding="utf-8") as f:
        json.dump(unified, f, indent=2)

    # Replace any existing entries for this week (idempotent re-run), then append fresh ones.
    history = [e for e in history if e["week_start"] != week_start]
    for rec in ga_records:
        history.append({
            "week_start": week_start,
            "campaign_id": rec["campaign_id"],
            "campaign_name": rec["campaign_name"],
            "spend": rec["spend"],
            "impressions": rec["impressions"],
            "clicks": rec["clicks"],
            "conversions": rec["conversions"],
        })

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    def totals(week):
        entries = [e for e in history if e["week_start"] == week]
        return {
            "spend": sum(e["spend"] for e in entries),
            "impressions": sum(e["impressions"] for e in entries),
            "clicks": sum(e["clicks"] for e in entries),
            "conversions": sum(e["conversions"] for e in entries),
        }

    summary = {
        "week_start": week_start,
        "prior_week": prior_week,
        "current_week_totals": totals(week_start),
        "prior_week_totals": totals(prior_week) if prior_week else None,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
