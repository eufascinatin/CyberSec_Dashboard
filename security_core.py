import time
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
import dateutil.parser

# MongoDB configuration
DB_NAME = "cybersec_db"
CENTRAL_DB_NAME = "cybersec_db_central"
TELEMETRY_COLLECTION = "telemetry_data"
AUDIT_COLLECTION = "audit_trail"
CENTRAL_AUDIT_COLLECTION = "central_audit_trail"

def get_server_settings(db_name):
    conn = sqlite3.connect("admin_config.db")
    c = conn.cursor()
    c.execute("SELECT name, enable_central_audit FROM servers WHERE db_name=?", (db_name,))
    res = c.fetchone()
    conn.close()
    if res:
        return res[0], bool(res[1])
    return db_name, False

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

def get_dashboard_settings():
    try:
        conn = sqlite3.connect("admin_config.db")
        c = conn.cursor()
        c.execute("SELECT temp_min, temp_max, temp_spike_threshold, temp_spike_window FROM dashboard_settings LIMIT 1")
        res = c.fetchone()
        conn.close()
        if res:
            return {
                "temp_min": float(res[0]),
                "temp_max": float(res[1]),
                "temp_spike_threshold": float(res[2]),
                "temp_spike_window": int(res[3])
            }
    except Exception:
        pass
    return {"temp_min": -20.0, "temp_max": 60.0, "temp_spike_threshold": 10.0, "temp_spike_window": 5}


def generate_hash(sensor_id, timestamp, temp, lat, lon):
    """Generates a SHA-256 hash representing the data's integrity."""
    data_string = f"{sensor_id}{timestamp}{temp}{lat}{lon}"
    return hashlib.sha256(data_string.encode('utf-8')).hexdigest()

def validate_telemetry(record, settings, sensor_history):
    """Validates the telemetry data for integrity and anomalies."""
    incidents = []
    
    # 1. Integrity Validation
    expected_hash = generate_hash(
        record.get("sensor_id"), 
        record.get("timestamp"), 
        record.get("temperature"), 
        record.get("gps", {}).get("lat"), 
        record.get("gps", {}).get("lon")
    )
    
    if record.get("hash") != expected_hash:
        incidents.append({
            "incident_type": "INTEGRITY_VIOLATION",
            "severity": "CRITICAL",
            "details": "Data hash mismatch detected! Potential tampering."
        })
        
    # 2. Anomaly Detection: Delayed Packet
    try:
        record_time = dateutil.parser.isoparse(record.get("timestamp"))
        if record_time.tzinfo is None:
            record_time = record_time.replace(tzinfo=timezone.utc)
            
        current_time = datetime.now(timezone.utc)
        time_difference = (current_time - record_time).total_seconds()
        
        # If delayed by more than 2 minutes (120 seconds)
        if time_difference > 120:
            incidents.append({
                "incident_type": "DELAYED_PACKET",
                "severity": "WARNING",
                "details": f"Packet delayed by {int(time_difference)} seconds."
            })
    except Exception as e:
        incidents.append({
            "incident_type": "INVALID_TIMESTAMP",
            "severity": "WARNING",
            "details": f"Could not parse timestamp: {e}"
        })
        
    # 3. Anomaly Detection: Temperature Out of Bounds
    temp = record.get("temperature", 0)
    if temp < settings["temp_min"] or temp > settings["temp_max"]:
        incidents.append({
            "incident_type": "TEMPERATURE_OUT_OF_BOUNDS",
            "severity": "WARNING",
            "details": f"Temperature {temp} is outside standard operational bounds ({settings['temp_min']} to {settings['temp_max']})."
        })
        
    # 4. Anomaly Detection: Temperature Spike
    sensor_id = record.get("sensor_id")
    record_time_str = record.get("timestamp")
    try:
        record_time = dateutil.parser.isoparse(record_time_str)
        if record_time.tzinfo is None:
            record_time = record_time.replace(tzinfo=timezone.utc)
            
        if sensor_id not in sensor_history:
            sensor_history[sensor_id] = []
            
        history = sensor_history[sensor_id]
        
        # Cleanup old history based on window
        window_ago = record_time - timedelta(minutes=settings["temp_spike_window"])
        history = [h for h in history if h[0] >= window_ago]
        
        if history:
            min_temp = min(h[1] for h in history)
            max_temp = max(h[1] for h in history)
            
            if abs(temp - min_temp) >= settings["temp_spike_threshold"] or abs(temp - max_temp) >= settings["temp_spike_threshold"]:
                incidents.append({
                    "incident_type": "TEMPERATURE_SPIKE",
                    "severity": "CRITICAL",
                    "details": f"Temperature changed by >= {settings['temp_spike_threshold']} degrees within {settings['temp_spike_window']} minutes."
                })
        
        history.append((record_time, temp))
        sensor_history[sensor_id] = history
    except Exception as e:
        pass
        
    return incidents

def log_incidents(local_db, central_db, incidents, record, server_name, enable_central_audit):
    """Logs identified incidents to the local audit_trail, and conditionally to the central DB."""
    local_audit = local_db[AUDIT_COLLECTION]
    central_audit = central_db[CENTRAL_AUDIT_COLLECTION]
    
    for incident in incidents:
        audit_log = {
            "detection_time": datetime.now(timezone.utc).isoformat(),
            "incident_type": incident["incident_type"],
            "severity": incident["severity"],
            "details": incident["details"],
            "affected_flow_id": str(record.get("_id")),
            "affected_sensor": record.get("sensor_id"),
            "original_record": record
        }
        
        # 1. Local Write
        local_audit.insert_one(audit_log)
        
        # 2. Conditional Central Write
        if enable_central_audit:
            central_log = audit_log.copy()
            central_log["source_server"] = server_name
            central_audit.insert_one(central_log)
            
        print(f"[!] INCIDENT DETECTED: {incident['severity']} - {incident['incident_type']} (Local: Yes, Central: {'Yes' if enable_central_audit else 'No'})")

import threading

def monitor_database(client, db_name, central_db):
    print(f"[{db_name}] Starting monitoring thread...")
    db = client[db_name]
    telemetry_collection = db[TELEMETRY_COLLECTION]
    
    last_processed_id = None
    latest_record = telemetry_collection.find_one(sort=[("_id", -1)])
    if latest_record:
        last_processed_id = latest_record["_id"]
        print(f"[{db_name}] Monitoring from latest record ID: {last_processed_id}")
    else:
        print(f"[{db_name}] No existing records. Monitoring from scratch.")
        
    sensor_history = {}
    try:
        while True:
            settings = get_dashboard_settings()
            query = {}
            if last_processed_id:
                query["_id"] = {"$gt": last_processed_id}
                
            new_records = list(telemetry_collection.find(query).sort("_id", 1))
            
            for record in new_records:
                incidents = validate_telemetry(record, settings, sensor_history)
                if incidents:
                    # Fetch settings dynamically in case they change
                    server_name, enable_central_audit = get_server_settings(db_name)
                    log_incidents(db, central_db, incidents, record, server_name, enable_central_audit)
                    
                last_processed_id = record["_id"]
                
            time.sleep(1)
    except Exception as e:
        print(f"[{db_name}] Thread error: {e}")

def run_security_core(target_db_name):
    print(f"Initializing Security Core SIEM for {target_db_name}...")
    mongo_uri = get_mongo_uri(target_db_name)
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        return

    central_db = client[CENTRAL_DB_NAME]
    try:
        # Block and monitor in this thread (the thread is spawned by engine_runner)
        monitor_database(client, target_db_name, central_db)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()

def main():
    if len(sys.argv) < 2:
        print("Usage: python security_core.py <target_db_name>")
        return
        
    target_db_name = sys.argv[1]
    run_security_core(target_db_name)

if __name__ == "__main__":
    main()
