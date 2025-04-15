import streamlit as st
import pandas as pd
import requests
import sqlite3
from datetime import datetime
import time
import numpy as np
import pydeck as pdk
import plotly.express as px

st.set_page_config(page_title="🚦 Mumbai Traffic Analyzer", layout="wide")
st.title("🚦 Live Traffic Analyzer (TomTom API - Mumbai)")

API_KEY = "3Lo3uEOWB9XZAzAa2olq7tutorXJvgpY"

# Central coordinates for Mumbai (Latitude, Longitude)
central_lat = 19.0760
central_lon = 72.8777

# Define the radius around Mumbai (in degrees)
lat_range = 0.5  # +/- 0.5 degrees latitude (approximately 50 km)
lon_range = 0.5  # +/- 0.5 degrees longitude (approximately 50 km)

# Number of coordinates along each axis (to get approximately 512 points)
n_points_lat = 32  # Number of points along latitude
n_points_lon = 16  # Number of points along longitude

# Generate grid of latitudes and longitudes
latitudes = np.linspace(central_lat - lat_range, central_lat + lat_range, n_points_lat)
longitudes = np.linspace(central_lon - lon_range, central_lon + lon_range, n_points_lon)

# Create the grid of coordinates
locations = [(lat, lon) for lat in latitudes for lon in longitudes]

# 🗃 SQLite setup
conn = sqlite3.connect("/tmp/traffic_data.db", check_same_thread=False, timeout=10)
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

# Safe insert with retry mechanism
def safe_insert_to_db(cursor, data):
    retries = 5  # Max number of retries
    for attempt in range(retries):
        try:
            cursor.execute('''INSERT INTO traffic (location, congestion_level, avg_speed, free_flow_speed, lat, lon, timestamp)
                              VALUES (?, ?, ?, ?, ?, ?, ?)''', data)
            return True  # Insert successful
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e).lower():
                if attempt < retries - 1:
                    time.sleep(1)  # Wait before retrying
                else:
                    return False  # Max retries reached
            else:
                raise  # Reraise other errors
    return False

@st.cache_data(ttl=60)
def get_traffic_data():
    traffic_rows = []
    for lat, lon in locations:
        url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={lat}%2C{lon}&key={API_KEY}"
        response = requests.get(url)
        if response.status_code != 200:
            continue
        data = response.json().get("flowSegmentData", {})
        if not data:
            continue

        congestion = int((1 - data["currentSpeed"] / data["freeFlowSpeed"]) * 100)

        traffic_rows.append({
            "Location": f"({lat}, {lon})",
            "Congestion_Level": max(0, congestion),
            "Avg_Speed": data["currentSpeed"],
            "Free_Flow_Speed": data["freeFlowSpeed"],
            "Latitude": lat,
            "Longitude": lon,
            "Timestamp": datetime.now()
        })

    return pd.DataFrame(traffic_rows)

# Define important locations (Mumbai landmarks + additional areas like Vasai, Andheri, Dadar, Mira Road)
important_locations = {
    "Gateway of India": (18.9219, 72.8347),
    "Marine Drive": (18.9388, 72.8231),
    "Bandra-Worli Sea Link": (19.0300, 72.8347),
    "Chhatrapati Shivaji Maharaj Terminus": (18.9400, 72.8350),
    "Elephanta Caves": (18.9276, 72.9398),
    "Vasai": (19.3753, 72.8333),
    "Andheri": (19.0993, 72.8347),
    "Dadar": (19.0187, 72.8498),
    "Mira Road": (19.2974, 72.8508),
    "Bhayandar": (19.2853, 72.8555),
    "Kandivali": (19.2144, 72.8492),
    "Mulund": (19.1890, 72.9262),
    "Borivali": (19.2875, 72.8582),
    "Goregaon": (19.1640, 72.8499),
    "Versova": (19.0980, 72.8282),
    "Malad": (19.1802, 72.8349),
    "Worli": (18.9940, 72.8268),
    "Juhu": (19.0976, 72.8263)
}

# 🔄 UI placeholders
placeholder_table = st.empty()
placeholder_map = st.empty()
placeholder_metrics = st.empty()
placeholder_chart = st.empty()

# ⏳ Live update loop
history = []

for _ in range(20):  # ⏱ Loop for a fixed number of cycles
    df = get_traffic_data()
    if df.empty:
        st.warning("No traffic data available.")
        break

    # Save to database with retry mechanism
    for _, row in df.iterrows():
        data = (row['Location'], row['Congestion_Level'], row['Avg_Speed'],
                row['Free_Flow_Speed'], row['Latitude'], row['Longitude'], row['Timestamp'].isoformat())
        if not safe_insert_to_db(cursor, data):
            st.warning("Failed to insert data after multiple retries.")
            break
    conn.commit()  # Commit all at once

    # Display table
    placeholder_table.dataframe(df, use_container_width=True)

    # Metrics
    with placeholder_metrics.container():
        st.metric(label="🚨 Most Congested", value=df.loc[df['Congestion_Level'].idxmax()]['Location'])
        st.metric(label="🚗 Avg Speed", value=f"{df['Avg_Speed'].mean():.2f} km/h")

    # Map (updates live)
    with placeholder_map.container():
        st.subheader("🗺️ Traffic Map")
        layers = [
            pdk.Layer(
                'ScatterplotLayer',
                data=df,
                get_position='[Longitude, Latitude]',
                get_color='[255, 140 - Congestion_Level, 0, 160]',
                get_radius=300,
                pickable=True
            )
        ]

        # Add important location markers
        for name, (lat, lon) in important_locations.items():
            layers.append(
                pdk.Layer(
                    'ScatterplotLayer',
                    data=[{"Latitude": lat, "Longitude": lon, "Location": name}],
                    get_position='[Longitude, Latitude]',
                    get_color='[255, 0, 0, 255]',  # Red color for important locations
                    get_radius=500,
                    pickable=True
                )
            )

        st.pydeck_chart(pdk.Deck(
            map_style='mapbox://styles/mapbox/streets-v12',
            initial_view_state=pdk.ViewState(
                latitude=df['Latitude'].mean(),
                longitude=df['Longitude'].mean(),
                zoom=10,
                pitch=40,
            ),
            layers=layers,
        ))

    # Append to history and show plot
    history.append(df)
    combined_df = pd.concat(history).reset_index(drop=True)
    combined_df['Timestamp'] = pd.to_datetime(combined_df['Timestamp'])

    # Melt for Plotly
    plot_df = combined_df.melt(id_vars='Timestamp', value_vars=['Avg_Speed', 'Congestion_Level'],
                               var_name='Metric', value_name='Value')

    fig = px.line(
        plot_df,
        x="Timestamp",
        y="Value",
        color="Metric",
        title="📊 Real-Time Traffic Trends",
        markers=True,
        labels={"Value": "Metric Value", "Timestamp": "Time"},
        template="plotly_white"
    )
    fig.update_traces(mode='lines+markers', hovertemplate='%{x}<br>%{y} %{fullData.name}<extra></extra>')

    placeholder_chart.plotly_chart(fig, use_container_width=True)

    time.sleep(10)
