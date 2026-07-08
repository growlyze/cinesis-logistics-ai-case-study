"""
Part A - Extraction Layer (LLM-based)
======================================
Reads the raw driver/dispatcher call transcript (data/sample_conversation.csv)
and uses the OpenAI API to extract a structured driver profile.

Why LLM-based:
The transcript never states the fields as clean data - they're scattered
through normal speech, sometimes stated directly, sometimes only implied
("I run a hotshot gooseneck trailer", confirming a question instead of
volunteering a fact, etc). An LLM reads for intent the same way a human
dispatcher would, and - critically - we ask it to return, for every field,
whether the value was STATED outright or INFERRED, plus the evidence line
it used. That keeps the extraction auditable even though it's model-driven.

Requirements to run:
    pip install requests
    export OPENAI_API_KEY=sk-...   (your own key)
    python3 part_a_extract.py

If OPENAI_API_KEY isn't set, the script exits with a clear message
rather than silently failing or fabricating a profile.

(A deterministic, non-LLM version of this same extraction is included as
part_a_extract_rulebased.py for comparison / offline use.)
"""

import csv
import json
import os
import sys
import requests

CONVO_PATH = "data/sample_conversation.csv"
PROFILE_OUT = "data/profile.json"
API_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o"  # swap for whichever model string your account has access to

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


def load_transcript(path=CONVO_PATH):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return "\n".join(f"{r['Speaker']}: {r['Dialogue']}" for r in rows)


def call_openai(transcript_text):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit(
            "ERROR: OPENAI_API_KEY is not set.\n"
            "Set your own key first, e.g.:\n"
            "    export OPENAI_API_KEY=sk-...\n"
            "then re-run this script."
        )

    payload = {
        "model": MODEL,
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

    resp = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    raw_text = data["choices"][0]["message"]["content"].strip()

    # Model is instructed to return raw JSON only, but strip fences defensively.
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    return json.loads(raw_text)


def print_profile(profile):
    print("=" * 70)
    print("PART A - EXTRACTED DRIVER PROFILE (via OpenAI API)")
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
    transcript_text = load_transcript()
    profile = call_openai(transcript_text)
    print_profile(profile)
    with open(PROFILE_OUT, "w") as f:
        json.dump(profile, f, indent=2)
    print(f"\nSaved -> {PROFILE_OUT}")
