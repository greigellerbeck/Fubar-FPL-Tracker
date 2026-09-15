"""
Generates docs/index.html for the FPL Mini-League Tracker.
Run by the GitHub Actions workflow on a schedule -- see
.github/workflows/update-tracker.yml. Can also be run locally:

    pip install requests
    python generate_site.py
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

LEAGUE_ID = 970639
BASE = "https://fantasy.premierleague.com/api"
OUTPUT_PATH = "docs/index.html"

REQUEST_TIMEOUT = 20
REQUEST_DELAY = 0.5
MAX_RETRIES = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://fantasy.premierleague.com",
    "Referer": "https://fantasy.premierleague.com/",
}


def make_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def get_json(session, url, params=None):
    """GET a URL with retries. Raises RuntimeError if all attempts fail."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
        except requests.RequestException as err:
            last_err = str(err)
        print(f"    retry {attempt}/{MAX_RETRIES} for {url} -> {last_err}")
        if attempt < MAX_RETRIES:
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"failed to fetch {url} after {MAX_RETRIES} attempts: {last_err}")


def get_current_event_status(session):
    """
    Work out which gameweek is 'live' right now, and whether its points
    are fully confirmed (finished + bonus added) or still provisional.
    Returns (event_id_or_None, is_final_bool).
    """
    data = get_json(session, f"{BASE}/bootstrap-static/")
    events = data.get("events", [])

    current = next((ev for ev in events if ev.get("is_current")), None)
    if current is None:
        finished = [ev for ev in events if ev.get("finished")]
        current = finished[-1] if finished else None

    if current is None:
        return None, True

    is_final = bool(current.get("finished")) and bool(current.get("data_checked"))
    return current.get("id"), is_final


def get_standings(session, league_id):
    entries, page, league_name = [], 1, ""
    while True:
        url = f"{BASE}/leagues-classic/{league_id}/standings/"
        print(f"Fetching standings page {page}...")
        data = get_json(session, url, params={"page_standings": page})
        league_name = data["league"]["name"]
        entries.extend(data["standings"]["results"])
        if not data["standings"]["has_next"]:
            break
        page += 1
        time.sleep(REQUEST_DELAY)
    return league_name, entries


def get_history(session, entry_id):
    url = f"{BASE}/entry/{entry_id}/history/"
    data = get_json(session, url)
    gw_data = {}
    for gw in data.get("current", []):
        gw_data[gw["event"]] = {
            "gross": gw["points"],
            "cost": gw.get("event_transfers_cost", 0),
            "net": gw["points"] - gw.get("event_transfers_cost", 0),
        }
    return gw_data


def fetch_all(league_id):
    session = make_session()

    live_gw, live_gw_is_final = get_current_event_status(session)

    league_name, entries = get_standings(session, league_id)
    managers, max_gw = [], 0

    print(f"Found {len(entries)} managers. Fetching individual histories...")
    for i, e in enumerate(entries):
        print(f"  [{i + 1}/{len(entries)}] {e['player_name']}")
        try:
            gw_data = get_history(session, e["entry"])
            if gw_data:
                max_gw = max(max_gw, max(gw_data.keys()))
            managers.append({
                "name": e["player_name"],
                "team": e["entry_name"],
                "official_total": e["total"],
                "gw_data": gw_data,
            })
        except Exception as err:
            print(f"  WARNING: could not fetch history for {e['player_name']}: {err}")
            managers.append({
                "name": e["player_name"],
                "team": e["entry_name"],
                "official_total": e["total"],
                "gw_data": {},
            })
        time.sleep(REQUEST_DELAY)

    return league_name, managers, max_gw, live_gw, live_gw_is_final


def render_html(league_name, managers, max_gw, generated_at, live_gw, live_gw_is_final):
    num_blocks = (max_gw + 3) // 4 if max_gw > 0 else 1
    live_unconfirmed = live_gw is not None and not live_gw_is_final

    rows_computed = []
    for m in managers:
        block_subtotals = []
        calculated_running_net = 0

        for b in range(num_blocks):
            start, end = b * 4 + 1, min(b * 4 + 4, max_gw)
            sub = (
                sum(m["gw_data"].get(gw, {}).get("net", 0) for gw in range(start, end + 1))
                if max_gw > 0 else 0
            )
            block_subtotals.append(sub)
            calculated_running_net += sub

        mismatch = m["official_total"] is not None and m["official_total"] != calculated_running_net

        rows_computed.append({
            **m,
            "blocks": block_subtotals,
            "mismatch": mismatch,
        })

    rows_computed.sort(key=lambda r: r["official_total"] if r["official_total"] is not None else 0, reverse=True)

    header_cells = ['<th class="name-cell">Manager</th>']
    for b in range(num_blocks):
        start, end = b * 4 + 1, min(b * 4 + 4, max_gw)
        for gw in range(start, end + 1):
            live_class = ' class="live-col"' if (live_unconfirmed and gw == live_gw) else ""
            header_cells.append(f"<th{live_class}>GW{gw}</th>")
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
                gw_info = m["gw_data"].get(gw) if max_gw > 0 else None
                live_class = ' class="live-col"' if (live_unconfirmed and gw == live_gw) else ""
                if gw_info:
                    net_val = gw_info["net"]
                    cost = gw_info["cost"]
                    if cost > 0:
                        val_str = f'{net_val}<span class="hit-hint">({gw_info["gross"]}-{cost})</span>'
                    else:
                        val_str = f'{net_val}'
                else:
                    val_str = "-"
                cells.append(f"<td{live_class}>{val_str}</td>")
            cells.append(f'<td class="subtotal-col">{m["blocks"][b] if b < len(m["blocks"]) else 0}</td>')

        total_class = "total-col mismatch-alert" if m["mismatch"] else "total-col"
        cells.append(f'<td class="{total_class}">{m["official_total"]}</td>')
        body_rows.append(f"<tr{rank_class}>" + "".join(cells) + "</tr>")

    live_note = (
        f'<div class="subtitle live-note">GW{live_gw} is still live &mdash; scores for that '
        f"column are provisional and may shift a little until bonus points are confirmed.</div>"
        if live_unconfirmed else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FUBAR FPL DOP TRACKER</title>
<link rel="preconnect" href="https://googleapis.com">
<link href="https://googleapis.com/css2?family=Oswald:wght@500;600;700&family=Work+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{{
    --turf-dark:#0f221a; --chalk:#F6F5F0; --chalk-dim:#D8DED8;
    --amber:#E0A93B; --amber-dim:#F3D89A; --line:rgba(246,245,240,0.16);
    --alert-orange: #d97706; --live-blue:#3b82f6;
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
  .live-note{{color:var(--live-blue);}}
  .table-scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);}}
  table{{border-collapse:collapse;width:100%;table-layout:fixed;font-variant-numeric:tabular-nums;}}
  th, td{{padding:7px 4px;text-align:center;font-size:0.78rem;white-space:nowrap;border-bottom:1px solid var(--line);overflow:hidden;text-overflow:ellipsis;}}
  th{{font-family:'Oswald',sans-serif;font-weight:600;font-size:0.74rem;color:var(--chalk-dim);background:var(--turf-dark);position:sticky;top:0;}}
  th:not(.name-cell):not(.subtotal-col):not(.total-col),
  td:not(.name-cell):not(.subtotal-col):not(.total-col){{width:52px;}}
  th.subtotal-col, td.subtotal-col{{width:54px;}}
  th.total-col, td.total-col{{width:58px;}}
  th.live-col, td.live-col{{background:rgba(59,130,246,0.14);}}
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
  tr:nth-child(even) td.live-col{{background:rgba(59,130,246,0.20);}}
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
    <img class="logo" src="logo.jpg" alt="League logo" onerror="this.style.display='none'">
    <div class="header-text">
      <h1>{league_name.upper()}</h1>
      <div class="subtitle">Net GW score (GW pts minus transfer hits) &middot; DOP for lowest pts every 4 gameweeks</div>
      <div class="subtitle">Last updated {generated_at}</div>
      {live_note}
    </div>
  </header>
  <div class="table-scroll">
    <table>
      <thead><tr>{''.join(header_cells)}</tr></thead>
      <tbody>{''.join(body_rows)}</tbody>
    </table>
  </div>
  <div class="scroll-hint">&larr; swipe to see all gameweeks &rarr;</div>
  <footer>This page is regenerated automatically on a schedule by GitHub Actions, pulling live from the official FPL API.</footer>
</div>
</body>
</html>"""


def main():
    print(f"Fetching league {LEAGUE_ID}...")
    try:
        league_name, managers, max_gw, live_gw, live_gw_is_final = fetch_all(LEAGUE_ID)
    except Exception as err:
        print(f"FATAL: failed to fetch league data: {err}")
        sys.exit(1)

    if max_gw == 0:
        print("No completed gameweeks found yet. Exiting without writing output.")
        return

    now_utc = datetime.now(timezone.utc)
    sa_time = now_utc + timedelta(hours=2)  # SAST = UTC+2
    generated_at_str = sa_time.strftime("%Y-%m-%d %H:%M SAST")

    print("Generating HTML...")
    html = render_html(league_name, managers, max_gw, generated_at_str, live_gw, live_gw_is_final)

    out_dir = os.path.dirname(OUTPUT_PATH)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote {OUTPUT_PATH} ({len(html)} bytes) at {generated_at_str}")


if __name__ == "__main__":
    main()
