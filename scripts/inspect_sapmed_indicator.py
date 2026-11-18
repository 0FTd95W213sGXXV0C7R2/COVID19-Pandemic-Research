#!/usr/bin/env python3
"""Inspect Sapporo Medical University indicator page network assets.

This is a discovery-only task: it does not infer or synthesize observations.
Captured response bodies are uploaded as a short-lived GitHub Actions artifact.
"""
from __future__ import annotations
import hashlib, json, re, time
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

PAGE = "https://web.sapmed.ac.jp/canmol/coronavirus/japan_indicator.html"
OUT = Path("artifacts/sapmed_discovery")
MAX_BODY = 20 * 1024 * 1024
OUT.mkdir(parents=True, exist_ok=True)
events = []
saved = []

def safe_name(url: str, content_type: str) -> str:
    parsed = urlparse(url)
    base = Path(parsed.path).name or "response"
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)[:100]
    digest = hashlib.sha256(url.encode()).hexdigest()[:12]
    suffix = Path(base).suffix
    if not suffix:
        suffix = ".json" if "json" in content_type else ".csv" if "csv" in content_type else ".txt"
    return f"{digest}_{base if Path(base).suffix else base + suffix}"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.on("request", lambda req: events.append({
        "kind":"request","url":req.url,"method":req.method,"resource_type":req.resource_type
    }))
    def on_response(resp):
        headers = resp.headers
        ct = headers.get("content-type", "")
        url = resp.url
        item = {"kind":"response","url":url,"status":resp.status,"content_type":ct}
        events.append(item)
        likely = (
            any(x in ct.lower() for x in ("json","csv","text","javascript","xml"))
            or re.search(r"\.(csv|json|js|txt|xml)(?:$|[?#])", url, re.I)
        )
        if not likely or resp.status >= 400:
            return
        try:
            body = resp.body()
            if not body or len(body) > MAX_BODY:
                item["saved"] = False
                item["reason"] = "empty_or_over_limit"
                return
            name = safe_name(url, ct)
            path = OUT / name
            path.write_bytes(body)
            item["saved"] = str(path)
            item["size_bytes"] = len(body)
            item["sha256"] = hashlib.sha256(body).hexdigest()
            saved.append(item)
        except Exception as exc:
            item["saved"] = False
            item["error"] = f"{type(exc).__name__}: {exc}"
    page.on("response", on_response)
    page.goto(PAGE, wait_until="domcontentloaded", timeout=90000)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except Exception:
        pass
    # Allow delayed chart/data requests to complete.
    page.wait_for_timeout(15000)
    # Record visible page text and script references.
    (OUT / "page_text.txt").write_text(page.locator("body").inner_text(), encoding="utf-8")
    scripts = page.locator("script[src]").evaluate_all("(els) => els.map(e => e.src)")
    (OUT / "script_urls.json").write_text(json.dumps(scripts, ensure_ascii=False, indent=2), encoding="utf-8")
    # Save the final HTML for static references to inline scripts/configuration.
    (OUT / "page.html").write_text(page.content(), encoding="utf-8")
    browser.close()

report = {
    "page": PAGE,
    "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "request_response_events": events,
    "saved_textual_responses": saved,
    "note": "No data values are accepted as verified until the response schema, date range, and nationwide series are inspected."
}
(OUT / "network_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "page": PAGE,
    "events": len(events),
    "saved_responses": len(saved),
    "files": [{"url":x["url"],"content_type":x["content_type"],"size_bytes":x.get("size_bytes"),"sha256":x.get("sha256")} for x in saved]
}, ensure_ascii=False, indent=2))
