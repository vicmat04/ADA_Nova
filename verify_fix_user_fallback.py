import os
import sys

# Add local path
sys.path.append(os.getcwd())

# 1. Setup DB Name BEFORE importing items that might instantiate it
from database_manager import DatabaseManager
DatabaseManager.DB_NAME = "verify_fallback.db"

# Force cleanup of existing instance if any
if DatabaseManager._instance:
    DatabaseManager._instance = None

# 2. Now import SyncManager
from sync_manager import SyncManager
# And AccessDataManager
from access_data_manager import AccessDataManager

# 3. Instantiate DB (singleton)
db = DatabaseManager()
db.init_db()

# 4. Patch SyncManager's db reference just in case it grabbed an old one
import sync_manager
sync_manager.db = db

# ----------------
access_path = r"c:\Users\vdominguez\OneDrive - infoplazas\AnalizadorDB by_VicTorD\AnalizaadorBD_byVicTor_por_módulo\ADA - Analizador de Datos y Actividades\ADA Nova\11-02-2026-oneroofccp.mdb"
password = "oNer00FooR3n0"

print("--- VERIFYING USERNAME FALLBACK FIX (RETRY) ---")

# 1. Reset
print("Resetting data...")
conn = db.get_connection()
conn.execute("DELETE FROM registros_ventas_cache")
conn.execute("DELETE FROM sync_state WHERE key = 'last_access_sync_timestamp'")
conn.commit()
conn.close()

# 2. Check sync state explicitly
state = db.get_sync_state("last_access_sync_timestamp")
print(f"[DEBUG] State before sync: {state}")

# 3. Check last user in DB
last_user = AccessDataManager.obtener_ultimo_usuario(access_path, password)
print(f"[CHECK] Last user in DB: {last_user}")

# 4. Initialize Manager and Run Sync
manager = SyncManager(access_path, password)

print("[ACTION] Running sync_access_incremental()...")
inserted, error = manager.sync_access_incremental()

if error:
    print(f"[FAIL] Error: {error}")
else:
    print(f"[SUCCESS] Inserted: {inserted}")
    
    # Verify Data
    rows = db.execute_query("SELECT COUNT(*) as c FROM registros_ventas_cache WHERE username IS NULL OR username = '' OR username = 'None' OR username = 'nan'")
    null_count = rows[0]['c']
    
    # Verify Fallback Usage
    # We suspect ~89 rows had nulls.
    rows_fallback = db.execute_query(f"SELECT COUNT(*) as c FROM registros_ventas_cache WHERE username = '{last_user}'")
    fallback_count = rows_fallback[0]['c']

    print(f"[VERIFY] Rows with NULL/Empty/None Username: {null_count}")
    print(f"[VERIFY] Rows with Active User '{last_user}': {fallback_count}")
    
    if null_count == 0:
        print("[PASS] No null usernames found.")
    else:
        print(f"[FAIL] Found {null_count} null usernames.")

# Cleanup
try: 
    db.close()
    os.remove(db.db_path)
except: pass
