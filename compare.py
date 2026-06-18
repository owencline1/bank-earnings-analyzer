"""Cross-read the 7 per-bank analyses and surface where they DIVERGE.

This is the payoff step. extract.py writes one outputs/<TICKER>.json per bank,
each filled against the same schema. Here we line those up dimension-by-dimension
so the divergences -- the whole value of the post -- jump out.

What it produces:
  1. A headline-metrics table (EPS, NII, CET1, NCO rate, NIM, ROTCE) across banks.
  2. A stance matrix: every dimension x every bank, so you can eyeball the splits.
  3. A divergence report: dimensions ranked by how split the banks are, with the
     minority camp called out and each bank's one-line summary + verbatim quote.
  4. A flag list of any quotes that failed the verbatim check in extract.py, so a
     hallucinated quote can never make it into the post unnoticed.

Everything is written to outputs/cross_read.md (Markdown, ready to read or paste
into a draft) and the divergence headlines are printed to the console.

Usage:
    python3 compare.py            # cross-read every outputs/<TICKER>.json present
"""

import os
import json
from collections import Counter, defaultdict

from banks import BANKS, QUARTER
from schema import DIMENSIONS

HERE = os.path.dirname(__file__)
OUT_DIR = os.path.join(HERE, "outputs")
REPORT_PATH = os.path.join(OUT_DIR, "cross_read.md")

# Column order for everything: the order banks are declared in banks.py.
BANK_ORDER = list(BANKS.keys())

# Headline metrics to surface, in display order: (json key, column label).
METRIC_COLS = [
    ("eps", "EPS"),
    ("revenue", "Revenue"),
    ("nii", "NII"),
    ("cet1", "CET1"),
    ("nco_rate", "NCO rate"),
    ("roe_rotce", "ROE/ROTCE"),
]


def load_analyses():
    """Load every outputs/<TICKER>.json that exists, in BANK_ORDER."""
    analyses = {}
    for ticker in BANK_ORDER:
        path = os.path.join(OUT_DIR, f"{ticker}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                analyses[ticker] = json.load(f)
    return analyses


def _md_escape(s):
    """Keep table cells from breaking the Markdown pipe grid."""
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def metrics_table(analyses):
    present = [t for t in BANK_ORDER if t in analyses]
    header = "| Metric | " + " | ".join(present) + " |"
    sep = "|" + "---|" * (len(present) + 1)
    rows = [header, sep]
    for key, label in METRIC_COLS:
        cells = []
        for t in present:
            m = analyses[t].get("headline_metrics", {}) or {}
            cells.append(_md_escape(str(m.get(key, "") or "-")))
        rows.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def stance_matrix(analyses):
    present = [t for t in BANK_ORDER if t in analyses]
    header = "| Dimension | " + " | ".join(present) + " |"
    sep = "|" + "---|" * (len(present) + 1)
    rows = [header, sep]
    for key, label, _g, _stances in DIMENSIONS:
        cells = []
        for t in present:
            dim = analyses[t].get("dimensions", {}).get(key, {}) or {}
            cells.append(_md_escape(dim.get("stance", "") or "-"))
        rows.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _norm_stance(s):
    return (s or "not discussed").strip().lower()


def divergence_score(stances):
    """How split is this dimension? Higher = more contested.

    We ignore 'not discussed' so a dimension only a few banks touched doesn't
    look falsely unanimous or falsely split. Score = number of DISTINCT real
    stances; ties broken by how even the camps are.
    """
    real = [_norm_stance(s) for s in stances if _norm_stance(s) != "not discussed"]
    if not real:
        return 0, Counter()
    counts = Counter(real)
    return len(counts), counts


def divergence_report(analyses):
    present = [t for t in BANK_ORDER if t in analyses]
    ranked = []
    for key, label, _g, _stances in DIMENSIONS:
        stance_by_bank = {}
        for t in present:
            dim = analyses[t].get("dimensions", {}).get(key, {}) or {}
            stance_by_bank[t] = _norm_stance(dim.get("stance", ""))
        n_distinct, counts = divergence_score(stance_by_bank.values())
        ranked.append((n_distinct, key, label, stance_by_bank, counts))

    # Most contested dimensions first (most distinct stances, then most even split).
    ranked.sort(key=lambda r: (r[0], -max(r[4].values()) if r[4] else 0), reverse=True)

    blocks = []
    for n_distinct, key, label, stance_by_bank, counts in ranked:
        if n_distinct <= 1:
            verdict = "CONSENSUS" if n_distinct == 1 else "not discussed by any bank"
        else:
            # Surface the minority camp -- that's usually the story.
            camps = sorted(counts.items(), key=lambda kv: kv[1])
            minority_stance, minority_n = camps[0]
            minority_banks = [t for t, s in stance_by_bank.items()
                              if s == minority_stance]
            majority = ", ".join(f"{s} ({n})" for s, n in
                                 sorted(counts.items(), key=lambda kv: -kv[1]))
            verdict = (f"DIVERGENCE -- {majority}. "
                       f"Odd ones out on '{minority_stance}': "
                       f"{', '.join(minority_banks)}")

        lines = [f"### {label}", f"*{verdict}*", ""]
        for t in present:
            dim = analyses[t].get("dimensions", {}).get(key, {}) or {}
            stance = dim.get("stance", "-") or "-"
            summary = _md_escape(dim.get("summary", ""))
            quote = (dim.get("quote") or "").strip()
            speaker = (dim.get("speaker") or "").strip()
            vok = dim.get("verbatim_ok")
            flag = " ⚠️UNVERIFIED" if vok is False else ""
            lines.append(f"- **{t}** [{stance}] {summary}")
            if quote:
                who = f" - {speaker}" if speaker else ""
                lines.append(f"  > \"{quote}\"{who}{flag}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def unverified_quotes(analyses):
    flags = []
    for t in [b for b in BANK_ORDER if b in analyses]:
        for key, dim in (analyses[t].get("dimensions", {}) or {}).items():
            if dim.get("verbatim_ok") is False:
                flags.append((t, key, (dim.get("quote") or "")[:100]))
    return flags


def main():
    analyses = load_analyses()
    if not analyses:
        print(f"No analyses found in {OUT_DIR}. Run extract.py --all first.")
        return

    present = [t for t in BANK_ORDER if t in analyses]
    missing = [t for t in BANK_ORDER if t not in analyses]

    parts = [
        f"# Bank earnings cross-read -- {QUARTER}",
        "",
        f"Banks covered ({len(present)}/7): {', '.join(present)}"
        + (f"  |  MISSING: {', '.join(missing)}" if missing else ""),
        "",
        "## Headline metrics",
        metrics_table(analyses),
        "",
        "## Stance matrix (the cross-read at a glance)",
        stance_matrix(analyses),
        "",
        "## Divergences (most contested first)",
        "",
        divergence_report(analyses),
    ]

    flags = unverified_quotes(analyses)
    if flags:
        parts += ["", "## ⚠️ Unverified quotes (do NOT publish without checking)"]
        for t, key, q in flags:
            parts.append(f"- {t} / {key}: \"{q}...\"")

    report = "\n".join(parts) + "\n"
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    # Console: just the divergence headlines so you see the story immediately.
    print(f"Cross-read written -> {REPORT_PATH}")
    print(f"Banks: {len(present)}/7 ({', '.join(present)})"
          + (f"  MISSING: {', '.join(missing)}" if missing else ""))
    if flags:
        print(f"\n⚠️  {len(flags)} unverified quote(s) flagged -- check before publishing.")
    print("\nMost contested dimensions:")
    for key, label, _g, _s in DIMENSIONS:
        stances = []
        for t in present:
            dim = analyses[t].get("dimensions", {}).get(key, {}) or {}
            stances.append(_norm_stance(dim.get("stance", "")))
        n, counts = divergence_score(stances)
        if n >= 2:
            spread = ", ".join(f"{s}={c}" for s, c in counts.most_common())
            print(f"  - {label}: {spread}")


if __name__ == "__main__":
    main()
