import time
import random
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
import sqlite3

def get_anomaly_chance():
    try:
        conn = sqlite3.connect("admin_config.db")
        c = conn.cursor()
        c.execute("SELECT anomaly_chance FROM dashboard_settings LIMIT 1")
        res = c.fetchone()
        conn.close()
        if res:
            return float(res[0]) / 100.0
    except Exception:
        pass
    return 0.05

def get_mongo_uri(db_name):
    try:
        conn = sqlite3.connect("admin_config.db")
        c = conn.cursor()
        c.execute("SELECT uri FROM servers WHERE db_name=?", (db_name,))
        res = c.fetchone()
        if res and res[0]:
            conn.close()
            return res[0]
            
        c.execute("SELECT central_db_uri FROM system_settings LIMIT 1")
        sys_res = c.fetchone()
        conn.close()
        if sys_res and sys_res[0]:
            return sys_res[0]
    except Exception:
        pass
    return "mongodb://localhost:27017/"

# MongoDB configuration
# Update this if using MongoDB Atlas: "mongodb+srv://<username>:<password>@cluster0...mongodb.net/"
COLLECTION_NAME = "telemetry_data"

def generate_hash(sensor_id, timestamp, temp, lat, lon):
    """Generates a SHA-256 hash representing the data's integrity."""
    data_string = f"{sensor_id}{timestamp}{temp}{lat}{lon}"
    return hashlib.sha256(data_string.encode('utf-8')).hexdigest()

SENSOR_TEMPERATURES = {}

def get_sensor_temp(sensor_id):
    if sensor_id not in SENSOR_TEMPERATURES:
        SENSOR_TEMPERATURES[sensor_id] = round(random.uniform(10.0, 30.0), 2)
    # Random walk: max 1.5 degree change per tick
    change = random.uniform(-1.5, 1.5)
    new_temp = SENSOR_TEMPERATURES[sensor_id] + change
    # Clamp between realistic bounds
    new_temp = max(-10.0, min(50.0, new_temp))
    SENSOR_TEMPERATURES[sensor_id] = round(new_temp, 2)
    return SENSOR_TEMPERATURES[sensor_id]

def generate_telemetry(sensor_list, anomaly_chance=0.05):
    """Generates fake telemetry data with a configurable chance of anomalies."""
    sensor = random.choice(sensor_list)
    sensor_id = sensor["sensor_id"]
    timestamp = datetime.now(timezone.utc).isoformat()
    temp = get_sensor_temp(sensor_id)
    lat = sensor["lat"]
    lon = sensor["lon"]
    
    # Dynamic chance to inject an anomaly
    is_anomaly = random.random() < anomaly_chance
    anomaly_type = None
    
    if is_anomaly:
        anomaly_choice = random.choice(["wrong_hash", "delayed_timestamp", "temperature_spike"])
        if anomaly_choice == "delayed_timestamp":
            # Simulate a delayed packet by subtracting 5 minutes from the timestamp
            delayed_time = datetime.now(timezone.utc) - timedelta(minutes=5)
            timestamp = delayed_time.isoformat()
            anomaly_type = "delayed_timestamp"
            data_hash = generate_hash(sensor_id, timestamp, temp, lat, lon)
        elif anomaly_choice == "wrong_hash":
            # Generate a completely invalid hash
            anomaly_type = "wrong_hash"
            data_hash = hashlib.sha256(b"tampered_data").hexdigest()
        elif anomaly_choice == "temperature_spike":
            # Add a massive spike
            temp += random.choice([20.0, -20.0])
            temp = round(max(-30.0, min(70.0, temp)), 2)
            anomaly_type = "temperature_spike"
            data_hash = generate_hash(sensor_id, timestamp, temp, lat, lon)
    else:
        # Valid data
        data_hash = generate_hash(sensor_id, timestamp, temp, lat, lon)

    payload = {
        "sensor_id": sensor_id,
        "region": sensor.get("region"),
        "location": sensor.get("location"),
        "timestamp": timestamp,
        "temperature": temp,
        "gps": {"lat": lat, "lon": lon},
        "hash": data_hash,
        "is_anomaly_injected": is_anomaly,
        "anomaly_type": anomaly_type
    }
    return payload

def main(target_db_name=None):
    if target_db_name is None:
        if len(sys.argv) < 2:
            print("Usage: python simulator.py <target_db_name>")
            return
        target_db_name = sys.argv[1]
        
    print(f"Initializing Data Simulator for {target_db_name}...")
    try:
        # Connect to MongoDB
        mongo_uri = get_mongo_uri(target_db_name)
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("Connected to MongoDB successfully.")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        print("Please ensure MongoDB is running locally or update the MONGO_URI.")
        return

    # Fetch stored sensors for THIS specific server
    try:
        sensor_db = client["cybersec_sensors_db"]
        # In a real scenario we might fallback to all if assigned_server isn't present, 
        # but here we strictly generate for assigned sensors
        available_sensors = list(sensor_db["sensors"].find({"status": "Online", "assigned_server": target_db_name}))
        if not available_sensors:
            print(f"No online sensors found assigned to {target_db_name}. Please assign some via the UI.")
            return
        print(f"Loaded {len(available_sensors)} online sensors assigned to {target_db_name}.")
    except Exception as e:
        print(f"Error fetching sensors from cybersec_sensors_db: {e}")
        return

    db = client[target_db_name]
    collection = db[COLLECTION_NAME]

    print(f"Starting data generation for {target_db_name}... (Press Ctrl+C to stop)")
    try:
        while True:
            current_anomaly_chance = get_anomaly_chance()
            data = generate_telemetry(available_sensors, current_anomaly_chance)
            collection.insert_one(data)
            
            # Print for local visualization
            print_data = data.copy()
            if '_id' in print_data:
                del print_data['_id']
            print(f"Pushed: {json.dumps(print_data)}")
            
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nData Simulator stopped by user.")
    finally:
        client.close()

if __name__ == "__main__":
    main()
