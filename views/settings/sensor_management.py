import streamlit as st
import sqlite3
import pandas as pd
from pymongo import MongoClient
from sqlalchemy import text
from core.db import DB_FILE, SENSORS_COLLECTION, get_servers, get_sensor_db_config, build_mongo_uri, get_sql_engine, check_sensor_db_status
from views.components import render_pagination_controls, render_table_headers

@st.dialog("Create New Sensor")
def create_sensor_dialog(db_type, config):
    servers_df = get_servers()
    active_servers = []
    if not servers_df.empty and 'is_active' in servers_df.columns:
        active_servers = servers_df[servers_df['is_active'] == 1]['db_name'].tolist()
    if not active_servers:
        active_servers = ["cybersec_db_mercury"]
        
    new_id = st.text_input("Sensor ID (e.g., SENSOR_001)")
    new_region = st.selectbox("Region", ["West", "Central", "East"])
    new_assigned_server = st.selectbox("Assigned Server", active_servers)
    new_location = st.text_input("Location (City)")
    new_status = st.selectbox("Status", ["Online", "Offline"])
    new_lat = st.number_input("Latitude", value=48.0, format="%.6f")
    new_lon = st.number_input("Longitude", value=17.0, format="%.6f")
    if st.button("Create Sensor"):
        if db_type == "MongoDB":
            uri = build_mongo_uri(config['server_host'], config['port'], config['username'], config['password'])
            with MongoClient(uri) as client:
                db = client[config['db_name']]
                if db[SENSORS_COLLECTION].find_one({"sensor_id": new_id}):
                    st.error("Sensor ID already exists!")
                    created = False
                else:
                    db[SENSORS_COLLECTION].insert_one({
                        "sensor_id": new_id,
                        "region": new_region,
                        "assigned_server": new_assigned_server,
                        "location": new_location,
                        "status": new_status,
                        "lat": new_lat,
                        "lon": new_lon
                    })
                    created = True
            if created:
                st.rerun()
        else:
            engine = get_sql_engine(db_type, config)
            if engine:
                with engine.begin() as conn:
                    res = conn.execute(text("SELECT sensor_id FROM sensors WHERE sensor_id = :sid"), {"sid": new_id}).fetchone()
                    if res:
                        st.error("Sensor ID already exists!")
                    else:
                        conn.execute(text("INSERT INTO sensors (sensor_id, lat, lon) VALUES (:sid, :lat, :lon)"), 
                                     {"sid": new_id, "lat": new_lat, "lon": new_lon})
                st.rerun()

@st.dialog("Edit Sensor")
def edit_sensor_dialog(sensor_id, lat, lon, region, assigned_server, location, status, db_type, config):
    servers_df = get_servers()
    active_servers = []
    if not servers_df.empty and 'is_active' in servers_df.columns:
        active_servers = servers_df[servers_df['is_active'] == 1]['db_name'].tolist()
    if not active_servers:
        active_servers = ["cybersec_db_mercury"]
        
    st.text_input("Sensor ID (Read Only)", value=sensor_id, disabled=True)
    
    new_region = st.selectbox("Region", ["West", "Central", "East"], index=["West", "Central", "East"].index(region) if region in ["West", "Central", "East"] else 0)
    
    # Safely find index or default to 0
    idx = active_servers.index(assigned_server) if assigned_server in active_servers else 0
    new_assigned_server = st.selectbox("Assigned Server", active_servers, index=idx)
    
    new_location = st.text_input("Location (City)", value=str(location) if pd.notna(location) else "")
    new_status = st.selectbox("Status", ["Online", "Offline"], index=["Online", "Offline"].index(status) if status in ["Online", "Offline"] else 0)
    new_lat = st.number_input("Latitude", value=float(lat), format="%.6f")
    new_lon = st.number_input("Longitude", value=float(lon), format="%.6f")
    if st.button("Update Sensor"):
        if db_type == "MongoDB":
            uri = build_mongo_uri(config['server_host'], config['port'], config['username'], config['password'])
            with MongoClient(uri) as client:
                db = client[config['db_name']]
                db[SENSORS_COLLECTION].update_one({"sensor_id": sensor_id}, {"$set": {"region": new_region, "assigned_server": new_assigned_server, "location": new_location, "status": new_status, "lat": new_lat, "lon": new_lon}})
        else:
            engine = get_sql_engine(db_type, config)
            if engine:
                with engine.begin() as conn:
                    conn.execute(text("UPDATE sensors SET lat = :lat, lon = :lon WHERE sensor_id = :sid"), 
                                 {"lat": new_lat, "lon": new_lon, "sid": sensor_id})
        st.rerun()

@st.dialog("Confirm Deletion")
def delete_sensor_dialog(sensor_id, db_type, config):
    st.warning(f"Are you absolutely sure you want to delete **{sensor_id}**?")
    if st.button("Yes, Delete Sensor", type="primary"):
        if db_type == "MongoDB":
            uri = build_mongo_uri(config['server_host'], config['port'], config['username'], config['password'])
            with MongoClient(uri) as client:
                db = client[config['db_name']]
                db[SENSORS_COLLECTION].delete_one({"sensor_id": sensor_id})
        else:
            engine = get_sql_engine(db_type, config)
            if engine:
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM sensors WHERE sensor_id = :sid"), {"sid": sensor_id})
        st.rerun()
    if st.button("Cancel"):
        st.rerun()

def sensor_management():
    st.title("Sensor Management")
    perms = st.session_state.get("permissions", [])
    
    config = get_sensor_db_config()
    if not config: config = {"db_type": "MongoDB", "server_host": "localhost", "port": "27017", "db_name": "cybersec_sensors", "username": "", "password": ""}
    
    if "manage_sensor" in perms:
        with st.expander("⚙️ Database Connection Settings", expanded=False):
            with st.form("sensor_db_form"):
                db_type = st.selectbox("Database Type", ["MongoDB", "SQLite", "PostgreSQL", "MySQL", "MS SQL"], index=["MongoDB", "SQLite", "PostgreSQL", "MySQL", "MS SQL"].index(config['db_type']))
                host = st.text_input("Server Host", value=config['server_host'])
                port = st.text_input("Port", value=config['port'])
                db_name = st.text_input("Database Name (or SQLite filename)", value=config['db_name'])
                username = st.text_input("Username", value=config['username'])
                password = st.text_input("Password", type="password", value=config['password'])
                
                if st.form_submit_button("Save Connection Settings"):
                    from core.auth import encrypt_password
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("""UPDATE sensor_db_config SET db_type=?, server_host=?, port=?, db_name=?, username=?, password=?
                                 WHERE id = (SELECT id FROM sensor_db_config ORDER BY id LIMIT 1)""",
                              (db_type, host, port, db_name, username, encrypt_password(password)))
                    conn.commit()
                    conn.close()
                    st.success("Connection settings saved!")
                    st.rerun()
            
    status = check_sensor_db_status(config['db_type'], config)
    
    if status == "Online":
        st.success(f"Sensor Database ({config['db_type']}) is **Online**")
    else:
        st.error(f"Sensor Database ({config['db_type']}) is **Offline**.")
        return 
        
    st.divider()
    st.header("Sensor Registry")
    
    if "manage_sensor" in perms:
        if st.button("➕ Create New Sensor"):
            create_sensor_dialog(config['db_type'], config)
        
    # Read Data
    df = pd.DataFrame()
    if config['db_type'] == "MongoDB":
        uri = build_mongo_uri(config['server_host'], config['port'], config['username'], config['password'])
        with MongoClient(uri) as client:
            db = client[config['db_name']]
            sensors = list(db[SENSORS_COLLECTION].find({}, {"_id": 0}))
        if sensors:
            df = pd.DataFrame(sensors)
            if 'gps' in df.columns:
                df['lat'] = df['gps'].apply(lambda x: x.get('lat') if isinstance(x, dict) else None)
                df['lon'] = df['gps'].apply(lambda x: x.get('lon') if isinstance(x, dict) else None)
                df = df.drop(columns=['gps'])
    else:
        engine = get_sql_engine(config['db_type'], config)
        if engine:
            with engine.connect() as conn:
                df = pd.read_sql("SELECT * FROM sensors", conn)
                
    if not df.empty:
        # Ensure new columns exist for SQL fallback
        for col in ['assigned_server', 'location', 'status']:
            if col not in df.columns:
                df[col] = "N/A"
                
        # Filtering UI
        st.subheader("Filter Sensors")
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        with f_col1:
            assigned_servers = ["All"] + sorted(df['assigned_server'].dropna().astype(str).unique().tolist())
            sel_assigned_server = st.selectbox("Assigned Server", assigned_servers)
        with f_col2:
            regions = ["All"] + sorted(df['region'].dropna().astype(str).unique().tolist() if 'region' in df.columns else [])
            sel_region = st.selectbox("Region", regions)
        with f_col3:
            locations = ["All"] + sorted(df['location'].dropna().astype(str).unique().tolist())
            sel_location = st.selectbox("Location", locations)
        with f_col4:
            statuses = ["All"] + sorted(df['status'].dropna().astype(str).unique().tolist())
            sel_status = st.selectbox("Status", statuses)
            
        filtered_df = df.copy()
        if sel_assigned_server != "All":
            filtered_df = filtered_df[filtered_df['assigned_server'] == sel_assigned_server]
        if sel_region != "All":
            filtered_df = filtered_df[filtered_df['region'] == sel_region]
        if sel_location != "All":
            filtered_df = filtered_df[filtered_df['location'] == sel_location]
        if sel_status != "All":
            filtered_df = filtered_df[filtered_df['status'] == sel_status]
            
        st.write(f"Showing {len(filtered_df)} sensors")

        # We render rows manually to add Edit/Delete buttons per row
        start_idx, end_idx = render_pagination_controls("sensors", len(filtered_df))
        render_table_headers([2, 1, 2, 2, 1, 1, 1, 1, 1], ["Sensor ID", "Region", "Assigned Server", "Location", "Status", "Lat", "Lon", "", ""])
        
        for idx, row in filtered_df.iloc[start_idx:end_idx].iterrows():
            cols = st.columns([2, 1, 2, 2, 1, 1, 1, 1, 1])
            cols[0].write(row['sensor_id'])
            cols[1].write(row.get('region', 'N/A'))
            cols[2].write(row.get('assigned_server', 'N/A'))
            cols[3].write(row['location'])
            status_color = "🟢" if row['status'] == "Online" else "🔴"
            cols[4].write(f"{status_color} {row['status']}")
            cols[5].write(row['lat'])
            cols[6].write(row['lon'])
            if "manage_sensor" in perms:
                if cols[7].button("Edit", key=f"edit_{row['sensor_id']}"):
                    edit_sensor_dialog(row['sensor_id'], row['lat'], row['lon'], row.get('region', 'N/A'), row.get('assigned_server', 'N/A'), row['location'], row['status'], config['db_type'], config)
            if "manage_sensor" in perms:
                if cols[8].button("Delete", key=f"del_{row['sensor_id']}"):
                    delete_sensor_dialog(row['sensor_id'], config['db_type'], config)
    else:
        st.info("No sensors registered yet.")
