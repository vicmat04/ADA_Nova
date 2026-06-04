import os
import sys
import pandas as pd
import numpy as np

# Add local path
sys.path.append(os.getcwd())

from access_data_manager import AccessDataManager

access_path = r"c:\Users\vdominguez\OneDrive - infoplazas\AnalizadorDB by_VicTorD\AnalizaadorBD_byVicTor_por_módulo\ADA - Analizador de Datos y Actividades\ADA Nova\11-02-2026-oneroofccp.mdb"
password = "oNer00FooR3n0"
last_sync = "2000-01-01 00:00:00"

print("--- DEBUG 2: Type Inspection ---")

try:
    df, error = AccessDataManager.extraer_nuevos_registros(access_path, password, last_sync)
    
    if error:
        print(f"Error loading data: {error}")
        sys.exit(1)

    print(f"Loaded {len(df)} rows.")

    # Check types of ALL columns in the first row with nulls
    null_rows = df[df.isnull().any(axis=1)]
    
    if not null_rows.empty:
        print(f"Found {len(null_rows)} rows with nulls.")
        idx = null_rows.index[0]
        row = df.loc[idx]
        
        print(f" inspecting row {idx}:")
        for col in df.columns:
            val = row[col]
            print(f"  Col: {col} | Val: {repr(val)} | Type: {type(val)}")
            
            # Explicit check for NaTType
            if "NaTType" in str(type(val)):
                print(f"  !!! FOUND NaTType in column {col} !!!")
                
    else:
        print("No null rows found (unexpected given previous run).")

except Exception as e:
    print(f"Error: {e}")
