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

# 📍 Multiple Locations (updated coordinates for Vasai Virar and surrounding areas)
locations = {
    "Goregaon": (19.1640, 72.8499),
    "Vasai West": (19.3867, 72.8296),
    "Vasai East": (19.3891, 72.8280),
    "Virar West": (19.3012, 72.8070),
    "Virar East": (19.3012, 72.8050),
    "Borivali West": (19.2801, 72.8492),
    "Borivali East": (19.2983, 72.8524),
    "Andheri West": (19.1064, 72.8311),
    "Andheri East": (19.1111, 72.8479),
    "Bandra West": (19.0654, 72.8260),
    "Bandra East": (19.0646, 72.8552),
    "Worli": (18.9863, 72.8258),
    "Dadar": (19.0196, 72.8340),
    "Lower Parel": (18.9984, 72.8259),
    "Parel": (19.0076, 72.8325),
    "Prabhadevi": (18.9995, 72.8249),
    "Juhu": (19.1132, 72.8258),
    "Santacruz West": (19.0870, 72.8356),
    "Kandivali West": (19.1953, 72.8563),
    "Kandivali East": (19.2137, 72.8691),
    "Malad West": (19.1791, 72.8553),
    "Malad East": (19.1910, 72.8560),
    "Thane": (19.2183, 72.9788),
    "Navi Mumbai": (19.0833, 73.0300),
    "Airoli": (19.1894, 73.0423),
    "Kalyan": (19.2406, 73.1303),
    "Dombivli": (19.2100, 73.0900),
    "Kharghar": (19.0434, 73.0952),
    "Vashi": (19.0760, 72.9916),
}

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
