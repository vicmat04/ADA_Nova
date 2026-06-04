"""
Módulo de Gestión de Base de Datos Local (SQLite)
=================================================

Este módulo gestiona la base de datos local `ada_local.db` que actúa como
fuente única de verdad para la aplicación, almacenando datos de:
1. Metas (Sincronizado desde Google Sheets)
2. Ventas y Actividades (Caché sincronizado desde Access)
3. Información de Infoplazas

Evita problemas de concurrencia y dependencia de internet.
"""

import sqlite3
import os
import sys
from datetime import datetime
import threading
from typing import List, Dict, Any, Optional, Tuple

class DatabaseManager:
    """
    Gestor Singleton para la base de datos SQLite.
    Garantiza inicialización correcta y acceso seguro a datos.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    DB_NAME = "ada_local.db"
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.db_path = self._get_db_path()
        self.init_db()
        self._initialized = True
        print(f"[DB_LOCAL] Base de datos inicializada en: {self.db_path}")

    def _get_db_path(self) -> str:
        """Determina la ruta persistente para la BD en AppData."""
        app_data = os.environ.get('APPDATA')
        if not app_data:
            app_data = os.path.expanduser("~")
        
        base_dir = os.path.join(app_data, "ADA_Nova")
        os.makedirs(base_dir, exist_ok=True)
        
        return os.path.join(base_dir, self.DB_NAME)

    def get_connection(self) -> sqlite3.Connection:
        """Retorna una nueva conexión configurada."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        # Habilitar Row Factory para acceder a columnas por nombre
        conn.row_factory = sqlite3.Row
        # Habilitar Foreign Keys
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        """Crea las tablas necesarias si no existen."""
        create_tables_sql = [
            # 1. Tabla de Infoplazas
            """
            CREATE TABLE IF NOT EXISTS infoplazas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                infoplaza_id TEXT UNIQUE NOT NULL,
                nombre TEXT,
                regional TEXT,
                provincia TEXT,
                updated_at TEXT
            );
            """,
            
            # 2. Tabla de Metas Mensuales
            """
            CREATE TABLE IF NOT EXISTS metas_mensuales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                infoplaza_id TEXT NOT NULL,
                mes INTEGER NOT NULL,
                anio INTEGER NOT NULL,
                actividad TEXT NOT NULL,
                valor REAL DEFAULT 0,
                meta REAL DEFAULT 0,
                cumplimiento REAL DEFAULT 0,
                updated_at TEXT,
                UNIQUE(infoplaza_id, mes, anio, actividad)
            );
            """,
            
            # 3. Cache de Ventas (Desde Access)
            """
            CREATE TABLE IF NOT EXISTS registros_ventas_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                access_id INTEGER,
                datetime TEXT NOT NULL,
                username TEXT,
                itemname TEXT,
                sync_timestamp TEXT,
                UNIQUE(datetime, username, itemname)
            );
            """,
            
            # 4. Estado de Sincronización y Configuración
            """
            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                timestamp TEXT
            );
            """,
            
            # 5. Cache de Cuentas de Usuario (Desde Access)
            """
            CREATE TABLE IF NOT EXISTS useraccount_cache (
                username TEXT PRIMARY KEY
            );
            """
        ]
        
        conn = self.get_connection()
        try:
            for sql in create_tables_sql:
                conn.execute(sql)
            conn.commit()
        finally:
            conn.close()
        
        # Migración: Asegurar que la columna access_id existe en registros_ventas_cache
        self._migrar_id_access()

    def _migrar_id_access(self):
        """Añade la columna access_id si no existe (Migración v4.0.2)."""
        conn = self.get_connection()
        try:
            # Verificar si la columna ya existe
            cursor = conn.execute("PRAGMA table_info(registros_ventas_cache)")
            columns = [row['name'] for row in cursor.fetchall()]
            
            if 'access_id' not in columns:
                print("[DB_LOCAL] Migrando: Añadiendo columna access_id...")
                conn.execute("ALTER TABLE registros_ventas_cache ADD COLUMN access_id INTEGER")
                conn.commit()
                print("[DB_LOCAL] Migración completada.")
        except Exception as e:
            print(f"[DB_LOCAL] Error en migración: {e}")
            conn.rollback()
        finally:
            conn.close()

    # =========================================================================
    # MÉTODOS DE UTILIDAD GENERAL
    # =========================================================================

    def execute_query(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Ejecuta una consulta SELECT y retorna resultados."""
        conn = self.get_connection()
        try:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            print(f"[DB_LOCAL] Error en execute_query: {e} | Query: {query}")
            return []
        finally:
            conn.close()

    def execute_non_query(self, query: str, params: tuple = ()) -> int:
        """Ejecuta INSERT/UPDATE/DELETE y retorna filas afectadas."""
        conn = self.get_connection()
        try:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            print(f"[DB_LOCAL] Error en execute_non_query: {e} | Query: {query}")
            conn.rollback()
            return -1
        finally:
            conn.close()

    def upsert_sync_state(self, key: str, value: str):
        """Actualiza el estado de sincronización (ej: 'last_access_sync')."""
        timestamp = datetime.now().isoformat()
        query = """
            INSERT INTO sync_state (key, value, timestamp) 
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                timestamp = excluded.timestamp
        """
        self.execute_non_query(query, (key, value, timestamp))

    def get_sync_state(self, key: str) -> Optional[str]:
        """Obtiene un valor de estado de sincronización."""
        rows = self.execute_query("SELECT value FROM sync_state WHERE key = ?", (key,))
        if rows:
            return rows[0]['value']
        return None

    def reset_sync_data(self):
        """
        Reinicia totalmente el cache de ventas y el estado de sincronización.
        Útil cuando se cambia de base de datos origen para evitar mezcla de datos.
        """
        print(f"[DB_LOCAL] Resetting sync data...")
        conn = self.get_connection()
        try:
            # 1. Borrar datos de ventas
            cursor = conn.execute("DELETE FROM registros_ventas_cache")
            rows_deleted = cursor.rowcount
            
            # 2. Borrar AMBOS estados de sync para forzar escaneo completo desde cero
            # CRÍTICO: Borrar también last_access_sync_id, si no se deja el puntero
            # de la BD anterior y el sync incremental nunca encuentra registros nuevos.
            conn.execute(
                "DELETE FROM sync_state WHERE key IN "
                "('last_access_sync_timestamp', 'last_access_sync_id')"
            )
            
            conn.commit()
            
            # 3. Forzar checkpoint para asegurar que el archivo se reduzca/limpie
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            
            print(f"[DB_LOCAL] CACHE ELIMINADO. Filas borradas: {rows_deleted}")
            return True
        except Exception as e:
            print(f"[DB_LOCAL] Error reseteando cache: {e}")
            conn.rollback()
            return False

    def check_and_apply_version_migration(self, current_version: str):
        """
        Verifica si la versión de la aplicación ha cambiado y, si es así,
        realiza las migraciones o reseteos necesarios.
        """
        last_version = self.get_sync_state('app_version')
        
        if last_version != current_version:
            print(f"[DB_LOCAL] Cambio de versión detectado: {last_version} -> {current_version}")
            
            # En este caso, como agregamos access_id, el reseteo es obligatorio
            # para asegurar que todos los registros se vuelvan a descargar con su ID.
            print("[DB_LOCAL] Ejecutando reseteo de caché preventivo por actualización...")
            self.reset_sync_data()
            
            # Actualizar la versión guardada
            self.upsert_sync_state('app_version', current_version)
            print(f"[DB_LOCAL] Versión actualizada a {current_version} en base de datos.")
        else:
            print(f"[DB_LOCAL] Versión coincide ({current_version}). No se requiere migración.")


# Instancia global para uso fácil
db = DatabaseManager()
