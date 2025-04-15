import streamlit as st
import pandas as pd
import requests
import sqlite3
from datetime import datetime
import time
import pydeck as pdk

# Set up the page configuration
st.set_page_config(page_title="🚦 Mumbai Traffic Analyzer", layout="wide")
st.title("🚦 Live Traffic Analyzer (TomTom API - Mumbai)")

API_KEY = "3Lo3uEOWB9XZAzAa2olq7tutorXJvgpY"

# 📍 Multiple Mumbai Locations
locations = {
    "Goregaon": (19.1640, 72.8499),
    "Vasai West": (19.3867, 72.8296),
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
            "Congestion Level (%)": max(0, congestion),
            "Avg Speed (km/h)": data["currentSpeed"],
            "Free Flow Speed (km/h)": data["freeFlowSpeed"],
            "Latitude": lat,
            "Longitude": lon,
            "Timestamp": datetime.now()
        })

    return pd.DataFrame(traffic_rows)

# Coordinates for the route from Goregaon to Vasai and back
coordinates = [
    {"location": "Goregaon", "lat": 19.1640, "lon": 72.8499},
    {"location": "Vasai West", "lat": 19.3867, "lon": 72.8296},
]

# Placeholder to show real-time updates
placeholder = st.empty()
history = []

for _ in range(20):  # limit for demo
    df = get_traffic_data()
    if df.empty:
        st.warning("No traffic data available.")
        break

    for _, row in df.iterrows():
        cursor.execute('''INSERT INTO traffic (location, congestion_level, avg_speed, free_flow_speed, lat, lon, timestamp)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (row['Location'], row['Congestion Level (%)'], row['Avg Speed (km/h)'],
                        row['Free Flow Speed (km/h)'], row['Latitude'], row['Longitude'], row['Timestamp'].isoformat()))
    conn.commit()

    history.append(df)
    placeholder.dataframe(df, use_container_width=True)

    st.metric(label="🚨 Most Congested", value=df.loc[df['Congestion Level (%)'].idxmax()]['Location'])
    st.metric(label="🚗 Avg Speed", value=f"{df['Avg Speed (km/h)'].mean():.2f} km/h")

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
                get_color='[255, 140 - (Congestion Level (%) * 1.5), 0, 160]',  # Fix here: ensure numeric calculation without '%' symbol
                get_radius=300,
                pickable=True
            ),
            pdk.Layer(
                'PathLayer',
                data=coordinates,
                get_path='coordinates',
                get_width=5,
                get_color=[255, 0, 0, 160],
                width_scale=10,
                pickable=True
            ),
        ],
    ))

    time.sleep(10)

# Display Historical Trends
st.subheader("📊 Historical Trends")
df_hist = pd.read_sql_query("SELECT * FROM traffic", conn, parse_dates=['timestamp'])
st.line_chart(df_hist.groupby(['timestamp'])[['congestion_level']].mean())
