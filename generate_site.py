"""
Generates docs/index.html for the FPL Mini-League Tracker.
Run by the GitHub Actions workflow on a schedule -- see
.github/workflows/update-tracker.yml. Can also be run locally:

    pip install requests
    python generate_site.py
"""

import time
from datetime import datetime, timezone, timedelta
import requests

LEAGUE_ID = 970639
# FIXED: Pointing directly to the official FPL API subdomain
BASE = "https://premierleague.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (fpl-tracker-site-generator)"}
OUTPUT_PATH = "docs/index.html"


def get_standings(league_id):
    entries, page, league_name = [], 1, ""
    while True:
        # FIXED: Updated endpoint targeting raw JSON standings
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
    # FIXED: Updated endpoint targeting raw JSON entry history
    resp = requests.get(f"{BASE}/entry/{entry_id}/history/", headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    
    gw_data = {}
    for gw in data.get("current", []):
        gw_data[gw["event"]] = {
            "gross": gw["points"],
            "cost": gw.get("event_transfers_cost", 0),
            "net": gw["points"] - gw.get("event_transfers_cost", 0)
        }
    return gw_data


def fetch_all(league_id):
    league_name, entries = get_standings(league_id)
    managers, max_gw = [], 0
    for i, e in enumerate(entries):
        print(f"  {i + 1}/{len(entries)}: {e['player_name']}")
        gw_data = get_history(e["entry"])
        if gw_data:
            max_gw = max(max_gw, max(gw_data.keys()))
        managers.append({
            "name": e["player_name"],
            "team": e["entry_name"],
            "official_total": e["total"],
            "gw_data": gw_data,
        })
        time.sleep(0.3)
    return league_name, managers, max_gw


def render_html(league_name, managers, max_gw, generated_at):
    num_blocks = (max_gw + 3) // 4

    rows_computed = []
    for m in managers:
        block_subtotals = []
        calculated_running_net = 0
        
        for b in range(num_blocks):
            start, end = b * 4 + 1, min(b * 4 + 4, max_gw)
            sub = sum(m["gw_data"].get(gw, {}).get("net", 0) for gw in range(start, end + 1))
            block_subtotals.append(sub)
            calculated_running_net += sub
            
        mismatch = m["official_total"] is not None and m["official_total"] != calculated_running_net
        
        rows_computed.append({
            **m, 
            "blocks": block_subtotals, 
            "mismatch": mismatch
        })
        
    rows_computed.sort(key=lambda r: r["official_total"], reverse=True)

    header_cells = ['<th class="name-cell">Manager</th>']
    for b in range(num_blocks):
        start, end = b * 4 + 1, min(b * 4 + 4, max_gw)
        for gw in range(start, end + 1):
            header_cells.append(f"<th>GW{gw}</th>")
        header_cells.append(f'<th class="subtotal-col">DOP{b + 1}</th>')
    header_cells.append('<th class="total-col">TOTAL</th>')

    body_rows = []
    for idx, m in enumerate(rows_computed):
        rank_class = ' class="rank-1"' if idx == 0 else ""
        cells = [
            f'<td class="name-cell"><span class="rank-col">{idx + 1}.</span> '
            f'<span class="manager-name">{m["name"]}</span>'
            f'<span class="team-name">{m["team"]}</span></td>'
        ]
        for b in range(num_blocks):
            start, end = b * 4 + 1, min(b * 4 + 4, max_gw)
            for gw in range(start, end + 1):
                gw_info = m["gw_data"].get(gw)
                if gw_info:
                    net_val = gw_info["net"]
                    cost = gw_info["cost"]
                    if cost > 0:
                        val_str = f'{net_val}<span class="hit-hint">({gw_info["gross"]}-{cost})</span>'
                    else:
                        val_str = f'{net_val}'
                else:
                    val_str = "-"
                cells.append(f"<td>{val_str}</td>")
            cells.append(f'<td class="subtotal-col">{m["blocks"][b]}</td>')
            
        total_class = "total-col mismatch-alert" if m["mismatch"] else "total-col"
        cells.append(f'<td class="{total_class}">{m["official_total"]}</td>')
        body_rows.append(f"<tr{rank_class}>" + "".join(cells) + "</tr>")

    # FIXED: Using the dynamically calculated SAST timestamp passed via main loop execution
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FUBAR FPL DOP TRACKER</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=Work+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{{
    --turf-dark:#0f221a; --chalk:#F6F5F0; --chalk-dim:#D8DED8;
    --amber:#E0A93B; --amber-dim:#F3D89A; --line:rgba(246,245,240,0.16);
    --alert-orange: #d97706;
  }}
  *{{box-sizing:border-box;}}
  body{{
    margin:0; background:var(--turf-dark);
    font-family:'Work Sans', sans-serif; color:var(--chalk); min-height:100vh; padding:18px 12px 40px;
  }}
  .wrap{{max-width:960px;margin:0 auto;}}
  header{{border-bottom:2px solid var(--line);padding-bottom:14px;margin-bottom:16px;display:flex;align-items:center;gap:16px;}}
  .logo{{width:64px;height:64px;border-radius:50%;object-fit:cover;flex-shrink:0;box-shadow:0 0 0 2px var(--amber);}}
  .header-text{{flex:1;min-width:0;}}
  h1{{font-family:'Oswald',sans-serif;font-weight:700;font-size:1.6rem;margin:0;}}
  .subtitle{{font-size:0.82rem;color:var(--chalk-dim);margin-top:4px;}}
  .table-scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);}}
  table{{border-collapse:collapse;width:100%;table-layout:fixed;font-variant-numeric:tabular-nums;}}
  th, td{{padding:7px 4px;text-align:center;font-size:0.78rem;white-space:nowrap;border-bottom:1px solid var(--line);overflow:hidden;text-overflow:ellipsis;}}
  th{{font-family:'Oswald',sans-serif;font-weight:600;font-size:0.74rem;color:var(--chalk-dim);background:var(--turf-dark);position:sticky;top:0;}}
  th:not(.name-cell):not(.subtotal-col):not(.total-col),
  td:not(.name-cell):not(.subtotal-col):not(.total-col){{width:52px;}}
  th.subtotal-col, td.subtotal-col{{width:54px;}}
  th.total-col, td.total-col{{width:58px;}}
  td.name-cell, th.name-cell{{
    text-align:left;position:sticky;left:0;background:var(--turf-dark);z-index:2;
    box-shadow:2px 0 4px rgba(0,0,0,0.35);width:135px;padding-left:8px;padding-right:8px;
  }}
  th.name-cell{{z-index:3;}}
  .manager-name{{font-weight:600;color:var(--chalk);display:block;overflow:hidden;text-overflow:ellipsis;white-space:normal;line-height:1.2;}}
  .team-name{{display:block;font-size:0.64rem;color:var(--chalk-dim);font-weight:400;overflow:hidden;text-overflow:ellipsis;white-space:normal;line-height:1.2;margin-top:2px;}}
  .hit-hint{{display:block;font-size:0.58rem;color:var(--amber-dim);font-weight:400;margin-top:1px;}}
  .mismatch-alert{{background:rgba(217, 119, 6, 0.35) !important;border:1px solid var(--amber);}}
  .scroll-hint{{font-size:0.72rem;color:var(--amber-dim);text-align:center;padding:6px 0 0;display:none;}}
  @media (max-width:480px){{
    .scroll-hint{{display:block;}}
    td.name-cell, th.name-cell{{width:125px;}}
  }}
  tr:nth-child(even) td:not(.name-cell){{background:rgba(246,245,240,0.03);}}
  tr:nth-child(even) td.name-cell{{background:#153d2f;}}
  .subtotal-col{{background:rgba(224,169,59,0.15) !important;font-weight:600;color:var(--amber);}}
  .total-col{{background:rgba(246,245,240,0.08) !important;font-weight:700;}}
  tr.rank-1 td{{border-top:1px solid var(--amber);border-bottom:1px solid var(--amber);}}
  tr.rank-1 td.name-cell{{color:var(--amber) !important;}}
  .rank-col{{font-family:'Oswald',sans-serif;font-weight:600;color:var(--amber);margin-right:4px;display:inline-block;width:16px;}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <img src="https://skynet.be" class="logo" alt="FUBAR Logo" onerror="this.style.display='none'">
    <div class="header-text">
      <h1>{league_name.upper()}</h1>
      <div class="subtitle">Nett GW score (GW pts minus transfer-cost hits) &middot; Dop for lowest pts every 4 gameweeks<br>Last updated {generated_at}</div>
    </div>
  </header>
  
  <div class="table-scroll">
    <table>
      <thead>
        <tr>{"".join(header_cells)}</tr>
      </thead>
      <tbody>
        {"".join(body_rows)}
      </tbody>
    </table>
  </div>
  <div class="scroll-hint">&larr; Scroll horizontally to view all Gameweeks &rarr;</div>
</div>
</body>
</html>"""


def main():
    print(f"Starting tracking collection for Classic League ID: {LEAGUE_ID}")
    
    # Calculate live time in South Africa (UTC+2) dynamically
    sast_now = datetime.now(timezone.utc) + timedelta(hours=2)
    generated_at_str = sast_now.strftime("%Y-%m-%d %H:%M SAST")
    
    league_name, managers, max_gw = fetch_all(LEAGUE_ID)
    
    html_content = render_html(league_name, managers, max_gw, generated_at_str)
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"Successfully generated static HTML documentation to {OUTPUT_PATH}!")


if __name__ == "__main__":
    main()
