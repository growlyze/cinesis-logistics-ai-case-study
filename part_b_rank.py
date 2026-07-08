"""
Part B - Rank & Match
=====================
Loads the driver profile produced by part_a_extract.py, filters the load
board (data/loads.csv) to loads the driver is actually eligible for, then
ranks the eligible loads by effective rate/mile:

    effective_rate_per_mile = price / (deadhead_to_origin + loaded_miles + deadhead_home)

    deadhead_to_origin = driver's CURRENT location -> load origin
    loaded_miles       = load origin -> load destination
    deadhead_home      = load destination -> driver's HOME BASE

All three legs use straight-line haversine distance from the given lat/lon.

Eligibility filter (applied BEFORE ranking):
    1. Trailer type must be one the driver runs (Hotshot / Gooseneck).
    2. Load weight must not exceed the driver's weight capacity.
    3. Effective rate/mile must be >= the driver's stated minimum ($2.00/mi).
    4. The row must have complete data (price and destination present) -
       rows missing either are reported separately and excluded rather
       than guessed at, since fabricating a price or destination would
       silently corrupt the ranking.
"""

import csv
import json
import math

LOADS_PATH = "data/loads.csv"
PROFILE_PATH = "data/profile.json"
EARTH_RADIUS_MI = 3958.8


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
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_profile(path=PROFILE_PATH):
    with open(path) as f:
        return json.load(f)


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

        # --- Incomplete-data guard --------------------------------------
        # A row missing price or destination cannot have loaded miles,
        # deadhead-home, or an effective rate computed for it at all. We
        # don't guess at a missing price or destination (that would just
        # be fabricating data), so these rows are excluded from ranking
        # and reported separately with the reason.
        if is_missing(price_raw) or is_missing(dest_raw):
            reason = []
            if is_missing(price_raw):
                reason.append("missing price")
            if is_missing(dest_raw):
                reason.append("missing destination")
            skipped.append((load_id, ", ".join(reason)))
            continue

        price = float(price_raw)

        # --- Eligibility filter (BEFORE ranking) ------------------------
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


def print_report(results, skipped, top_n=3):
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
    rows = load_board()
    profile = load_profile()
    results, skipped = evaluate_loads(rows, profile)
    print_report(results, skipped)
