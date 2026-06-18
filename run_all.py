"""One-command runner: fetch -> extract -> compare for the whole bank universe.

This is a thin convenience wrapper. It just calls the three stages in order for
every bank listed in banks.py, so you don't have to run them by hand. Each stage
can still be run on its own (see the README) when you only want part of it.

Usage:
    python run_all.py            # fetch all, extract all, then cross-read

Stops early with a clear message if a stage can't run (e.g. no API key set).
"""

import sys

import fetch
import extract
import compare
from banks import BANKS


def main():
    tickers = list(BANKS.keys())

    print("=" * 60)
    print(f"STEP 1/3  Fetching {len(tickers)} transcripts")
    print("=" * 60)
    fetch.main(["--all"])

    print("\n" + "=" * 60)
    print(f"STEP 2/3  Extracting analysis (calls Claude once per bank)")
    print("=" * 60)
    # extract.main handles the missing-API-key case and prints a clear error.
    extract.main(["--all"])

    print("\n" + "=" * 60)
    print("STEP 3/3  Cross-reading into outputs/cross_read.md")
    print("=" * 60)
    compare.main()

    print("\nDone. See outputs/cross_read.md for the divergence report.")


if __name__ == "__main__":
    sys.exit(main())
