import streamlit as st

def apply_custom_css():
    st.markdown("""
    <style>
    /* Streamlit Metric and Button 3D Card Styling */
    div[data-testid="stMetric"], div.stButton > button {
        background-color: #1e1e2f;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.1);
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    div[data-testid="stMetric"]:hover, div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(0, 255, 200, 0.2), inset 0 1px 0 rgba(255,255,255,0.2);
        border-color: rgba(0, 255, 200, 0.4);
    }
    
    
    
    
    
    /* Ensure toasts appear at the bottom right and do not block top-right buttons */
    [data-testid="stToastContainer"] {
        bottom: 20px !important;
        right: 20px !important;
        top: auto !important;
    }
    
    /* Adjust metric value colors for neon vibe */
    div[data-testid="stMetricValue"] {
        color: #00ffc8;
        text-shadow: 0 0 10px rgba(0, 255, 200, 0.3);
        padding-left: 10px;
    }
    
    /* Option Menu tweaks are handled via its built-in styles param */
    </style>
    """, unsafe_allow_html=True)
