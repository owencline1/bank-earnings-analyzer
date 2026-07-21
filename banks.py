"""The bank universe for the cross-read, plus the active quarter and its URLs.

The seven banks (names + a distinctive identity token) live here in code, since
they rarely change. The transcript URLs -- which DO change every quarter and embed
a publish date that can't be guessed -- live in urls.json, keyed by quarter.

This module reads urls.json, picks the `active_quarter`, and exposes the same two
names the rest of the pipeline imports:

    QUARTER -- e.g. "Q1 2026"
    BANKS   -- {ticker: {"name", "match", "url"}}; url is "TODO" if not set yet.

To run a new quarter you don't edit this file: add the quarter's URL block to
urls.json and set active_quarter. See README "Run a new quarter (with Claude)".
"""

import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
URLS_PATH = os.path.join(HERE, "urls.json")

# The seven banks: ticker -> (display name, a distinctive lowercase token that
# must appear in a genuine transcript for that bank). The `match` token is the
# wrong-bank tripwire used by fetch.py's validation gate -- pick something that
# shows up in that company's call but not the others (not the word "bank").
BANK_UNIVERSE = {
    "JPM": {"name": "JPMorgan Chase", "match": "jpmorgan"},
    "BAC": {"name": "Bank of America", "match": "bank of america"},
    "WFC": {"name": "Wells Fargo", "match": "wells fargo"},
    "C": {"name": "Citigroup", "match": "citi"},
    "USB": {"name": "U.S. Bancorp", "match": "bancorp"},
    "PNC": {"name": "PNC Financial", "match": "pnc"},
    "TFC": {"name": "Truist Financial", "match": "truist"},
}


def _load_urls():
    """Return (active_quarter, {ticker: url}). Tolerates a missing/partial file
    so the pipeline degrades to 'TODO' URLs (which fetch.py refuses) rather than
    crashing on import."""
    if not os.path.exists(URLS_PATH):
        return "UNSET", {}
    with open(URLS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    quarter = data.get("active_quarter", "UNSET")
    urls = data.get("quarters", {}).get(quarter, {})
    return quarter, urls


QUARTER, _URLS = _load_urls()

# Build the same BANKS shape the pipeline has always used, now with a `match`
# token and the url pulled from urls.json (TODO when the quarter has no URL yet).
BANKS = {
    ticker: {
        "name": meta["name"],
        "match": meta["match"],
        "url": _URLS.get(ticker, "TODO"),
    }
    for ticker, meta in BANK_UNIVERSE.items()
}
