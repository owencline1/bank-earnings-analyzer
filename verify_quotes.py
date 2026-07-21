"""Independently re-check every quote in outputs/*.json against its transcript.
Reuses the same canonicalization extract.py uses, so this is the real verbatim gate."""
import os, json, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
TR = os.path.join(HERE, "transcripts")

def canon(s):
    # keep in sync with _canon() in extract.py (punctuation-insensitive matching)
    s = s.replace("’","'").replace("‘","'")
    s = s.replace("“",'"').replace("”",'"')
    s = s.replace("—","-").replace("–","-").replace("‒","-")
    s = re.sub(r"[^\w\s$%]"," ", s)
    return re.sub(r"\s+"," ", s).strip().lower()

total=ok=empty=bad=0
for t in ["JPM","BAC","WFC","C","USB","PNC","TFC"]:
    jp=os.path.join(OUT,f"{t}.json")
    if not os.path.exists(jp): continue
    data=json.load(open(jp,encoding="utf-8"))
    ct=canon(open(os.path.join(TR,f"{t}.txt"),encoding="utf-8").read())
    for k,d in data.get("dimensions",{}).items():
        q=(d.get("quote") or "").strip()
        total+=1
        if not q:
            empty+=1; continue
        if canon(q) in ct:
            ok+=1
        else:
            bad+=1
            print(f"  MISMATCH {t}/{k}: {q[:90]}...")
print(f"\nchecked={total}  verbatim_ok={ok}  empty={empty}  MISMATCHES={bad}")
