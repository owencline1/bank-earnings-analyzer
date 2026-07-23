# Bank Earnings Cross-Read

Read a whole sector's earnings calls the way one analyst can't in earnings week:
all at once, the same questions asked of every bank, and the **divergences** —
where the banks quietly disagree — pulled to the surface automatically.

Point it at a set of bank earnings-call transcripts and it produces a single
Markdown report: a headline-metrics table, a stance matrix (every bank × every
topic), and a divergence report that ranks the topics by how split the banks are
and calls out the odd ones out. Every supporting quote is checked **word-for-word**
against the source transcript, so a made-up quote can't reach your writeup.

Run live on Q1 and Q2 2026 across 7 banks (JPM, BAC, WFC, C, USB, PNC, TFC); the
bank list and quarter are just config — see [Run a new quarter](#run-a-new-quarter).

## Latest research — Q2 2026 earnings season

- **[Coverage initiation deck](deck/initiation-deck-2026-Q2.md)** — ratings on all
  7 names (sector-relative), full comp table, sector view. The flagship artifact.
- **[Q2 2026 cross-read](outputs/cross_read.md)** — the 7-bank divergence report
  on live Q2 results (52 management quotes, all verified verbatim).
- **[Earnings-week writeup](outputs/Q2-2026-earnings-week-writeup.md)** — the
  consolidated read of the week the seven reported (Jul 14–17), including an
  honest ledger of what was captured when.
- **[First-reads](outputs/first-reads/)** — same-day and post-print reaction notes
  written as the numbers dropped.
- **[Weekly briefs](briefs/)** — the living coverage brief, published here
  automatically each week (newest file = current brief).

---

## How it works (3 stages)

```
  banks.py            transcripts/<T>.txt        outputs/<T>.json       outputs/cross_read.md
  (URLs +    fetch.py   ───────────►   extract.py   ──────────►  compare.py   ──────────►
   universe)  (scrape)                  (Claude +                 (line up &
                                         quote-check)              find splits)
```

1. **`fetch.py`** — downloads each transcript from its URL and saves clean text to
   `transcripts/<TICKER>.txt`. Standard library only. Two transcript sources are
   supported (Motley Fool and Benzinga), chosen automatically by the URL's host.
2. **`extract.py`** — sends each transcript to Claude and forces a structured
   analysis against a fixed schema (the same 8 dimensions for every bank), then
   re-checks every quote verbatim against the transcript. Writes
   `outputs/<TICKER>.json`. *This is the only stage that needs an API key.*
3. **`compare.py`** — lines up all the per-bank JSON files and writes the
   cross-read to `outputs/cross_read.md`.

The eight dimensions compared: NIM/NII, credit normalization, CRE reserves,
deposit costs, capital return & regulation, loan growth, macro view, and the
sharpest Q&A exchange — plus a headline-metrics table (EPS, revenue, NII, CET1,
NCO rate, ROE/ROTCE).

---

## Quickstart

You need **Python 3.9+** and an **Anthropic API key**
([console.anthropic.com](https://console.anthropic.com/)).

```bash
# 1. Install the one dependency
pip install -r requirements.txt

# 2. Add your API key
cp .env.example .env        # then edit .env and paste your real key
                            # (Windows: copy .env.example .env)

# 3. Run the whole pipeline
python run_all.py
```

That fetches all 7 transcripts, analyzes each, and writes the cross-read to
`outputs/cross_read.md`. Done.

### Running stages individually

Handy when you only want part of the pipeline (e.g. re-run one bank):

```bash
python fetch.py JPM          # fetch one bank   (or: python fetch.py --all)
python extract.py JPM        # analyze one bank (or: python extract.py --all)
python compare.py            # cross-read whatever JSON is in outputs/
python verify_quotes.py      # independently re-check every quote is verbatim
```

Running `fetch.py` or `extract.py` with no arguments prints its own usage help.

### Wrapping it in a pipeline

Each stage is callable both ways and reports success through its **exit code**, so
a scheduler or wrapper can check `$?` (or the return value of `main()`) instead of
scraping stdout:

- **`0`** — every requested bank in that stage succeeded.
- **non-zero** — at least one bank failed, the API key was missing (`extract`), or
  there was nothing to cross-read (`compare`).

`run_all.py` chains the three stages and **stops at the first non-zero stage**, so it
won't extract on missing transcripts or cross-read on stale data; it returns that
stage's code. Paths are anchored to the scripts' own folder, so it runs correctly
from any working directory. Calling from Python:

```python
import fetch, extract, compare
if fetch.main(["--all"]):   raise SystemExit("fetch failed")
if extract.main(["--all"]): raise SystemExit("extract failed")
if compare.main():          raise SystemExit("cross-read failed")
```

Note: a quote that fails the verbatim check is **not** a stage failure — extraction
still succeeded. That signal lives in the JSON (`verbatim_ok`) and the report's flag
list; re-run `verify_quotes.py` to gate on it.

---

## What you get

- **`outputs/cross_read.md`** — the deliverable. Headline-metrics table, stance
  matrix, and a divergence report (most-contested topics first, minority camp
  named). Any quote that failed the verbatim check is flagged here, loudly.
- **`outputs/<TICKER>.json`** — the structured analysis for each bank, with a
  `verbatim_ok` flag on every quote.
- **`transcripts/<TICKER>.txt`** — the cleaned transcript text (local cache).

---

## Run a new quarter (with Claude)

URLs now live in **`urls.json`**, not in code, so starting a new quarter is a data
edit, not a Python edit. The pipeline reads `active_quarter` from that file and
builds the bank list from the matching URL block.

**Ask Claude to do it end-to-end** — "run the Q2 2026 bank report". A capable
Claude session can:

1. **Discover the 7 URLs** via web search — one search per bank,
   `"<Bank> (TICKER) Q2 2026 earnings call transcript"` scoped to fool.com and
   benzinga.com (both are supported; whichever posts first wins). Confirm each
   result URL slug contains the ticker *and* the quarter (e.g.
   `.../jpmorgan-jpm-q2-2026-...`) before trusting it.
2. **Write them into `urls.json`** — add a `"Q2 2026": { ... }` block under
   `quarters`, and set `"active_quarter": "Q2 2026"`. (It's plain JSON, so there's
   no Python syntax to break.)
3. **Run** `python run_all.py`.

You don't have to trust the auto-found URLs blindly — `fetch.py` has a **validation
gate** that fails loud if a URL points at the wrong bank or the wrong quarter:

- **Wrong bank** — the subject bank's name must be the most-mentioned of all seven
  in the transcript (a rival analyst on the call isn't enough to fool it).
- **Wrong quarter/year** — the call's dated header must match the expected
  reporting month (Q1→April, Q2→July, Q3→October, Q4→the next January) and year.
  The error names the date it actually found and distinguishes a wrong-year URL
  (almost certainly the wrong link) from a right-year/wrong-month one (flagged
  **`OFF-SCHEDULE?`** — the bank may have reported off its usual week, so the
  transcript could be valid; open the link and confirm before discarding).

So a misrouted link produces a hard error before any analysis runs, not a
confident-but-wrong report. Timing note: each bank's transcript only exists once
its call has been published (a few hours-to-days after it reports), so run this
*after* all seven have reported — mid-to-late in earnings week.

To change *which* banks are covered, edit `BANK_UNIVERSE` in `banks.py` (name +
the distinctive `match` token used by the validation gate). To change *what* is
extracted, edit the `DIMENSIONS` list in `schema.py` — that single list is the
contract every bank is held to.

---

## Honest limitations

Read these before assuming it's plug-and-play:

- **It costs money.** `extract.py` makes one Claude API call per bank (8 here).
  Small — cents to low dollars per full run — but not free.
- **Transcript URLs need discovery each quarter.** They live in `urls.json` and
  embed a publish date that can't be guessed. A Claude session can find and write
  them for you (see [Run a new quarter](#run-a-new-quarter-with-claude)), and the
  fetch-stage validation gate rejects a wrong-bank or wrong-quarter link — but
  auto-found URLs should still get a glance before a published writeup.
- **The scraper is source-specific and can break.** `fetch.py` is tuned to two
  transcript providers' page layouts. If either site changes its markup, fetching
  breaks and the script fails loudly rather than saving garbage — at which point
  `fetch.py` needs updating. A new transcript source needs a new parser.
- **Sometimes a transcript never publishes free.** In Q2 2026, neither supported
  source carried Wells Fargo's or Citigroup's call. The documented fallback: use
  the bank's SEC 8-K earnings release as the source text instead, with an explicit
  provenance header in the text file and a `source` field in the output JSON, and
  let the cross-read honestly report the Q&A dimension as unavailable. Numbers and
  written management commentary survive; call color doesn't. Never present a
  release-based read as a call-based one.
- **The analysis is a model's reading, not ground truth.** The verbatim-quote
  check guarantees quotes are *real*, not that the *summary or stance* is the only
  fair interpretation. Treat the output as a fast, consistent first pass a human
  still reviews — especially the dollar figures, which should be confirmed against
  each bank's actual earnings release before anything is published.

---

## Don't republish transcripts

`transcripts/` and `.env` are gitignored on purpose. The transcripts are a local
cache for your own analysis — don't commit or republish them. Any public writeup
should be your own cross-read plus short, attributed quotes.

---

## Files

| File | Role |
|---|---|
| `banks.py` | The bank universe (names + identity tokens); reads URLs from `urls.json` |
| `urls.json` | Transcript URLs per quarter + the `active_quarter` selector (data, not code) |
| `schema.py` | The extraction contract: the dimensions pulled from every call |
| `fetch.py` | Stage 1 — download & clean transcripts |
| `extract.py` | Stage 2 — Claude analysis + verbatim-quote check |
| `compare.py` | Stage 3 — cross-read & divergence report |
| `verify_quotes.py` | Standalone re-check that every saved quote is verbatim |
| `run_all.py` | Convenience: run all three stages in order |
