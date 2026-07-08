# Cinesis Good Fit Test

## Run it
```
pip install requests
export ANTHROPIC_API_KEY=sk-ant-...      # your own key
python3 part_a_extract.py                # calls the Claude API -> data/profile.json
python3 part_b_rank.py                   # reads data/profile.json + data/loads.csv
```
`data/profile.json` is already checked in from a live run, so `part_b_rank.py` works
out of the box even without an API key. A deterministic, non-LLM version of the same
extraction logic is included as `part_a_extract_rulebased.py` for comparison/offline use
(same output schema, no API key required).

## Assumptions
- **Current location**: Dallas, TX - stated directly ("I'm in Dallas").
- **Home base**: San Antonio, TX - driver confirms dispatch's question directly.
- **Min rate/mile**: $2.00 - stated directly ("above $2 per mile, I'll consider it").
- **Equipment**: Hotshot / Gooseneck - driver says "I run a hotshot gooseneck trailer," describing one rig two ways; both terms are matched against the load board's Trailer column. Flatbed loads (e.g. L05) are treated as a different trailer type since the driver never claims to run flatbeds himself.
- **Weight capacity**: 16,500 lb - **inferred**, not stated. The only weight mentioned (44,000 lb) belongs to the Huntsville van load discussed hypothetically, not the driver's rig. 16,500 lb is a typical payload ceiling for a hotshot/gooseneck combo.

## Extraction approach (Part A)
`part_a_extract.py` calls the Claude API directly (raw `requests` call to `/v1/messages`, no SDK dependency) with a system prompt that spells out the exact fields to pull and requires, for every field, a `stated` vs `inferred` basis plus the evidence line it used - so the extraction stays auditable even though a model is doing the reading. `part_a_extract_rulebased.py` is a deterministic fallback using targeted phrase-matching (same output schema), useful for offline runs or comparison.

## Incomplete rows (Part B)
L06 is missing price; L07 is missing destination. Neither price nor destination is guessed - both rows are excluded from ranking and reported separately, since fabricating either would silently corrupt the effective rate/mile math.

## Rejected high-paying load
**L08** ($1,700, the highest raw price on the board) passes the equipment/weight/rate filters, but its destination (McAllen) is far south of home base (San Antonio), adding heavy deadhead-home miles. Its effective rate ($2.480/mi) loses to L03 ($3.098/mi, only $1,500) once deadhead is properly counted - exactly the "don't rank on price alone" trap. **L04** and **L01** (Van trailers) are excluded outright on equipment mismatch regardless of price.
