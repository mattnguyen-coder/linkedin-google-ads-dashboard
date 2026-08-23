#!/usr/bin/env python3
"""
Render dashboard.html from unified.json + google-ads-history.json.

Structure: top-level tabs (Combined / Google Ads / LinkedIn Ads), each with
its own in-page jump-nav to its tables/topics.

Usage:
    python3 generate_dashboard.py <unified.json> <history.json> <out.html> [generated_at_iso]
"""
import html
import json
import sys
from datetime import datetime, timezone

SEARCH_TERM_TOP_N = 50


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def fmt_money(v):
    return "—" if v is None else f"${v:,.2f}"


def fmt_int(v):
    return "—" if v is None else f"{v:,.0f}"


def fmt_pct(v, decimals=2):
    return "—" if v is None else f"{v:,.{decimals}f}%"


def safe_div(a, b):
    return (a / b) if b else None


def wow_badge(pct):
    if pct is None:
        return '<span class="wow wow-na">—</span>'
    cls = "wow-up" if pct > 0 else ("wow-down" if pct < 0 else "wow-flat")
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "▪")
    return f'<span class="wow {cls}">{arrow} {abs(pct):,.1f}%</span>'


def week_label(start, end):
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    if s.month == e.month:
        return f"{s.strftime('%b %-d')} – {e.strftime('%-d, %Y')}"
    return f"{s.strftime('%b %-d')} – {e.strftime('%b %-d, %Y')}"


def kpi_card(label, value, wow_pct=None, sub=None):
    sub_html = f'<div class="kpi-sub">{esc(sub)}</div>' if sub else ""
    return f"""
    <div class="kpi-card">
      <div class="kpi-label">{esc(label)}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-wow">{wow_badge(wow_pct)}</div>
      {sub_html}
    </div>"""


def wow(now, prior):
    if prior is None or not prior:
        return None
    return (now - prior) / prior * 100


def table_section(anchor, title, note, thead, rows_html):
    note_html = f'<p class="note">{note}</p>' if note else ""
    return f"""
    <section id="{anchor}" class="topic">
      <h3>{esc(title)}</h3>
      {note_html}
      <div class="table-scroll">
      <table>
        <thead><tr>{thead}</tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      </div>
    </section>"""


def main():
    unified_path, history_path, out_path = sys.argv[1:4]
    generated_at = sys.argv[4] if len(sys.argv) > 4 else datetime.now(timezone.utc).isoformat()

    unified = json.load(open(unified_path, encoding="utf-8"))
    history = json.load(open(history_path, encoding="utf-8"))
    meta = unified["meta"]
    records = unified["records"]
    week_start, week_end = meta["week_start"], meta["week_end"]

    ga = [r for r in records if r["table_type"] == "google_ads_campaign"]
    ga_adgroup = [r for r in records if r["table_type"] == "google_ads_adgroup"]
    ga_keyword = [r for r in records if r["table_type"] == "google_ads_keyword"]
    ga_geo = [r for r in records if r["table_type"] == "google_ads_geo"]
    ga_searchterm = [r for r in records if r["table_type"] == "google_ads_searchterm"]
    li_camp = [r for r in records if r["table_type"] == "linkedin_campaign"]  # ad-set level
    li_creative = [r for r in records if r["table_type"] == "linkedin_creative"]
    li_demo = [r for r in records if r["table_type"] == "linkedin_demographic"]

    def s(rows, field):
        return sum((r.get(field) or 0) for r in rows)

    # ---- Google Ads totals (current + prior, from history) ----
    ga_now = {
        "spend": s(ga, "spend"), "impressions": s(ga, "impressions"),
        "clicks": s(ga, "clicks"), "conversions": s(ga, "conversions"),
        "conversion_value": s(ga, "conversion_value"),
    }
    prior_weeks = sorted({e["week_start"] for e in history if e["week_start"] < week_start})
    prior_week = prior_weeks[-1] if prior_weeks else None
    if prior_week:
        prior_entries = [e for e in history if e["week_start"] == prior_week]
        ga_prior = {
            "spend": sum(e["spend"] for e in prior_entries),
            "impressions": sum(e["impressions"] for e in prior_entries),
            "clicks": sum(e["clicks"] for e in prior_entries),
            "conversions": sum(e["conversions"] for e in prior_entries),
        }
    else:
        ga_prior = None

    ga_ctr = safe_div(ga_now["clicks"], ga_now["impressions"])
    ga_ctr_pct = ga_ctr * 100 if ga_ctr is not None else None
    ga_cpc = safe_div(ga_now["spend"], ga_now["clicks"])
    ga_cost_per_conv = safe_div(ga_now["spend"], ga_now["conversions"])
    if ga_prior:
        ga_prior_ctr = safe_div(ga_prior["clicks"], ga_prior["impressions"])
        ga_prior_cpc = safe_div(ga_prior["spend"], ga_prior["clicks"])
        ga_prior_cost_per_conv = safe_div(ga_prior["spend"], ga_prior["conversions"])
    ga_wow = {
        "spend": wow(ga_now["spend"], ga_prior["spend"]) if ga_prior else None,
        "impressions": wow(ga_now["impressions"], ga_prior["impressions"]) if ga_prior else None,
        "clicks": wow(ga_now["clicks"], ga_prior["clicks"]) if ga_prior else None,
        "conversions": wow(ga_now["conversions"], ga_prior["conversions"]) if ga_prior else None,
        "ctr": wow(ga_ctr, ga_prior_ctr) if ga_prior and ga_prior_ctr else None,
        "cpc": wow(ga_cpc, ga_prior_cpc) if ga_prior and ga_prior_cpc else None,
        "cost_per_conv": wow(ga_cost_per_conv, ga_prior_cost_per_conv) if ga_prior and ga_prior_cost_per_conv else None,
    }

    # ---- LinkedIn totals (current + prior, from Compare-range columns) ----
    li_now = {
        "spend": s(li_camp, "spend"), "impressions": s(li_camp, "impressions"),
        "clicks": s(li_camp, "clicks"), "conversions": s(li_camp, "conversions"),
        "conversion_value": s(li_camp, "conversion_value"),
        "engagement_total": s(li_camp, "engagement_total"),
    }
    li_prior = {
        "spend": s(li_camp, "spend_prior_period"), "impressions": s(li_camp, "impressions_prior_period"),
        "clicks": s(li_camp, "clicks_prior_period"), "conversions": s(li_camp, "conversions_prior_period"),
        "engagement_total": s(li_camp, "engagement_total_prior_period"),
    }
    li_ctr = safe_div(li_now["clicks"], li_now["impressions"])
    li_ctr_pct = li_ctr * 100 if li_ctr is not None else None
    li_cpc = safe_div(li_now["spend"], li_now["clicks"])
    li_cost_per_conv = safe_div(li_now["spend"], li_now["conversions"])
    li_cost_per_engagement = safe_div(li_now["spend"], li_now["engagement_total"])
    li_prior_ctr = safe_div(li_prior["clicks"], li_prior["impressions"])
    li_prior_cpc = safe_div(li_prior["spend"], li_prior["clicks"])
    li_prior_cost_per_conv = safe_div(li_prior["spend"], li_prior["conversions"])
    li_prior_cost_per_engagement = safe_div(li_prior["spend"], li_prior["engagement_total"])
    li_wow = {
        "spend": wow(li_now["spend"], li_prior["spend"]),
        "impressions": wow(li_now["impressions"], li_prior["impressions"]),
        "clicks": wow(li_now["clicks"], li_prior["clicks"]),
        "conversions": wow(li_now["conversions"], li_prior["conversions"]),
        "engagement_total": wow(li_now["engagement_total"], li_prior["engagement_total"]),
        "ctr": wow(li_ctr, li_prior_ctr) if li_prior_ctr else None,
        "cpc": wow(li_cpc, li_prior_cpc) if li_prior_cpc else None,
        "cost_per_conv": wow(li_cost_per_conv, li_prior_cost_per_conv) if li_prior_cost_per_conv else None,
        "cost_per_engagement": wow(li_cost_per_engagement, li_prior_cost_per_engagement) if li_prior_cost_per_engagement else None,
    }

    # ---- Combined (blend absolute totals, then recompute ratios) ----
    comb_spend = ga_now["spend"] + li_now["spend"]
    comb_impr = ga_now["impressions"] + li_now["impressions"]
    comb_clicks = ga_now["clicks"] + li_now["clicks"]
    comb_conv = ga_now["conversions"] + li_now["conversions"]
    comb_ctr = safe_div(comb_clicks, comb_impr)
    comb_ctr_pct = comb_ctr * 100 if comb_ctr is not None else None
    comb_cpc = safe_div(comb_spend, comb_clicks)
    comb_cost_per_conv = safe_div(comb_spend, comb_conv)
    comb_engagements = li_now["engagement_total"]
    comb_cost_per_engagement = li_cost_per_engagement

    have_both_priors = ga_prior is not None
    if have_both_priors:
        comb_prior_spend = ga_prior["spend"] + li_prior["spend"]
        comb_prior_impr = ga_prior["impressions"] + li_prior["impressions"]
        comb_prior_clicks = ga_prior["clicks"] + li_prior["clicks"]
        comb_prior_conv = ga_prior["conversions"] + li_prior["conversions"]
    else:
        comb_prior_spend = comb_prior_impr = comb_prior_clicks = comb_prior_conv = None

    comb_wow_spend = wow(comb_spend, comb_prior_spend) if have_both_priors else None
    comb_wow_impr = wow(comb_impr, comb_prior_impr) if have_both_priors else None
    comb_wow_clicks = wow(comb_clicks, comb_prior_clicks) if have_both_priors else None
    comb_wow_conv = wow(comb_conv, comb_prior_conv) if have_both_priors else None
    comb_prior_ctr = safe_div(comb_prior_clicks, comb_prior_impr) if have_both_priors else None
    comb_prior_cpc = safe_div(comb_prior_spend, comb_prior_clicks) if have_both_priors else None
    comb_prior_cost_per_conv = safe_div(comb_prior_spend, comb_prior_conv) if have_both_priors else None
    comb_wow_ctr = wow(comb_ctr, comb_prior_ctr) if comb_prior_ctr else None
    comb_wow_cpc = wow(comb_cpc, comb_prior_cpc) if comb_prior_cpc else None
    comb_wow_cost_per_conv = wow(comb_cost_per_conv, comb_prior_cost_per_conv) if comb_prior_cost_per_conv else None
    comb_wow_engagement = li_wow["engagement_total"]
    comb_wow_cost_per_engagement = li_wow["cost_per_engagement"]

    # ================= Executive Summary =================
    wow_clause = ""
    if have_both_priors and comb_wow_spend is not None:
        direction = "up" if comb_wow_spend > 0 else ("down" if comb_wow_spend < 0 else "flat")
        wow_clause = f" That's {direction} {abs(comb_wow_spend):.1f}% week-over-week on spend."
    first_run_clause = (
        " Google Ads week-over-week comparisons aren't available yet — this is the first "
        "tracked week for that history file." if not prior_week else ""
    )
    exec_summary = (
        f"This week ({esc(week_label(week_start, week_end))}), combined marketing spend was "
        f"{fmt_money(comb_spend)} across Google Ads ({fmt_money(ga_now['spend'])}) and "
        f"LinkedIn Ads ({fmt_money(li_now['spend'])}).{wow_clause} "
        f"Combined activity drove {fmt_int(comb_impr)} impressions and {fmt_int(comb_clicks)} clicks "
        f"({fmt_pct(comb_ctr_pct)} CTR) at {fmt_money(comb_cpc)} average CPC, producing "
        f"{fmt_int(comb_conv)} conversions at {fmt_money(comb_cost_per_conv)} cost per conversion. "
        f"LinkedIn also generated {fmt_int(comb_engagements)} engagements at "
        f"{fmt_money(comb_cost_per_engagement)} cost per engagement"
        + (f" ({wow_badge(comb_wow_engagement)} WoW)." if li_wow["engagement_total"] is not None else ".")
        + first_run_clause
    )

    combined_kpis_html = "".join([
        kpi_card("Spend", fmt_money(comb_spend), comb_wow_spend),
        kpi_card("Impressions", fmt_int(comb_impr), comb_wow_impr),
        kpi_card("Clicks", fmt_int(comb_clicks), comb_wow_clicks),
        kpi_card("CTR", fmt_pct(comb_ctr_pct), comb_wow_ctr),
        kpi_card("CPC", fmt_money(comb_cpc), comb_wow_cpc),
        kpi_card("Conversions", fmt_int(comb_conv), comb_wow_conv),
        kpi_card("Cost / Conversion", fmt_money(comb_cost_per_conv), comb_wow_cost_per_conv),
        kpi_card("Engagements", fmt_int(comb_engagements), comb_wow_engagement, sub="LinkedIn only"),
        kpi_card("Cost / Engagement", fmt_money(comb_cost_per_engagement), comb_wow_cost_per_engagement, sub="LinkedIn only"),
    ])

    google_totals_html = "".join([
        kpi_card("Spend", fmt_money(ga_now["spend"]), ga_wow["spend"]),
        kpi_card("Impressions", fmt_int(ga_now["impressions"]), ga_wow["impressions"]),
        kpi_card("Clicks", fmt_int(ga_now["clicks"]), ga_wow["clicks"]),
        kpi_card("CTR", fmt_pct(ga_ctr_pct), ga_wow["ctr"]),
        kpi_card("CPC", fmt_money(ga_cpc), ga_wow["cpc"]),
        kpi_card("Conversions", fmt_int(ga_now["conversions"]), ga_wow["conversions"]),
        kpi_card("Cost / Conversion", fmt_money(ga_cost_per_conv), ga_wow["cost_per_conv"]),
    ])

    linkedin_totals_html = "".join([
        kpi_card("Spend", fmt_money(li_now["spend"]), li_wow["spend"]),
        kpi_card("Impressions", fmt_int(li_now["impressions"]), li_wow["impressions"]),
        kpi_card("Clicks", fmt_int(li_now["clicks"]), li_wow["clicks"]),
        kpi_card("CTR", fmt_pct(li_ctr_pct), li_wow["ctr"]),
        kpi_card("CPC", fmt_money(li_cpc), li_wow["cpc"]),
        kpi_card("Conversions", fmt_int(li_now["conversions"]), li_wow["conversions"]),
        kpi_card("Cost / Conversion", fmt_money(li_cost_per_conv), li_wow["cost_per_conv"]),
        kpi_card("Engagements", fmt_int(li_now["engagement_total"]), li_wow["engagement_total"]),
        kpi_card("Cost / Engagement", fmt_money(li_cost_per_engagement), li_wow["cost_per_engagement"]),
    ])

    if not prior_week:
        ga_first_run_note = (
            "First run for this history file — no prior week to compare against, so WoW is "
            "blank for all Google Ads figures. This is expected, not a bug."
        )
    else:
        ga_first_run_note = None

    # ================= GOOGLE ADS section =================
    ga_campaign_rows = ""
    for r in sorted(ga, key=lambda x: -(x["spend"] or 0)):
        cpc = safe_div(r["spend"], r["clicks"])
        cost_per_conv = safe_div(r["spend"], r["conversions"])
        ga_campaign_rows += f"""<tr>
          <td>{esc(r['campaign_name'])}</td>
          <td><span class="status status-{esc(r['campaign_status']).lower()}">{esc(r['campaign_status'])}</span></td>
          <td>{esc(r['channel_type'])}</td>
          <td class="num">{fmt_money(r['spend'])}</td>
          <td class="num">{fmt_int(r['impressions'])}</td>
          <td class="num">{fmt_int(r['clicks'])}</td>
          <td class="num">{fmt_pct(r['ctr'])}</td>
          <td class="num">{fmt_money(cpc)}</td>
          <td class="num">{fmt_int(r['conversions'])}</td>
          <td class="num">{fmt_money(cost_per_conv)}</td>
          <td class="num">{wow_badge(r['wow_spend_change_pct'])}</td>
        </tr>"""

    ga_adgroup_rows = ""
    for r in sorted(ga_adgroup, key=lambda x: -(x["spend"] or 0)):
        cost_per_conv = safe_div(r["spend"], r["conversions"])
        ga_adgroup_rows += f"""<tr>
          <td>{esc(r['campaign_name'])}</td>
          <td>{esc(r['ad_group_name'])}</td>
          <td><span class="status status-{esc(r['ad_group_status']).lower()}">{esc(r['ad_group_status'])}</span></td>
          <td class="num">{fmt_money(r['spend'])}</td>
          <td class="num">{fmt_int(r['impressions'])}</td>
          <td class="num">{fmt_int(r['clicks'])}</td>
          <td class="num">{fmt_pct(r['ctr'])}</td>
          <td class="num">{fmt_money(r['cpc'])}</td>
          <td class="num">{fmt_int(r['conversions'])}</td>
          <td class="num">{fmt_money(cost_per_conv)}</td>
        </tr>"""

    ga_keyword_rows = ""
    for r in sorted(ga_keyword, key=lambda x: -(x["spend"] or 0)):
        ga_keyword_rows += f"""<tr>
          <td>{esc(r['campaign_name'])}</td>
          <td>{esc(r['ad_group_name'])}</td>
          <td>{esc(r['keyword_text'])}</td>
          <td>{esc(r['match_type'])}</td>
          <td class="num">{fmt_money(r['spend'])}</td>
          <td class="num">{fmt_int(r['impressions'])}</td>
          <td class="num">{fmt_int(r['clicks'])}</td>
          <td class="num">{fmt_pct(r['ctr'])}</td>
          <td class="num">{fmt_money(r['cpc'])}</td>
          <td class="num">{fmt_int(r['conversions'])}</td>
        </tr>"""

    ga_geo_rows = ""
    for r in sorted(ga_geo, key=lambda x: -(x["spend"] or 0)):
        ga_geo_rows += f"""<tr>
          <td>{esc(r['campaign_name'])}</td>
          <td>{esc(r['country_name'])}</td>
          <td>{esc(r['location_type'])}</td>
          <td class="num">{fmt_money(r['spend'])}</td>
          <td class="num">{fmt_int(r['impressions'])}</td>
          <td class="num">{fmt_int(r['clicks'])}</td>
          <td class="num">{fmt_pct(r['ctr'])}</td>
          <td class="num">{fmt_int(r['conversions'])}</td>
        </tr>"""

    searchterm_sorted = sorted(ga_searchterm, key=lambda x: -(x["spend"] or 0))
    ga_searchterm_rows = ""
    for r in searchterm_sorted[:SEARCH_TERM_TOP_N]:
        ga_searchterm_rows += f"""<tr>
          <td>{esc(r['campaign_name'])}</td>
          <td>{esc(r['ad_group_name'])}</td>
          <td>{esc(r['search_term'])}</td>
          <td>{esc(r['search_term_status'])}</td>
          <td class="num">{fmt_money(r['spend'])}</td>
          <td class="num">{fmt_int(r['impressions'])}</td>
          <td class="num">{fmt_int(r['clicks'])}</td>
          <td class="num">{fmt_pct(r['ctr'])}</td>
          <td class="num">{fmt_int(r['conversions'])}</td>
        </tr>"""
    searchterm_note = (
        f"Showing top {SEARCH_TERM_TOP_N} of {len(ga_searchterm)} unique search terms by spend."
    )

    # ================= LINKEDIN section =================
    # Campaign roll-up (NEW): aggregate ad-set rows by campaign_id
    li_campaign_rollup = {}
    for r in li_camp:
        key = r["campaign_id"]
        b = li_campaign_rollup.setdefault(key, {
            "campaign_name": r["campaign_name"], "spend": 0.0, "impressions": 0.0,
            "clicks": 0.0, "engagement_total": 0.0,
            "spend_prior_period": 0.0, "impressions_prior_period": 0.0,
            "clicks_prior_period": 0.0, "engagement_total_prior_period": 0.0,
            "has_spend_prior": False,
        })
        b["spend"] += r["spend"] or 0
        b["impressions"] += r["impressions"] or 0
        b["clicks"] += r["clicks"] or 0
        b["engagement_total"] += r["engagement_total"] or 0
        if r.get("spend_prior_period") is not None:
            b["spend_prior_period"] += r["spend_prior_period"]
            b["has_spend_prior"] = True
        b["impressions_prior_period"] += r.get("impressions_prior_period") or 0
        b["clicks_prior_period"] += r.get("clicks_prior_period") or 0
        b["engagement_total_prior_period"] += r.get("engagement_total_prior_period") or 0

    li_campaign_rows = ""
    for b in sorted(li_campaign_rollup.values(), key=lambda x: -x["spend"]):
        ctr = safe_div(b["clicks"], b["impressions"])
        ctr_pct = ctr * 100 if ctr is not None else None
        cpm = safe_div(b["spend"], b["impressions"] / 1000) if b["impressions"] else None
        cpc = safe_div(b["spend"], b["clicks"])
        engagement_rate = safe_div(b["engagement_total"], b["impressions"])
        engagement_rate_pct = engagement_rate * 100 if engagement_rate is not None else None
        campaign_wow_spend = wow(b["spend"], b["spend_prior_period"]) if b["has_spend_prior"] and b["spend_prior_period"] else None
        li_campaign_rows += f"""<tr>
          <td>{esc(b['campaign_name'])}</td>
          <td class="num">{fmt_money(b['spend'])}</td>
          <td class="num">{fmt_int(b['impressions'])}</td>
          <td class="num">{fmt_int(b['clicks'])}</td>
          <td class="num">{fmt_pct(ctr_pct)}</td>
          <td class="num">{fmt_money(cpm)}</td>
          <td class="num">{fmt_money(cpc)}</td>
          <td class="num">{fmt_int(b['engagement_total'])}</td>
          <td class="num">{fmt_pct(engagement_rate_pct)}</td>
          <td class="num">{wow_badge(campaign_wow_spend)}</td>
        </tr>"""

    li_adset_rows = ""
    for r in sorted(li_camp, key=lambda x: -(x["spend"] or 0)):
        li_adset_rows += f"""<tr>
          <td>{esc(r['campaign_name'])}</td>
          <td>{esc(r['ad_set_name'])}</td>
          <td class="num">{fmt_money(r['spend'])}</td>
          <td class="num">{fmt_int(r['impressions'])}</td>
          <td class="num">{fmt_int(r['clicks'])}</td>
          <td class="num">{fmt_pct(r['ctr'])}</td>
          <td class="num">{fmt_money(r['cpm'])}</td>
          <td class="num">{fmt_money(r['cpc'])}</td>
          <td class="num">{fmt_int(r['engagement_total'])}</td>
          <td class="num">{fmt_pct(r['engagement_rate'])}</td>
          <td class="num">{wow_badge(r['wow_spend_change_pct'])}</td>
        </tr>"""

    li_creative_rows = ""
    for r in sorted(li_creative, key=lambda x: -(x["spend"] or 0)):
        li_creative_rows += f"""<tr>
          <td>{esc(r['ad_name'])}</td>
          <td>{esc(r['ad_set_name'])}</td>
          <td>{esc(r['ad_headline'])}</td>
          <td class="num">{fmt_money(r['spend'])}</td>
          <td class="num">{fmt_int(r['impressions'])}</td>
          <td class="num">{fmt_int(r['clicks'])}</td>
          <td class="num">{fmt_pct(r['ctr'])}</td>
          <td class="num">{fmt_int(r['engagement_total'])}</td>
          <td class="num">{wow_badge(r['wow_spend_change_pct'])}</td>
        </tr>"""

    demo_sections = ""
    demo_nav_items = ""
    seg_types = list(dict.fromkeys(r["segment_type"] for r in li_demo))
    for i, seg_type in enumerate(seg_types):
        seg_rows = [r for r in li_demo if r["segment_type"] == seg_type]
        total_impr = sum(r["impressions"] or 0 for r in seg_rows)
        total_clicks = sum(r["clicks"] or 0 for r in seg_rows)
        rows_html = ""
        for r in sorted(seg_rows, key=lambda x: -(x["impressions"] or 0)):
            pct_impr = safe_div(r["impressions"], total_impr)
            pct_clicks = safe_div(r["clicks"], total_clicks)
            rows_html += f"""<tr>
              <td>{esc(r['segment_value'])}</td>
              <td class="num">{fmt_int(r['impressions'])}</td>
              <td class="num">{fmt_pct(pct_impr * 100 if pct_impr is not None else None)}</td>
              <td class="num">{fmt_int(r['clicks'])}</td>
              <td class="num">{fmt_pct(pct_clicks * 100 if pct_clicks is not None else None)}</td>
              <td class="num">{fmt_pct(r['ctr'])}</td>
              <td class="num">{fmt_int(r['conversions'])}</td>
              <td class="num">{fmt_pct(r['conversion_rate'])}</td>
            </tr>"""
        note = ""
        if seg_type == "Job Title":
            note = ('Note: LinkedIn labeled this block "Job Title Segment" in the source export, '
                    "but its values (Engineering, Sales, Operations...) are job functions, not "
                    "titles. Shown as exported, not corrected.")
        anchor = f"li-demo-{i}"
        demo_nav_items += f'<a href="#{anchor}">{esc(seg_type)}</a>'
        demo_sections += table_section(
            anchor, seg_type, note,
            "<th>Segment Value</th><th class=\"num\">Impressions</th><th class=\"num\">% of Total Impr.</th>"
            "<th class=\"num\">Clicks</th><th class=\"num\">% of Total Clicks</th><th class=\"num\">CTR</th>"
            "<th class=\"num\">Conversions</th><th class=\"num\">Conv. Rate</th>",
            rows_html,
        )

    generated_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))

    # ================= Assemble page =================
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Ads Performance Dashboard</title>
<style>
  :root {{
    --bg: #f7f8fa; --card-bg: #ffffff; --border: #e2e5ea; --text: #1a1d24;
    --text-muted: #6b7280; --accent: #2563eb; --up: #16a34a; --down: #dc2626;
    --flat: #6b7280; --na: #9ca3af; --table-head: #f1f3f6; --row-hover: #fafbfc;
    --accent-soft: rgba(37,99,235,.08); --accent-soft-strong: rgba(37,99,235,.16);
    --up-soft: rgba(22,163,74,.1); --down-soft: rgba(220,38,38,.1); --flat-soft: rgba(107,114,128,.1);
    --status-enabled-bg: rgba(22,163,74,.12); --status-paused-bg: rgba(107,114,128,.12);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #12151b; --card-bg: #1b1f27; --border: #2b303b; --text: #e7e9ee;
      --text-muted: #9aa2b1; --accent: #5b8cff; --up: #34d399; --down: #f87171;
      --flat: #9aa2b1; --na: #6b7280; --table-head: #20242e; --row-hover: #20242e;
      --accent-soft: rgba(91,140,255,.14); --accent-soft-strong: rgba(91,140,255,.24);
      --up-soft: rgba(52,211,153,.14); --down-soft: rgba(248,113,113,.14); --flat-soft: rgba(154,162,177,.14);
      --status-enabled-bg: rgba(52,211,153,.16); --status-paused-bg: rgba(154,162,177,.16);
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #12151b; --card-bg: #1b1f27; --border: #2b303b; --text: #e7e9ee;
    --text-muted: #9aa2b1; --accent: #5b8cff; --up: #34d399; --down: #f87171;
    --flat: #9aa2b1; --na: #6b7280; --table-head: #20242e; --row-hover: #20242e;
    --accent-soft: rgba(91,140,255,.14); --accent-soft-strong: rgba(91,140,255,.24);
    --up-soft: rgba(52,211,153,.14); --down-soft: rgba(248,113,113,.14); --flat-soft: rgba(154,162,177,.14);
    --status-enabled-bg: rgba(52,211,153,.16); --status-paused-bg: rgba(154,162,177,.16);
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
          background: var(--bg); color: var(--text); }}
  .page {{ max-width: 1280px; margin: 0 auto; padding: 0 24px 80px; }}
  header.report-header {{ display: flex; justify-content: space-between; align-items: flex-start;
          padding: 24px 0 20px; border-bottom: 1px solid var(--border); margin-bottom: 0; flex-wrap: wrap; gap: 16px; }}
  header.report-header h1 {{ font-size: 22px; margin: 0 0 4px; }}
  header.report-header .week-range {{ font-size: 15px; color: var(--text-muted); }}
  header.report-header .last-updated {{ font-size: 13px; color: var(--text-muted); margin-top: 6px; }}
  .run-report-btn {{ background: var(--accent); color: white; border: none; border-radius: 6px;
          padding: 10px 18px; font-size: 14px; font-weight: 600; cursor: not-allowed; opacity: 0.55; }}
  .run-report-wrap {{ text-align: right; }}
  .run-report-wrap .hint {{ display: block; font-size: 11px; color: var(--text-muted); margin-top: 6px; max-width: 220px; }}

  .top-nav {{ position: sticky; top: 0; z-index: 20; background: var(--bg); display: flex; gap: 4px;
              border-bottom: 1px solid var(--border); padding-top: 10px; margin-bottom: 20px; }}
  .top-nav button {{ background: none; border: none; font: inherit; font-weight: 600; font-size: 14.5px;
              color: var(--text-muted); padding: 10px 18px; border-bottom: 3px solid transparent; cursor: pointer; }}
  .top-nav button.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
  .top-nav button:hover {{ color: var(--text); }}

  .sub-nav {{ position: sticky; top: 45px; z-index: 15; background: var(--bg); display: flex; flex-wrap: wrap;
              gap: 8px; padding: 8px 0 16px; }}
  .sub-nav a {{ font-size: 12.5px; font-weight: 600; color: var(--accent); background: var(--accent-soft);
              padding: 5px 12px; border-radius: 999px; text-decoration: none; }}
  .sub-nav a:hover {{ background: var(--accent-soft-strong); }}

  .top-section {{ display: none; }}
  .top-section.active {{ display: block; }}

  .topic {{ margin-bottom: 40px; scroll-margin-top: 100px; }}
  .topic h3 {{ font-size: 16px; margin: 0 0 6px; }}
  .subblock {{ margin-bottom: 28px; }}
  .subblock h4 {{ font-size: 12.5px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .04em; margin: 0 0 10px; }}

  h2.exec-summary-title {{ font-size: 17px; border-left: 4px solid var(--accent); padding-left: 10px; margin-bottom: 12px; }}
  .exec-summary-box {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px;
              padding: 18px 20px; font-size: 14.5px; line-height: 1.6; margin-bottom: 32px; }}

  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 8px; }}
  .kpi-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; padding: 14px; }}
  .kpi-label {{ font-size: 11.5px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .03em; }}
  .kpi-value {{ font-size: 20px; font-weight: 700; margin: 5px 0 4px; }}
  .kpi-sub {{ font-size: 11px; color: var(--text-muted); margin-top: 2px; }}
  .wow {{ font-size: 12px; font-weight: 600; padding: 2px 6px; border-radius: 4px; display: inline-block; }}
  .wow-up {{ color: var(--up); background: var(--up-soft); }}
  .wow-down {{ color: var(--down); background: var(--down-soft); }}
  .wow-flat {{ color: var(--flat); background: var(--flat-soft); }}
  .wow-na {{ color: var(--na); }}
  table {{ width: 100%; border-collapse: collapse; background: var(--card-bg); border: 1px solid var(--border);
           border-radius: 8px; overflow: hidden; font-size: 13px; }}
  thead th {{ background: var(--table-head); text-align: left; padding: 9px 11px; font-weight: 600;
              border-bottom: 1px solid var(--border); white-space: nowrap; }}
  thead th.sortable-th {{ cursor: pointer; user-select: none; }}
  thead th.sortable-th:hover {{ background: var(--accent-soft); }}
  .sort-indicator {{ display: inline-block; width: 1.1em; font-size: 10px; color: var(--accent); }}
  tbody td {{ padding: 7px 11px; border-bottom: 1px solid var(--border); }}
  tbody tr:last-child td {{ border-bottom: none; }}
  tbody tr:hover {{ background: var(--row-hover); }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .table-scroll {{ overflow-x: auto; }}
  .status {{ padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; white-space: nowrap; }}
  .status-enabled {{ background: var(--status-enabled-bg); color: var(--up); }}
  .status-paused {{ background: var(--status-paused-bg); color: var(--flat); }}
  .note {{ font-size: 12.5px; color: var(--text-muted); font-style: italic; margin: 2px 0 10px; }}
</style>
</head>
<body>
<div class="page">
  <header class="report-header">
    <div>
      <h1>Weekly Marketing Dashboard</h1>
      <div class="week-range">{esc(week_label(week_start, week_end))}</div>
      <div class="last-updated">Last updated: {generated_dt.strftime('%b %-d, %Y, %-I:%M %p UTC')}</div>
    </div>
    <div class="run-report-wrap">
      <button class="run-report-btn" disabled title="Not wired up in this build">Run Report</button>
      <span class="hint">Static placeholder — not connected to a live Routine/Apps Script relay.</span>
    </div>
  </header>

  <nav class="top-nav">
    <button class="tab-btn active" data-tab="combined">Combined</button>
    <button class="tab-btn" data-tab="google">Google Ads</button>
    <button class="tab-btn" data-tab="linkedin">LinkedIn Ads</button>
  </nav>

  <div id="tab-combined" class="top-section active">
    <nav class="sub-nav">
      <a href="#exec-summary">Executive Summary</a>
      <a href="#combined-kpis">Combined KPIs</a>
      <a href="#google-totals">Google Ads Totals</a>
      <a href="#linkedin-totals">LinkedIn Ads Totals</a>
    </nav>

    <section id="exec-summary" class="topic">
      <h2 class="exec-summary-title">Executive Summary</h2>
      <div class="exec-summary-box">{exec_summary}</div>
    </section>

    <section id="combined-kpis" class="topic">
      <h3>Combined KPIs</h3>
      <div class="kpi-grid">{combined_kpis_html}</div>
    </section>

    <section id="google-totals" class="topic">
      <h3>Google Ads Totals</h3>
      {'<p class="note">' + ga_first_run_note + '</p>' if ga_first_run_note else ''}
      <div class="kpi-grid">{google_totals_html}</div>
    </section>

    <section id="linkedin-totals" class="topic">
      <h3>LinkedIn Ads Totals</h3>
      <div class="kpi-grid">{linkedin_totals_html}</div>
    </section>
  </div>

  <div id="tab-google" class="top-section">
    <nav class="sub-nav">
      <a href="#ga-campaign">Campaign</a>
      <a href="#ga-adgroup">Ad Group</a>
      <a href="#ga-keyword">Keyword</a>
      <a href="#ga-location">Location</a>
      <a href="#ga-searchterm">Search Term</a>
    </nav>

    {table_section("ga-campaign", "Campaign Performance",
        ga_first_run_note,
        '<th>Campaign Name</th><th>Status</th><th>Channel Type</th><th class="num">Spend</th>'
        '<th class="num">Impressions</th><th class="num">Clicks</th><th class="num">CTR</th><th class="num">CPC</th>'
        '<th class="num">Conversions</th><th class="num">Cost / Conv.</th><th class="num">WoW Spend</th>',
        ga_campaign_rows)}

    {table_section("ga-adgroup", "Ad Group Performance", None,
        '<th>Campaign Name</th><th>Ad Group Name</th><th>Status</th><th class="num">Spend</th>'
        '<th class="num">Impressions</th><th class="num">Clicks</th><th class="num">CTR</th><th class="num">CPC</th>'
        '<th class="num">Conversions</th><th class="num">Cost / Conv.</th>',
        ga_adgroup_rows)}

    {table_section("ga-keyword", "Keyword Performance", None,
        '<th>Campaign Name</th><th>Ad Group Name</th><th>Keyword</th><th>Match Type</th>'
        '<th class="num">Spend</th><th class="num">Impressions</th><th class="num">Clicks</th>'
        '<th class="num">CTR</th><th class="num">CPC</th><th class="num">Conversions</th>',
        ga_keyword_rows)}

    {table_section("ga-location", "Location Performance", None,
        '<th>Campaign Name</th><th>Country</th><th>Location Type</th><th class="num">Spend</th>'
        '<th class="num">Impressions</th><th class="num">Clicks</th><th class="num">CTR</th>'
        '<th class="num">Conversions</th>',
        ga_geo_rows)}

    {table_section("ga-searchterm", "Search Term Performance", searchterm_note,
        '<th>Campaign Name</th><th>Ad Group Name</th><th>Search Term</th><th>Status</th>'
        '<th class="num">Spend</th><th class="num">Impressions</th><th class="num">Clicks</th>'
        '<th class="num">CTR</th><th class="num">Conversions</th>',
        ga_searchterm_rows)}
  </div>

  <div id="tab-linkedin" class="top-section">
    <nav class="sub-nav">
      <a href="#li-campaign">Campaign</a>
      <a href="#li-adset">Ad Set</a>
      <a href="#li-creative">Creative Performance</a>
      {demo_nav_items}
    </nav>

    {table_section("li-campaign", "Campaign Performance (roll-up)", None,
        '<th>Campaign Name</th><th class="num">Spend</th><th class="num">Impressions</th>'
        '<th class="num">Clicks</th><th class="num">CTR</th><th class="num">CPM</th><th class="num">CPC</th>'
        '<th class="num">Engagements</th><th class="num">Engagement Rate</th><th class="num">WoW Spend</th>',
        li_campaign_rows)}

    {table_section("li-adset", "Ad Set Performance", None,
        '<th>Campaign Name</th><th>Ad Set Name</th><th class="num">Spend</th><th class="num">Impressions</th>'
        '<th class="num">Clicks</th><th class="num">CTR</th><th class="num">CPM</th><th class="num">CPC</th>'
        '<th class="num">Engagements</th><th class="num">Engagement Rate</th><th class="num">WoW Spend</th>',
        li_adset_rows)}

    {table_section("li-creative", "Creative Performance (ad-level)", f"{len(li_creative)} ads.",
        '<th>Ad Name</th><th>Ad Set Name</th><th>Headline</th><th class="num">Spend</th>'
        '<th class="num">Impressions</th><th class="num">Clicks</th><th class="num">CTR</th>'
        '<th class="num">Engagements</th><th class="num">WoW Spend</th>',
        li_creative_rows)}

    {demo_sections}
  </div>
</div>
<script>
  document.querySelectorAll('.tab-btn').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      document.querySelectorAll('.tab-btn').forEach(function(b) {{ b.classList.remove('active'); }});
      document.querySelectorAll('.top-section').forEach(function(s) {{ s.classList.remove('active'); }});
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    }});
  }});

  // Sortable tables: click a header to cycle ascending -> descending -> unsorted.
  // Every table defaults to descending by its Impressions column on load.
  function parseCellValue(cell) {{
    var text = cell.textContent.trim();
    if (text === '' || text === '—') return null;
    var isNegative = text.indexOf('▼') !== -1;
    var cleaned = text.replace(/[▲▼▪$,%]/g, '').trim();
    if (cleaned !== '' && /^-?[0-9.]+$/.test(cleaned)) {{
      var num = parseFloat(cleaned);
      return isNegative ? -Math.abs(num) : num;
    }}
    return text.toLowerCase();
  }}

  function compareRows(a, b, colIndex, dir) {{
    var va = parseCellValue(a.children[colIndex]);
    var vb = parseCellValue(b.children[colIndex]);
    if (va === null && vb === null) return 0;
    if (va === null) return 1;
    if (vb === null) return -1;
    var cmp = (typeof va === 'number' && typeof vb === 'number')
      ? va - vb
      : String(va).localeCompare(String(vb));
    return dir === 'asc' ? cmp : -cmp;
  }}

  function initSortableTables() {{
    document.querySelectorAll('table').forEach(function(table) {{
      var thead = table.querySelector('thead');
      var tbody = table.querySelector('tbody');
      if (!thead || !tbody) return;
      var ths = Array.prototype.slice.call(thead.querySelectorAll('th'));
      if (!ths.length) return;
      var headerTexts = ths.map(function(th) {{ return th.textContent.trim(); }});
      var originalRows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
      var state = {{ col: -1, dir: 'none' }};

      function applySort(colIndex, dir) {{
        if (dir === 'none') {{
          originalRows.forEach(function(r) {{ tbody.appendChild(r); }});
          return;
        }}
        var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
        rows.sort(function(a, b) {{ return compareRows(a, b, colIndex, dir); }});
        rows.forEach(function(r) {{ tbody.appendChild(r); }});
      }}

      function updateIndicators() {{
        ths.forEach(function(th, idx) {{
          var ind = th.querySelector('.sort-indicator');
          if (!ind) return;
          if (state.col === idx && state.dir !== 'none') {{
            ind.textContent = state.dir === 'asc' ? '▲' : '▼';
          }} else {{
            ind.textContent = '';
          }}
        }});
      }}

      ths.forEach(function(th, idx) {{
        th.classList.add('sortable-th');
        var indicator = document.createElement('span');
        indicator.className = 'sort-indicator';
        th.appendChild(indicator);
        th.addEventListener('click', function() {{
          if (state.col !== idx) {{
            state = {{ col: idx, dir: 'asc' }};
          }} else if (state.dir === 'asc') {{
            state = {{ col: idx, dir: 'desc' }};
          }} else if (state.dir === 'desc') {{
            state = {{ col: -1, dir: 'none' }};
          }} else {{
            state = {{ col: idx, dir: 'asc' }};
          }}
          applySort(idx, state.dir);
          updateIndicators();
        }});
      }});

      var defaultCol = headerTexts.indexOf('Impressions');
      if (defaultCol >= 0) {{
        state = {{ col: defaultCol, dir: 'desc' }};
        applySort(defaultCol, 'desc');
        updateIndicators();
      }}
    }});
  }}
  initSortableTables();
</script>
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)

    print(f"Wrote {out_path} ({len(html_doc):,} bytes)")


if __name__ == "__main__":
    main()
