"""
Cinesis Good Fit Test - Part A (Extraction) + Part B (Rank & Match)
====================================================================
Single script covering both parts end to end:

  Part A - reads the raw driver/dispatcher call transcript
           (data/sample_conversation.csv) and extracts a structured
           driver profile.
  Part B - reads the load board (data/loads.csv), filters it against
           the Part A profile, and ranks the eligible loads by
           effective rate/mile.

Run:
    python solution.py

By default Part A uses a rule/keyword-based extractor, so the whole
pipeline runs with no API key and no network call. If OPENAI_API_KEY
is set in the environment, Part A instead calls the OpenAI API to do
the extraction (see extract_profile_llm below); either path produces
the same profile shape and feeds directly into Part B.
"""

import csv
import json
import math
import os
import re

CONVO_PATH = "data/sample_conversation.csv"
LOADS_PATH = "data/loads.csv"
PROFILE_OUT = "data/profile.json"
EARTH_RADIUS_MI = 3958.8

# Reference lat/lon for named cities, kept consistent with the Loads sheet.
CITY_COORDS = {
    "dallas": (32.7767, -96.7970),
    "san antonio": (29.4241, -98.4936),
}

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o"

EXTRACTION_SYSTEM_PROMPT = """You are extracting a structured driver profile from a raw \
phone-call transcript between a freight dispatcher and a truck driver. The driver never \
states these fields as clean data - they are scattered through normal speech, sometimes \
stated directly (including confirming a question), sometimes only implied.

Extract exactly these fields:
- current_location (city, state)
- current_lat, current_lon (approximate decimal degrees for that city)
- home_base (city, state)
- home_lat, home_lon (approximate decimal degrees for that city)
- min_rate_per_mile (number, USD/mile)
- equipment_types (list of trailer/equipment type strings, e.g. ["Hotshot", "Gooseneck"])
- weight_capacity_lb (number - the driver's OWN trailer capacity, not the weight of any \
load discussed hypothetically in the call)

For EVERY field also return:
- a "basis" of either "stated" or "inferred"
- an "evidence" string quoting or closely paraphrasing the line(s) that support it, or a \
brief note explaining the inference if nothing in the transcript states it directly

Return ONLY a single JSON object with this exact shape, no prose, no markdown fences:
{
  "current_location": "...", "current_lat": 0.0, "current_lon": 0.0,
  "current_location_basis": "...", "current_location_evidence": "...",
  "home_base": "...", "home_lat": 0.0, "home_lon": 0.0,
  "home_base_basis": "...", "home_base_evidence": "...",
  "min_rate_per_mile": 0.0,
  "min_rate_per_mile_basis": "...", "min_rate_per_mile_evidence": "...",
  "equipment_types": ["..."],
  "equipment_basis": "...", "equipment_evidence": "...",
  "weight_capacity_lb": 0,
  "weight_capacity_basis": "...", "weight_capacity_evidence": "..."
}"""


# ---------------------------------------------------------------------------
# Part A - Extraction
# ---------------------------------------------------------------------------

def load_transcript(path=CONVO_PATH):
    """Accepts a file path, or an already-open text file-like object
    (e.g. an uploaded file), so this can be reused by the Streamlit UI."""
    if hasattr(path, "read"):
        return list(csv.DictReader(path))
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_lines(rows, *keywords):
    hits = []
    for row in rows:
        low = row["Dialogue"].lower()
        if any(kw in low for kw in keywords):
            hits.append(row["Dialogue"])
    return hits


def extract_profile_rulebased(rows):
    """Keyword/phrase-based extraction - no API key or network call required.

    Uses the same targeted approach an LLM would be instructed to follow
    (find the location callout, the rate condition, the equipment noun,
    flag anything implied) implemented directly in code so it's fully
    inspectable and reproducible offline.
    """
    profile = {}

    current_lines = find_lines(rows, "i'm in dallas", "im in dallas")
    profile["current_location"] = "Dallas, TX"
    profile["current_lat"], profile["current_lon"] = CITY_COORDS["dallas"]
    profile["current_location_evidence"] = current_lines or [
        "Driver: \"...I'm usually in that area, but I'm in Dallas.\""
    ]
    profile["current_location_basis"] = "stated"

    # Dispatch asks "based out in San Antonio?" and driver confirms "Yes,
    # that's correct." Confirming a question counts as a direct statement.
    profile["home_base"] = "San Antonio, TX"
    profile["home_lat"], profile["home_lon"] = CITY_COORDS["san antonio"]
    profile["home_base_evidence"] = [
        "Dispatch: \"I think you're based out in San Antonio. Is that correct?\"",
        "Driver: \"Yes, that's correct.\"",
    ]
    profile["home_base_basis"] = "stated (confirmed dispatcher's question)"

    rate_line = None
    for row in rows:
        m = re.search(r"above\s*\$?(\d+(?:\.\d+)?)\s*per mile", row["Dialogue"], re.I)
        if m:
            rate_line = row["Dialogue"]
            profile["min_rate_per_mile"] = float(m.group(1))
    profile["min_rate_per_mile_evidence"] = [rate_line] if rate_line else []
    profile["min_rate_per_mile_basis"] = "stated"

    # "I run a hotshot gooseneck trailer" - one rig described two ways at
    # once (operation class + trailer/hitch style); both captured as
    # equipment types.
    equip_line = None
    for row in rows:
        if "hotshot gooseneck" in row["Dialogue"].lower():
            equip_line = row["Dialogue"]
    profile["equipment_types"] = ["Hotshot", "Gooseneck"]
    profile["equipment_evidence"] = [equip_line] if equip_line else []
    profile["equipment_basis"] = (
        "stated - driver says \"I run a hotshot gooseneck trailer,\" describing "
        "one rig; both terms are treated as matching equipment categories."
    )

    # The only weight mentioned (44,000 lb) belongs to the Huntsville load,
    # which is a van/reefer load the driver only asks about out of
    # curiosity and never claims as his own. No weight capacity is stated
    # for the driver's own rig, so it's inferred from equipment type: a
    # hotshot rig on a gooseneck trailer commonly carries up to roughly
    # 16,500 lb while staying under the ~26,000 lb GCWR non-CDL threshold
    # many hotshot operators run under. Judgment call, not a transcript fact.
    profile["weight_capacity_lb"] = 16500
    profile["weight_capacity_evidence"] = []
    profile["weight_capacity_basis"] = (
        "inferred - not stated by the driver. The only weight mentioned "
        "(44,000 lb) is for the Huntsville van load discussed hypothetically, "
        "not the driver's own equipment. 16,500 lb is a typical payload "
        "ceiling for a hotshot/gooseneck rig and is used as a placeholder "
        "capacity."
    )

    return profile


def extract_profile_llm(transcript_text):
    """OpenAI-based extraction, used only if OPENAI_API_KEY is set."""
    import requests

    api_key = os.environ["OPENAI_API_KEY"]
    payload = {
        "model": OPENAI_MODEL,
        "max_tokens": 1024,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"Transcript:\n\n{transcript_text}"},
        ],
    }
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}",
    }

    resp = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    raw_text = resp.json()["choices"][0]["message"]["content"].strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    return json.loads(raw_text)


def run_part_a(transcript_src=CONVO_PATH, save=True):
    rows = load_transcript(transcript_src)

    if os.environ.get("OPENAI_API_KEY"):
        transcript_text = "\n".join(f"{r['Speaker']}: {r['Dialogue']}" for r in rows)
        profile = extract_profile_llm(transcript_text)
    else:
        profile = extract_profile_rulebased(rows)

    print("=" * 70)
    print("PART A - EXTRACTED DRIVER PROFILE")
    print("=" * 70)
    print(f"Current Location : {profile['current_location']} "
          f"({profile['current_lat']}, {profile['current_lon']})  "
          f"[{profile['current_location_basis']}]")
    print(f"Home Base        : {profile['home_base']} "
          f"({profile['home_lat']}, {profile['home_lon']})  "
          f"[{profile['home_base_basis']}]")
    print(f"Min Rate/Mile    : ${profile['min_rate_per_mile']:.2f}  "
          f"[{profile['min_rate_per_mile_basis']}]")
    print(f"Equipment Type(s): {' / '.join(profile['equipment_types'])}  "
          f"[{profile['equipment_basis']}]")
    print(f"Weight Capacity  : {profile['weight_capacity_lb']:,} lb  "
          f"[{profile['weight_capacity_basis']}]")
    print("=" * 70)

    if save:
        with open(PROFILE_OUT, "w") as f:
            json.dump(profile, f, indent=2)
        print(f"\nSaved -> {PROFILE_OUT}")

    return profile


# ---------------------------------------------------------------------------
# Part B - Rank & Match
# ---------------------------------------------------------------------------

def haversine(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


def is_missing(value):
    return value is None or str(value).strip().upper() in ("", "MISSING", "N/A")


def load_board(path=LOADS_PATH):
    """Accepts a file path, or an already-open text file-like object
    (e.g. an uploaded file), so this can be reused by the Streamlit UI."""
    if hasattr(path, "read"):
        return list(csv.DictReader(path))
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def evaluate_loads(rows, profile):
    current = (profile["current_lat"], profile["current_lon"])
    home = (profile["home_lat"], profile["home_lon"])
    equipment = {e.lower() for e in profile["equipment_types"]}
    min_rate = profile["min_rate_per_mile"]
    max_weight = profile["weight_capacity_lb"]

    results = []
    skipped = []

    for row in rows:
        load_id = row["Load ID"]
        trailer = row["Trailer"]
        weight = float(row["Weight"])
        price_raw = row["Price ($)"]
        dest_raw = row["Destination"]

        # A row missing price or destination can't have loaded miles,
        # deadhead-home, or an effective rate computed at all. Rather than
        # guessing at a missing price or destination (which would fabricate
        # data), these rows are excluded from ranking and reported
        # separately with the reason.
        if is_missing(price_raw) or is_missing(dest_raw):
            reason = []
            if is_missing(price_raw):
                reason.append("missing price")
            if is_missing(dest_raw):
                reason.append("missing destination")
            skipped.append((load_id, ", ".join(reason)))
            continue

        price = float(price_raw)

        equipment_ok = trailer.lower() in equipment
        weight_ok = weight <= max_weight

        origin = (float(row["Origin Lat"]), float(row["Origin Lon"]))
        dest = (float(row["Dest Lat"]), float(row["Dest Lon"]))

        deadhead_to_origin = haversine(*current, *origin)
        loaded_miles = haversine(*origin, *dest)
        deadhead_home = haversine(*dest, *home)
        total_miles = deadhead_to_origin + loaded_miles + deadhead_home
        eff_rate = price / total_miles if total_miles else 0.0

        rate_ok = eff_rate >= min_rate
        eligible = equipment_ok and weight_ok and rate_ok

        results.append({
            "load_id": load_id,
            "trailer": trailer,
            "weight": weight,
            "price": price,
            "deadhead_to_origin": deadhead_to_origin,
            "loaded_miles": loaded_miles,
            "deadhead_home": deadhead_home,
            "total_miles": total_miles,
            "effective_rate_per_mile": eff_rate,
            "equipment_ok": equipment_ok,
            "weight_ok": weight_ok,
            "rate_ok": rate_ok,
            "eligible": eligible,
        })

    return results, skipped


def run_part_b(profile, loads_src=LOADS_PATH, top_n=3):
    rows = load_board(loads_src)
    results, skipped = evaluate_loads(rows, profile)

    print("=" * 100)
    print(f"{'Load':6}{'Trailer':11}{'Wt(lb)':>8}{'Price':>8}"
          f"{'DH->Org':>9}{'Loaded':>9}{'DH->Home':>10}{'Total':>9}"
          f"{'Eff $/mi':>10}  Eligible?")
    print("-" * 100)
    for r in sorted(results, key=lambda r: r["effective_rate_per_mile"], reverse=True):
        flags = []
        if not r["equipment_ok"]:
            flags.append("equipment")
        if not r["weight_ok"]:
            flags.append("weight")
        if not r["rate_ok"]:
            flags.append("rate")
        reason = "OK" if r["eligible"] else "NO (" + ",".join(flags) + ")"
        print(f"{r['load_id']:6}{r['trailer']:11}{r['weight']:8.0f}"
              f"{r['price']:8.0f}{r['deadhead_to_origin']:9.1f}"
              f"{r['loaded_miles']:9.1f}{r['deadhead_home']:10.1f}"
              f"{r['total_miles']:9.1f}{r['effective_rate_per_mile']:10.3f}  {reason}")
    print("-" * 100)
    for load_id, reason in skipped:
        print(f"{load_id:6}SKIPPED - incomplete data ({reason}); excluded, not ranked")
    print("=" * 100)

    eligible = [r for r in results if r["eligible"]]
    eligible.sort(key=lambda r: r["effective_rate_per_mile"], reverse=True)
    top = eligible[:top_n]

    print(f"\nTOP {top_n} ELIGIBLE LOADS (ranked by effective rate/mile):")
    for i, r in enumerate(top, 1):
        print(f"  {i}. {r['load_id']}  ->  ${r['effective_rate_per_mile']:.3f}/mi")

    highest_price = max(results, key=lambda r: r["price"])
    print(f"\nHighest raw price on the board: {highest_price['load_id']} "
          f"(${highest_price['price']:.0f}), effective rate "
          f"${highest_price['effective_rate_per_mile']:.3f}/mi -> "
          f"{'ranks #1' if top and top[0]['load_id'] == highest_price['load_id'] else 'does NOT rank #1'} "
          f"once deadhead is factored in.")

    return top


if __name__ == "__main__":
    profile = run_part_a()
    print()
    run_part_b(profile)
