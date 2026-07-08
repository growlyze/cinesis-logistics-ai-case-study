"""
Cinesis Good Fit Test - Streamlit UI
=====================================
Simple UI wrapper around solution.py: upload the transcript CSV and the
loads CSV, click Run, and it extracts the driver profile (Part A) then
ranks eligible loads (Part B).

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import io
import json

import pandas as pd
import streamlit as st

from solution import (
    evaluate_loads,
    extract_profile_llm,
    extract_profile_rulebased,
    load_board,
    load_transcript,
)

st.set_page_config(page_title="Cinesis Load Matcher", page_icon="🚚", layout="wide")

st.title("🚚 Driver Profile Extraction + Load Matching")
st.caption(
    "Upload a driver/dispatcher call transcript and the load board. "
    "This runs Part A (extract the driver profile) then Part B "
    "(filter + rank eligible loads by effective rate/mile)."
)

with st.sidebar:
    st.header("Inputs")
    transcript_file = st.file_uploader(
        "Driver call transcript (CSV)", type=["csv"],
        help="Expected columns: Speaker, Dialogue",
    )
    loads_file = st.file_uploader(
        "Load board (CSV)", type=["csv"],
        help="Expected columns: Load ID, Trailer, Weight, Price ($), "
             "Destination, Origin Lat, Origin Lon, Dest Lat, Dest Lon",
    )
    top_n = st.number_input("Top N loads to show", min_value=1, max_value=20, value=3)
    use_llm = st.checkbox(
        "Use OpenAI for extraction (requires OPENAI_API_KEY env var)",
        value=False,
    )
    run = st.button("Run", type="primary", disabled=not (transcript_file and loads_file))

if not (transcript_file and loads_file):
    st.info("Upload both CSV files in the sidebar, then click Run.")
    st.stop()

if not run:
    st.stop()


def to_text_stream(uploaded_file):
    return io.StringIO(uploaded_file.getvalue().decode("utf-8"))


# --- Part A ------------------------------------------------------------
st.header("Part A - Extracted Driver Profile")

rows = load_transcript(to_text_stream(transcript_file))

if use_llm:
    import os
    if not os.environ.get("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY is not set in the environment. Uncheck "
                  "'Use OpenAI' or set the key before running.")
        st.stop()
    transcript_text = "\n".join(f"{r['Speaker']}: {r['Dialogue']}" for r in rows)
    with st.spinner("Calling OpenAI..."):
        profile = extract_profile_llm(transcript_text)
else:
    profile = extract_profile_rulebased(rows)

col1, col2, col3 = st.columns(3)
col1.metric("Current Location", profile["current_location"])
col2.metric("Home Base", profile["home_base"])
col3.metric("Min Rate/Mile", f"${profile['min_rate_per_mile']:.2f}")

col4, col5 = st.columns(2)
col4.metric("Equipment", " / ".join(profile["equipment_types"]))
col5.metric("Weight Capacity", f"{profile['weight_capacity_lb']:,} lb")

with st.expander("Basis & evidence for every field"):
    for field in ["current_location", "home_base", "min_rate_per_mile",
                  "equipment", "weight_capacity"]:
        basis = profile.get(f"{field}_basis", "-")
        evidence = profile.get(f"{field}_evidence", "-")
        st.markdown(f"**{field.replace('_', ' ').title()}** — *{basis}*")
        st.write(evidence)

st.download_button(
    "Download profile.json",
    data=json.dumps(profile, indent=2),
    file_name="profile.json",
    mime="application/json",
)

# --- Part B --------------------------------------------------------------
st.header("Part B - Eligible Loads Ranked by Effective Rate/Mile")

load_rows = load_board(to_text_stream(loads_file))
results, skipped = evaluate_loads(load_rows, profile)

results_df = pd.DataFrame(results)
if not results_df.empty:
    results_df = results_df.sort_values("effective_rate_per_mile", ascending=False)
    results_df["reason"] = results_df.apply(
        lambda r: "OK" if r["eligible"] else "NO (" + ",".join(
            f for f, ok in [("equipment", r["equipment_ok"]),
                             ("weight", r["weight_ok"]),
                             ("rate", r["rate_ok"])] if not ok
        ) + ")",
        axis=1,
    )
    display_df = results_df[[
        "load_id", "trailer", "weight", "price", "deadhead_to_origin",
        "loaded_miles", "deadhead_home", "total_miles",
        "effective_rate_per_mile", "reason",
    ]].round(3)
    st.dataframe(display_df, use_container_width=True, hide_index=True)

if skipped:
    st.warning(
        "Skipped (incomplete data, excluded from ranking): "
        + "; ".join(f"{load_id} ({reason})" for load_id, reason in skipped)
    )

eligible = [r for r in results if r["eligible"]]
eligible.sort(key=lambda r: r["effective_rate_per_mile"], reverse=True)
top = eligible[:top_n]

st.subheader(f"Top {top_n} Eligible Loads")
if top:
    top_df = pd.DataFrame(top)[["load_id", "effective_rate_per_mile"]].round(3)
    top_df.columns = ["Load ID", "Effective $/mi"]
    st.table(top_df)
else:
    st.warning("No eligible loads found.")

if results:
    highest_price = max(results, key=lambda r: r["price"])
    ranks_first = bool(top) and top[0]["load_id"] == highest_price["load_id"]
    st.caption(
        f"Highest raw price on the board: **{highest_price['load_id']}** "
        f"(${highest_price['price']:.0f}), effective rate "
        f"${highest_price['effective_rate_per_mile']:.3f}/mi -> "
        f"{'ranks #1' if ranks_first else 'does NOT rank #1'} once deadhead "
        f"is factored in."
    )
