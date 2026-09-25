import sqlite3
import pandas as pd
from pymongo import MongoClient
from sqlalchemy import create_engine, text
import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
import json
from core.auth import hash_password
import streamlit as st

logger = logging.getLogger(__name__)

import os
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(_base_dir, "test_admin_config.db" if os.environ.get("TESTING") == "1" else "admin_config.db")
TELEMETRY_COLLECTION = "telemetry_data"
AUDIT_COLLECTION = "audit_trail"
SENSORS_COLLECTION = "sensors"

def init_sqlite():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS servers
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE, uri TEXT, db_name TEXT)''')
                 
    # Migration check for assigned_region
    try:
        c.execute("SELECT assigned_region FROM servers LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE servers ADD COLUMN assigned_region TEXT DEFAULT 'All'")
        c.execute("UPDATE servers SET assigned_region = 'All' WHERE name = 'Cele Slovensko'")
        c.execute("UPDATE servers SET assigned_region = 'East' WHERE name = 'Vychod'")

    # Migration check for is_active
    try:
        c.execute("SELECT is_active FROM servers LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE servers ADD COLUMN is_active INTEGER DEFAULT 1")

    # Migration check for enable_central_audit
    try:
        c.execute("SELECT enable_central_audit FROM servers LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE servers ADD COLUMN enable_central_audit INTEGER DEFAULT 1")

    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
                 
    # Migration check for session_token
    try:
        c.execute("SELECT session_token FROM users LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE users ADD COLUMN session_token TEXT DEFAULT NULL")
        
    # Migration checks for new user profile fields
    for col, col_type in [("email", "TEXT"), ("is_locked", "INTEGER DEFAULT 0"), 
                          ("failed_attempts", "INTEGER DEFAULT 0"),
                          ("first_name", "TEXT"), ("title", "TEXT"), 
                          ("last_name", "TEXT"), ("phone_number", "TEXT"),
                          ("must_change_password", "INTEGER DEFAULT 1"),
                          ("last_activity", "TEXT")]:
        try:
            c.execute(f"SELECT {col} FROM users LIMIT 1")
        except sqlite3.OperationalError:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")

    c.execute('''CREATE TABLE IF NOT EXISTS roles
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE, permissions TEXT)''')
                 
    # Try to add db_type column if it doesn't exist (SQLite ALTER TABLE limitation workaround)
    c.execute('''CREATE TABLE IF NOT EXISTS sensor_db_config
                 (id INTEGER PRIMARY KEY, db_type TEXT, server_host TEXT, port TEXT, db_name TEXT, username TEXT, password TEXT)''')
                 
    c.execute('''CREATE TABLE IF NOT EXISTS permissions
                 (id INTEGER PRIMARY KEY, key TEXT UNIQUE, label TEXT)''')
                 
    # Seed granular permissions
    granular_perms = [
        ("read_dashboard", "View Dashboard"),
        ("manage_dashboard", "Manage Dashboard"),
        ("read_user", "Read Users"),
        ("manage_user", "Manage Users"),
        ("read_sensor", "Read Sensors"),
        ("manage_sensor", "Manage Sensors"),
        ("read_server", "Read Servers"),
        ("manage_server", "Manage Servers"),
        ("read_role", "Read Roles"),
        ("manage_role", "Manage Roles"),
        ("read_permission", "Read Permissions"),
        ("manage_permission", "Manage Permissions"),
        ("read_system", "Read System Settings"),
        ("manage_system", "Manage System Settings"),
        ("audit_trails", "View Audit Trails"),
        ("export_csv", "Export Data to CSV")
    ]
    for k, lbl in granular_perms:
        c.execute("INSERT OR IGNORE INTO permissions (key, label) VALUES (?, ?)", (k, lbl))
    conn.commit()
    
    # Ensure Admin role has all permissions immediately
    c.execute("SELECT key FROM permissions")
    all_keys = [r[0] for r in c.fetchall()]
    c.execute("UPDATE roles SET permissions=? WHERE name='Admin'", (json.dumps(all_keys),))
    conn.commit()
                 
    # Migration check for db_type
    try:
        c.execute("SELECT db_type FROM sensor_db_config LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE sensor_db_config ADD COLUMN db_type TEXT DEFAULT 'MongoDB'")
    
    # Seed roles
    c.execute("SELECT COUNT(*) FROM roles")
    if c.fetchone()[0] == 0:
        admin_perms = json.dumps(all_keys)
        viewer_perms = json.dumps(["read_dashboard"])
        c.execute("INSERT INTO roles (name, permissions) VALUES (?, ?)", ("Admin", admin_perms))
        c.execute("INSERT INTO roles (name, permissions) VALUES (?, ?)", ("Viewer", viewer_perms))
        
    # Seed default user if none exists
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        default_pwd = hash_password("admin")
        c.execute("INSERT INTO users (username, password, role, must_change_password) VALUES (?, ?, ?, ?)", ("admin", default_pwd, "Admin", 1))
        
    # Seed default server if none exists
    c.execute("SELECT COUNT(*) FROM servers")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO servers (name, uri, db_name) VALUES (?, ?, ?)", ("Local CyberSec DB", "mongodb://localhost:27017/", "cybersec_db"))
        
    # Seed Planetary Servers
    planetary_servers = [
        ("Mercury", "mongodb://localhost:27017/", "cybersec_db_mercury", "All", 1),
        ("Venus", "mongodb://localhost:27017/", "cybersec_db_venus", "All", 1),
        ("Moon", "mongodb://localhost:27017/", "cybersec_db_moon", "All", 1),
        ("Mars", "mongodb://localhost:27017/", "cybersec_db_mars", "All", 1),
        ("Jupiter", "mongodb://localhost:27017/", "cybersec_db_jupiter", "All", 1),
        ("Saturn", "mongodb://localhost:27017/", "cybersec_db_saturn", "All", 1),
        ("Uranus", "mongodb://localhost:27017/", "cybersec_db_uranus", "All", 1),
        ("Neptune", "mongodb://localhost:27017/", "cybersec_db_neptune", "All", 1)
    ]
    for p_name, p_uri, p_db, p_region, p_active in planetary_servers:
        c.execute("INSERT OR IGNORE INTO servers (name, uri, db_name, assigned_region, is_active) VALUES (?, ?, ?, ?, ?)", (p_name, p_uri, p_db, p_region, p_active))

    # Seed default sensor db config if none exists
    c.execute("SELECT COUNT(*) FROM sensor_db_config")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO sensor_db_config (db_type, server_host, port, db_name, username, password) VALUES (?, ?, ?, ?, ?, ?)", ("MongoDB", "localhost", "27017", "cybersec_sensors_db", "", ""))
        
    # Dashboard Settings table
    c.execute('''CREATE TABLE IF NOT EXISTS dashboard_settings
                 (id INTEGER PRIMARY KEY, auto_refresh_rate INTEGER, map_agg_window INTEGER, anomaly_chance FLOAT, temp_min FLOAT, temp_max FLOAT, temp_spike_threshold FLOAT, temp_spike_window INTEGER)''')
    
    # Seed default dashboard settings if none exists
    c.execute("SELECT COUNT(*) FROM dashboard_settings")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO dashboard_settings (auto_refresh_rate, map_agg_window, anomaly_chance, temp_min, temp_max, temp_spike_threshold, temp_spike_window) VALUES (?, ?, ?, ?, ?, ?, ?)", (30, 5, 0.5, -20.0, 60.0, 10.0, 5))
    
    # System Settings table
    c.execute('''CREATE TABLE IF NOT EXISTS system_settings
                 (id INTEGER PRIMARY KEY, central_db_uri TEXT, central_db_name TEXT)''')
    
    # Seed default system settings if none exists
    c.execute("SELECT COUNT(*) FROM system_settings")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO system_settings (central_db_uri, central_db_name) VALUES (?, ?)", ("mongodb://localhost:27017/", "cybersec_db_central"))
    
    conn.commit()
    conn.close()

init_sqlite()

def get_dashboard_settings():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT auto_refresh_rate, map_agg_window, anomaly_chance, temp_min, temp_max, temp_spike_threshold, temp_spike_window FROM dashboard_settings LIMIT 1")
    res = c.fetchone()
    conn.close()
    if res:
        return {
            "auto_refresh_rate": res[0],
            "map_agg_window": res[1],
            "anomaly_chance": res[2],
            "temp_min": res[3],
            "temp_max": res[4],
            "temp_spike_threshold": res[5],
            "temp_spike_window": res[6]
        }
    return None
def check_server_status(uri):
    try:
        with MongoClient(uri, serverSelectionTimeoutMS=1000) as client:
            client.admin.command('ping')
        return "Online"
    except Exception as e:
        logger.warning(f"Server status check failed for {uri}: {e}")
        return "Offline"

def get_servers():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM servers", conn).fillna("")
    conn.close()
    
    if not df.empty:
        df['Status'] = df['uri'].apply(check_server_status)
    else:
        df['Status'] = []
    return df

def get_users():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT id, username, role, email, is_locked, first_name, title, last_name, phone_number FROM users", conn).fillna("")
    conn.close()
    return df

def fetch_data(uri, db_name, collection, limit=100):
    try:
        with MongoClient(uri, serverSelectionTimeoutMS=2000) as client:
            db = client[db_name]
            sort_key = "timestamp" if collection == TELEMETRY_COLLECTION else "detection_time"
            items = list(db[collection].find({}, {"_id": 0}).sort(sort_key, -1).limit(limit))
        return pd.DataFrame(items).fillna("")
    except Exception as e:
        logger.warning(f"fetch_data failed for {db_name}.{collection}: {e}")
        return pd.DataFrame()

def get_collection_count(uri, db_name, collection):
    try:
        with MongoClient(uri, serverSelectionTimeoutMS=2000) as client:
            db = client[db_name]
            count = db[collection].count_documents({})
        return count
    except Exception as e:
        logger.warning(f"get_collection_count failed for {db_name}.{collection}: {e}")
        return 0

def get_recent_incident_count(uri, db_name, collection):
    try:
        with MongoClient(uri, serverSelectionTimeoutMS=2000) as client:
            db = client[db_name]
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            iso_str = one_hour_ago.isoformat()
            count = db[collection].count_documents({"detection_time": {"$gte": iso_str}})
        return count
    except Exception as e:
        logger.warning(f"get_recent_incident_count failed for {db_name}.{collection}: {e}")
        return 0

def get_roles_list():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name FROM roles")
    roles = [r[0] for r in c.fetchall()]
    conn.close()
    return roles
def get_sensor_db_config():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT db_type, server_host, port, db_name, username, password FROM sensor_db_config LIMIT 1")
    res = c.fetchone()
    conn.close()
    if res:
        from core.auth import decrypt_password
        return {"db_type": res[0], "server_host": res[1], "port": res[2], "db_name": res[3], "username": res[4], "password": decrypt_password(res[5])}
    return None

def build_mongo_uri(host, port, username, password):
    if username and password:
        user_enc = urllib.parse.quote_plus(username)
        pass_enc = urllib.parse.quote_plus(password)
        return f"mongodb://{user_enc}:{pass_enc}@{host}:{port}/"
    return f"mongodb://{host}:{port}/"

def get_sql_engine(db_type, config):
    try:
        user = config['username']
        pw = config['password']
        host = config['server_host']
        port = config['port']
        db = config['db_name']
        
        if db_type == "SQLite":
            # For SQLite, db_name is the file path.
            engine = create_engine(f"sqlite:///{db}.db")
        elif db_type == "PostgreSQL":
            engine = create_engine(f"postgresql://{user}:{pw}@{host}:{port}/{db}")
        elif db_type == "MySQL":
            engine = create_engine(f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db}")
        elif db_type == "MS SQL":
            engine = create_engine(f"mssql+pyodbc://{user}:{pw}@{host}:{port}/{db}?driver=ODBC+Driver+17+for+SQL+Server")
        else:
            return None
            
        # Ensure table exists
        with engine.begin() as conn:
            conn.execute(text('''CREATE TABLE IF NOT EXISTS sensors (
                                 sensor_id VARCHAR(100) PRIMARY KEY,
                                 lat FLOAT,
                                 lon FLOAT)'''))
        return engine
    except Exception as e:
        st.error(f"SQL Engine Error: {e}")
        return None

def check_sensor_db_status(db_type, config):
    if db_type == "MongoDB":
        uri = build_mongo_uri(config['server_host'], config['port'], config['username'], config['password'])
        return check_server_status(uri)
    else:
        engine = get_sql_engine(db_type, config)
        if engine:
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return "Online"
            except Exception as e:
                logger.warning(f"Sensor DB status check failed: {e}")
                return "Offline"
        return "Offline"
def get_all_permissions():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT key, label FROM permissions", conn).fillna("")
    conn.close()
    return dict(zip(df['key'], df['label']))

def get_system_settings():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT central_db_uri, central_db_name FROM system_settings LIMIT 1")
    res = c.fetchone()
    conn.close()
    if res:
        return {"central_db_uri": res[0], "central_db_name": res[1]}
    return {"central_db_uri": "mongodb://localhost:27017/", "central_db_name": "cybersec_db_central"}

def update_system_settings(uri, db_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE system_settings SET central_db_uri=?, central_db_name=? WHERE id=1", (uri, db_name))
    conn.commit()
    conn.close()

