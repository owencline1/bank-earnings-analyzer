"""The bank universe for the Q1 2026 cross-read, plus the transcript source URLs.

Discovery on Motley Fool isn't automatic (the URL embeds the publish date), so we
pin the 7 URLs here once. To add a new quarter, drop in the new URLs.

Fill in the six TODO URLs by searching:
    "<Bank> (TICKER) Q1 2026 earnings call transcript motley fool"
and pasting the fool.com/earnings/call-transcripts/... link.
"""

QUARTER = "Q1 2026"

BANKS = {
    "JPM": {
        "name": "JPMorgan Chase",
        "url": "https://www.fool.com/earnings/call-transcripts/2026/04/21/jpmorgan-jpm-q1-2026-earnings-call-transcript/",
    },
    "BAC": {
        "name": "Bank of America",
        "url": "https://www.fool.com/earnings/call-transcripts/2026/04/15/bofa-bac-q1-2026-earnings-call-transcript/",
    },
    "WFC": {
        "name": "Wells Fargo",
        "url": "https://www.fool.com/earnings/call-transcripts/2026/04/14/wells-fargo-wfc-q1-2026-earnings-call-transcript/",
    },
    "C": {
        "name": "Citigroup",
        "url": "https://www.fool.com/earnings/call-transcripts/2026/04/14/citigroup-c-q1-2026-earnings-call-transcript/",
    },
    "USB": {
        "name": "U.S. Bancorp",
        "url": "https://www.fool.com/earnings/call-transcripts/2026/04/16/us-bancorp-usb-q1-2026-earnings-call-transcript/",
    },
    "PNC": {
        "name": "PNC Financial",
        "url": "https://www.fool.com/earnings/call-transcripts/2026/04/15/pnc-pnc-q1-2026-earnings-call-transcript/",
    },
    "TFC": {
        "name": "Truist Financial",
        "url": "https://www.fool.com/earnings/call-transcripts/2026/04/17/truist-tfc-q1-2026-earnings-call-transcript/",
    },
}
