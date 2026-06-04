import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

# Add local path
sys.path.append(os.getcwd())

from access_data_manager import AccessDataManager

access_path = r"c:\Users\vdominguez\OneDrive - infoplazas\AnalizadorDB by_VicTorD\AnalizaadorBD_byVicTor_por_módulo\ADA - Analizador de Datos y Actividades\ADA Nova\11-02-2026-oneroofccp.mdb"
password = "oNer00FooR3n0"
last_sync = "2000-01-01 00:00:00"

print("--- DEBUG: Inspecting for NaT/Nulls ---")

try:
    df, error = AccessDataManager.extraer_nuevos_registros(access_path, password, last_sync)
    
    if error:
        print(f"[FAIL] Error reading DB: {error}")
        sys.exit(1)
        
    print(f"[INFO] Loaded {len(df)} rows.")
    
    # 1. Check for NaT in DATETIME
    nat_count = df['DATETIME'].isna().sum()
    print(f"[CHECK] NaT/Null count in DATETIME: {nat_count}")
    
    if nat_count > 0:
        print("[FOUND] Rows with NaT in DATETIME:")
        print(df[df['DATETIME'].isna()])
        
    # 2. Check for NaN in other columns (which might be passed as param 2)
    # Param 2 in insert is USERNAME
    null_user = df['USERNAME'].isna().sum()
    print(f"[CHECK] Null count in USERNAME: {null_user}")
    
    if null_user > 0:
        print("[FOUND] Rows with Null USERNAME:")
        # Show sample
        print(df[df['USERNAME'].isna()].head())

    # 3. Simulate loop
    print("[SIMULATION] Running loop...")
    for idx, row in df.iterrows():
        try:
            # Code from SyncManager
            dt_str = row['DATETIME'].strftime("%Y-%m-%d %H:%M:%S")
            
            # Param 2 binding check: what happens if USERNAME is NaN?
            username = row['USERNAME']
            itemname = row['ITEMNAME']
            
            # Simulate what sqlite3 receives
            params = (dt_str, username, itemname)
            
            # Check specifically for numpy types that fail in sqlite
            # Start with obvious:
            if pd.isna(username):
                 pass # usually turns into None if object, or nan if float
                 
        except Exception as e:
            print(f"[CRITICAL FAIL] Loop error at index {idx}: {e}")
            print(f"Row Content: {row}")
            break
            
    print("[INFO] Simulation finished.")

except Exception as e:
    print(f"[ERROR] Script crashed: {e}")
