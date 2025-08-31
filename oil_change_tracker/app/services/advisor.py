import json, os
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from statistics import mean, pstdev

EVENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "events.jsonl")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")

def _read_events(days: int = 30):
    cutoff = datetime.utcnow() - timedelta(days=days)
    evts = []
    if not os.path.exists(EVENTS_PATH):
        return evts
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                ts = rec.get("ts")
                if not ts:
                    continue
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt >= cutoff:
                    rec["_dt"] = dt
                    evts.append(rec)
            except Exception:
                continue
    return evts

def _ensure_reports_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)

def compute_metrics(days: int = 30):
    evts = _read_events(days)
    counts = Counter([e["action"] for e in evts])
    # derived
    searches = [e for e in evts if e["action"] == "search"]
    search_terms = Counter([e["details"].get("term", "") for e in searches if e["details"].get("term")])
    search_no_results = sum(1 for e in searches if e["details"].get("results", 0) == 0)
    search_total = len(searches)

    deducts = [e for e in evts if e["action"] == "deduct"]
    restores = [e for e in evts if e["action"] == "restore"]
    vehicles_added = [e for e in evts if e["action"] == "vehicle_add"]
    specs_lookups = [e for e in evts if e["action"] == "spec_lookup"]

    metrics = {
        "window_days": days,
        "action_counts": counts,
        "search_total": search_total,
        "search_no_result": search_no_results,
        "search_no_result_rate": (search_no_results / search_total) if search_total else 0.0,
        "top_search_terms": search_terms.most_common(10),
        "deducts": len(deducts),
        "restores": len(restores),
        "restore_ratio": (len(restores) / len(deducts)) if deducts else 0.0,
        "vehicles_added": len(vehicles_added),
        "spec_lookups": len(specs_lookups),
    }
    return metrics

def generate_advice(metrics: dict):
    tips = []
    # Rule: high no-result search rate
    if metrics["search_total"] >= 10 and metrics["search_no_result_rate"] > 0.2:
        tips.append("Searches without matches are over 20%. Consider importing customers from a CSV to reduce 'no result' searches.")
    # Rule: high restore ratio (possible mis-clicks)
    if metrics["deducts"] >= 10 and metrics["restore_ratio"] > 0.2:
        tips.append("More than 20% of oil change deductions were restored. Consider staff refresher or confirm dialog on deduct.")
    # Rule: vehicles added but few spec lookups
    if metrics["vehicles_added"] >= 10 and metrics["spec_lookups"] < (0.4 * metrics["vehicles_added"]):
        tips.append("Many vehicles added but few oil spec lookups. Add more entries to the local oil_specs.json or review workflow.")
    if not tips:
        tips.append("System usage looks healthy. Keep building your local oil spec table for instant lookups.")
    return tips

def save_report(metrics: dict, tips: list[str]):
    _ensure_reports_dir()
    stamp = datetime.utcnow().strftime("%Y-%m-%d")
    payload = {"generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
               "metrics": metrics, "advice": tips}
    json_path = os.path.join(REPORTS_DIR, f"advisor_{stamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    # html
    html_path = os.path.join(REPORTS_DIR, f"advisor_{stamp}.html")
    html = ["""<!doctype html><html><head><meta charset='utf-8'><title>Advisor Report</title>
<style>body{font-family:system-ui,Segoe UI,Roboto,sans-serif;margin:16px} code{background:#f3f3f3;padding:2px 4px}</style>
</head><body><h1>Advisor Report</h1>"""]
    html.append(f"""<p><strong>Generated (UTC):</strong> {payload['generated_utc']}</p>""")
    html.append("<h2>Key Metrics (last %d days)</h2>" % metrics.get("window_days", 30))
    html.append("<ul>")
    html.append(f"<li>Total searches: {metrics['search_total']} (no result: {metrics['search_no_result']} → {metrics['search_no_result_rate']:.0%})</li>")
    html.append(f"<li>Oil change deducts: {metrics['deducts']}, restores: {metrics['restores']} (restore ratio: {metrics['restore_ratio']:.0%})</li>")
    html.append(f"<li>Vehicles added: {metrics['vehicles_added']}, spec lookups: {metrics['spec_lookups']}</li>")
    html.append("</ul>")
    if metrics.get("top_search_terms"):
        html.append("<h3>Top search terms</h3><ol>")
        for term, cnt in metrics["top_search_terms"]:
            safe = (term or "").replace("<","&lt;").replace(">","&gt;")
            html.append(f"<li>{safe} — {cnt}</li>")
        html.append("</ol>")
    html.append("<h2>Advisor Suggestions</h2><ul>")
    for t in tips:
        html.append(f"<li>{t}</li>")
    html.append("</ul>")
    html.append("</body></html>")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html))
    return json_path, html_path

def run_once(days: int = 30):
    metrics = compute_metrics(days=days)
    tips = generate_advice(metrics)
    return save_report(metrics, tips)
