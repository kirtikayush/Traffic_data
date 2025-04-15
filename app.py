import streamlit as st
import pandas as pd
import requests
import sqlite3
from datetime import datetime
import time
import pydeck as pdk
import plotly.express as px

st.set_page_config(page_title="🚦 Mumbai Traffic Analyzer", layout="wide")
st.title("🚦 Live Traffic Analyzer (TomTom API - Mumbai)")

API_KEY = "3Lo3uEOWB9XZAzAa2olq7tutorXJvgpY"

# 100 Coordinates for famous locations around Mumbai and Vasai-Virar
locations = [
    (19.0760, 72.8777), # Mumbai Central
    (19.0993, 72.8347), # Andheri
    (19.0187, 72.8498), # Dadar
    (19.3753, 72.8333), # Vasai
    (19.2974, 72.8508), # Mira Road
    (19.2875, 72.8582), # Borivali
    (19.0645, 72.8420), # Malad
    (18.9219, 72.8347), # Gateway of India
    (18.9388, 72.8231), # Marine Drive
    (18.9940, 72.8268), # Worli
    (19.1625, 72.8500), # Goregaon
    (19.1336, 72.8347), # Juhu
    (19.2152, 72.8574), # Kandivali
    (19.1510, 72.8886), # Lower Parel
    (19.1828, 72.8679), # Kurla
    (19.1264, 72.8313), # Vile Parle
    (19.1358, 72.8871), # Parel
    (19.0976, 72.8282), # Versova
    (19.1791, 72.8518), # Malad West
    (19.1311, 72.9130), # Mulund
    (19.1539, 72.9075), # Bhandup
    (19.0409, 72.8504), # Bandra
    (19.2145, 72.8560), # Kandivali East
    (19.2207, 72.8538), # Borivali East
    (19.0967, 72.8311), # Andheri West
    (19.0395, 72.8270), # Khar
    (19.1900, 72.9286), # Ghatkopar
    (19.0145, 72.8465), # Sion
    (19.0244, 72.8609), # Vikhroli
    (19.1541, 72.8340), # Santacruz
    (19.0846, 72.8795), # Versova Beach
    (19.1763, 72.8489), # Andheri East
    (19.1325, 72.8598), # Kandivali West
    (19.1505, 72.8442), # Ville Parle East
    (19.2010, 72.8956), # Dahisar
    (19.1079, 72.8581), # Borivali West
    (19.0682, 72.8644), # Malad East
    (19.0744, 72.8720), # Oshiwara
    (19.0240, 72.8155), # Chembur
    (19.1422, 72.8210), # Mahim
    (19.2110, 72.8467), # Vasai East
    (19.1206, 72.8905), # Thane
    (19.1016, 72.9209), # Bhiwandi
    (19.2280, 72.9545), # Virar
    (19.1796, 72.8324), # Jogeshwari
    (19.1573, 72.8485), # Vile Parle West
    (19.0864, 72.8839), # Borivali East
    (19.1013, 72.8652), # Mira Road East
    (19.0809, 72.8534), # Vikhroli East
    (19.1494, 72.8320), # Bandra West
    (19.1642, 72.8397), # Malad West
    (19.1960, 72.9090), # Kopar Khairane
    (19.1055, 72.8747), # Jogeshwari East
    (19.0300, 72.8284), # Wadala
    (19.1479, 72.8359), # Santacruz East
    (19.1368, 72.8712), # Saki Naka
    (19.1095, 72.8517), # Kanjurmarg
    (19.1950, 72.8659), # Bhandup West
    (19.1334, 72.8344), # Parel West
    (19.1429, 72.9078), # Mahim East
    (19.0781, 72.8793), # Jogeshwari West
    (19.1540, 72.8601), # Malad West
    (19.1023, 72.9097), # Ghansoli
    (19.2053, 72.8401), # Mira Road West
    (19.2155, 72.8385), # Vasai West
    (19.1202, 72.9010), # Dombivli
    (19.1221, 72.9291), # Kalwa
    (19.1133, 72.8819), # Andheri East
    (19.0889, 72.8315), # Borivali West
    (19.0705, 72.8466), # Malad East
    (19.1355, 72.8342), # Parel East
    (19.1269, 72.8590), # Bhandup East
    (19.2018, 72.8705), # Vikhroli West
    (19.2213, 72.9263), # Vasai East
    (19.2055, 72.8741), # Bhayandar East
    (19.1097, 72.8207), # Lower Parel East
    (19.0812, 72.8592), # Ghatkopar West
    (19.0345, 72.8200), # LBS Nagar
    (19.2270, 72.8983), # Dahisar East
    (19.1793, 72.8505), # Andheri East
    (19.0584, 72.8318), # Bhandup East
    (19.2079, 72.9398), # Virar East
    (19.1351, 72.8537), # Bandra East
    (19.0855, 72.8288), # Versova Beach
    (19.1423, 72.8888), # Vile Parle East
    (19.0933, 72.8208), # Kalyan
    (19.1442, 72.8587), # Thane West
    (19.1749, 72.9305), # Mira Road West
    (19.1156, 72.9221), # Bhiwandi East
]

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

# 🔄 UI placeholders
placeholder_table = st.empty()
placeholder_map = st.empty()
placeholder_metrics = st.empty()
placeholder_chart = st.empty()

# Variable to store clicked location details
clicked_location_details = st.empty()

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
                pickable=True,
                auto_highlight=True
            )
        ]

        # Add important location markers
        for lat, lon in locations:
            layers.append(
                pdk.Layer(
                    'ScatterplotLayer',
                    data=[{"Latitude": lat, "Longitude": lon}],
                    get_position='[Longitude, Latitude]',
                    get_color
