"""
Módulo de Sincronización de Datos
=================================

Este módulo coordinar la sincronización de datos entre las fuentes externas
(Google Sheets, BD Access) y la base de datos local SQLite.

Funcionalidades:
- Sincronización incremental desde Access (Solo nuevos registros).
- Sincronización completa/parcial desde Google Sheets.
- Actualización de estados de sincronización.
"""

from datetime import datetime
import pandas as pd
from typing import Tuple, Optional

from database_manager import db
from access_data_manager import AccessDataManager

class SyncManager:
    """Clase principal para gestionar la sincronización de datos."""

    def __init__(self, access_db_path: str, access_db_password: str):
        self.access_db_path = access_db_path
        self.access_db_password = access_db_password

    # =========================================================================
    # SINCRONIZACIÓN DE ACCESS
    # =========================================================================

    def sync_access_incremental(self) -> Tuple[int, Optional[str]]:
        """
        Sincroniza los registros de ventas de Access a SQLite usando el ID autoincremental.
        
        Returns:
            Tuple[int, str]: (Registros insertados, Mensaje error si hubo)
        """
        try:
            # 1. Obtener último ID de sincronización
            last_id_str = db.get_sync_state("last_access_sync_id")
            last_id = int(last_id_str) if last_id_str else 0
            
            # Fallback: Si no hay ID en el estado, buscamos el máximo en el cache local
            if last_id == 0:
                rows = db.execute_query("SELECT MAX(access_id) as max_id FROM registros_ventas_cache")
                if rows and rows[0]['max_id']:
                    last_id = int(rows[0]['max_id'])

            print(f"[SYNC ACCESS] Buscando registros con ID superior a: {last_id}")
            
            # 2. Obtener datos nuevos desde Access
            df_new, error = AccessDataManager.extraer_nuevos_registros(
                self.access_db_path, 
                self.access_db_password, 
                last_id
            )
            
            if error:
                return 0, f"Error leyendo Access: {error}"
            
            if df_new is None or df_new.empty:
                print("[SYNC ACCESS] No hay registros nuevos por ID.")
                return 0, None

            # --- SANITIZACIÓN Y CORRECCIÓN DE DATOS ---
            df_new = df_new.dropna(subset=['DATETIME'])
            
            fallback_user = AccessDataManager.obtener_ultimo_usuario(self.access_db_path, self.access_db_password)
            if not fallback_user:
                fallback_user = "Usuario Desconocido"

            df_new['USERNAME'] = df_new['USERNAME'].fillna(fallback_user)
            df_new['ITEMNAME'] = df_new['ITEMNAME'].fillna("") 

            count = len(df_new)
            print(f"[SYNC ACCESS] Procesando {count} registros (IDs: {df_new['ID'].min()} a {df_new['ID'].max()})")
            
            # 3. Guardar en SQLite
            conn = db.get_connection()
            try:
                rows_to_insert = []
                max_id_in_batch = last_id
                
                for _, row in df_new.iterrows():
                    dt_val = row['DATETIME']
                    if pd.isna(dt_val): continue 

                    dt_str = dt_val.strftime("%Y-%m-%d %H:%M:%S")
                    
                    access_id = int(row['ID'])
                    username = str(row['USERNAME']) if not pd.isna(row['USERNAME']) else fallback_user
                    itemname = str(row['ITEMNAME']) if not pd.isna(row['ITEMNAME']) else ""

                    rows_to_insert.append((
                        access_id,
                        dt_str,
                        username,
                        itemname,
                        datetime.now().isoformat()
                    ))
                    if access_id > max_id_in_batch:
                        max_id_in_batch = access_id
                
                sql = """
                    INSERT OR IGNORE INTO registros_ventas_cache 
                    (access_id, datetime, username, itemname, sync_timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """
                
                cursor = conn.executemany(sql, rows_to_insert)
                inserted = cursor.rowcount
                conn.commit()
                
                print(f"[SYNC ACCESS] Insertados {inserted} nuevos registros por ID.")
                
                # 4. Actualizar estado de sync con el ID máximo procesado
                db.upsert_sync_state("last_access_sync_id", str(max_id_in_batch))
                
                # Opcional: También actualizar el timestamp por compatibilidad/referencia
                if not df_new.empty:
                    last_dt = df_new['DATETIME'].iloc[-1].strftime("%Y-%m-%d %H:%M:%S")
                    db.upsert_sync_state("last_access_sync_timestamp", last_dt)
                
                return inserted, None
                
            except Exception as e:
                conn.rollback()
                return 0, f"Error escribiendo en SQLite: {e}"
            finally:
                conn.close()

        except Exception as e:
            return 0, f"Error general en sync_access: {e}"

    # =========================================================================
    # SINCRONIZACIÓN DE METAS (SHEETS)
    # =========================================================================

    def save_metas_to_sqlite(self, data: dict, infoplaza_id: str) -> bool:
        """
        Guarda los datos de metas descargados de Google Sheets en local.
        Data format esperado: Diccionario procesado por MetasCalculator.
         { 
           'Metas': [...], 
           'Totales': {...},
           ...
         }
        Pero idealmente necesitamos la data cruda o semi-procesada por mes.
        
        Para esta fase, asumiremos que recibimos una lista de objetos/dicts
        que representan las filas de metas.
        """
        # TODO: Implementar guardado de metas
        # Esto requerirá adaptar el output de GoogleSheetsWorker para que sea compatible.
        pass
