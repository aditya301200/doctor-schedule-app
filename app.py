import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import time

# Page setup for mobile screens
st.set_page_config(
    page_title="Doctor Schedule Finder",
    page_icon="🩺",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS to make cards and layout look clean on mobile phones
st.markdown("""
<style>
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
}
.doc-card {
    background-color: #f8f9fa;
    border-left: 5px solid #0d6efd;
    padding: 12px 15px;
    border-radius: 8px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    color: #1f2937;
}
.doc-name {
    font-weight: 700;
    font-size: 1.05rem;
    color: #0f172a;
    margin-bottom: 4px;
}
.doc-meta {
    font-size: 0.9rem;
    margin-bottom: 2px;
}
.doc-time {
    display: inline-block;
    background-color: #e0f2fe;
    color: #0369a1;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.85rem;
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)

st.title("🩺 Doctor Schedule Finder")

# Automatically find schedule.db in the same folder as app.py
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "schedule.db"

if not DB_PATH.exists():
    st.error(f"Database file not found at: {DB_PATH}. Please run clean_data.py first.")
    st.stop()

def get_connection():
    return sqlite3.connect(DB_PATH)

def min_to_12hr(m):
    h = (m // 60) % 24
    mins = m % 60
    period = "AM" if h < 12 else "PM"
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    return f"{h12:02d}:{mins:02d} {period}"

conn = get_connection()

# Fetch distinct Areas from DB
areas_df = pd.read_sql("SELECT DISTINCT AREA FROM schedules WHERE AREA != '' ORDER BY AREA", conn)
area_options = ["All Areas"] + areas_df["AREA"].tolist()
default_area_idx = area_options.index("LAKE TOWN") if "LAKE TOWN" in area_options else 0

days_options = ["All Days", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

# --- Mobile Search Filters ---
with st.container(border=True):
    col_a, col_b = st.columns(2)
    with col_a:
        selected_area = st.selectbox("📍 Area", area_options, index=default_area_idx)
    with col_b:
        selected_day = st.selectbox("📅 Day of Week", days_options, index=1)  # Default MONDAY

    # Time range filter
    use_time_filter = st.checkbox("⏰ Filter by Time Range", value=True)

    if use_time_filter:
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            start_time = st.time_input("From Time", value=time(11, 0), step=1800)  # Default 11:00 AM
        with t_col2:
            end_time = st.time_input("To Time", value=time(18, 0), step=1800)      # Default 06:00 PM

        search_start = start_time.hour * 60 + start_time.minute
        search_end = end_time.hour * 60 + end_time.minute
        st.caption(f"Showing schedules active between **{min_to_12hr(search_start)}** and **{min_to_12hr(search_end)}**")

    # Optional text search for Name or Location
    search_text = st.text_input("🔍 Search Doctor Name or Clinic Location (Optional)", placeholder="e.g. Dr. Sunil or Shree Krishna...")

# --- Build SQL Query ---
query = """
    SELECT 
        NAME, 
        LOCATION, 
        AREA, 
        DAY, 
        CLEANED_TIMING AS TIMINGS, 
        RAW_TIMING,
        "PHONE NO" AS PHONE
    FROM schedules
    WHERE 1=1
"""
params = []

if selected_area != "All Areas":
    query += " AND AREA = ?"
    params.append(selected_area)

if selected_day != "All Days":
    query += " AND DAY = ?"
    params.append(selected_day)

if use_time_filter:
    if search_start <= search_end:
        query += " AND (START_MIN <= ? AND END_MIN >= ?)"
        params.extend([search_end, search_start])
    else:
        query += " AND (END_MIN >= ? OR START_MIN <= ?)"
        params.extend([search_start, search_end])

if search_text.strip():
    query += " AND (NAME LIKE ? OR LOCATION LIKE ?)"
    wildcard = f"%{search_text.strip().upper()}%"
    params.extend([wildcard, wildcard])

query += " ORDER BY START_MIN ASC, NAME ASC"

results = pd.read_sql(query, conn, params=params)
conn.close()

# --- Display Results ---
st.subheader(f"Results ({len(results)} found)")

view_mode = st.radio(
    "Display Format:",
    ["📱 Mobile Cards", "📊 Table View"],
    horizontal=True,
    label_visibility="collapsed"
)

if results.empty:
    st.info("No doctors found matching your selected filters.")
else:
    if view_mode == "📊 Table View":
        display_df = results[["NAME", "LOCATION", "AREA", "DAY", "TIMINGS", "PHONE"]]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        for _, row in results.iterrows():
            phone_html = f'<div class="doc-meta">📞 <a href="tel:{row["PHONE"]}">{row["PHONE"]}</a></div>' if row["PHONE"] else ""
            card_html = (
                f'<div class="doc-card">'
                f'<div class="doc-name">{row["NAME"]}</div>'
                f'<div class="doc-meta">🏥 <b>Location:</b> {row["LOCATION"]}</div>'
                f'<div class="doc-meta">📍 <b>Area:</b> {row["AREA"]} &nbsp;|&nbsp; 📅 <b>{row["DAY"]}</b></div>'
                f'{phone_html}'
                f'<div class="doc-time">⏰ {row["TIMINGS"]} <span style="font-weight:normal; color:#555;"></span></div>'
                f'</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)