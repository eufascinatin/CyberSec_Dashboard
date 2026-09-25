import streamlit as st
import sqlite3
from core.db import DB_FILE, get_servers
from views.components import render_pagination_controls, render_table_headers

# --- DIALOGS ---

@st.dialog("Add New Telemetry Server")
def add_server_dialog():
    name = st.text_input("Server Name")
    uri = st.text_input("MongoDB URI", value="mongodb://localhost:27017/")
    db_name = st.text_input("Database Name", value="cybersec_db")
    assigned_region = st.selectbox("Assigned Region", ["All", "West", "Central", "East"])
    is_active = st.checkbox("Active", value=True)
    enable_central_audit = st.checkbox("Enable Centralized Audit", value=True)
    if st.button("Save Server"):
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO servers (name, uri, db_name, assigned_region, is_active, enable_central_audit) VALUES (?, ?, ?, ?, ?, ?)", (name, uri, db_name, assigned_region, int(is_active), int(enable_central_audit)))
            conn.commit()
            conn.close()
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

@st.dialog("Edit Telemetry Server")
def edit_server_dialog(server_id, current_name, current_uri, current_db, current_region, current_active, current_central_audit):
    name = st.text_input("Server Name", value=current_name)
    uri = st.text_input("MongoDB URI", value=current_uri)
    db_name = st.text_input("Database Name", value=current_db)
    idx = ["All", "West", "Central", "East"].index(current_region) if current_region in ["All", "West", "Central", "East"] else 0
    assigned_region = st.selectbox("Assigned Region", ["All", "West", "Central", "East"], index=idx)
    perms = st.session_state.get("permissions", [])
    if "manage_server" in perms:
        is_active = st.checkbox("Active", value=bool(current_active))
    else:
        is_active = bool(current_active)
    enable_central_audit = st.checkbox("Enable Centralized Audit", value=bool(current_central_audit))
    if st.button("Save Changes"):
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE servers SET name=?, uri=?, db_name=?, assigned_region=?, is_active=?, enable_central_audit=? WHERE id=?", (name, uri, db_name, assigned_region, int(is_active), int(enable_central_audit), server_id))
            conn.commit()
            conn.close()
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

@st.dialog("Delete Telemetry Server")
def delete_server_dialog(server_id, server_name):
    st.warning(f"Are you sure you want to delete the server **{server_name}**?")
    if st.button("Yes, Delete Server", type="primary"):
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM servers WHERE id=?", (server_id,))
            conn.commit()
            conn.close()
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
def server_settings():
    st.title("Telemetry Server Management")
    servers = get_servers()
    perms = st.session_state.get("permissions", [])
    
    if "manage_server" in perms:
        if st.button("➕ Add New Server"):
            add_server_dialog()
        
    st.divider()
    
    if not servers.empty:
        start_idx, end_idx = render_pagination_controls("servers", len(servers))
        render_table_headers([1, 2, 2, 2, 2, 1, 1, 1, 1, 1], ["ID", "Name", "URI", "DB Name", "Region", "Active", "Central Audit", "Status", "", ""])
        for idx, row in servers.iloc[start_idx:end_idx].iterrows():
            cols = st.columns([1, 2, 2, 2, 2, 1, 1, 1, 1, 1])
            cols[0].write(row['id'])
            cols[1].write(row['name'])
            cols[2].write(row['uri'])
            cols[3].write(row['db_name'])
            region_val = row.get('assigned_region', 'All')
            cols[4].write(region_val)
            is_active_val = row.get('is_active', 1)
            cols[5].write("✅ Yes" if is_active_val else "❌ No")
            central_audit_val = row.get('enable_central_audit', 1)
            cols[6].write("✅ Yes" if central_audit_val else "❌ No")
            status_color = "🟢" if row['Status'] == "Online" else "🔴"
            cols[7].write(f"{status_color} {row['Status']}")
            if "manage_server" in perms:
                if cols[8].button("Edit", key=f"edit_srv_{row['id']}"):
                    edit_server_dialog(row['id'], row['name'], row['uri'], row['db_name'], region_val, is_active_val, central_audit_val)
            if "manage_server" in perms:
                if cols[9].button("Delete", key=f"del_srv_{row['id']}"):
                    delete_server_dialog(row['id'], row['name'])
    else:
        st.info("No servers configured.")
