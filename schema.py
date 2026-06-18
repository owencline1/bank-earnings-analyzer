"""The extraction schema: the dimensions we pull from every call, identically.

The whole point of the cross-read is comparing the SAME fields across all 7 banks,
so this schema is the contract. Each dimension is captured as:
    summary    - 1-2 sentence synthesis of what management said
    stance     - a short tag that makes banks line up against each other
                 (e.g. CRE reserves: "building" vs "releasing" vs "flat")
    quote      - a VERBATIM supporting quote from the transcript ("" if none)
    speaker    - who said the quote
    confidence - high / medium / low: how well the quote backs the summary

The stance tags are what compare.py uses to surface divergence.
"""

# key -> (human label, guidance the model gets, suggested stance vocabulary)
DIMENSIONS = [
    ("nim_nii", "NIM / NII trajectory & outlook",
     "Net interest margin and net interest income this quarter and the full-year "
     "outlook. Did guidance go up, down, or hold? Capture the direction and the driver.",
     ["raised", "lowered", "held", "expanding", "compressing", "not discussed"]),

    ("credit_normalization", "Credit normalization",
     "Net charge-offs, NCO rate, delinquencies, and whether credit is normalizing, "
     "stabilizing, or deteriorating. Capture the trend and any specific portfolios called out.",
     ["improving", "stable", "normalizing", "deteriorating", "not discussed"]),

    ("cre_reserves", "Commercial real estate (CRE) reserves",
     "Commercial real estate exposure and loan-loss reserves: did they BUILD reserves, "
     "RELEASE reserves, or hold flat this quarter, and WHY? Office CRE especially. "
     "This is the headline divergence -- be precise about build vs release and the reasoning.",
     ["building", "releasing", "flat", "not discussed"]),

    ("deposit_costs", "Deposit costs / betas / mix",
     "Deposit costs, deposit betas, and mix shift (e.g. into higher-cost CDs). "
     "Are funding costs rising, peaking, or falling?",
     ["rising", "peaking", "falling", "stable", "not discussed"]),

    ("capital_return", "Capital return & regulation",
     "Buybacks, dividends, CET1 ratio, and commentary on Basel III endgame / G-SIB. "
     "Are they returning more or less capital, and how do they frame the regulatory outlook?",
     ["increasing", "steady", "decreasing", "constrained", "not discussed"]),

    ("loan_growth", "Loan growth outlook",
     "Loan growth this quarter and the outlook. Distinguish ORGANIC growth from growth "
     "driven by acquisitions -- this matters a lot for comparability.",
     ["accelerating", "steady", "soft", "acquisition-driven", "not discussed"]),

    ("macro_outlook", "Macro / consumer-health view",
     "Management's read on the economy: recession odds, rate path, consumer health, "
     "and any caution vs confidence. Capture how cautious or constructive they sound.",
     ["cautious", "balanced", "constructive", "not discussed"]),

    ("notable_qa", "Notable Q&A pushback",
     "The most pointed analyst question or tense exchange in the Q&A, and how management "
     "handled it. This is where guards come down -- capture what they were pressed on.",
     None),
]


def _field_schema(dim_key, stances):
    stance_desc = "Short tag classifying the bank's stance on this dimension."
    if stances:
        stance_desc += " Prefer one of: " + ", ".join(stances) + "."
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string",
                        "description": "1-2 sentence synthesis of what management said."},
            "stance": {"type": "string", "description": stance_desc},
            "quote": {"type": "string",
                      "description": "A VERBATIM quote from the transcript that supports the "
                                     "summary. Copy it exactly, word for word. Empty string if "
                                     "the topic was not discussed."},
            "speaker": {"type": "string",
                        "description": "Name/role of who said the quote, or empty string."},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"],
                           "description": "How well the quote supports the summary."},
        },
        "required": ["summary", "stance", "quote", "speaker", "confidence"],
        "additionalProperties": False,
    }


def input_schema():
    """JSON schema for the forced tool call the model must fill in."""
    dim_props = {k: _field_schema(k, stances) for (k, _label, _g, stances) in DIMENSIONS}
    return {
        "type": "object",
        "properties": {
            "call_date": {"type": "string", "description": "Date of the earnings call."},
            "headline_metrics": {
                "type": "object",
                "description": "Key reported numbers as short strings (with units).",
                "properties": {
                    "eps": {"type": "string"},
                    "revenue": {"type": "string"},
                    "nii": {"type": "string"},
                    "cet1": {"type": "string"},
                    "nco_rate": {"type": "string"},
                    "roe_rotce": {"type": "string"},
                },
                "required": [],
                "additionalProperties": True,
            },
            "dimensions": {
                "type": "object",
                "properties": dim_props,
                "required": [k for (k, *_rest) in DIMENSIONS],
                "additionalProperties": False,
            },
        },
        "required": ["call_date", "headline_metrics", "dimensions"],
        "additionalProperties": False,
    }


TOOL_NAME = "record_bank_analysis"


def tool_definition():
    return {
        "name": TOOL_NAME,
        "description": "Record the structured analysis of one bank's earnings call.",
        "input_schema": input_schema(),
    }
