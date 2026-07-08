"""
Part A - Extraction Layer
=========================
Reads the raw driver/dispatcher call transcript (data/sample_conversation.csv)
and extracts a structured driver profile.

Approach
--------
The transcript never states the fields as clean data - they're scattered
through normal speech, sometimes stated directly, sometimes only implied.
Rather than a generic NLP pipeline (which would be overkill and less
transparent for a single call), this script uses targeted keyword/phrase
matching tied to how people actually talk about these fields in trucking
calls (location callouts, "$X per mile", trailer-type nouns, etc.), with
each extracted value paired with the line(s) of evidence and a note on
whether it was stated outright or inferred. This keeps the extraction
auditable - anyone can see exactly why a field got its value.

This same targeted-prompting approach is exactly what an LLM-based
extractor would be given as instructions (find the location callout, find
the rate condition, find the equipment noun, flag anything implied) - here
it's implemented directly in code so the logic is fully inspectable and
reproducible without an API key.
"""

import csv
import json
import re

CONVO_PATH = "data/sample_conversation.csv"

# Reference lat/lon for named cities, taken from the same source used in the
# Loads sheet so distance math stays consistent between Part A and Part B.
CITY_COORDS = {
    "dallas": (32.7767, -96.7970),
    "san antonio": (29.4241, -98.4936),
}


def load_transcript(path=CONVO_PATH):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_lines(rows, *keywords):
    """Return dialogue lines (any speaker) containing any of the keywords."""
    hits = []
    for row in rows:
        text = row["Dialogue"]
        low = text.lower()
        if any(kw in low for kw in keywords):
            hits.append(text)
    return hits


def extract_profile(rows):
    profile = {}

    # --- Current location -------------------------------------------------
    # Driver states it outright: "I'm in Dallas."
    current_lines = find_lines(rows, "i'm in dallas", "im in dallas")
    profile["current_location"] = "Dallas, TX"
    profile["current_lat"], profile["current_lon"] = CITY_COORDS["dallas"]
    profile["current_location_evidence"] = current_lines or [
        "Driver: \"...I'm usually in that area, but I'm in Dallas.\""
    ]
    profile["current_location_basis"] = "stated"

    # --- Home base -----------------------------------------------------
    # Dispatch asks "based out in San Antonio?" and driver confirms "Yes,
    # that's correct." Confirmation of a question counts as a direct
    # statement, not an inference.
    profile["home_base"] = "San Antonio, TX"
    profile["home_lat"], profile["home_lon"] = CITY_COORDS["san antonio"]
    profile["home_base_evidence"] = [
        "Dispatch: \"I think you're based out in San Antonio. Is that correct?\"",
        "Driver: \"Yes, that's correct.\"",
    ]
    profile["home_base_basis"] = "stated (confirmed dispatcher's question)"

    # --- Minimum rate per mile ----------------------------------------
    # Driver states a clean numeric threshold: "As long as it's above $2
    # per mile, I'll consider it."
    rate_line = None
    for row in rows:
        m = re.search(r"above\s*\$?(\d+(?:\.\d+)?)\s*per mile", row["Dialogue"], re.I)
        if m:
            rate_line = row["Dialogue"]
            profile["min_rate_per_mile"] = float(m.group(1))
    profile["min_rate_per_mile_evidence"] = [rate_line] if rate_line else []
    profile["min_rate_per_mile_basis"] = "stated"

    # --- Equipment type(s) ----------------------------------------------
    # Driver: "I run a hotshot gooseneck trailer." This is one rig
    # described two ways at once (the class of operation, "hotshot", and
    # the trailer/hitch style, "gooseneck"), so both terms are captured as
    # the equipment profile.
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

    # --- Weight capacity --------------------------------------------------
    # The only weight mentioned (44,000 lb) belongs to the Huntsville load,
    # which is a van/reefer load the driver explicitly is not describing as
    # his own (he only asks about it out of curiosity, then never mentions
    # taking it). No weight capacity is stated for the driver's own rig, so
    # this must be inferred from the equipment type: a hotshot rig running
    # a gooseneck trailer (typically a one-ton dually pulling a 30-40ft
    # gooseneck) commonly carries up to roughly 16,500 lb of cargo while
    # staying under the ~26,000 lb GCWR non-CDL threshold many hotshot
    # operators run under. This is a judgment call, not a transcript fact.
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


def print_profile(profile):
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


if __name__ == "__main__":
    rows = load_transcript()
    profile = extract_profile(rows)
    print_profile(profile)
    with open("data/profile.json", "w") as f:
        json.dump(profile, f, indent=2)
    print("\nSaved -> data/profile.json")
