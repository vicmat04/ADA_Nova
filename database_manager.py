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
                username TEXT PRIMARY KEY,
                sex TEXT
            );
            """,

            # 6. Informe Cuatrimestral Header (SQLite Local)
            """
            CREATE TABLE IF NOT EXISTS informe_cuatrimestral_header (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                infoplaza_id TEXT NOT NULL,
                anio INTEGER NOT NULL,
                cuatrimestre INTEGER NOT NULL,
                cant_computadoras INTEGER DEFAULT 6,
                asociado_nombre TEXT,
                asociado_cedula TEXT,
                dinamizador_nombre TEXT,
                dinamizador_cedula TEXT,
                observaciones_generales TEXT,
                updated_at TEXT,
                UNIQUE(infoplaza_id, anio, cuatrimestre)
            );
            """,

            # 7. Informe Capacitaciones (SQLite Local)
            """
            CREATE TABLE IF NOT EXISTS informe_capacitaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                infoplaza_id TEXT NOT NULL,
                anio INTEGER NOT NULL,
                cuatrimestre INTEGER NOT NULL,
                mes TEXT NOT NULL,
                tema TEXT NOT NULL,
                participantes INTEGER DEFAULT 0,
                horas REAL DEFAULT 0,
                observaciones TEXT,
                orden INTEGER DEFAULT 0
            );
            """,

            # 8. Informe Servicios (SQLite Local)
            """
            CREATE TABLE IF NOT EXISTS informe_servicios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                infoplaza_id TEXT NOT NULL,
                anio INTEGER NOT NULL,
                cuatrimestre INTEGER NOT NULL,
                servicio_nombre TEXT NOT NULL,
                ofrecido INTEGER DEFAULT 1,
                es_personalizado INTEGER DEFAULT 0,
                observaciones TEXT
            );
            """,

            # 9. Informe Otras Actividades (SQLite Local)
            """
            CREATE TABLE IF NOT EXISTS informe_otras_actividades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                infoplaza_id TEXT NOT NULL,
                anio INTEGER NOT NULL,
                cuatrimestre INTEGER NOT NULL,
                categoria TEXT,
                actividad TEXT NOT NULL,
                participantes INTEGER DEFAULT 0,
                observaciones TEXT,
                orden INTEGER DEFAULT 0
            );
            """,

            # 10. Catálogo de Categorías (SQLite Local)
            """
            CREATE TABLE IF NOT EXISTS catalogo_categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                nombre TEXT NOT NULL,
                descripcion TEXT,
                activo INTEGER DEFAULT 1,
                orden INTEGER DEFAULT 0,
                UNIQUE(tipo, nombre)
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
        
        # Migraciones y Sembrado
        self._migrar_id_access()
        self._migrar_useraccount_sex()
        self._migrar_informe_cuatrimestral_categorias()
        self._sembrar_catalogo_categorias_inicial()


    def get_informe_cuatrimestral_local(self, infoplaza_id: str, anio: int, cuatrimestre: int) -> Dict[str, Any]:
        """Recupera la cabecera, capacitaciones, servicios y actividades guardadas localmente."""
        hdr_rows = self.execute_query(
            "SELECT * FROM informe_cuatrimestral_header WHERE infoplaza_id = ? AND anio = ? AND cuatrimestre = ?",
            (str(infoplaza_id), int(anio), int(cuatrimestre))
        )
        header = dict(hdr_rows[0]) if hdr_rows else None

        cap_rows = self.execute_query(
            "SELECT * FROM informe_capacitaciones WHERE infoplaza_id = ? AND anio = ? AND cuatrimestre = ? ORDER BY orden ASC",
            (str(infoplaza_id), int(anio), int(cuatrimestre))
        )
        capacitaciones = [dict(r) for r in cap_rows]

        srv_rows = self.execute_query(
            "SELECT * FROM informe_servicios WHERE infoplaza_id = ? AND anio = ? AND cuatrimestre = ?",
            (str(infoplaza_id), int(anio), int(cuatrimestre))
        )
        servicios = [dict(r) for r in srv_rows]

        act_rows = self.execute_query(
            "SELECT * FROM informe_otras_actividades WHERE infoplaza_id = ? AND anio = ? AND cuatrimestre = ? ORDER BY orden ASC",
            (str(infoplaza_id), int(anio), int(cuatrimestre))
        )
        otras_actividades = [dict(r) for r in act_rows]

        return {
            "header": header,
            "capacitaciones": capacitaciones,
            "servicios": servicios,
            "otras_actividades": otras_actividades
        }

    def save_informe_cuatrimestral_local(
        self,
        infoplaza_id: str,
        anio: int,
        cuatrimestre: int,
        header_data: Dict[str, Any],
        capacitaciones: List[Dict[str, Any]],
        servicios: List[Dict[str, Any]],
        otras_actividades: List[Dict[str, Any]]
    ) -> bool:
        """Guarda localmente en SQLite el informe cuatrimestral completo."""
        conn = self.get_connection()
        try:
            timestamp = datetime.now().isoformat()
            
            # 1. Header Upsert
            conn.execute("""
                INSERT INTO informe_cuatrimestral_header 
                (infoplaza_id, anio, cuatrimestre, cant_computadoras, asociado_nombre, asociado_cedula, dinamizador_nombre, dinamizador_cedula, observaciones_generales, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(infoplaza_id, anio, cuatrimestre) DO UPDATE SET
                    cant_computadoras = excluded.cant_computadoras,
                    asociado_nombre = excluded.asociado_nombre,
                    asociado_cedula = excluded.asociado_cedula,
                    dinamizador_nombre = excluded.dinamizador_nombre,
                    dinamizador_cedula = excluded.dinamizador_cedula,
                    observaciones_generales = excluded.observaciones_generales,
                    updated_at = excluded.updated_at
            """, (
                str(infoplaza_id), int(anio), int(cuatrimestre),
                int(header_data.get('cant_computadoras', 6)),
                header_data.get('asociado_nombre', ''),
                header_data.get('asociado_cedula', ''),
                header_data.get('dinamizador_nombre', ''),
                header_data.get('dinamizador_cedula', ''),
                header_data.get('observaciones_generales', ''),
                timestamp
            ))

            # 2. Capacitaciones
            conn.execute("DELETE FROM informe_capacitaciones WHERE infoplaza_id = ? AND anio = ? AND cuatrimestre = ?", (str(infoplaza_id), int(anio), int(cuatrimestre)))
            for idx, cap in enumerate(capacitaciones, start=1):
                conn.execute("""
                    INSERT INTO informe_capacitaciones (infoplaza_id, anio, cuatrimestre, mes, categoria, tema, participantes, horas, observaciones, orden)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(infoplaza_id), int(anio), int(cuatrimestre),
                    cap.get('mes', ''), cap.get('categoria', ''), cap.get('tema', ''),
                    int(cap.get('participantes', 0)), float(cap.get('horas', 0)),
                    cap.get('observaciones', ''), idx
                ))

            # 3. Servicios
            conn.execute("DELETE FROM informe_servicios WHERE infoplaza_id = ? AND anio = ? AND cuatrimestre = ?", (str(infoplaza_id), int(anio), int(cuatrimestre)))
            for srv in servicios:
                conn.execute("""
                    INSERT INTO informe_servicios (infoplaza_id, anio, cuatrimestre, servicio_nombre, ofrecido, es_personalizado, observaciones)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(infoplaza_id), int(anio), int(cuatrimestre),
                    srv.get('servicio_nombre', ''),
                    1 if srv.get('ofrecido', True) else 0,
                    1 if srv.get('es_personalizado', False) else 0,
                    srv.get('observaciones', '')
                ))

            # 4. Otras Actividades
            conn.execute("DELETE FROM informe_otras_actividades WHERE infoplaza_id = ? AND anio = ? AND cuatrimestre = ?", (str(infoplaza_id), int(anio), int(cuatrimestre)))
            for idx, act in enumerate(otras_actividades, start=1):
                conn.execute("""
                    INSERT INTO informe_otras_actividades (infoplaza_id, anio, cuatrimestre, categoria, actividad, participantes, observaciones, orden)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(infoplaza_id), int(anio), int(cuatrimestre),
                    act.get('categoria', ''), act.get('actividad', ''),
                    int(act.get('participantes', 0)), act.get('observaciones', ''), idx
                ))

            conn.commit()
            return True
        except Exception as e:
            print(f"[DB_LOCAL] Error guardando informe cuatrimestral: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def _migrar_informe_cuatrimestral_categorias(self):
        """Añade las columnas categoria y participantes si no existen en informe_capacitaciones e informe_otras_actividades."""
        conn = self.get_connection()
        try:
            # 1. informe_capacitaciones: categoria
            cursor = conn.execute("PRAGMA table_info(informe_capacitaciones)")
            cols_cap = [row['name'] for row in cursor.fetchall()]
            if 'categoria' not in cols_cap:
                print("[DB_LOCAL] Migrando: Añadiendo columna categoria a informe_capacitaciones...")
                conn.execute("ALTER TABLE informe_capacitaciones ADD COLUMN categoria TEXT")

            # 2. informe_otras_actividades: categoria, participantes
            cursor = conn.execute("PRAGMA table_info(informe_otras_actividades)")
            cols_act = [row['name'] for row in cursor.fetchall()]
            if 'categoria' not in cols_act:
                print("[DB_LOCAL] Migrando: Añadiendo columna categoria a informe_otras_actividades...")
                conn.execute("ALTER TABLE informe_otras_actividades ADD COLUMN categoria TEXT")
            if 'participantes' not in cols_act:
                print("[DB_LOCAL] Migrando: Añadiendo columna participantes a informe_otras_actividades...")
                conn.execute("ALTER TABLE informe_otras_actividades ADD COLUMN participantes INTEGER DEFAULT 0")

            conn.commit()
        except Exception as e:
            print(f"[DB_LOCAL] Error en migración de categorías: {e}")
            conn.rollback()
        finally:
            conn.close()

    def _sembrar_catalogo_categorias_inicial(self):
        """Siembra las categorías base por defecto si el catálogo está vacío."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("SELECT COUNT(*) as total FROM catalogo_categorias")
            row = cursor.fetchone()
            if row and row['total'] == 0:
                print("[DB_LOCAL] Sembrando catálogo inicial de categorías...")
                initial_cats = [
                    ('CAPACITACION', 'Computación Básica', 'Aprender a usar la PC, correo e internet', 1, 1),
                    ('CAPACITACION', 'Ofimática', 'Manejo de Word, Excel y presentaciones', 1, 2),
                    ('CAPACITACION', 'Tecnología e IA', 'Programación, robótica, redes e inteligencia artificial', 1, 3),
                    ('CAPACITACION', 'Diseño y Multimedia', 'Edición de fotos, video y redes sociales', 1, 4),
                    ('CAPACITACION', 'Emprendimiento', 'Ventas, finanzas y administración de negocios', 1, 5),
                    ('CAPACITACION', 'Refuerzo Escolar', 'Tutorías, tareas e investigación estudiantil', 1, 6),
                    ('CAPACITACION', 'Oficios Prácticos', 'Reparación de PCs, electricidad o artesanías', 1, 7),
                    ('ACTIVIDAD', 'Ferias y Exposiciones', 'Muestras tecnológicas, comunitarias o de empleo', 1, 1),
                    ('ACTIVIDAD', 'Reuniones y Asambleas', 'Encuentros de vecinos, directivas o instituciones', 1, 2),
                    ('ACTIVIDAD', 'Cine y Recreación', 'Proyección de películas, torneos o lectura', 1, 3),
                    ('ACTIVIDAD', 'Trámites Ciudadanos', 'Ayuda a la gente con impresiones y trámites web', 1, 4),
                    ('ACTIVIDAD', 'Charlas de Salud y Ambiente', 'Prevención médica, reciclaje y seguridad', 1, 5),
                    ('ACTIVIDAD', 'Soporte y Mantenimiento', 'Jornadas de revisión de equipos e inventario', 1, 6),
                ]
                conn.executemany("""
                    INSERT OR IGNORE INTO catalogo_categorias (tipo, nombre, descripcion, activo, orden)
                    VALUES (?, ?, ?, ?, ?)
                """, initial_cats)
                conn.commit()
        except Exception as e:
            print(f"[DB_LOCAL] Error en sembrado de catálogo: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_catalogo_categorias_local(self, tipo: str = None) -> List[Dict[str, Any]]:
        """Obtiene las categorías guardadas en SQLite filtradas por tipo ('CAPACITACION' o 'ACTIVIDAD')."""
        if tipo:
            rows = self.execute_query("SELECT * FROM catalogo_categorias WHERE tipo = ? ORDER BY orden ASC, nombre ASC", (tipo,))
        else:
            rows = self.execute_query("SELECT * FROM catalogo_categorias ORDER BY tipo ASC, orden ASC, nombre ASC")
        return [dict(r) for r in rows]

    def save_catalogo_categorias_batch_local(self, categorias: List[Dict[str, Any]]) -> bool:
        """Guarda/actualiza un lote de categorías en la BD local SQLite haciendo UPSERT por (tipo, nombre)."""
        conn = self.get_connection()
        try:
            for cat in categorias:
                tipo     = cat.get('tipo', 'CAPACITACION')
                nombre   = str(cat.get('nombre', '')).strip()
                desc     = str(cat.get('descripcion', '')).strip()
                activo   = 1 if cat.get('activo', True) else 0
                orden    = int(cat.get('orden', 0))

                conn.execute("""
                    INSERT INTO catalogo_categorias (tipo, nombre, descripcion, activo, orden)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(tipo, nombre) DO UPDATE SET
                        descripcion = excluded.descripcion,
                        activo      = excluded.activo,
                        orden       = excluded.orden
                """, (tipo, nombre, desc, activo, orden))

            conn.commit()
            return True
        except Exception as e:
            print(f"[DB_LOCAL] Error guardando catálogo local: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()


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

    def _migrar_useraccount_sex(self):
        """Añade la columna sex a useraccount_cache si no existe."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("PRAGMA table_info(useraccount_cache)")
            columns = [row['name'] for row in cursor.fetchall()]
            
            if 'sex' not in columns:
                print("[DB_LOCAL] Migrando: Añadiendo columna sex a useraccount_cache...")
                conn.execute("ALTER TABLE useraccount_cache ADD COLUMN sex TEXT")
                conn.commit()
        except Exception as e:
            print(f"[DB_LOCAL] Error en migración de useraccount_sex: {e}")
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

            # 2. Borrar tablas de informe cuatrimestral para un consumo 100% limpio
            conn.execute("DELETE FROM informe_cuatrimestral_header")
            conn.execute("DELETE FROM informe_capacitaciones")
            conn.execute("DELETE FROM informe_servicios")
            conn.execute("DELETE FROM informe_otras_actividades")
            
            # 3. Borrar AMBOS estados de sync para forzar escaneo completo desde cero
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
