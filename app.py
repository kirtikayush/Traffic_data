import streamlit as st
import pandas as pd
import requests
import sqlite3
from datetime import datetime
import time
import pydeck as pdk
import plotly.express as px

st.set_page_config(page_title="🚦 Mumbai Traffic Analyzer", layout="wide")
st.title("🚦 Live Traffic Analyzer (TomTom API - Mumbai & Vasai-Virar)")

API_KEY = "3Lo3uEOWB9XZAzAa2olq7tutorXJvgpY"

# Precise Locations across Mumbai and Vasai-Virar
locations = {
    "Colaba": (18.9196, 72.8347),
    "Churchgate": (18.9400, 72.8280),
    "Nariman Point": (18.9240, 72.8230),
    "Bandra": (19.0638, 72.8326),
    "Andheri": (19.1200, 72.8342),
    "Goregaon": (19.1640, 72.8499),
    "Vikhroli": (19.1870, 72.9519),
    "Mulund": (19.1901, 72.9253),
    "Thane": (19.2183, 72.9787),
    "Vashi": (19.0760, 72.9312),
    "Powai": (19.1155, 72.9139),
    "Kandivali": (19.2265, 72.8589),
    "Dadar": (19.0215, 72.8341),
    
    # Vasai-Virar Region (North Mumbai)
    "Vasai West": (19.3867, 72.8296),
    "Virar": (19.3797, 72.8149),
    "Nalasopara": (19.3727, 72.9337),
    "Vasai East": (19.3000, 72.8486),
    "Virar East": (19.4464, 72.8257),
    "Naigaon": (19.3773, 72.8051)
}

# 🗃 SQLite setup
conn = sqlite3.connect("/tmp/traffic_data.db", check_same_thread=False)
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

    # Save to database
    for _, row in df.iterrows():
        cursor.execute('''INSERT INTO traffic (location, congestion_level, avg_speed, free_flow_speed, lat, lon, timestamp)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (row['Location'], row['Congestion_Level'], row['Avg_Speed'],
                        row['Free_Flow_Speed'], row['Latitude'], row['Longitude'], row['Timestamp'].isoformat()))
    conn.commit()

    # Display table
    placeholder_table.dataframe(df, use_container_width=True)

    # Metrics
    with placeholder_metrics.container():
        st.metric(label="🚨 Most Congested", value=df.loc[df['Congestion_Level'].idxmax()]['Location'])
        st.metric(label="🚗 Avg Speed", value=f"{df['Avg_Speed'].mean():.2f} km/h")

    # Map (updates live)
    with placeholder_map.container():
        st.subheader("🗺️ Traffic Map (Mumbai & Vasai-Virar)")
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
