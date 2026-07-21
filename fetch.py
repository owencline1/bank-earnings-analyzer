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
import re
import time
import urllib.request
from html.parser import HTMLParser

from banks import BANKS, QUARTER

# Quarter -> (reporting month, year offset). These large banks report on a
# reliable calendar: Q1 in April, Q2 in July, Q3 in October, Q4 the following
# January. We can't validate on the spoken phrase ("second quarter" shows up
# constantly in forward guidance), but the dated call header is unambiguous.
_Q_REPORTING = {
    "1": ("april", 0),
    "2": ("july", 0),
    "3": ("october", 0),
    "4": ("january", 1),
}


def _expected_call_date(quarter):
    """('april', '2026') for 'Q1 2026'. Returns (None, None) if unparseable.

    Note the Q4 roll: a Q4 2026 call is reported in January 2027, so the year
    advances by one.
    """
    parts = quarter.replace("Q", "").split()
    if len(parts) != 2 or parts[0] not in _Q_REPORTING or not parts[1].isdigit():
        return None, None
    month, yr_off = _Q_REPORTING[parts[0]]
    return month, str(int(parts[1]) + yr_off)


_MONTHS = ("january|february|march|april|may|june|july|august|september|"
           "october|november|december")
_DATE_RE = re.compile(rf"\b(?:{_MONTHS}) \d{{1,2}}, \d{{4}}\b")


def _found_call_date(body):
    """The call-header 'Month DD, YYYY' (searched in the header region only, so we
    don't pick up a balance-sheet reference date from the body). None if absent."""
    m = _DATE_RE.search(body[:2000])
    return m.group(0) if m else None


def _quarter_check(quarter, body):
    """Confirm the call header date matches the quarter we expect. Returns (ok, reason).

    We look for an explicit 'Month DD, YYYY' in the body (the call-date line),
    not the spoken quarter phrase -- banks reference adjacent quarters in
    guidance, so phrase-counting misidentifies the call (USB's Q1 call says
    'second quarter' more than 'first quarter'). The dated header doesn't lie.

    When it DOESN'T match, the reason names the date we actually found and
    distinguishes the two cases so you know which you're looking at:
      - right year, wrong month  -> the bank may have reported off its usual
        schedule; the transcript could be valid (flagged 'OFF-SCHEDULE?').
      - wrong year, or no date    -> almost certainly the wrong URL.
    """
    month, year = _expected_call_date(quarter)
    if not month:
        return True, ""  # unparseable quarter label -> don't block on it
    if re.search(rf"\b{month} \d{{1,2}}, {year}\b", body):
        return True, ""

    found = _found_call_date(body)
    expected = f"{month.title()} {year}"
    if not found:
        return False, (
            f"expected a call date in {expected} for {quarter}, but found no dated "
            f"header in the text -- can't confirm the quarter; verify the link"
        )
    found = found.title()
    if found.endswith(year):
        # Same year, different month: the alarming-but-possibly-fine case.
        return False, (
            f"OFF-SCHEDULE? found a call dated '{found}' but expected {expected} for "
            f"{quarter}. If this bank genuinely reported outside its usual {month.title()} "
            f"window this quarter, the transcript may be VALID -- open the link and "
            f"confirm it really is {quarter}. If it's the wrong link, fix it in urls.json"
        )
    return False, (
        f"found a call dated '{found}', which doesn't match the expected {expected} "
        f"for {quarter} -- this is almost certainly the wrong quarter/year URL"
    )


def _identity_check(ticker, body):
    """Confirm `body` is THIS bank's call, not a competitor's.

    A bank-name token alone is too weak: rival analysts on the call name other
    banks (a BofA analyst asking a question puts 'bank of america' on JPM's
    call). Usually the SUBJECT bank's token dominates, so we accept when this
    bank's token is the single most frequent of all seven. But frequency alone
    can mislead on sources with bare speaker labels (Benzinga): management says
    'the firm' while a rival-bank analyst affiliation ('Truist Securities')
    piles up in the Q&A. The page lead always names the SUBJECT bank, so a
    mention in the first 600 chars rescues a genuine transcript -- a wrong-bank
    page names someone else there and still fails both checks.
    Returns (ok, reason).
    """
    counts = {t: body.count(BANKS[t]["match"].lower()) for t in BANKS}
    mine = counts[ticker]
    if mine == 0:
        return False, f"identity token '{BANKS[ticker]['match']}' not found"
    rivals = {t: c for t, c in counts.items() if t != ticker}
    top_rival = max(rivals, key=rivals.get)
    if mine > rivals[top_rival]:
        return True, ""
    if BANKS[ticker]["match"].lower() in body[:600]:
        return True, ""
    return False, (
        f"'{BANKS[top_rival]['match']}' ({rivals[top_rival]}x) appears at least "
        f"as often as '{BANKS[ticker]['match']}' ({mine}x), and "
        f"'{BANKS[ticker]['match']}' isn't named in the page lead -- likely the "
        f"wrong bank"
    )

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


# Tags that never get a closing tag; counting them toward nesting depth would
# leak the capture past the container.
VOID_TAGS = {"br", "img", "hr", "meta", "input", "source", "wbr", "area", "col",
             "embed", "link", "track"}


class BenzingaExtractor(HTMLParser):
    """Benzinga streams the article body as React chunks, so the body container
    div is empty in the raw HTML and a by-id capture comes back near-empty. The
    body paragraphs all carry the 'core-block' class wherever they land in the
    stream, so we capture by class instead. The call date lives in a page-header
    element ('article-date') outside the body; we grab it too so
    parse_transcript can restore it for the quarter gate."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0          # >0 while inside a core-block element
        self.parts = []
        self.date_capture = False
        self.date_parts = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        cls = dict(attrs).get("class") or ""
        if self.depth == 0 and "article-date" in cls:
            self.date_capture = True
        if "core-block" in cls:
            if self.depth == 0:
                self.parts.append("\n")
            self.depth += 1
        elif self.depth:
            self.depth += 1

    def handle_endtag(self, tag):
        self.date_capture = False
        if tag in VOID_TAGS:
            return
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.date_capture:
            self.date_parts.append(data)
        if self.depth:
            self.parts.append(data)


def parse_transcript(html, url):
    """Extract clean transcript text from a supported source's page.

    Source is chosen by URL host: Motley Fool (by container id) or Benzinga
    (by paragraph class, with the call date restored as the first line so the
    quarter gate still has a dated header to check)."""
    if "benzinga.com" in url:
        parser = BenzingaExtractor()
        parser.feed(html)
        text = _normalize("".join(parser.parts))
        date = " ".join("".join(parser.date_parts).split())
        if date:
            text = f"Call date: {date}\n{text}"
        return text
    parser = TranscriptExtractor()
    parser.feed(html)
    return _normalize("".join(parser.parts))


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
    text = parse_transcript(html, url)

    words = len(text.split())
    if words < 3000:
        # Bank calls run ~10-15k words. A short result means the page layout
        # changed or we hit a stub -- fail loud rather than save garbage.
        raise RuntimeError(
            f"{ticker}: extracted only {words} words -- the source's page layout "
            f"may have changed. Inspect the page before trusting this."
        )

    # Identity + quarter gate. This is the tripwire for an auto-discovered URL
    # that points at the wrong bank or wrong quarter: a confident-but-wrong page
    # would otherwise sail through and produce a plausible, wrong report.
    body = text.lower()
    ok, reason = _identity_check(ticker, body)
    if not ok:
        raise RuntimeError(f"{ticker}: {reason}. Check banks.py / urls.json.")
    ok, reason = _quarter_check(QUARTER, body)
    if not ok:
        raise RuntimeError(f"{ticker}: {reason}. Verify the link in urls.json.")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{ticker}.txt")
    header = f"{info['name']} ({ticker}) -- {url}\n{'=' * 70}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + text)
    print(f"  {ticker}: {words:,} words -> {path}")
    return path


def main(argv):
    """Fetch transcripts. Returns 0 if every requested bank succeeded, else 1.

    A non-zero return means at least one transcript failed to fetch, so a
    pipeline can stop instead of running later stages on missing data.
    """
    if not argv:
        print(__doc__)
        return 0
    if argv[0] == "--all":
        tickers = [t for t, i in BANKS.items() if i["url"] and i["url"] != "TODO"]
    else:
        tickers = [t.upper() for t in argv]

    failed = []
    for t in tickers:
        try:
            fetch_transcript(t)
        except Exception as e:
            print(f"  {t}: FAILED -- {e}")
            failed.append(t)
        time.sleep(1)   # be polite between requests

    if failed:
        print(f"fetch: {len(tickers) - len(failed)}/{len(tickers)} ok; "
              f"FAILED: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
