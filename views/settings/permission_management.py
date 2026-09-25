import streamlit as st
import sqlite3
import time
import pandas as pd
from core.db import DB_FILE
from views.components import render_pagination_controls, render_table_headers

@st.dialog("Add New Permission")
def add_permission_dialog():
    key = st.text_input("Permission Key (e.g., view_reports)")
    label = st.text_input("Permission Label (e.g., View Reports)")
    
    if st.button("Save Permission"):
        if not key or not label:
            st.error("Both key and label are required.")
            return
            
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO permissions (key, label) VALUES (?, ?)", (key, label))
            conn.commit()
            conn.close()
            st.success("Permission added.")
            time.sleep(1)
            st.rerun()
        except sqlite3.IntegrityError:
            st.error("A permission with this key already exists.")
        except Exception as e:
            st.error(f"Error: {e}")

@st.dialog("Edit Permission")
def edit_permission_dialog(perm_id, current_key, current_label):
    key = st.text_input("Permission Key", value=current_key, disabled=True)
    label = st.text_input("Permission Label", value=current_label)
    
    if st.button("Save Changes"):
        if not label:
            st.error("Label cannot be empty.")
            return
            
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE permissions SET label=? WHERE id=?", (label, perm_id))
            conn.commit()
            conn.close()
            st.success("Permission updated.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
@st.dialog("Delete Permission")
def delete_permission_dialog(perm_id, key):
    st.warning(f"Are you sure you want to delete permission **{key}**?")
    if st.button("Confirm Delete", type="primary"):
        if key in ["dashboard", "role_management"]:
            st.error("Cannot delete core permission.")
        else:
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("DELETE FROM permissions WHERE id=?", (perm_id,))
                conn.commit()
                conn.close()
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

def permission_settings():
    st.title("Permission Management")
    conn = sqlite3.connect(DB_FILE)
    perms_df = pd.read_sql_query("SELECT id, key, label FROM permissions", conn)
    conn.close()
    
    perms = st.session_state.get("permissions", [])
    if "manage_permission" in perms:
        if st.button("➕ Add New Permission"):
            add_permission_dialog()
        
    st.divider()
    
    if not perms_df.empty:
        start_idx, end_idx = render_pagination_controls("permissions", len(perms_df))
        render_table_headers([2, 4, 1, 1], ["Key", "Label", "", ""])
        
        for idx, row in perms_df.iloc[start_idx:end_idx].iterrows():
            cols = st.columns([2, 4, 1, 1])
            cols[0].write(f"`{row['key']}`")
            cols[1].write(f"**{row['label']}**")
            
            if "manage_permission" in perms:
                if cols[2].button("Edit", key=f"edit_perm_{row['id']}"):
                    edit_permission_dialog(row['id'], row['key'], row['label'])
                    
                if cols[3].button("Delete", key=f"del_perm_{row['id']}"):
                    delete_permission_dialog(row['id'], row['key'])
    else:
        st.info("No permissions found.")

