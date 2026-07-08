# Cinesis Good Fit Test

## Run it
```
python3 solution.py                      # runs Part A then Part B end to end
```
By default Part A uses a deterministic, rule/keyword-based extractor, so the whole
pipeline runs with no API key and no network call. If `OPENAI_API_KEY` is set in the
environment, Part A instead calls the OpenAI API to do the extraction; either path
produces the same profile shape and feeds directly into Part B.
```
pip install requests
export OPENAI_API_KEY=sk-...             # optional, your own key
python3 solution.py
```

### UI
A minimal Streamlit UI (`app.py`) lets you upload the transcript CSV and loads CSV and
runs the same `solution.py` logic, showing the extracted profile and ranked loads in the
browser.
```
pip install -r requirements.txt
streamlit run app.py
```

## Assumptions
- **Current location**: Dallas, TX - stated directly ("I'm in Dallas").
- **Home base**: San Antonio, TX - driver confirms dispatch's question directly.
- **Min rate/mile**: $2.00 - stated directly ("above $2 per mile, I'll consider it").
- **Equipment**: Hotshot / Gooseneck - driver says "I run a hotshot gooseneck trailer," describing one rig two ways; both terms are matched against the load board's Trailer column. Flatbed loads (e.g. L05) are treated as a different trailer type since the driver never claims to run flatbeds himself.
- **Weight capacity**: 16,500 lb - **inferred**, not stated. The only weight mentioned (44,000 lb) belongs to the Huntsville van load discussed hypothetically, not the driver's rig. 16,500 lb is a typical payload ceiling for a hotshot/gooseneck combo.

## Extraction approach (Part A)
`solution.py` extracts the profile with targeted phrase-matching by default (finds the location callout, the rate condition, the equipment noun, flags anything implied) - deterministic and auditable with no API key required. If `OPENAI_API_KEY` is set, it instead calls the OpenAI API (raw `requests` call to `/v1/chat/completions`, no SDK dependency) with a system prompt that spells out the exact fields to pull and requires, for every field, a `stated` vs `inferred` basis plus the evidence line it used. Both paths produce the same profile schema and feed directly into Part B.

## Incomplete rows (Part B)
L06 is missing price; L07 is missing destination. Neither price nor destination is guessed - both rows are excluded from ranking and reported separately, since fabricating either would silently corrupt the effective rate/mile math.

## Rejected high-paying load
**L08** ($1,700, the highest raw price on the board) passes the equipment/weight/rate filters, but its destination (McAllen) is far south of home base (San Antonio), adding heavy deadhead-home miles. Its effective rate ($2.480/mi) loses to L03 ($3.098/mi, only $1,500) once deadhead is properly counted - exactly the "don't rank on price alone" trap. **L04** and **L01** (Van trailers) are excluded outright on equipment mismatch regardless of price.
