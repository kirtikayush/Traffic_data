import streamlit as st
import pandas as pd
import requests
import sqlite3
from datetime import datetime
import time
import pydeck as pdk

st.set_page_config(page_title="🚦 Mumbai Traffic Analyzer", layout="wide")
st.title("🚦 Live Traffic Analyzer (TomTom API - Mumbai)")

API_KEY = "3Lo3uEOWB9XZAzAa2olq7tutorXJvgpY"

# 📍 Locations
locations = {
    "Goregaon": (19.1640, 72.8499),
    "Vasai West": (19.3867, 72.8296),
    "GE Kolkata": (22.5908, 88.4552),
}

# 🗃 Initialize SQLite DB
conn = sqlite3.connect("traffic_data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS traffic (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location TEXT,
        congestion_level INTEGER,
        avg_speed REAL,
        free_flow_speed REAL,
        lat REAL,
        lon REAL,
        timestamp TEXT
    )
''')
conn.commit()

@st.cache_data(ttl=60)
def get_traffic_data():
    traffic_rows = []

    for name, (lat, lon) in locations.items():
        url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={lat}%2C{lon}&key={API_KEY}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json().get("flowSegmentData", {})
            if not data:
                continue

            congestion = int((1 - data["currentSpeed"] / data["freeFlowSpeed"]) * 100)

            traffic_rows.append({
                "Location": name,
                "Congestion_Level": max(0, congestion),
                "Avg_Speed": data["currentSpeed"],
                "Free_Flow_Speed": data["freeFlowSpeed"],
                "Latitude": lat,
                "Longitude": lon,
                "Timestamp": datetime.now()
            })
        except Exception as e:
            st.error(f"Error fetching {name}: {e}")

    return pd.DataFrame(traffic_rows)

# 🎯 Placeholders
placeholder_table = st.empty()
placeholder_map = st.empty()
placeholder_metrics = st.empty()

for _ in range(20):  # Limit for demo
    df = get_traffic_data()
    if df.empty:
        st.warning("No traffic data available.")
        break

    # Save to DB
    for _, row in df.iterrows():
        cursor.execute('''INSERT INTO traffic (location, congestion_level, avg_speed, free_flow_speed, lat, lon, timestamp)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (row['Location'], row['Congestion_Level'], row['Avg_Speed'],
                        row['Free_Flow_Speed'], row['Latitude'], row['Longitude'], row['Timestamp'].isoformat()))
    conn.commit()

    # 📊 Table
    placeholder_table.dataframe(df, use_container_width=True)

    # ⏱️ Metrics
    with placeholder_metrics.container():
        st.metric(label="🚨 Most Congested", value=df.loc[df['Congestion_Level'].idxmax()]['Location'])
        st.metric(label="🚗 Avg Speed", value=f"{df['Avg_Speed'].mean():.2f} km/h")

    # 🗺️ Live Updating Map
    with placeholder_map.container():
        st.subheader("🗺️ Traffic Map")
        st.pydeck_chart(pdk.Deck(
            map_style='mapbox://styles/mapbox/streets-v12',
            initial_view_state=pdk.ViewState(
                latitude=df['Latitude'].mean(),
                longitude=df['Longitude'].mean(),
                zoom=10,
                pitch=40,
            ),
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    data=df,
                    get_position="[Longitude, Latitude]",
                    get_color="[255, 140 - Congestion_Level, 0, 160]",
                    get_radius=400,
                    pickable=True,
                    tooltip={"text": "{Location}\nCongestion: {Congestion_Level}%"}
                )
            ],
        ))

    time.sleep(10)

# 📈 Historical Trends
st.subheader("📊 Historical Trends")
df_hist = pd.read_sql_query("SELECT * FROM traffic", conn, parse_dates=['timestamp'])
if not df_hist.empty:
    df_trend = df_hist.groupby(pd.to_datetime(df_hist['timestamp']).dt.round("1min"))[['congestion_level']].mean()
    st.line_chart(df_trend)
else:
    st.info("No historical data available yet.")
