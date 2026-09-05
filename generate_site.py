import time
from datetime import datetime, timezone
import os
import requests

LEAGUE_ID = 970639
BASE = "https://fantasy.premierleague.com/api"
HEADERS = {"User-Agent": "Mozilla/5.0 (fpl-tracker-site-generator)"}
OUTPUT_PATH = "docs/index.html"

def get_standings(league_id):
    entries, page, league_name = [], 1, ""
    while True:
        resp = requests.get(
            f"{BASE}/leagues-classic/{league_id}/standings/",
            params={"page_standings": page},
            headers=HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        league_name = data["league"]["name"]
        entries.extend(data["standings"]["results"])
        if not data["standings"]["has_next"]:
            break
        page += 1
        time.sleep(0.3)
    return league_name, entries

def get_history(entry_id):
    resp = requests.get(f"{BASE}/entry/{entry_id}/history/", headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    net_by_gw = {}
    for gw in data.get("current", []):
        net_by_gw[gw["event"]] = gw["points"] - gw.get("event_transfers_cost", 0)
    return net_by_gw

def fetch_all(league_id):
    league_name, entries = get_standings(league_id)
    managers, max_gw = [], 0
    for i, e in enumerate(entries):
        print(f"  {i + 1}/{len(entries)}: {e['player_name']}")
        net_by_gw = get_history(e["entry"])
        if net_by_gw:
            max_gw = max(max_gw, max(net_by_gw.keys()))
        managers.append({
            "name": e["player_name"],
            "team": e["entry_name"],
            "official_total": e["total"],
            "net_by_gw": net_by_gw,
        })
        time.sleep(0.3)
    return league_name, managers, max_gw

def render_html(league_name, managers, max_gw, generated_at):
    num_blocks = (max_gw + 3) // 4
    rows_computed = []
    for m in managers:
        block_subtotals = []
        running = 0
        for b in range(num_blocks):
            start, end = b * 4 + 1, min(b * 4 + 4, max_gw)
            sub = sum(m["net_by_gw"].get(gw, 0) for gw in range(start, end + 1))
            block_subtotals.append(sub)
            running += sub
        mismatch = m["official_total"] is not None and m["official_total"] != running
        rows_computed.append({**m, "running": running, "blocks": block_subtotals, "mismatch": mismatch})
    rows_computed.sort(key=lambda r: r["running"], reverse=True)

    header_cells = ['<th class="name-cell">Manager</th>']
    for b in range(num_blocks):
        start, end = b * 4 + 1, min(b * 4 + 4, max_gw)
        for gw in range(start, end + 1):
            header_cells.append(f"<th>GW{gw}</th>")
        header_cells.append(f'<th class="subtotal-col">GW{start}-{end}</th>')
    header_cells.append('<th class="total-col">TOTAL</th>')

    body_rows = []
    for idx, m in enumerate(rows_computed):
        rank_class = ' class="rank-1"' if idx == 0 else ""
        flag = " ⚠️" if m["mismatch"] else ""
        cells = [
            f'<td class="name-cell"><span class="rank-col">{idx + 1}.</span> '
            f'<span class="manager-name">{m["name"]}{flag}</span>'
            f'<span class="team-name">{m["team"]}</span></td>'
        ]
        for b in range(num_blocks):
            start, end = b * 4 + 1, min(b * 4 + 4, max_gw)
            for gw in range(start, end + 1):
                val = m["net_by_gw"].get(gw, "-")
                cells.append(f"<td>{val}</td>")
            cells.append(f'<td class="subtotal-col">{m["blocks"][b]}</td>')
        cells.append(f'<td class="total-col">{m["running"]}</td>')
        body_rows.append(f"<tr{rank_class}>" + "".join(cells) + "</tr>")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{league_name} &mdash; FPL Tracker</title>
<link rel="preconnect" href="https://googleapis.com">
<link href="https://googleapis.com/css2?family=Oswald:wght@500;600;700&family=Work+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{{
    --turf-dark:#12352A; --turf-stripe:#1F5A44; --chalk:#F6F5F0; --chalk-dim:#D8DED8;
    --amber:#E0A93B; --amber-dim:#F3D89A; --line:rgba(246,245,240,0.16);
  }}
  *{{box-sizing:border-box;}}
  body{{
    margin:0; background:#12352A;
    font-family:'Work Sans', sans-serif; color:var(--chalk); min-height:100vh; padding:18px 12px 40px;
  }}
  .wrap{{max-width:960px;margin:0 auto;}}
  header{{border-bottom:2px solid var(--line);padding-bottom:14px;margin-bottom:16px;display:flex;align-items:center;gap:16px;}}
  .logo{{width:64px;height:64px;border-radius:50%;object-fit:cover;flex-shrink:0;box-shadow:0 0 0 2px var(--amber);}}
  .header-text{{flex:1;min-width:0;}}
  h1{{font-family:'Oswald',sans-serif;font-weight:700;font-size:1.6rem;margin:0;}}
  .subtitle{{font-size:0.82rem;color:var(--chalk-dim);margin-top:4px;}}
  .table-scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);}}
  table{{border-collapse:collapse;width:100%;min-width:640px;font-variant-numeric:tabular-nums;}}
  th, td{{padding:8px 10px;text-align:center;font-size:0.82rem;white-space:nowrap;border-bottom:1px solid var(--line);}}
  th{{font-family:'Oswald',sans-serif;font-weight:600;font-size:0.78rem;color:var(--chalk-dim);background:var(--turf-dark);position:sticky;top:0;}}
  td.name-cell, th.name-cell{{text-align:left;position:sticky;left:0;background:var(--turf-dark);z-index:2;box-shadow:2px 0 0 var(--line);min-width:150px;}}
  th.name-cell{{z-index:3;}}
  .manager-name{{font-weight:600;color:var(--chalk);}}
  .team-name{{display:block;font-size:0.72rem;color:var(--chalk-dim);font-weight:400;}}
  tr:nth-child(even) td:not(.name-cell){{background:rgba(246,245,240,0.03);}}
  tr:nth-child(even) td.name-cell{{background:#153d2f;}}
  .subtotal-col{{background:rgba(224,169,59,0.14);font-weight:600;color:var(--amber);}}
  tr:nth-child(even) .subtotal-col{{background:rgba(224,169,59,0.20);}}
  .total-col{{background:rgba(224,169,59,0.30);font-weight:700;color:var(--chalk);}}
  tr:nth-child(even) .total-col{{background:rgba(224,169,59,0.36);}}
  .rank-col{{color:var(--chalk-dim);font-weight:600;}}
  .rank-1 .rank-col{{color:var(--amber);}}
  footer{{margin-top:16px;font-size:0.76rem;color:var(--chalk-dim);line-height:1.5;}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <img class="logo" src="logo.jpg" alt="League logo">
    <div class="header-text">
      <h1>{league_name}</h1>
      <div class="subtitle">Net score = GW points minus transfer-cost hits &middot; every 4 GWs is its own competition</div>
      <div class="subtitle">Last updated {generated_at}</div>
    </div>
  </header>
  <div class="table-scroll">
    <table>
      <thead><tr>{"".join(header_cells)}</tr></thead>
      <tbody>{"".join(body_rows)}</tbody>
    </table>
  </div>
  <footer>This page is regenerated automatically on a schedule by GitHub Actions, pulling live from the official FPL API.</footer>
</div>
</body>
</html>"""
    return html_content

def main():
    print(f"Fetching league {LEAGUE_ID}...")
    league_name, managers, max_gw = fetch_all(LEAGUE_ID)
    if max_gw == 0:
        print("No completed gameweeks yet -- nothing to render.")
        return
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = render_html(league_name, managers, max_gw, generated_at)
    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
