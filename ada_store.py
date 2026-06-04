
import sqlite3
import pyodbc
import os
import shutil
import tempfile
import logging
import datetime
import time
import pandas as pd
from contextlib import contextmanager

# Configuración de Logging
logging.basicConfig(
    filename=os.path.join(os.environ.get('APPDATA'), 'ADA_Nova', 'ada_store.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class AdaStore:
    def __init__(self, db_path=None):
        """
        Inicializa el almacén de datos SQLite.
        :param db_path: Ruta al archivo .db. Si es None, usa %APPDATA%/ADA_Nova/data/ada_cache.db
        """
        if db_path is None:
            app_data = os.environ.get('APPDATA')
            base_dir = os.path.join(app_data, "ADA_Nova", "data")
            os.makedirs(base_dir, exist_ok=True)
            self.db_path = os.path.join(base_dir, "ada_cache.db")
        else:
            self.db_path = db_path
            
        self._init_db()

    def _init_db(self):
        """Crea la estructura de tablas si no existen."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Tabla de Ventas (SALES)
                # Usamos DATETIME como pivote principal, pero agregamos un ID autoincremental local
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sales (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        datetime TIMESTAMP,
                        username TEXT,
                        itemname TEXT,
                        sync_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Índices para búsqueda rápida
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_datetime ON sales(datetime)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_username ON sales(username)")
                
                conn.commit()
        except Exception as e:
            logging.error(f"Error inicializando DB SQLite: {e}")
            print(f"Error inicializando DB SQLite: {e}")

    def get_last_sync_date(self):
        """Obtiene la fecha de la última venta registrada en SQLite."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(datetime) FROM sales")
                result = cursor.fetchone()
                if result and result[0]:
                    # SQLite a veces devuelve strings, aseguramos formato
                    return result[0]
        except Exception as e:
            logging.error(f"Error obteniendo ultima fecha: {e}")
        return "2000-01-01 00:00:00"

    def get_last_user(self):
        """
        Obtiene el último usuario registrado (equivalente a obtener_ultimo_usuario).
        Esta consulta es instantánea en SQLite.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT username FROM sales ORDER BY datetime DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    return row[0]
        except Exception as e:
            logging.error(f"Error obteniendo ultimo usuario de cache: {e}")
        return None

    def get_sales_dataframe(self, start_date, end_date):
        """
        Devuelve un DataFrame de Pandas con las ventas en el rango.
        Reemplaza a extraer_datos_rango.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT datetime as DATETIME, username as USERNAME, itemname as ITEMNAME 
                    FROM sales 
                    WHERE datetime BETWEEN ? AND ?
                    ORDER BY datetime DESC
                """
                df = pd.read_sql_query(query, conn, params=(start_date, end_date))
                # Asegurar formato datetime compatible con el resto de ADA
                df['DATETIME'] = pd.to_datetime(df['DATETIME'])
                return df, None
        except Exception as e:
            logging.error(f"Error leyendo dataframe de cache: {e}")
            return pd.DataFrame(), str(e)

    # --- LÓGICA DE SINCRONIZACIÓN SEGURA (COPY-ON_WRITE) ---
    
    def sync_from_access(self, access_path, password):
        """
        Sincroniza datos desde Access a SQLite de forma incremental.
        """
        logging.info(f"Iniciando sincronización desde: {access_path}")
        
        # 1. Preparar copia temporal de Access (SAFETY FIRST)
        temp_mdb = self._create_temp_copy(access_path)
        if not temp_mdb:
            return False, "No se pudo crear copia de seguridad del MDB"

        conn_access = None
        new_records_count = 0
        
        try:
            # 2. Conectar a Access usando pyodbc (Driver Check)
            conn_str = self._get_access_connection_string(temp_mdb, password)
            if not conn_str:
                return False, "No se encontró driver ODBC compatible"
                
            conn_access = pyodbc.connect(conn_str, autocommit=True, timeout=20)
            cursor_access = conn_access.cursor()
            
            # 3. Determinar punto de corte (Incremental)
            last_date = self.get_last_sync_date()
            logging.info(f"Última fecha en caché: {last_date}")
            
            # 4. Extraer nuevos datos
            # IMPORTANTE: Access necesita formato de fecha específico o parámetros.
            # Usamos parámetros '?' que son seguros.
            query = "SELECT DATETIME, USERNAME, ITEMNAME FROM SALES WHERE DATETIME > ? ORDER BY DATETIME ASC"
            
            # Conversión de fecha string a objeto datetime si es necesario para pyodbc
            # Pero pyodbc suele manejar strings ISO bien.
            
            cursor_access.execute(query, last_date)
            
            # 5. Insertar en SQLite por lotes
            batch_size = 1000
            rows = cursor_access.fetchmany(batch_size)
            
            with sqlite3.connect(self.db_path) as conn_lite:
                cursor_lite = conn_lite.cursor()
                
                while rows:
                    # Convertir filas a lista de tuplas para executemany
                    # Access devuelve tipos nativos (datetime.datetime), SQLite los guarda como strings o timestamp
                    data_to_insert = [(row.DATETIME, row.USERNAME, row.ITEMNAME) for row in rows]
                    
                    cursor_lite.executemany("""
                        INSERT INTO sales (datetime, username, itemname) VALUES (?, ?, ?)
                    """, data_to_insert)
                    
                    new_records_count += len(rows)
                    rows = cursor_access.fetchmany(batch_size)
                
                conn_lite.commit()
                
            logging.info(f"Sincronización completada. Nuevos registros: {new_records_count}")
            return True, f"Sincronizados {new_records_count} registros"

        except Exception as e:
            logging.error(f"Error crítico en sincronización: {e}")
            return False, str(e)
            
        finally:
            if conn_access:
                try: conn_access.close()
                except: pass
            
            # Limpiar temporal
            self._cleanup_temp(temp_mdb)

    def _create_temp_copy(self, src_path):
        try:
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, "sync_temp.mdb")
            
            # Lógica especial para OneDrive (reintentos)
            shutil.copy2(src_path, temp_path)
            return temp_path
        except Exception as e:
            logging.error(f"Error copiando MDB: {e}")
            return None

    def _cleanup_temp(self, path):
        if path and os.path.exists(path):
            try:
                os.remove(path)
                os.rmdir(os.path.dirname(path))
            except: pass

    def _get_access_connection_string(self, db_path, password):
        drivers = pyodbc.drivers()
        driver = next((d for d in drivers if 'Access' in d and 'mdb' in d.lower()), None)
        if not driver:
            return None
            
        return f"DRIVER={{{driver}}};DBQ={db_path};PWD={password};"

if __name__ == "__main__":
    # Modo CLI para pruebas o ejecución subprocess
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--sync":
        # python ada_store.py --sync "path/to/db.mdb" "password"
        if len(sys.argv) < 4:
            print("Uso: ada_store.py --sync <db_path> <password>")
            sys.exit(1)
            
        store = AdaStore()
        success, msg = store.sync_from_access(sys.argv[2], sys.argv[3])
        print(f"SYNC_RESULT: {success}|{msg}")
    else:
        print("Módulo de Almacenamiento ADA (SQLite Backend)")
