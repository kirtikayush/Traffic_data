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

# Named locations for famous areas around Mumbai and Vasai-Virar
locations = [
    ("Mumbai Central", 19.0760, 72.8777),
    ("Andheri", 19.0993, 72.8347),
    ("Dadar", 19.0187, 72.8498),
    ("Vasai", 19.3753, 72.8333),
    ("Mira Road", 19.2974, 72.8508),
    ("Borivali", 19.2875, 72.8582),
    ("Malad", 19.0645, 72.8420),
    ("Gateway of India", 18.9219, 72.8347),
    ("Marine Drive", 18.9388, 72.8231),
    ("Worli", 18.9940, 72.8268),
    ("Goregaon", 19.1625, 72.8500),
    ("Juhu", 19.1336, 72.8347),
    ("Kandivali", 19.2152, 72.8574),
    ("Lower Parel", 19.1510, 72.8886),
    ("Kurla", 19.1828, 72.8679),
    ("Vile Parle", 19.1264, 72.8313),
    ("Parel", 19.1358, 72.8871),
    ("Versova", 19.0976, 72.8282),
    ("Malad West", 19.1791, 72.8518),
    ("Ghatkopar", 19.1311, 72.9130),
    ("Mulund", 19.1539, 72.9075),
    ("Bandra", 19.0409, 72.8504),
    ("Kandivali East", 19.2145, 72.8560),
    ("Borivali East", 19.2207, 72.8538),
    ("Andheri West", 19.0967, 72.8311),
    ("Khar", 19.0395, 72.8270),
    ("Marine Lines", 19.1900, 72.9286),
    ("Sion", 19.0145, 72.8465),
    ("Vikhroli", 19.0244, 72.8609),
    ("Santacruz", 19.1541, 72.8340),
    ("Mahalaxmi", 19.0846, 72.8795),
    ("Jogeshwari", 19.1763, 72.8489),
    ("Versova Beach", 19.0864, 72.8839),
    ("Bandra West", 19.1355, 72.8537),
    ("Malad East", 19.0705, 72.8466),
    ("Mira Road West", 19.2053, 72.8401),
    ("Vasai West", 19.2155, 72.8385),
    ("Bhayandar", 19.2055, 72.8741),
    ("Ghatkopar West", 19.0812, 72.8592),
    ("Thane", 19.1221, 72.9291),
    ("Virar", 19.2280, 72.9545),
    ("Vasai East", 19.2110, 72.8467),
    ("Mira Bhayandar", 19.1156, 72.9221),
    ("Vikhroli East", 19.1368, 72.8712),
    ("Wadala", 19.0300, 72.8284),
    ("Goregaon West", 19.1642, 72.8397),
    ("Kurla East", 19.1351, 72.8537),
    ("Chembur", 19.0240, 72.8155),
    ("Bhandup", 19.2018, 72.8705),
    ("Bhandup West", 19.1950, 72.8659),
    ("Parel West", 19.1423, 72.8888),
    ("Lower Parel East", 19.1097, 72.8207),
    ("Kandivali West", 19.1325, 72.8598),
    ("Malad West", 19.1796, 72.8324),
    ("Jogeshwari East", 19.1065, 72.8620),
    ("Thane West", 19.1442, 72.8587),
    ("Chembur East", 19.0889, 72.8315),
    ("Vile Parle East", 19.1429, 72.9078),
    ("Bhiwandi", 19.1202, 72.9010),
    ("Vasai East", 19.2055, 72.8741),
    ("Virar East", 19.2270, 72.8983),
    ("Kalyan", 19.0933, 72.8208),
    ("Bhayandar East", 19.2079, 72.9398),
    ("Goregaon East", 19.0676, 72.8506),
    ("Borivali East", 19.2207, 72.8538),
    ("Mira Road East", 19.1016, 72.9209),
    ("Mahalaxmi West", 19.1494, 72.8320),
    ("Kandivali North", 19.1056, 72.8545),
    ("Vikhroli West", 19.2010, 72.8679),
    ("Saki Naka", 19.1368, 72.8712),
    ("Thane East", 19.1371, 72.9406),
    ("Dadar West", 19.0187, 72.8498),
    ("Bandra East", 19.1409, 72.8700),
    ("Kurla West", 19.1776, 72.8598),
    ("Vikhroli North", 19.1179, 72.8854),
    ("Mulund West", 19.1510, 72.8680),
    ("Mira Road", 19.2018, 72.8705),
    ("Bhiwandi East", 19.1809, 72.9072),
    ("Navi Mumbai", 19.0523, 72.9009)
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
    for name, lat, lon in locations:
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
            st
