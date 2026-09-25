import streamlit as st
import sqlite3
from core.db import DB_FILE, get_dashboard_settings

def dashboard_management_settings():
    st.title("Dashboard Management")
    settings = get_dashboard_settings()
    if not settings:
        st.error("Settings not found.")
        return
        
    with st.form("dashboard_settings_form"):
        st.subheader("General Settings")
        auto_refresh = st.number_input("Auto-Refresh Rate (seconds)", min_value=1, max_value=300, value=settings['auto_refresh_rate'])
        map_agg_window = st.number_input("Map Aggregation Window (minutes)", min_value=1, max_value=1440, value=settings['map_agg_window'])
        
        st.subheader("Simulator Settings")
        anomaly_chance = st.number_input("Anomaly Chance (%)", min_value=0.0, max_value=100.0, value=float(settings['anomaly_chance']), format="%.4f")
        
        st.subheader("Anomaly Definition (Temperature)")
        col1, col2 = st.columns(2)
        with col1:
            temp_min = st.number_input("Minimum Valid Temp", value=float(settings['temp_min']))
            temp_max = st.number_input("Maximum Valid Temp", value=float(settings['temp_max']))
        with col2:
            temp_spike_thresh = st.number_input("Temp Change Threshold (Spike)", value=float(settings['temp_spike_threshold']))
            temp_spike_window = st.number_input("Time Interval for Temp Change (minutes)", min_value=1, max_value=60, value=settings['temp_spike_window'])
            
        if st.form_submit_button("Save Settings"):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('''UPDATE dashboard_settings SET
                         auto_refresh_rate=?, map_agg_window=?, anomaly_chance=?,
                         temp_min=?, temp_max=?, temp_spike_threshold=?, temp_spike_window=?
                         WHERE id = (SELECT id FROM dashboard_settings ORDER BY id LIMIT 1)''',
                      (auto_refresh, map_agg_window, anomaly_chance, temp_min, temp_max, temp_spike_thresh, temp_spike_window))
            conn.commit()
            conn.close()
            st.success("Settings saved successfully!")
            st.rerun()
