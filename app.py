import streamlit as st
import pandas as pd
import requests
import sqlite3
from datetime import datetime
import time
import pydeck as pdk
import urllib.parse

# Set up the page title and layout
st.set_page_config(page_title="🚦 Mumbai Traffic Analyzer", layout="wide")
st.title("🚦 Live Traffic Analyzer (TomTom API - Mumbai)")

# TomTom API key
API_KEY = "3Lo3uEOWB9XZAzAa2olq7tutorXJvgpY"
# OpenWeatherMap API key
WEATHER_API_KEY = "c5a0effad9d37c130e42a58a47c421be6f54459e"

# Predefined locations
locations = {
    "Goregaon": (19.1640, 72.8499),
    "Vasai West": (19.3867, 72.8296),
    "GE": (22.59076821366648, 88.45522500345601)
}

# SQLite database initialization
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
        temperature REAL,
        weather_description TEXT,
        timestamp TEXT
    )
''')
conn.commit()

# Function to fetch traffic data and weather data
@st.cache_data(ttl=60)
def get_traffic_data(selected_locations):
    traffic_rows = []

    for name, (lat, lon) in locations.items():
        if name not in selected_locations:
            continue
        
        # Fetch traffic data
        url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={lat}%2C{lon}&key={API_KEY}"
        response = requests.get(url)
        if response.status_code != 200:
            continue
        data = response.json().get("flowSegmentData", {})
        if not data:
            continue

        congestion = int((1 - data["currentSpeed"] / data["freeFlowSpeed"]) * 100)

        # Fetch weather data
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
        weather_data = requests.get(weather_url).json()
        weather_description = weather_data['weather'][0]['description']
        temperature = weather_data['main']['temp']

        # Append traffic and weather data
        traffic_rows.append({
            "Location": name,
            "Congestion_Level": max(0, congestion),
            "Avg_Speed": data["currentSpeed"],
            "Free_Flow_Speed": data["freeFlowSpeed"],
            "Latitude": lat,
            "Longitude": lon,
            "Temperature": temperature,
            "Weather_Description": weather_description,
            "Timestamp": datetime.now()
        })

    return pd.DataFrame(traffic_rows)

# User selects locations to monitor
selected_locations = st.multiselect(
    "Select locations to monitor",
    options=list(locations.keys()),
    default=list(locations.keys())
)

# Placeholder for live data table, metrics, and map
placeholder = st.empty()
history = []

# Main loop for data refresh every 10 seconds
for _ in range(20):  # limit for demo purposes
    df = get_traffic_data(selected_locations)
    if df.empty:
        st.warning("No traffic data available.")
        break

    # Save data to the database
    for _, row in df.iterrows():
        cursor.execute('''INSERT INTO traffic (location, congestion_level, avg_speed, free_flow_speed, lat, lon, temperature, weather_description, timestamp)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (row['Location'], row['Congestion_Level'], row['Avg_Speed'],
                        row['Free_Flow_Speed'], row['Latitude'], row['Longitude'],
                        row['Temperature'], row['Weather_Description'], row['Timestamp'].isoformat()))
    conn.commit()

    history.append(df)
    placeholder.dataframe(df, use_container_width=True)

    # Display metrics
    st.metric(label="🚨 Most Congested", value=df.loc[df['Congestion_Level'].idxmax()]['Location'])
    st.metric(label="🚗 Avg Speed", value=f"{df['Avg_Speed'].mean():.2f} km/h")

    # Interactive map with tooltips
    st.subheader("🗺️ Traffic Map")
    tooltip = {
        "html": "<b>{Location}</b><br/>"
                "Congestion: {Congestion_Level}%<br/>"
                "Speed: {Avg_Speed} km/h<br/>"
                "Temp: {Temperature}°C<br/>"
                "Weather: {Weather_Description}",
        "style": {
            "backgroundColor": "steelblue",
            "color": "white"
        }
    }

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
                get_position='[Longitude, Latitude]',
                get_radius=300,
                get_fill_color='[255, 140 - Congestion_Level, 0, 160]',
                pickable=True,
                tooltip=tooltip,
            ),
        ],
    ))

    time.sleep(10)

# 📊 Historical Trends
st.subheader("📊 Historical Trends")
df_hist = pd.read_sql_query("SELECT * FROM traffic", conn, parse_dates=['timestamp'])
st.line_chart(df_hist.groupby(['timestamp'])[['congestion_level']].mean())
