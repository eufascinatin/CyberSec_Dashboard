import streamlit as st
import sqlite3
import secrets
import string
import html
import re
from core.db import DB_FILE, get_roles_list, get_users
from core.auth import hash_password
from views.components import render_pagination_controls, render_table_headers

import uuid

@st.dialog("Add New User")
def add_user_dialog():
    st.markdown("""
        <style>
        div[data-testid="stForm"] {
            opacity: 1 !important;
            transition: none !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    if "add_usr_dialog_key" not in st.session_state:
        st.session_state.add_usr_dialog_key = str(uuid.uuid4())
        
    dk = st.session_state.add_usr_dialog_key
    
    st.subheader("Account Details")
    username = st.text_input("Username*", key=f"uname_{dk}")
    roles_list = get_roles_list()
    if st.session_state.get('user_role') != "Admin" and "Admin" in roles_list:
        roles_list.remove("Admin")
    role = st.selectbox("Role", roles_list, key=f"role_{dk}")
    
    st.subheader("Security")
    custom_pwd = st.checkbox("Set Custom Password", key=f"custom_pwd_{dk}")
    
    with st.form(f"add_user_form_{dk}", border=False):
        if custom_pwd:
            password = st.text_input("Password*", type="password", key=f"pwd_{dk}", autocomplete="new-password")
            confirm_password = st.text_input("Confirm Password*", type="password", key=f"cpwd_{dk}", autocomplete="new-password")
        else:
            if "auto_pwd" not in st.session_state:
                st.session_state["auto_pwd"] = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            st.text_input("Auto-Generated Password (Copy this now!)", value=st.session_state["auto_pwd"], disabled=True, key=f"apwd_{dk}")
            password = st.session_state["auto_pwd"]
            confirm_password = password
            
        keep_open = st.checkbox("Keep Open (Create Next)", key=f"keep_{dk}")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Create", use_container_width=True)
        with col2:
            canceled = st.form_submit_button("Cancel", use_container_width=True)

    if canceled:
        st.session_state.add_usr_dialog_key = str(uuid.uuid4()) 
        st.rerun()

    if submitted:
        if not username:
            st.error("Username cannot be empty")
        elif custom_pwd and password != confirm_password:
            st.error("Passwords do not match!")
        else:
            username = html.escape(username)
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute('''INSERT INTO users 
                             (username, password, role, email, first_name, title, last_name, phone_number, is_locked, failed_attempts) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                          (username, hash_password(password), role, "", "", "", "", "", 0, 0))
                conn.commit()
                conn.close()
                
                if keep_open:
                    st.session_state["auto_pwd"] = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                    st.session_state.add_usr_dialog_key = str(uuid.uuid4()) 
                    st.toast(f"User '{username}' added successfully!", icon="✅")
                    st.rerun()
                else:
                    st.session_state.add_usr_dialog_key = str(uuid.uuid4()) 
                    st.toast(f"User '{username}' added successfully!", icon="✅")
                    st.rerun()
                    
            except sqlite3.IntegrityError:
                st.error("Username already exists!")
            except Exception as e:
                st.error(f"Error: {e}")

@st.dialog("Edit User")
def edit_user_dialog(user):
    st.markdown("""
        <style>
        div[data-testid="stForm"] {
            opacity: 1 !important;
            transition: none !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    if "edit_usr_dialog_key" not in st.session_state:
        st.session_state.edit_usr_dialog_key = str(uuid.uuid4())
    dk = st.session_state.edit_usr_dialog_key

    st.write(f"Editing profile for **{user['username']}**")
    
    perms = st.session_state.get("permissions", [])
    
    st.subheader("Account Settings")
    new_username = st.text_input("Username", value=user['username'], key=f"euname_{dk}")
    
    roles_list = get_roles_list()
    if st.session_state.get('user_role') != "Admin" and "Admin" in roles_list:
        roles_list.remove("Admin")
    idx = roles_list.index(user['role']) if user['role'] in roles_list else 0
    new_role = st.selectbox("Role", roles_list, index=idx, key=f"erole_{dk}")
    
    with st.expander("Personal Details"):
        new_email = st.text_input("Email", value=user.get('email', '') or '', key=f"email_{dk}")
        new_title = st.text_input("Title", value=user.get('title', '') or '', key=f"title_{dk}")
        new_first_name = st.text_input("First Name", value=user.get('first_name', '') or '', key=f"fname_{dk}")
        new_last_name = st.text_input("Last Name", value=user.get('last_name', '') or '', key=f"lname_{dk}")
        new_phone = st.text_input("Phone Number", value=user.get('phone_number', '') or '', key=f"phone_{dk}")

    reset_pwd = False
    custom_pwd_toggle = False
    new_password = None
    confirm_password = None
    
    if "manage_user" in perms:
        st.subheader("Security")
        
        is_current_user = user['username'] == st.session_state.get('username_logged_in', '')
        is_locked = st.checkbox("Account Locked", value=bool(user.get('is_locked', 0)), disabled=is_current_user, key=f"elock_{dk}")
        if is_current_user:
            st.caption("You cannot lock your own account.")
            
        reset_pwd = st.checkbox("Reset Password", key=f"reset_pwd_{dk}")
        if reset_pwd:
            custom_pwd_toggle = st.checkbox("Set Custom Password for Reset", key=f"custom_pwd_{dk}")
            
        with st.form(f"edit_pwd_form_{dk}", border=False):
            if reset_pwd:
                if custom_pwd_toggle:
                    new_password = st.text_input("New Password", type="password", key=f"npwd_{dk}", autocomplete="new-password")
                    confirm_password = st.text_input("Confirm New Password", type="password", key=f"cnpwd_{dk}", autocomplete="new-password")
                else:
                    if f"auto_pwd_{user['id']}" not in st.session_state:
                        st.session_state[f"auto_pwd_{user['id']}"] = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                    st.text_input("Auto-Generated Password (Copy this now!)", value=st.session_state[f"auto_pwd_{user['id']}"], disabled=True, key=f"eapwd_{dk}")
                    new_password = st.session_state[f"auto_pwd_{user['id']}"]
                    confirm_password = new_password
            
            col1, col2 = st.columns([1, 1])
            with col1:
                submitted = st.form_submit_button("Save", use_container_width=True)
            with col2:
                canceled = st.form_submit_button("Cancel", use_container_width=True)
    else:
        is_locked = bool(user.get('is_locked', 0))
        with st.form(f"edit_pwd_form_{dk}", border=False):
            col1, col2 = st.columns([1, 1])
            with col1:
                submitted = st.form_submit_button("Save", use_container_width=True)
            with col2:
                canceled = st.form_submit_button("Cancel", use_container_width=True)

    if canceled:
        st.session_state.edit_usr_dialog_key = str(uuid.uuid4())
        st.rerun()
            
    if submitted:
        if not new_username:
            st.error("Username cannot be empty")
        elif reset_pwd and custom_pwd_toggle and not new_password:
            st.error("Password cannot be empty!")
        elif (new_password or confirm_password) and (new_password != confirm_password):
            st.error("Passwords do not match!")
        elif new_email and not re.match(r"^[^@]+@[^@]+\.[^@]+$", new_email):
            st.error("Invalid email format")
        elif new_phone and not re.match(r"^\+?[\d\s\-()]{7,20}$", new_phone):
            st.error("Invalid phone number format")
        else:
            new_username = html.escape(new_username)
            new_email = html.escape(new_email) if new_email else ""
            new_first_name = html.escape(new_first_name) if new_first_name else ""
            new_last_name = html.escape(new_last_name) if new_last_name else ""
            new_title = html.escape(new_title) if new_title else ""
            new_phone = html.escape(new_phone) if new_phone else ""
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                
                if reset_pwd:
                    c.execute('''UPDATE users SET 
                                 username=?, email=?, role=?, is_locked=?, 
                                 first_name=?, title=?, last_name=?, phone_number=?, password=?, failed_attempts=0 
                                 WHERE id=?''', 
                              (new_username, new_email, new_role, int(is_locked), 
                               new_first_name, new_title, new_last_name, new_phone, hash_password(new_password), user['id']))
                else:
                    c.execute('''UPDATE users SET 
                                 username=?, email=?, role=?, is_locked=?, 
                                 first_name=?, title=?, last_name=?, phone_number=?, failed_attempts=0 
                                 WHERE id=?''', 
                              (new_username, new_email, new_role, int(is_locked), 
                               new_first_name, new_title, new_last_name, new_phone, user['id']))
                conn.commit()
                conn.close()
                if reset_pwd and f"auto_pwd_{user['id']}" in st.session_state:
                    del st.session_state[f"auto_pwd_{user['id']}"]
                
                st.session_state.edit_usr_dialog_key = str(uuid.uuid4())
                st.toast(f"User '{new_username}' updated successfully!", icon="✅")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Username already exists!")
            except Exception as e:
                st.error(f"Error: {e}")
            


@st.dialog("Delete User")
def delete_user_dialog(user_id, username):
    st.warning(f"Are you sure you want to delete user **{username}**?")
    if username == "admin":
        st.error("Cannot delete the default admin user!")
        if st.button("Close"):
            st.rerun()
        return
        
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Yes, Delete User", type="primary", use_container_width=True):
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                conn.close()
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    with col2:
        if st.button("Cancel", key=f"cancel_del_{user_id}", use_container_width=True):
            st.rerun()

def user_settings():
    st.title("User Management")
    users = get_users()
    perms = st.session_state.get("permissions", [])
    
    if st.session_state.get('user_role') != "Admin":
        users = users[users['role'] != 'Admin']
    
    if "manage_user" in perms:
        if st.button("➕ Add New User"):
            add_user_dialog()
        
    st.divider()
    
    if not users.empty:
        start_idx, end_idx = render_pagination_controls("users", len(users))
        # Ensure we have the new columns even if DB hasn't re-queried perfectly yet
        for col in ['email', 'is_locked', 'first_name', 'last_name']:
            if col not in users.columns:
                users[col] = None
                
        render_table_headers([1, 2, 2, 2, 1, 1, 1], ["ID", "Username", "Email", "Name", "Role", "", ""])
        
        for idx, row in users.iloc[start_idx:end_idx].iterrows():
            cols = st.columns([1, 2, 2, 2, 1, 1, 1])
            cols[0].write(row['id'])
            
            # Show lock icon if locked
            lock_status = " 🔒" if row.get('is_locked', 0) == 1 else ""
            cols[1].write(f"{row['username']}{lock_status}")
            
            cols[2].write(row.get('email', '') or '')
            
            # Combine name
            fname = row.get('first_name', '') or ''
            lname = row.get('last_name', '') or ''
            full_name = f"{fname} {lname}".strip()
            cols[3].write(full_name)
            
            cols[4].write(row['role'])
            
            can_manage = False
            if "manage_user" in perms:
                if row['role'] == "Admin":
                    if st.session_state.get('user_role') == "Admin":
                        can_manage = True
                else:
                    can_manage = True
                    
            if can_manage:
                if cols[5].button("Edit", key=f"edit_usr_{row['id']}"):
                    edit_user_dialog(row)
                if cols[6].button("Delete", key=f"del_usr_{row['id']}"):
                    delete_user_dialog(row['id'], row['username'])
    else:
        st.info("No users found.")
