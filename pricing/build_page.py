"""
Build the pricing comparison HTML page from scraped data.

Usage:
    python pricing/build_page.py
    python pricing/build_page.py --input pricing/data.json --output pricing/index.html
"""

import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def format_price(price: float | int | None) -> str:
    if price is None:
        return "N/A"
    if price == 0:
        return "Free"
    if price < 0.01:
        return f"${price:.4f}"
    if price < 1:
        return f"${price:.2f}"
    return f"${price:,.2f}"


def build_html(data: dict) -> str:
    generated_at = data.get("generated_at", "")
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        date_label = dt.strftime("%B %d, %Y")
    except Exception:
        date_label = generated_at[:10] if generated_at else "Unknown"

    provider_count = data.get("provider_count", 0)
    total_models = data.get("total_models", 0)

    # Build table rows sorted by input price (cheapest first)
    all_models = []
    for p in data.get("providers", []):
        provider = p.get("provider", "")
        for m in p.get("models", []):
            all_models.append({
                "provider": provider,
                "model": m.get("model_name", ""),
                "input": m.get("input_price_per_1m_tokens"),
                "output": m.get("output_price_per_1m_tokens"),
                "context": m.get("context_window", ""),
                "type": m.get("model_type", "chat"),
            })

    # Sort: cheapest input price first, N/A at bottom
    all_models.sort(key=lambda x: (x["input"] is None, x["input"] or 999999))

    rows_html = ""
    for m in all_models:
        provider_color = {
            "OpenAI": "#10B981", "Anthropic": "#D97706", "Google Gemini": "#3B82F6",
            "Mistral": "#F97316", "Groq": "#EC4899", "Together AI": "#8B5CF6",
            "xAI": "#6366F1", "Perplexity": "#06B6D4", "Cohere": "#EF4444",
            "AWS Bedrock": "#F59E0B",
        }.get(m["provider"], "#94A3B8")

        rows_html += f"""<tr>
<td><span style="color:{provider_color};font-weight:600">{m['provider']}</span></td>
<td style="font-family:'JetBrains Mono',monospace;font-size:13px">{m['model']}</td>
<td style="text-align:right">{format_price(m['input'])}</td>
<td style="text-align:right">{format_price(m['output'])}</td>
<td style="text-align:center;color:#94A3B8">{m['context'] or 'N/A'}</td>
<td style="text-align:center"><span style="background:rgba(255,255,255,0.06);padding:2px 8px;border-radius:4px;font-size:11px">{m['type']}</span></td>
</tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI API Pricing Tracker - Koda</title>
<meta name="description" content="Live comparison of AI API pricing across {provider_count} providers and {total_models} models. Updated weekly.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:#0a0f1a;color:#E2E8F0;min-height:100vh}}
.container{{max-width:1200px;margin:0 auto;padding:24px 16px}}
.topbar{{display:flex;justify-content:space-between;align-items:center;padding:12px 0;margin-bottom:32px;border-bottom:1px solid rgba(255,255,255,0.06)}}
.topbar a{{color:#94A3B8;text-decoration:none;font-size:14px}}
.topbar a:hover{{color:#E2E8F0}}
h1{{font-size:28px;font-weight:800;background:linear-gradient(135deg,#3B82F6,#8B5CF6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}}
.subtitle{{color:#94A3B8;font-size:14px;margin-bottom:32px}}
.stats{{display:flex;gap:24px;margin-bottom:24px}}
.stat{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px 20px}}
.stat-value{{font-size:24px;font-weight:700;color:#E2E8F0}}
.stat-label{{font-size:12px;color:#64748B;margin-top:2px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
thead th{{text-align:left;padding:12px 16px;color:#64748B;font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid rgba(255,255,255,0.06);position:sticky;top:0;background:#0a0f1a;z-index:1}}
tbody tr{{border-bottom:1px solid rgba(255,255,255,0.03)}}
tbody tr:hover{{background:rgba(255,255,255,0.03)}}
tbody td{{padding:10px 16px}}
.search{{width:100%;padding:10px 16px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:8px;color:#E2E8F0;font-size:14px;margin-bottom:16px;outline:none}}
.search:focus{{border-color:#3B82F6}}
@media(max-width:768px){{
.stats{{flex-wrap:wrap}}
table{{font-size:12px}}
thead th,tbody td{{padding:8px}}
}}
</style>
</head>
<body>
<div class="container">
<div class="topbar">
<a href="../index.html">&#8592; Home</a>
<span style="color:#64748B;font-size:12px">Updated: {date_label}</span>
</div>
<h1>AI API Pricing Tracker</h1>
<p class="subtitle">{provider_count} providers, {total_models} models -- sorted by input cost (cheapest first)</p>

<div class="stats">
<div class="stat"><div class="stat-value">{provider_count}</div><div class="stat-label">Providers</div></div>
<div class="stat"><div class="stat-value">{total_models}</div><div class="stat-label">Models</div></div>
<div class="stat"><div class="stat-value">{date_label}</div><div class="stat-label">Last Updated</div></div>
</div>

<input type="text" class="search" placeholder="Filter models (e.g. gpt, claude, gemini, llama)..." oninput="filterTable(this.value)">

<table id="pricingTable">
<thead>
<tr>
<th>Provider</th>
<th>Model</th>
<th style="text-align:right">Input / 1M</th>
<th style="text-align:right">Output / 1M</th>
<th style="text-align:center">Context</th>
<th style="text-align:center">Type</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>

<p style="margin-top:32px;color:#475569;font-size:12px;text-align:center">
Prices scraped from official provider pages. All prices in USD per 1M tokens.
<br>Data may lag behind real-time changes. Verify on provider sites before purchasing.
<br>Powered by <a href="https://www.koda.community" style="color:#3B82F6;text-decoration:none">Koda Intelligence</a>
</p>
</div>
<script>
function filterTable(q) {{
  var rows = document.querySelectorAll('#pricingTable tbody tr');
  q = q.toLowerCase();
  rows.forEach(function(r) {{
    r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build pricing comparison page")
    parser.add_argument("--input", default=str(Path(__file__).parent / "data.json"))
    parser.add_argument("--output", default=str(Path(__file__).parent / "index.html"))
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run scrape_pricing.py first.")
        sys.exit(1)

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    html = build_html(data)
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Built pricing page: {output_path} ({len(html)} chars)")


if __name__ == "__main__":
    main()
