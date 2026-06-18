"""Fetch earnings call transcripts from Motley Fool and save clean text.

Stdlib only (urllib + html.parser) so there are no dependencies to install for
this stage. Each transcript is saved to transcripts/<TICKER>.txt.

Usage:
    python3 fetch.py JPM          # fetch one bank
    python3 fetch.py --all        # fetch every bank with a real URL in banks.py

NOTE: We fetch for our own analysis only. Don't republish full transcripts; the
blog post should be your cross-read plus short attributed quotes.
"""

import sys
import os
import time
import urllib.request
from html.parser import HTMLParser

from banks import BANKS

# The transcript body lives in this container on Motley Fool pages.
TRANSCRIPT_DIV_ID = "article-body-transcript"

# Tags whose boundaries should become line breaks so speaker turns stay readable.
BLOCK_TAGS = {"p", "br", "div", "h1", "h2", "h3", "h4", "li"}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

OUT_DIR = os.path.join(os.path.dirname(__file__), "transcripts")


class TranscriptExtractor(HTMLParser):
    """Collect text only while inside the transcript div, tracking nested depth."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.capturing = False
        self.depth = 0          # div nesting depth once we're inside the target
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if not self.capturing:
            if tag == "div" and dict(attrs).get("id") == TRANSCRIPT_DIV_ID:
                self.capturing = True
                self.depth = 1
            return
        if tag == "div":
            self.depth += 1
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if not self.capturing:
            return
        if tag == "div":
            self.depth -= 1
            if self.depth == 0:      # closed the transcript container
                self.capturing = False
                return
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.capturing:
            self.parts.append(data)


def _normalize(text):
    """Collapse whitespace within lines and drop empty lines."""
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = []
    for ln in lines:
        ln = " ".join(ln.split())   # collapse internal runs of whitespace
        if ln:
            cleaned.append(ln)
    return "\n".join(cleaned)


def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="ignore")


def fetch_transcript(ticker):
    info = BANKS[ticker]
    url = info["url"]
    if not url or url == "TODO":
        raise ValueError(f"{ticker}: no URL set in banks.py yet")

    html = fetch_html(url)
    parser = TranscriptExtractor()
    parser.feed(html)
    text = _normalize("".join(parser.parts))

    words = len(text.split())
    if words < 3000:
        # Bank calls run ~10-15k words. A short result means the container
        # changed or we hit a stub -- fail loud rather than save garbage.
        raise RuntimeError(
            f"{ticker}: extracted only {words} words -- container '{TRANSCRIPT_DIV_ID}' "
            f"may have changed. Inspect the page before trusting this."
        )

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{ticker}.txt")
    header = f"{info['name']} ({ticker}) -- {url}\n{'=' * 70}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + text)
    print(f"  {ticker}: {words:,} words -> {path}")
    return path


def main(argv):
    if not argv:
        print(__doc__)
        return
    if argv[0] == "--all":
        tickers = [t for t, i in BANKS.items() if i["url"] and i["url"] != "TODO"]
    else:
        tickers = [t.upper() for t in argv]

    for t in tickers:
        try:
            fetch_transcript(t)
        except Exception as e:
            print(f"  {t}: FAILED -- {e}")
        time.sleep(1)   # be polite between requests


if __name__ == "__main__":
    main(sys.argv[1:])
