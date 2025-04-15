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

# 📍 Multiple Mumbai Locations
locations = {
    "Goregaon": (19.1640, 72.8499),
    "Vasai West": (19.3867, 72.8296),
    "GE" = (22.59076821366648,88.45522500345601)
}

# 🗃 Initialize SQLite database
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
        response = requests.get(url)
        if response.status_code != 200:
            continue
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

    return pd.DataFrame(traffic_rows)

placeholder = st.empty()
history = []

for _ in range(20):  # limit for demo
    df = get_traffic_data()
    if df.empty:
        st.warning("No traffic data available.")
        break

    # Save to database
    for _, row in df.iterrows():
        cursor.execute('''INSERT INTO traffic (location, congestion_level, avg_speed, free_flow_speed, lat, lon, timestamp)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (row['Location'], row['Congestion_Level'], row['Avg_Speed'],
                        row['Free_Flow_Speed'], row['Latitude'], row['Longitude'], row['Timestamp'].isoformat()))
    conn.commit()

    history.append(df)
    placeholder.dataframe(df, use_container_width=True)

    st.metric(label="🚨 Most Congested", value=df.loc[df['Congestion_Level'].idxmax()]['Location'])
    st.metric(label="🚗 Avg Speed", value=f"{df['Avg_Speed'].mean():.2f} km/h")

    # 🗺️ Traffic Map
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
                'ScatterplotLayer',
                data=df,
                get_position='[Longitude, Latitude]',
                get_color='[255, 140 - Congestion_Level, 0, 160]',
                get_radius=300,
                pickable=True
            ),
        ],
    ))

    time.sleep(10)

# 📊 Historical Trends
st.subheader("📊 Historical Trends")
df_hist = pd.read_sql_query("SELECT * FROM traffic", conn, parse_dates=['timestamp'])
st.line_chart(df_hist.groupby(['timestamp'])[['congestion_level']].mean())
