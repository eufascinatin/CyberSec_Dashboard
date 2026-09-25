import sqlite3
import threading
import time
import sys

import simulator
import security_core

DB_FILE = "admin_config.db"

def get_active_servers():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT db_name FROM servers WHERE is_active = 1")
        servers = [row[0] for row in c.fetchall()]
        conn.close()
        return servers
    except Exception as e:
        print(f"Error reading from {DB_FILE}: {e}")
        return []

def main():
    print("Starting Engine Runner (Multithreaded)...")
    active_servers = get_active_servers()
    
    if not active_servers:
        print("No active servers found. Exiting.")
        return
        
    print(f"Found {len(active_servers)} active servers: {', '.join(active_servers)}")
    
    threads = []
    
    for db_name in active_servers:
        print(f"Spawning simulator and security core threads for {db_name}...")
        
        # Spawn simulator thread
        sim_thread = threading.Thread(target=simulator.main, args=(db_name,), daemon=True)
        sim_thread.start()
        threads.append(sim_thread)
        
        # Spawn security core thread
        sec_thread = threading.Thread(target=security_core.run_security_core, args=(db_name,), daemon=True)
        sec_thread.start()
        threads.append(sec_thread)
        
    print("All engine threads spawned. Press Ctrl+C to terminate.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEngine Runner stopped by user. Threads will terminate automatically.")

if __name__ == "__main__":
    main()
