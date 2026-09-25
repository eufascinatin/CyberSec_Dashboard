import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from sqlalchemy import text
from core.db import get_dashboard_settings, get_servers, fetch_data, get_sensor_db_config, build_mongo_uri, get_sql_engine, TELEMETRY_COLLECTION, SENSORS_COLLECTION, AUDIT_COLLECTION, get_collection_count, get_recent_incident_count, logger, get_system_settings

def render_dashboard_view():
    dash_settings = get_dashboard_settings()
    if dash_settings:
        st.session_state.auto_refresh_rate = dash_settings['auto_refresh_rate']
        agg_window_minutes = dash_settings['map_agg_window']
    else:
        agg_window_minutes = 5
        
    servers_df = get_servers()
    
    # Filter active servers only
    if not servers_df.empty and 'is_active' in servers_df.columns:
        servers_df = servers_df[servers_df['is_active'] == 1]
    
    if servers_df.empty:
        st.warning("No servers configured or all servers are inactive. Please go to Server Management to add or activate a server.")
        return
        
    col1, col_refresh, col_space, col_server = st.columns([4, 2, 2, 2], vertical_alignment="bottom")
    with col1:
        status_filter = st.radio("Filter Servers by Status:", ["All Servers", "Online", "Offline"], horizontal=True)
    
    if status_filter != "All Servers":
        filtered_servers = servers_df[servers_df['Status'] == status_filter]
    else:
        filtered_servers = servers_df
        
    if filtered_servers.empty:
        st.info(f"No servers found matching status: {status_filter}")
        return
        
    options = {}
    for _, row in filtered_servers.iterrows():
        server_name = row['name']
        if server_name not in options:
            options[server_name] = row
            
    if not options:
        st.info("No servers available.")
        return
        
    dropdown_options = ["All servers"] + list(options.keys())
    
    with col_refresh:
        st.write(f"**Auto-Refresh:** {st.session_state.auto_refresh_rate}s")
        
    with col_server:
        selected_server_name = st.selectbox("Select Server to Monitor", dropdown_options, label_visibility="collapsed")
        

    
    
    def render_live_dashboard():
        if selected_server_name == "All servers":
            st.write("**Monitoring Region:** All | **Server:** All Servers | **Status:** `Online (Global)`")
        
            # Aggregate telemetry across all active servers
            telemetry_dfs = []
            for s in options.values():
                df = fetch_data(s['uri'], s['db_name'], TELEMETRY_COLLECTION, limit=50)
                if not df.empty:
                    telemetry_dfs.append(df)
            if telemetry_dfs:
                telemetry_df = pd.concat(telemetry_dfs, ignore_index=True)
            else:
                telemetry_df = pd.DataFrame()
        
            # Fetch all sensors for the global map
            config = get_sensor_db_config()
            sensors_df = pd.DataFrame()
            valid_sensor_ids = set()
            if config and config['db_type'] == "MongoDB":
                sensor_uri = build_mongo_uri(config['server_host'], config['port'], config['username'], config['password'])
                try:
                    with MongoClient(sensor_uri, serverSelectionTimeoutMS=2000) as client:
                        sensor_db = client[config['db_name']]
                        sensors_list = list(sensor_db[SENSORS_COLLECTION].find({}, {"_id": 0}))
                    if sensors_list:
                        sensors_df = pd.DataFrame(sensors_list)
                        valid_sensor_ids = set(sensors_df['Sensor ID'].tolist()) if 'Sensor ID' in sensors_df.columns else set([s.get('sensor_id') for s in sensors_list])
                except Exception as e:
                    st.warning(f"Could not load global sensor data: {e}")
                
        
            # Fetch directly from the Central Audit database
            system_settings = get_system_settings()
            unfiltered_audit_df = fetch_data(system_settings['central_db_uri'], system_settings['central_db_name'], "central_audit_trail", limit=1000)
            audit_df = unfiltered_audit_df.copy()
        
            # Dummy selected_server to prevent crashes in KPI queries below
            selected_server = {
                "uri": system_settings['central_db_uri'],
                "db_name": system_settings['central_db_name'],
                "name": "All Servers"
            }
        
        else:
            selected_server = options[selected_server_name]
            st.write(f"**Monitoring Region:** {selected_server.get('assigned_region', 'All')} | **Server:** {selected_server['name']} | **Status:** `{selected_server['Status']}`")
        
            if selected_server['Status'] == "Offline":
                st.error("Cannot fetch data. Server is offline.")
                return
            
            # Fetch sensor list (needed for map and audit filtering)
            config = get_sensor_db_config()
            sensors_df = pd.DataFrame()
            valid_sensor_ids = set()
            if config and config['db_type'] == "MongoDB":
                sensor_uri = build_mongo_uri(config['server_host'], config['port'], config['username'], config['password'])
                try:
                    with MongoClient(sensor_uri, serverSelectionTimeoutMS=2000) as client:
                        sensor_db = client[config['db_name']]

                        query = {"assigned_server": selected_server['db_name']}

                        sensors_list = list(sensor_db[SENSORS_COLLECTION].find(query, {"_id": 0}))
                    if sensors_list:
                        sensors_df = pd.DataFrame(sensors_list)
                        valid_sensor_ids = set(sensors_df['Sensor ID'].tolist()) if 'Sensor ID' in sensors_df.columns else set([s.get('sensor_id') for s in sensors_list])
                except Exception as e:
                    st.warning(f"Could not load sensor data for map: {e}")

            telemetry_df = fetch_data(selected_server['uri'], selected_server['db_name'], TELEMETRY_COLLECTION)
        
            # Read from LOCAL database for audit trail
            unfiltered_audit_df = fetch_data(selected_server['uri'], selected_server['db_name'], AUDIT_COLLECTION, limit=500)
        
            # Filter audit using valid_sensor_ids (only those mapped to this server)
            if not unfiltered_audit_df.empty and valid_sensor_ids:
                unfiltered_audit_df = unfiltered_audit_df[unfiltered_audit_df['affected_sensor'].isin(valid_sensor_ids)]
            
            audit_df = unfiltered_audit_df.copy()
    
        # --- INCIDENT NOTIFICATION LOGIC ---
        if not unfiltered_audit_df.empty:
            latest_incident = unfiltered_audit_df.iloc[0]
            latest_time_str = str(latest_incident['detection_time'])
        
            if 'last_alert_time' not in st.session_state:
                st.session_state['last_alert_time'] = latest_time_str
            
            is_new = False
            if latest_time_str != st.session_state['last_alert_time']:
                st.session_state['last_alert_time'] = latest_time_str
                is_new = True
            
            severity = latest_incident['severity']
            incident_type = latest_incident['incident_type']
            affected_sensor = latest_incident['affected_sensor']
        
            location_str = ""
            config = get_sensor_db_config()
            if config:
                try:
                    if config['db_type'] == "MongoDB":
                        sensor_uri = build_mongo_uri(config['server_host'], config['port'], config['username'], config['password'])
                        with MongoClient(sensor_uri, serverSelectionTimeoutMS=2000) as client:
                            sensor_db = client[config['db_name']]
                            sensor_data = sensor_db[SENSORS_COLLECTION].find_one({"sensor_id": affected_sensor})
                        if sensor_data and 'location' in sensor_data and pd.notna(sensor_data['location']):
                            location_str = f" ({sensor_data['location']})"
                    else:
                        engine = get_sql_engine(config['db_type'], config)
                        if engine:
                            with engine.connect() as conn:
                                res = conn.execute(text("SELECT location FROM sensors WHERE sensor_id = :sid"), {"sid": affected_sensor}).fetchone()
                                if res and res[0]:
                                    location_str = f" ({res[0]})"
                except Exception as e:
                    logger.warning(f"Could not resolve location for sensor {affected_sensor}: {e}")
                
            msg = f"🚨 {severity}: {incident_type} detected on {affected_sensor}{location_str}!"
        
            if is_new:
                st.toast(msg)
            
            if severity == 'CRITICAL':
                severity = latest_incident['severity']
                msg = f"New {severity} incident on {latest_incident['affected_sensor']}: {latest_incident['incident_type']}"
                if severity == 'CRITICAL':
                    st.toast(f"🚨 {msg}", icon="🚨")
                elif severity == 'WARNING':
                    st.toast(f"⚠️ {msg}", icon="⚠️")
                else:
                    st.toast(f"ℹ️ {msg}", icon="ℹ️")


    
        # --- ROW 1 (TOP): KPI METRICS ---
        if selected_server_name == "All servers":
            total_packets = sum(get_collection_count(s['uri'], s['db_name'], TELEMETRY_COLLECTION) for s in options.values())
        else:
            total_packets = get_collection_count(selected_server['uri'], selected_server['db_name'], TELEMETRY_COLLECTION)
    
        # KPIs use the filtered audit_df counts
        if selected_server_name == "All servers":
            system_settings = get_system_settings()
            total_incidents = get_collection_count(system_settings['central_db_uri'], system_settings['central_db_name'], "central_audit_trail")
        else:
            total_incidents = get_collection_count(selected_server['uri'], selected_server['db_name'], "audit_trail")
    
        if selected_server_name == "All servers":
            system_settings = get_system_settings()
            recent_incidents = get_recent_incident_count(system_settings['central_db_uri'], system_settings['central_db_name'], "central_audit_trail")
        else:
            recent_incidents = get_recent_incident_count(selected_server['uri'], selected_server['db_name'], "audit_trail")
    
        network_health = 100.0
        if total_packets > 0:
            network_health = 100.0 - ((total_incidents / total_packets) * 100.0)
        
        with st.container(border=True):
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total Packets Received", total_packets)
            kpi2.metric("Incidents (Last Hour)", recent_incidents)
            kpi3.metric("Network Health (%)", f"{network_health:.2f}%")
    
        st.divider()

        # --- ROW 2 (MIDDLE): MAP AND AUDIT TRAIL ---
    
        st.write("**Interactive Map & Audit Filters**")
        f_col1, f_col2, f_col3 = st.columns(3)
    
        selected_severities = []
        selected_regions = []
        sensor_search = ""
    
        if not audit_df.empty:
            # Map region from sensors_df if possible
            if not sensors_df.empty:
                sensor_to_region = dict(zip(sensors_df['sensor_id'], sensors_df['region'])) if 'sensor_id' in sensors_df.columns else dict(zip(sensors_df['Sensor ID'], sensors_df['Region']))
                audit_df['region'] = audit_df['affected_sensor'].map(sensor_to_region).fillna('Unknown')
            else:
                audit_df['region'] = 'Unknown'
            
            severities = sorted(audit_df['severity'].dropna().unique().tolist())
            if "Normal" not in severities:
                severities.append("Normal")
            
            selected_severities = f_col1.multiselect("Severity", options=severities, default=[], key=f"filter_sev_{selected_server_name}")
        
            if not sensors_df.empty:
                region_col = 'Region' if 'Region' in sensors_df.columns else 'region'
                regions = sorted([str(r) for r in sensors_df[region_col].unique() if pd.notna(r) and r != "Unknown"])
            else:
                regions = sorted([str(r) for r in audit_df['region'].unique() if pd.notna(r) and r != "Unknown"])
                
            if "Unknown" in audit_df['region'].unique().tolist():
                regions.append("Unknown")
            
            selected_regions = f_col2.multiselect("Region", options=regions, default=[], key=f"filter_reg_{selected_server_name}")
        
            sensor_search = f_col3.text_input("Sensor ID", value="", key=f"filter_sid_{selected_server_name}")
        
            # Apply filters to audit_df
            if selected_severities:
                audit_df = audit_df[audit_df['severity'].isin(selected_severities)]
            if selected_regions:
                audit_df = audit_df[audit_df['region'].isin(selected_regions)]
            if sensor_search:
                audit_df = audit_df[audit_df['affected_sensor'].str.contains(sensor_search, case=False, na=False)]

        c_mid_left, c_mid_right = st.columns(2)
    
        with c_mid_left:
            # --- LIVE GEOGRAPHICAL MAP ---
            st.subheader("Live Sensor Map")
                
            if not sensors_df.empty:
                # First, filter by region and sensor_id if needed
                region_col = 'Region' if 'Region' in sensors_df.columns else 'region'
                sensor_id_col = 'Sensor ID' if 'Sensor ID' in sensors_df.columns else 'sensor_id'
            
                if selected_regions:
                    sensors_df = sensors_df[sensors_df[region_col].isin(selected_regions)]
                if sensor_search:
                    sensors_df = sensors_df[sensors_df[sensor_id_col].str.contains(sensor_search, case=False, na=False)]
                map_sensor_status = {}
                window_ago = datetime.now(timezone.utc) - timedelta(minutes=agg_window_minutes)
                recent_map_audit = unfiltered_audit_df.copy()
                if not recent_map_audit.empty:
                    recent_map_audit['detection_time'] = pd.to_datetime(recent_map_audit['detection_time'])
                    if recent_map_audit['detection_time'].dt.tz is None:
                        recent_map_audit['detection_time'] = recent_map_audit['detection_time'].dt.tz_localize('UTC')
                    recent_map_audit = recent_map_audit[recent_map_audit['detection_time'] >= window_ago]
                
                    for _, row in recent_map_audit.iterrows():
                        sensor = row['affected_sensor']
                        sev = row['severity']
                        if sensor not in map_sensor_status:
                            map_sensor_status[sensor] = sev
                        elif map_sensor_status[sensor] != 'CRITICAL' and sev == 'CRITICAL':
                            map_sensor_status[sensor] = 'CRITICAL'

                sensors_df['Current Status'] = sensors_df['sensor_id' if 'sensor_id' in sensors_df.columns else 'Sensor ID'].apply(
                    lambda x: map_sensor_status.get(x, 'Normal')
                )
            
                if selected_severities:
                    sensors_df = sensors_df[sensors_df['Current Status'].isin(selected_severities)]
                
                if sensors_df.empty:
                    st.warning("No sensors match the current filter criteria.")
                else:
                    sensors_df = sensors_df.rename(columns={"location": "City", "region": "Region", "sensor_id": "Sensor ID"})
                
                    fig_map = px.scatter_map(
                        sensors_df, 
                        lat="lat", 
                        lon="lon", 
                        color="Current Status",
                        hover_name="Sensor ID",
                        hover_data={"lat": False, "lon": False, "City": True, "Region": True, "Current Status": True},
                        color_discrete_map={"Normal": "green", "WARNING": "orange", "CRITICAL": "red"},
                        zoom=6.5, 
                        center={"lat": 48.6690, "lon": 19.6990},
                        map_style="carto-darkmatter"
                    )
                    fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_map, width='stretch')
            else:
                st.info("No sensor data available for the map.")
            
        with c_mid_right:
            # --- AUDIT TRAIL ---
            st.subheader("Audit Trail (Incidents)")
        
            if not audit_df.empty:
                if 'source_server' not in audit_df.columns:
                    audit_df['source_server'] = selected_server_name if selected_server_name != "All servers" else "Unknown"
                display_df = audit_df[['detection_time', 'source_server', 'region', 'incident_type', 'severity', 'affected_sensor']].copy()
                
                # Convert to local time for better user readability
                display_df['detection_time'] = pd.to_datetime(display_df['detection_time'])
                if display_df['detection_time'].dt.tz is not None:
                    display_df['detection_time'] = display_df['detection_time'].dt.tz_convert(datetime.now().astimezone().tzinfo)
                display_df['detection_time'] = display_df['detection_time'].dt.strftime('%Y-%m-%d %H:%M:%S')

                display_df = display_df.sort_values(by='detection_time', ascending=False)
                st.dataframe(display_df, width='stretch', height=400, hide_index=True)
                csv = audit_df.to_csv(index=False).encode('utf-8')
                if 'export_csv' in st.session_state.get('permissions', []):
                    st.download_button("Download Audit Trail as CSV", data=csv, file_name='audit_trail.csv', mime='text/csv')
            else:
                st.success("No incidents logged. System is secure.")

        st.divider()

        # --- ROW 3 (BOTTOM): PIE CHART AND LIVE TELEMETRY ---
        c_bot_left, c_bot_right = st.columns([3, 7])
    
        with c_bot_left:
            st.subheader(f"Sensor Status (Last {agg_window_minutes} Min)")
        
            if not sensors_df.empty:
                pie_data = []
            
                window_ago = datetime.now(timezone.utc) - timedelta(minutes=agg_window_minutes)
                recent_audit = unfiltered_audit_df.copy()
                if not recent_audit.empty:
                    recent_audit['detection_time'] = pd.to_datetime(recent_audit['detection_time'])
                    if recent_audit['detection_time'].dt.tz is None:
                        recent_audit['detection_time'] = recent_audit['detection_time'].dt.tz_localize('UTC')
                
                    recent_audit = recent_audit[recent_audit['detection_time'] >= window_ago]
            
                sensor_status_map = {}
                if not recent_audit.empty:
                    for _, row in recent_audit.iterrows():
                        sensor = row['affected_sensor']
                        sev = row['severity']
                    
                        if sensor not in sensor_status_map:
                            sensor_status_map[sensor] = sev
                        elif sensor_status_map[sensor] != 'CRITICAL' and sev == 'CRITICAL':
                            sensor_status_map[sensor] = 'CRITICAL'
                        
                status_counts = {"Normal": 0, "WARNING": 0, "CRITICAL": 0}
            
                for _, row in sensors_df.iterrows():
                    sid = row['Sensor ID']
                    if sid in sensor_status_map:
                        status_counts[sensor_status_map[sid]] += 1
                    else:
                        status_counts["Normal"] += 1
                    
                pie_df = pd.DataFrame([
                    {"Status": "Normal", "Count": status_counts["Normal"]},
                    {"Status": "WARNING", "Count": status_counts["WARNING"]},
                    {"Status": "CRITICAL", "Count": status_counts["CRITICAL"]}
                ])
                pie_df = pie_df[pie_df["Count"] > 0]
            
                if not pie_df.empty:
                    fig_pie = px.pie(
                        pie_df, 
                        names="Status", 
                        values="Count",
                        color="Status",
                        color_discrete_map={
                            "Normal": "green",
                            "WARNING": "orange",
                            "CRITICAL": "red"
                        },
                        hole=0.4
                    )
                    fig_pie.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_pie, width='stretch')
                else:
                    st.info("No sensor status available.")
            else:
                st.info("No sensor data available for pie chart.")

        with c_bot_right:
            # --- LIVE TELEMETRY DATA ---
            st.subheader("Live Telemetry Data (Temperature)")
            if not telemetry_df.empty:
                telemetry_df['timestamp'] = pd.to_datetime(telemetry_df['timestamp'])
                telemetry_df = telemetry_df.sort_values('timestamp')
                fig = px.line(telemetry_df, x='timestamp', y='temperature', title="Sensor Temperature Over Time")
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No telemetry data found.")
            

    
    if st.session_state.auto_refresh_rate > 0:
        fragment = st.fragment(run_every=f"{st.session_state.auto_refresh_rate}s")(render_live_dashboard)
    else:
        fragment = st.fragment(render_live_dashboard)
        
    fragment()
