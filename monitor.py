#!/usr/bin/env python3
"""
Monitors Forum Cinemas Vingis (Vilnius) for new IMAX showtimes of "The Odyssey"
and sends a Telegram message whenever a NEW date/showtime is published that
wasn't seen on the previous run.

Data source: kinoafisha.info's schedule page for Forum Cinemas Vingis.
This mirrors forumcinemas.lt's own published schedule and is easier to
parse reliably than the forumcinemas.lt site itself (which renders most
content client-side / behind a different template per release).

If forumcinemas.lt changes its structure or you'd rather hit it directly,
swap SCHEDULE_URL and rewrite `parse_odyssey_imax_showtimes()` accordingly
-- the rest of the script (state diffing + Telegram notify) stays the same.

State is persisted to state.json so the script only alerts on genuinely
NEW showtimes, not on every run.
"""

import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SCHEDULE_URL = "https://lt.kinoafisha.info/en/vilnius/cinema/8326312/schedule/"
MOVIE_NAME = "The Odyssey"
STATE_FILE = Path(__file__).parent / "state.json"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def fetch_page() -> str:
    resp = requests.get(SCHEDULE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_odyssey_imax_showtimes(html: str) -> dict:
    """
    Returns a dict of {date_string: [showtimes]} for IMAX screenings of
    MOVIE_NAME. Date sections on the page look like:

        ## Forum Cinemas Vingis schedule in Vilnius on 21 August 2026
        ...
        The Odyssey ...
        2D, IMAX, SUB LT
        12:30 20:10

    We walk the page's headings in order, and within each date's section
    look for the movie name followed by a line containing "IMAX", followed
    by a line of HH:MM times.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [l for l in text.split("\n") if l.strip()]

    results = {}
    current_date = None
    i = 0
    date_re = re.compile(r"schedule in Vilnius on (.+)$")
    time_re = re.compile(r"^\d{1,2}:\d{2}(\s+\d{1,2}:\d{2})*$")

    while i < len(lines):
        line = lines[i]
        date_match = date_re.search(line)
        if date_match:
            current_date = date_match.group(1).strip()
            i += 1
            continue

        if MOVIE_NAME.lower() in line.lower() and current_date:
            # Scan forward a few lines for an "IMAX" format tag and a
            # following line of showtimes.
            for j in range(i, min(i + 8, len(lines))):
                if "imax" in lines[j].lower():
                    # times are usually 1-2 lines after the format tag
                    for k in range(j, min(j + 3, len(lines))):
                        if time_re.match(lines[k]):
                            times = lines[k].split()
                            results.setdefault(current_date, [])
                            for t in times:
                                if t not in results[current_date]:
                                    results[current_date].append(t)
                            break
                    break
        i += 1

    return results


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def diff_new_showtimes(old: dict, new: dict) -> dict:
    """Return only the dates/times present in `new` but not in `old`."""
    new_entries = {}
    for date, times in new.items():
        old_times = set(old.get(date, []))
        added = [t for t in times if t not in old_times]
        if added:
            new_entries[date] = added
    return new_entries


def send_telegram(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[warn] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set, "
              "skipping notification. Message would have been:\n" + message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    resp.raise_for_status()


def main() -> int:
    try:
        html = fetch_page()
    except requests.RequestException as e:
        print(f"[error] Failed to fetch schedule page: {e}", file=sys.stderr)
        return 1

    current = parse_odyssey_imax_showtimes(html)
    previous = load_state()

    new_showtimes = diff_new_showtimes(previous, current)

    if new_showtimes:
        lines = [f"New IMAX showtimes for {MOVIE_NAME} at Forum Cinemas Vingis:"]
        for date in sorted(new_showtimes):
            times = ", ".join(sorted(new_showtimes[date]))
            lines.append(f"- {date}: {times}")
        lines.append("")
        lines.append("Book here: https://forumcinemas.lt/en/")
        message = "\n".join(lines)
        print(message)
        send_telegram(message)
    else:
        print("No new IMAX showtimes found. "
              f"Currently tracked dates: {sorted(current.keys())}")

    save_state(current)
    return 0


if __name__ == "__main__":
    sys.exit(main())
