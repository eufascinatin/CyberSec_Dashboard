import os
import sys
import random
import sqlite3
from pymongo import MongoClient

# Make sure we can read cities.md (checks same folder first, then parent folder)
_curr_dir = os.path.dirname(os.path.abspath(__file__))
cities_path = os.path.join(_curr_dir, "cities.md")
if not os.path.exists(cities_path):
    cities_path = os.path.join(os.path.dirname(_curr_dir), "cities.md")

db_path = os.path.join(os.path.dirname(_curr_dir), "admin_config.db")

def get_active_servers():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT db_name FROM servers WHERE is_active = 1")
    servers = [row[0] for row in c.fetchall()]
    conn.close()
    return servers

def main():
    with open(cities_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Execute the content to get SENSOR_LOCATIONS
    local_env = {}
    exec(content, {}, local_env)
    sensor_locations = local_env.get("SENSOR_LOCATIONS", [])
    
    if not sensor_locations:
        print("No sensors found in cities.md")
        return
        
    print(f"Loaded {len(sensor_locations)} sensors from cities.md")
    
    servers = get_active_servers()
    if not servers:
        print("No active servers found!")
        return
        
    print(f"Found active servers: {servers}")
    
    client = MongoClient("mongodb://localhost:27017/")
    db = client["cybersec_sensors_db"]
    collection = db["sensors"]
    
    # Drop all old sensors
    deleted = collection.delete_many({})
    print(f"Deleted {deleted.deleted_count} old sensors.")
    
    # Prepare new sensors
    new_sensors = []
    for s in sensor_locations:
        new_sensor = {
            "sensor_id": s["id"],
            "region": s["region"],
            "location": s["location"],
            "lat": s["lat"],
            "lon": s["lon"],
            "status": "Online",
            "assigned_server": random.choice(servers)
        }
        new_sensors.append(new_sensor)
        
    # Insert new sensors
    result = collection.insert_many(new_sensors)
    print(f"Inserted {len(result.inserted_ids)} new sensors and assigned them randomly to active servers.")

if __name__ == "__main__":
    main()
