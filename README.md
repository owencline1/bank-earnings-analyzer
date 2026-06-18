# Bank Earnings Cross-Read

Read a whole sector's earnings calls the way one analyst can't in earnings week:
all at once, the same questions asked of every bank, and the **divergences** —
where the banks quietly disagree — pulled to the surface automatically.

Point it at a set of bank earnings-call transcripts and it produces a single
Markdown report: a headline-metrics table, a stance matrix (every bank × every
topic), and a divergence report that ranks the topics by how split the banks are
and calls out the odd ones out. Every supporting quote is checked **word-for-word**
against the source transcript, so a made-up quote can't reach your writeup.

Built for Q1 2026 across 7 banks (JPM, BAC, WFC, C, USB, PNC, TFC), but the bank
list and quarter are just config — see [Run a new quarter](#run-a-new-quarter).

---

## How it works (3 stages)

```
  banks.py            transcripts/<T>.txt        outputs/<T>.json       outputs/cross_read.md
  (URLs +    fetch.py   ───────────►   extract.py   ──────────►  compare.py   ──────────►
   universe)  (scrape)                  (Claude +                 (line up &
                                         quote-check)              find splits)
```

1. **`fetch.py`** — downloads each transcript from its URL and saves clean text to
   `transcripts/<TICKER>.txt`. Standard library only.
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

---

## What you get

- **`outputs/cross_read.md`** — the deliverable. Headline-metrics table, stance
  matrix, and a divergence report (most-contested topics first, minority camp
  named). Any quote that failed the verbatim check is flagged here, loudly.
- **`outputs/<TICKER>.json`** — the structured analysis for each bank, with a
  `verbatim_ok` flag on every quote.
- **`transcripts/<TICKER>.txt`** — the cleaned transcript text (local cache).

---

## Run a new quarter

1. In **`banks.py`**, set `QUARTER` (e.g. `"Q2 2026"`) and update each bank's
   transcript `url`. URLs aren't auto-discovered — find each by searching
   `"<Bank> (TICKER) Q2 2026 earnings call transcript"` and pasting the link.
2. `python run_all.py`.

To change *which* banks are covered, add or remove entries in `BANKS`. To change
*what* is extracted, edit the `DIMENSIONS` list in `schema.py` — that single list
is the contract every bank is held to.

---

## Honest limitations

Read these before assuming it's plug-and-play:

- **It costs money.** `extract.py` makes one Claude API call per bank (8 here).
  Small — cents to low dollars per full run — but not free.
- **Transcript URLs are manual.** You paste them into `banks.py` each quarter.
  There's no automatic discovery.
- **The scraper is source-specific and can break.** `fetch.py` is tuned to one
  transcript provider's page layout (it looks for a specific HTML container). If
  that site changes its markup, fetching breaks and the script will fail loudly
  rather than save garbage — at which point `fetch.py` needs updating. A
  different transcript source needs a different parser.
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
| `banks.py` | The bank universe + transcript URLs + the quarter label |
| `schema.py` | The extraction contract: the dimensions pulled from every call |
| `fetch.py` | Stage 1 — download & clean transcripts |
| `extract.py` | Stage 2 — Claude analysis + verbatim-quote check |
| `compare.py` | Stage 3 — cross-read & divergence report |
| `verify_quotes.py` | Standalone re-check that every saved quote is verbatim |
| `run_all.py` | Convenience: run all three stages in order |
