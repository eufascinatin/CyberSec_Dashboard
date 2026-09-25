import streamlit as st
from streamlit_option_menu import option_menu
from views.settings.server_management import server_settings
from views.settings.sensor_management import sensor_management
from views.settings.user_management import user_settings
from views.settings.permission_management import permission_settings
from views.settings.role_management import role_settings
from views.settings.dashboard_config import dashboard_management_settings
from views.settings.system_management import system_management

def render_settings_view():
    # st.tabs executes every tab's body on every rerun regardless of which tab is
    # visible, so a session-state-tracked selector is used instead to only run the
    # backend logic for the actively selected section.
    perms = st.session_state.get("permissions", [])
    tab_options = []
    if "manage_dashboard" in perms: tab_options.append("📊 Dashboard")
    if "read_sensor" in perms or "manage_sensor" in perms: tab_options.append("📡 Sensors")
    if "read_server" in perms or "manage_server" in perms: tab_options.append("🖥️ Servers")
    if "read_user" in perms or "manage_user" in perms: tab_options.append("👥 Users")
    if "read_role" in perms or "manage_role" in perms: tab_options.append("🔑 Roles")
    if "read_permission" in perms or "manage_permission" in perms: tab_options.append("🛡️ Permissions")
    if "read_system" in perms or "manage_system" in perms: tab_options.append("⚙️ System")

    if not tab_options:
        st.warning("You do not have permission to view any settings.")
        return

    if "settings_active_tab" not in st.session_state or st.session_state.settings_active_tab not in tab_options:
        st.session_state.settings_active_tab = tab_options[0]

    active_tab = option_menu(
        menu_title=None,
        options=tab_options,
        default_index=tab_options.index(st.session_state.settings_active_tab),
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"display": "none"},
            "nav-link": {
                "font-size": "15px", 
                "text-align": "center", 
                "margin": "0px", 
                "--hover-color": "rgba(255,255,255,0.05)",
                "border-radius": "0px"
            },
            "nav-link-selected": {
                "background-color": "#2b2b3b",
                "color": "#ffffff",
                "border-top": "1px solid rgba(250, 250, 250, 0.2)",
                "border-left": "1px solid rgba(250, 250, 250, 0.2)",
                "border-right": "1px solid rgba(250, 250, 250, 0.2)",
                "border-bottom": "4px solid #0e1117",
                "margin-bottom": "-2px",
                "border-radius": "6px 6px 0 0"
            },
        }
    )
    
    if active_tab != st.session_state.settings_active_tab:
        st.session_state.settings_active_tab = active_tab
        st.rerun()

    # Inject CSS to make the menu overlap the container border precisely
    st.markdown("""
        <style>
        /* Force iframe to its natural height */
        iframe[title="streamlit_option_menu.option_menu"] {
            height: 48px !important;
        }
        div[data-testid="stVerticalBlock"] > div:has(iframe[title="streamlit_option_menu.option_menu"]) {
            height: 48px !important;
            margin-bottom: -15px !important; /* Pull the container border up to meet the tabs */
            z-index: 999;
            position: relative;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        if active_tab == "🖥️ Servers":
            server_settings()
        elif active_tab == "📡 Sensors":
            sensor_management()
        elif active_tab == "👥 Users":
            user_settings()
        elif active_tab == "🛡️ Permissions":
            permission_settings()
        elif active_tab == "🔑 Roles":
            role_settings()
        elif active_tab == "📊 Dashboard":
            dashboard_management_settings()
        elif active_tab == "⚙️ System":
            system_management()
        
