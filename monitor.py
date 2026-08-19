#!/usr/bin/env python3
"""
Queries Forum Cinemas' real internal REST API (the one their own booking
widget uses) for all published IMAX screenings of "The Odyssey" at Forum
Cinemas Vingis, and sends a daily Telegram digest naming the single
showing with the most available seats right now.

This replaces the old kinoafisha.info-scraping approach. That approach
could only see published DATES, not seat counts, because Forum Cinemas'
own site renders its schedule via JavaScript. The API below is what that
JavaScript actually calls, discovered via browser dev tools -- it returns
real, current seat availability directly, no scraping/parsing needed.

How the IDs below were found (documented for future maintenance):
  - REGION_ID / CINEMA_ID: captured from the Network tab while browsing
    forumcinemas.lt's schedule for Forum Cinemas Vingis.
  - MOVIE_ID: identified by matching IMAX screenings' times against the
    already-known Odyssey IMAX showtimes (12:30 / 16:20 / 20:10). The API
    doesn't return movie titles, only this internal ID, so if Forum
    Cinemas' IMAX screen moves on to a different film, this ID will
    simply stop appearing and the script will report "no showings found"
    rather than silently tracking the wrong movie.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REGION_ID = "e9202daa-51f9-4de9-8811-3076ad5449be"   # Vilnius region
CINEMA_ID = "f933f355-2e6b-466f-9b97-e267ecd8e266"   # Forum Cinemas Vingis
MOVIE_ID = "2a36684b-4f5e-4474-a3aa-9a86516cc5f1"    # The Odyssey

API_BASE = "https://restapi.forumcinemas.lt/api"
DAYS_AHEAD = 14   # how many days into the future to check

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

VILNIUS_TZ = timezone(timedelta(hours=3))  # EEST; Vilnius is UTC+2/+3


def fetch_screenings_for_day(day: datetime) -> list:
    """Fetches all screenings at any cinema in the region for one
    calendar day (day is a date-only datetime, time part ignored)."""
    date_str = day.strftime("%Y-%m-%d")
    dt_from = f"{date_str}T02:00:00.000"
    next_day = (day + timedelta(days=1)).strftime("%Y-%m-%d")
    dt_to = f"{next_day}T01:59:59.999"

    url = f"{API_BASE}/region/{REGION_ID}/screening"
    resp = requests.get(
        url,
        params={"dateTimeFrom": dt_from, "dateTimeTo": dt_to, "movieId": "null"},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def find_odyssey_imax_showings(screenings: list) -> list:
    """Filters a list of raw screening dicts down to Odyssey IMAX
    showings at the right cinema, returning simplified records with
    computed seat availability."""
    results = []
    for s in screenings:
        if s.get("cinemaId") != CINEMA_ID:
            continue
        if s.get("movieId") != MOVIE_ID:
            continue
        if "IMAX" not in (s.get("screenFeatures") or []):
            continue

        max_occ = s.get("maxOccupancy") or 0
        audience = s.get("audience") or 0
        seats_left = max_occ - audience

        results.append({
            "id": s.get("id"),
            "start": s.get("screeningTimeFrom"),
            "seats_left": seats_left,
            "max_occupancy": max_occ,
            "audience": audience,
        })
    return results


def collect_all_upcoming_showings() -> list:
    """Walks forward day by day from today and collects every currently
    published Odyssey IMAX showing found, across the whole DAYS_AHEAD
    window."""
    all_showings = []
    today = datetime.now(VILNIUS_TZ)
    for i in range(DAYS_AHEAD):
        day = today + timedelta(days=i)
        try:
            screenings = fetch_screenings_for_day(day)
        except requests.RequestException as e:
            print(f"[warn] Failed to fetch {day.strftime('%Y-%m-%d')}: {e}",
                  file=sys.stderr)
            continue
        all_showings.extend(find_odyssey_imax_showings(screenings))
    return all_showings


def format_showing(showing: dict) -> str:
    start = datetime.fromisoformat(showing["start"])
    when = start.strftime("%a %d %B, %H:%M")
    return (f"{when} — {showing['seats_left']} seats left "
            f"(out of {showing['max_occupancy']})")


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
    showings = collect_all_upcoming_showings()

    if not showings:
        message = (
            "No IMAX showings of The Odyssey currently found at Forum "
            "Cinemas Vingis in the published schedule. Either the run has "
            "ended, or no dates are published yet."
        )
        print(message)
        send_telegram(message)
        return 0

    # Sort by most seats left, descending.
    showings.sort(key=lambda s: s["seats_left"], reverse=True)
    best = showings[0]
    runner_ups = showings[1:4]  # next few, for context

    lines = [
        "Best seat availability today for The Odyssey (IMAX, Vingis):",
        f"BEST: {format_showing(best)}",
    ]
    if runner_ups:
        lines.append("")
        lines.append("Other options:")
        for s in runner_ups:
            lines.append(f"- {format_showing(s)}")

    lines.append("")
    lines.append("Book here: https://forumcinemas.lt/en/")
    message = "\n".join(lines)
    print(message)
    send_telegram(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
