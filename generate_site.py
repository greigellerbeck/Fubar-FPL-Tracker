import time
from datetime import datetime, timezone

import requests

LEAGUE_ID = 970639
BASE = "https://premierleague.com"
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
