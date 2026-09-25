import streamlit as st
import sqlite3
import json
import pandas as pd
from core.db import DB_FILE, get_all_permissions
from views.components import render_pagination_controls, render_table_headers

@st.dialog("Add New Role")
def add_role_dialog():
    name = st.text_input("Role Name")
    st.write("Permissions:")
    selected_perms = []
    for perm_key, perm_label in get_all_permissions().items():
        if st.checkbox(perm_label, key=f"add_{perm_key}"):
            selected_perms.append(perm_key)
            
    if st.button("Save Role"):
        if not name:
            st.error("Role name cannot be empty")
            return
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO roles (name, permissions) VALUES (?, ?)", (name, json.dumps(selected_perms)))
            conn.commit()
            conn.close()
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

@st.dialog("Edit Role Permissions")
def edit_role_permissions_dialog(role_name, current_perms):
    st.write(f"Editing permissions for **{role_name}**")
    selected_perms = []
    for perm_key, perm_label in get_all_permissions().items():
        is_selected = perm_key in current_perms
        if st.checkbox(perm_label, value=is_selected, key=f"edit_{role_name}_{perm_key}"):
            selected_perms.append(perm_key)
            
    if st.button("Save Permissions"):
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE roles SET permissions = ? WHERE name = ?", (json.dumps(selected_perms), role_name))
            conn.commit()
            conn.close()
            if st.session_state.get("user_role") == role_name:
                st.session_state["permissions"] = selected_perms
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
@st.dialog("Delete Role")
def delete_role_dialog(role_id, name):
    st.warning(f"Are you sure you want to delete role **{name}**?")
    if st.button("Confirm Delete", type="primary"):
        if name == "Admin":
            st.error("Cannot delete Admin role!")
        else:
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("DELETE FROM roles WHERE id = ?", (role_id,))
                conn.commit()
                conn.close()
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

def role_settings():
    st.title("Role Management")
    conn = sqlite3.connect(DB_FILE)
    roles_df = pd.read_sql_query("SELECT id, name, permissions FROM roles", conn)
    conn.close()
    
    perms = st.session_state.get("permissions", [])
    
    if "manage_role" in perms:
        if st.button("➕ Add New Role"):
            add_role_dialog()
        
    st.divider()
    
    if not roles_df.empty:
        start_idx, end_idx = render_pagination_controls("roles", len(roles_df))
        render_table_headers([2, 5, 1, 1], ["Role Name", "Permissions", "", ""])
        
        for idx, row in roles_df.iloc[start_idx:end_idx].iterrows():
            cols = st.columns([2, 5, 1, 1])
            cols[0].write(f"**{row['name']}**")
            perms_list = json.loads(row['permissions']) if row['permissions'] else []
            all_perms = get_all_permissions()
            cols[1].write(", ".join([all_perms.get(p, p) for p in perms_list]))
            
            if "manage_role" in perms:
                if cols[2].button("Edit", key=f"edit_role_{row['id']}"):
                    edit_role_permissions_dialog(row['name'], perms_list)
            if "manage_role" in perms:
                if cols[3].button("Delete", key=f"del_role_{row['id']}"):
                    delete_role_dialog(row['id'], row['name'])
    else:
        st.info("No roles found.")
