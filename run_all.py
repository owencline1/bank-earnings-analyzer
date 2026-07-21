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
    """Run all three stages in order. Returns the exit code of the first stage
    that fails (non-zero), or 0 if the whole pipeline succeeds.

    Each stage now returns an exit code, so we stop the moment one fails rather
    than running extract on missing transcripts or cross-reading stale data.
    This is what lets a pipeline call run_all and trust `$?`.
    """
    tickers = list(BANKS.keys())

    print("=" * 60)
    print(f"STEP 1/3  Fetching {len(tickers)} transcripts")
    print("=" * 60)
    rc = fetch.main(["--all"])
    if rc:
        print("\nABORT: fetch stage failed -- not extracting on missing transcripts.")
        return rc

    print("\n" + "=" * 60)
    print(f"STEP 2/3  Extracting analysis (calls Claude once per bank)")
    print("=" * 60)
    # extract.main handles the missing-API-key case and prints a clear error.
    rc = extract.main(["--all"])
    if rc:
        print("\nABORT: extract stage failed -- not cross-reading on incomplete data.")
        return rc

    print("\n" + "=" * 60)
    print("STEP 3/3  Cross-reading into outputs/cross_read.md")
    print("=" * 60)
    rc = compare.main()
    if rc:
        print("\nABORT: cross-read stage failed.")
        return rc

    print("\nDone. See outputs/cross_read.md for the divergence report.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
