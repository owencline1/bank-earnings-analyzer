"""Extract the structured analysis from each transcript using Claude (Sonnet).

For each bank we force a single tool call against the schema in schema.py, then
run a VERBATIM-QUOTE CHECK: every non-empty quote must actually appear in the
transcript. Quotes that don't are flagged (verbatim_ok=false) so you never put a
hallucinated quote in the blog post.

Reads ANTHROPIC_API_KEY from the environment (or a .env file in this folder).

Usage:
    python3 extract.py JPM         # one bank
    python3 extract.py --all       # every fetched transcript
"""

import sys
import os
import re
import json

import anthropic

from banks import BANKS, QUARTER
from schema import DIMENSIONS, TOOL_NAME, tool_definition

MODEL = "claude-sonnet-4-6"
HERE = os.path.dirname(__file__)
TRANSCRIPT_DIR = os.path.join(HERE, "transcripts")
OUT_DIR = os.path.join(HERE, "outputs")


def load_dotenv():
    """Minimal .env loader so a key in ./.env works without extra packages."""
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _canon(s):
    """Normalize for verbatim matching: collapse whitespace, unify quotes/dashes,
    and drop punctuation entirely. Auto-transcribed sources punctuate the same
    words inconsistently ('Yeah, so' vs 'Yeah. So'), so the check is on the exact
    WORD sequence; punctuation-only differences aren't a mismatch. Applied to
    both the quote and the transcript, so word order must still match exactly.
    Keep in sync with canon() in verify_quotes.py."""
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-").replace("‒", "-")
    s = re.sub(r"[^\w\s$%]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def build_prompt(ticker, transcript):
    name = BANKS[ticker]["name"]
    labels = "\n".join(f"  - {k}: {label}\n      {guidance}"
                       for (k, label, guidance, _s) in DIMENSIONS)
    return (
        f"You are a bank equity analyst. Below is the full {QUARTER} earnings call "
        f"transcript for {name} ({ticker}).\n\n"
        f"Extract a structured analysis covering exactly these dimensions:\n{labels}\n\n"
        "Rules:\n"
        "1. Every 'quote' MUST be ONE CONTIGUOUS passage copied VERBATIM from the "
        "transcript -- exact words, no paraphrasing, and NEVER stitch two separate "
        "passages together with '...' or '[...]' (a spliced quote fails verification "
        "even if both halves are real). Prefer a shorter quote that is exactly "
        "contiguous in the transcript. If you can't find an exact supporting quote, "
        "set quote to \"\" and confidence to \"low\".\n"
        "2. If a dimension genuinely isn't discussed, set stance to \"not discussed\", "
        "summary to a brief note, quote to \"\".\n"
        "3. Do not infer numbers that weren't stated. Ground everything in the text.\n"
        "4. For loan growth, explicitly distinguish organic vs acquisition-driven.\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )


def verify_quotes(analysis, transcript):
    """Annotate each dimension with verbatim_ok; return list of failures."""
    canon_t = _canon(transcript)
    failures = []
    for key, field in analysis.get("dimensions", {}).items():
        q = (field.get("quote") or "").strip()
        if not q:
            field["verbatim_ok"] = None  # no quote to check
            continue
        ok = _canon(q) in canon_t
        field["verbatim_ok"] = ok
        if not ok:
            failures.append((key, q))
    return failures


def extract_one(client, ticker):
    tpath = os.path.join(TRANSCRIPT_DIR, f"{ticker}.txt")
    if not os.path.exists(tpath):
        raise FileNotFoundError(f"{tpath} -- run fetch.py first")
    transcript = open(tpath, encoding="utf-8").read()

    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[tool_definition()],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=[{"role": "user", "content": build_prompt(ticker, transcript)}],
    )

    analysis = None
    for block in resp.content:
        if block.type == "tool_use" and block.name == TOOL_NAME:
            analysis = block.input
            break
    if analysis is None:
        raise RuntimeError(f"{ticker}: model did not return the tool call")

    analysis["ticker"] = ticker
    analysis["bank_name"] = BANKS[ticker]["name"]
    failures = verify_quotes(analysis, transcript)

    os.makedirs(OUT_DIR, exist_ok=True)
    outpath = os.path.join(OUT_DIR, f"{ticker}.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    n_dims = len(analysis.get("dimensions", {}))
    flag = "OK" if not failures else f"{len(failures)} UNVERIFIED QUOTE(S)"
    print(f"  {ticker}: {n_dims} dimensions -> {outpath}  [{flag}]")
    for key, q in failures:
        print(f"      ! {key}: quote not found verbatim -> {q[:80]}...")
    return analysis


def main(argv):
    """Extract analyses. Returns 0 if every requested bank succeeded, else 1.

    Missing API key, or any bank that fails to extract, returns non-zero so a
    pipeline can stop before cross-reading on incomplete data. Note: a quote
    that fails the verbatim check is flagged in the JSON, not a hard failure --
    extraction still succeeded, the flag is the signal there.
    """
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Set it in your environment or in a .env file.")
        return 1
    if not argv:
        print(__doc__)
        return 0

    if argv[0] == "--all":
        tickers = [t for t in BANKS
                   if os.path.exists(os.path.join(TRANSCRIPT_DIR, f"{t}.txt"))]
    else:
        tickers = [t.upper() for t in argv]

    client = anthropic.Anthropic()
    failed = []
    for t in tickers:
        try:
            extract_one(client, t)
        except Exception as e:
            print(f"  {t}: FAILED -- {e}")
            failed.append(t)

    if failed:
        print(f"extract: {len(tickers) - len(failed)}/{len(tickers)} ok; "
              f"FAILED: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
