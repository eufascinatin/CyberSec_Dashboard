import os
import sys
import sqlite3
from pymongo import MongoClient

# Ensure the core module can be found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import init_sqlite

def setup_env():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "admin_config.db")
    
    # 1. Ensure admin_config.db is empty
    if os.path.exists(db_path):
        print(f"Deleting existing {db_path} to ensure clean first run...")
        os.remove(db_path)
        
    print("Initializing local SQLite database...")
    init_sqlite()
    print("Local SQLite initialized (admin:admin created).")
    
    # 2. Generate 8 servers
    print("Generating 8 servers...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    PLANETARY_DBS = [
        "cybersec_db_mercury", "cybersec_db_venus", "cybersec_db_moon",
        "cybersec_db_mars", "cybersec_db_jupiter", "cybersec_db_saturn",
        "cybersec_db_uranus", "cybersec_db_neptune"
    ]
    
    c.execute("DELETE FROM servers")
    for db_name in PLANETARY_DBS:
        name = db_name.split("_")[-1].capitalize()
        c.execute("INSERT INTO servers (name, uri, db_name, is_active, enable_central_audit) VALUES (?, ?, ?, 1, 1)", 
                 (name, "mongodb://localhost:27017/", db_name))
    conn.commit()
    conn.close()
    
    # 3. Generate sensors using setup_sensors.py logic
    print("Generating sensors via setup_sensors...")
    try:
        import setup_sensors
        setup_sensors.main()
    except Exception as e:
        print(f"Error running setup_sensors: {e}")
        
    # 4. Validation
    print("Validating setup...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    user_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM servers")
    server_count = c.fetchone()[0]
    conn.close()
    
    try:
        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
        sensor_count = client["cybersec_sensors_db"]["sensors"].count_documents({})
        client.close()
    except:
        sensor_count = 0
        
    print(f"Validation Results - Users: {user_count}, Servers: {server_count}, Sensors: {sensor_count}")
    
    if user_count == 1 and server_count == 8 and sensor_count == 210:
        print("Validation SUCCEEDED! Writing success flag for installer cleanup...")
        
        # Write flag for install.bat to see
        flag_file = os.path.join(base_dir, ".setup_success")
        try:
            with open(flag_file, "w") as f:
                f.write("ok")
        except Exception as e:
            print(f"Error writing success flag: {e}")
            
        print("Done.")
    else:
        print("Validation FAILED. Keeping setup files for debugging.")

if __name__ == "__main__":
    setup_env()
