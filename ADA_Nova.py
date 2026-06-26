import sys
import os
import datetime
import traceback
import faulthandler

# --- DEBUGGING: BOOT LOGGER & FAULTHANDLER (MODO SEGURO) ---
# Esto se ejecuta antes de cualquier otra librería para capturar errores de carga (DLLs, Imports)
# y fallos graves de memoria (Segmentation Faults).
try:
    # 1. Definir ruta de logs segura (AppData)
    app_data = os.environ.get('APPDATA')
    if not app_data:
        app_data = os.path.expanduser("~") # Fallback a home
        
    log_dir = os.path.join(app_data, "ADA_Nova", "Infoplazas", "Logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # 2. Activar Faulthandler para crashes de C/C++
    crash_dump_path = os.path.join(log_dir, "ada_crash_dump.log")
    fs_crash = open(crash_dump_path, "a", encoding="utf-8")
    
    # Escribir marca de tiempo de inicio de sesión para referencia en caso de crash duro
    fs_crash.write(f"\n[{datetime.datetime.now()}] --- SESIÓN DE ADA NOVA INICIADA ---\n")
    fs_crash.flush()
    
    faulthandler.enable(file=fs_crash)
    
    # 3. Redirigir STDOUT y STDERR a archivo (boot log)
    # Esto captura errores de importación que sys.excepthook no ve porque ocurren antes.
    boot_log_path = os.path.join(log_dir, "ada_boot.log")
    
    class TeeLogger:
        """Redirige la salida a un archivo y mantiene la original si es posible."""
        def __init__(self, filename, stream):
            self.terminal = stream
            self.log = open(filename, "a", encoding="utf-8")
        def write(self, message):
            try:
                self.log.write(message)
                self.log.flush()
                if self.terminal:
                   self.terminal.write(message)
                   self.terminal.flush()
            except: pass
        def flush(self):
            try:
                self.log.flush()
            except: pass
            
    sys.stdout = TeeLogger(boot_log_path, sys.stdout)
    sys.stderr = TeeLogger(boot_log_path, sys.stderr)
    
    print(f"\n[{datetime.datetime.now()}] --- INICIO DE BOOT DE ADA NOVA ---")
    print(f"[{datetime.datetime.now()}] Python Version: {sys.version}")
    print(f"[{datetime.datetime.now()}] Platform: {sys.platform}")
    print(f"[{datetime.datetime.now()}] Executable: {sys.executable}")
    
except Exception as e:
    # Si falla el sistema de logs, intentamos dejar una nota de suicidio local
    try:
        with open("ada_FATAL_BOOT.txt", "w") as f:
            f.write(f"Error iniciando logger: {e}")
    except: pass
# -----------------------------------------------------------

import ssl
import socket
import numpy as np
import re
import shutil
import tempfile
import secrets

import random
from urllib.parse import urlparse
import requests 

# --- PARCHE GLOBAL PARA CERTIFICADOS SSL (Equipos con certificados desactualizados) ---
try:
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
    # Desactivar advertencias de InsecureRequestWarning en requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except Exception as e:
    print(f"[SSL Patch] No se pudo aplicar el parche global: {e}")
# --------------------------------------------------------------------------------------
import subprocess # Para ejecutar el script .bat
from facebook_module import FacebookAnalyzerWidget
from metas_card_module import MetasCardWidget, MetasTableView
from novedades_manager import NovedadesManager
from novedades_ui import NovedadesWindow, SingleEventWindow
#..Importaciones para las cámaras de vigilancia...#
import platform
import gspread
from oauth2client.service_account import ServiceAccountCredentials

import base64
import json

import urllib.request  # <-- para el bloqueo
import time            # <-- para el bloqueo

# Coloca esto al inicio de tu archivo, con los demás imports
try:
    import pyi_splash
except ImportError:
    # Esta línea es la clave: si la importación falla,
    # creamos la variable 'pyi_splash' y le damos el valor 'None'.
    pyi_splash = None 

#para garantizar el empaquetado 
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))



from pathlib import Path
from appdirs import user_data_dir
import pandas as pd
from PyQt5.QtGui import (QIcon, QBrush, QColor, QFont, QMovie, QDesktopServices, QKeySequence, QLinearGradient)
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QCheckBox, QGridLayout, QHeaderView, QMessageBox, QLineEdit, QMenu,
    QComboBox, QStyle, QDialog, QSizePolicy, QGroupBox, QShortcut, QProgressBar,
    QGraphicsDropShadowEffect, QFrame, QGraphicsOpacityEffect, QStackedWidget,
    QScrollArea, QButtonGroup, QAbstractButton, QToolButton
)
from PyQt5.QtCore import Qt, QSize, QPoint, QTimer, QThread, pyqtSignal, QCoreApplication, QUrl, QPropertyAnimation, QSequentialAnimationGroup, QEasingCurve
from datetime import datetime

import calendar
import ctypes
import pyodbc
# Desactivar pooling interno de pyodbc globalmente para evitar conflictos con Access
pyodbc.pooling = False

# Importaciones de Matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas # NavigationToolbar2QT ya no es necesario aquí
from matplotlib.figure import Figure
import matplotlib.ticker as mticker
from matplotlib.animation import FuncAnimation 

# --- INICIO: NUEVA FUNCIÓN DE AYUDA PARA FORMATEAR TIEMPO ---
def format_duration(seconds):
    """Convierte segundos a un formato de texto H:M:S."""
    try:
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    except (ValueError, TypeError):
        return "00:00:00"
# --- FIN DE LA FUNCIÓN DE AYUDA ---


# Configuración modificada para rutas más flexibles... versión
VERSION = "4.0.4.4"
VERSION_UI = ".".join(VERSION.split(".")[:3])
fechaVersion = "26/06/2026"
AUTOR = "A.D.A. © 2026 Víctor Domínguez. Todos los derechos reservados."

# Obtener rutas dinámicas
# BASE_DIR ya se definió arriba respetando sys._MEIPASS
DB_DEFAULT_PATH = os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'),
                               'CyberCafePro Server', 'DB', 'oneroofccp.mdb')
DB_PASSWORD = "oNer00FooR3n0"

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# --- LIBRERÍA DE SERVICIOS CON PRIORIDAD Y VARIANTES ---
LISTA_SERVICIOS_PRIORIZADA = [
    {'categoria': 'TALLER', 'variantes': ['TALLER','CURSO', 'CURSOS', 'CAPACITACION','CAPACITACIÓN','CAPACITACIONES']},
    {'categoria': 'REUNIÓN', 'variantes': ['REUNION', 'REUNIÓN','REUNIONES', 'MEETING']},
    {'categoria': 'CONSULTA', 'variantes': ['CONSULTA', 'CONSULTAS', 'ASESORIA', 'ASESORÍA']},
    {'categoria': 'VENTA', 'variantes': ['VENTA', 'VENTAS', 'PRODUCTO']},
    {'categoria': 'SCAN', 'variantes': ['SCAN', 'ESCANER', 'ESCANEADO','DIGITALIZACIÓN', 'SCANEOS']},
    {'categoria': 'CORREO', 'variantes': ['CORREO', 'EMAIL', 'E-MAIL', 'CORREOS']},
    {'categoria': 'TEL', 'variantes': ['TEL', 'TRAMITES EN LINEA','RECORD POLICIVO', 'TRAMITE EN LINEA']},
    {'categoria': 'LT', 'variantes': ['LT', 'LEVANTAMIENTO', 'LIBRE TECNOLOGÍA']},
    {'categoria': 'IMPRESIÓN', 'variantes': ['IMPRESION', 'IMPRESIÓN', 'IMPRESIONES', 'PRINT']},
    {'categoria': 'COPIA', 'variantes': ['COPIA', 'COPIAS', 'FOTOCOPIA', 'FOTOCOPIAS']},
    {'categoria': 'CINE', 'variantes': ['CINE', 'DOCUMENTAL', 'PELICULAS', 'PELÍCULA', 'CINE FORO','FORO', 'FOROS']}
]

# La lista simple de SERVICIOS ahora se genera a partir de la estructura principal
SERVICIOS = [item['categoria'] for item in LISTA_SERVICIOS_PRIORIZADA]

# --- PATRONES PARA DETECCIÓN DE 'USO DE PC' ---
PATRONES_USO_PC = [
    re.compile(r'^PC\d*$', re.IGNORECASE),
    re.compile(r'^LAPTOP\d*$', re.IGNORECASE),
    re.compile(r'^CRON[OÓ]METRO\d*$', re.IGNORECASE),
    re.compile(r'^HORAS?$', re.IGNORECASE),
]


from access_data_manager import AccessDataManager


# --- NUEVO: Item de tabla personalizado para mantener la fila de totales al final ---
class PinnedRowItem(QTableWidgetItem):
    """
    Un QTableWidgetItem personalizado que siempre permanece al final de la tabla
    durante el ordenamiento, independientemente de si es orden ascendente o descendente.
    """
    def __lt__(self, other):
        # Si estamos comparando con otro PinnedRowItem, usar el valor normal
        if isinstance(other, PinnedRowItem):
            return super().__lt__(other)
        # Si estamos comparando con un item normal, siempre somos "mayores"
        # Esto nos mantiene al final en orden ascendente
        return False
    
    def __gt__(self, other):
        # Si estamos comparando con otro PinnedRowItem, usar el valor normal
        if isinstance(other, PinnedRowItem):
            return super().__gt__(other)
        # Si estamos comparando con un item normal, siempre somos "mayores"
        # Esto también nos mantiene al final en orden descendente
        return True





from database_manager import db

# --- Hilo dedicado para cargar el usuario (Desde Cache SQLite - Instantáneo) ---
class UserLoaderThread(QThread):
    finished = pyqtSignal(str)

    def __init__(self, db_path, password):
        super().__init__()
        self.db_path = db_path
        self.password = password

    def run(self):
        result = ""
        try:
            # 1. Intentar leer DIRECTAMENTE de Access usando el puente seguro (Subproceso)
            # Esto garantiza que veamos el último usuario REAL, no el cacheado.
            # Al ser un subproceso, NO genera Access Violation en la app principal.
            import os
            if os.path.exists(self.db_path):
                 user_access = AccessDataManager.obtener_ultimo_usuario(self.db_path, self.password)
                 if user_access:
                     self.finished.emit(str(user_access))
                     return

            # 2. Fallback: Consultamos el último usuario registrado en la caché local
            sql = "SELECT username FROM registros_ventas_cache ORDER BY datetime DESC LIMIT 1"
            rows = db.execute_query(sql)
            
            if rows:
                result = str(rows[0]['username'])
            else:
                # Si no hay datos, tratamos de sincronizar rapido o devolvemos dummy
                result = "Esperando Sincronización..."
                
        except Exception as e:
            print(f"[UserLoaderThread] Error: {e}")
            result = "ERROR_LOAD"
            
        self.finished.emit(result)

from sync_manager import SyncManager

# --- Hilo dedicado a la Sincronización de Access (DataSyncThread) ---
class DataSyncThread(QThread):
    finished = pyqtSignal(int, str) # inserted_count, error_msg

    def __init__(self, db_path, password):
        super().__init__()
        self.db_path = db_path
        self.password = password

    def run(self):
        try:
            # Inicializar COM para ODBC en Thread
            ctypes.windll.ole32.CoInitialize(None)
        except: pass
        
        try:
            manager = SyncManager(self.db_path, self.password)
            inserted, error = manager.sync_access_incremental()
            
            # Sincronizar cuentas de usuario (no bloquea si falla)
            try:
                ua_count, ua_error = manager.sync_useraccount_full()
                if ua_error:
                    print(f"[WARN] Sync de useraccount falló: {ua_error}")
            except Exception as ua_exc:
                print(f"[WARN] Excepción en sync useraccount: {ua_exc}")
            
            self.finished.emit(inserted, str(error) if error else None)
        except Exception as e:
            self.finished.emit(0, str(e))
        finally:
            try: ctypes.windll.ole32.CoUninitialize()
            except: pass


# --- Worker Thread for heavy operations (Logic remains identical) ---
class Worker(QThread):
    finished = pyqtSignal(pd.DataFrame, str)

    def __init__(self, db_path, password, start_date, end_date):
        super().__init__()
        self.db_path = db_path
        self.password = password
        self.start_date = start_date
        self.end_date = end_date
        self.temp_dir = None




    def run(self):
        # NOTA: Ya no necesitamos COM/OLE ni AccessDataManager aquí.
        # Leemos directo de SQLite que es thread-safe y rápido.
        
        try:
            conn = db.get_connection()
            # Usamos alias para mantener compatibilidad con el resto del código que espera mayúsculas
            query = """
                SELECT datetime as DATETIME, username as USERNAME, itemname as ITEMNAME 
                FROM registros_ventas_cache
                WHERE datetime BETWEEN ? AND ?
                ORDER BY datetime DESC
            """
            
            # Pandas lee directo de la conexión SQLite
            data = pd.read_sql_query(query, conn, params=[self.start_date, self.end_date])
            
            # Asegurar tipo datetime
            if not data.empty:
                data['DATETIME'] = pd.to_datetime(data['DATETIME'])
            
            conn.close()

            if data is None or data.empty:
                self.finished.emit(pd.DataFrame(), None)
                return

            # Procesamiento de lógica de negocio (identificar tipo de servicio)
            data = analizar_itemname(data)
            self.finished.emit(data, None)
            
        except Exception as e:
            error_msg = f"Error leyendo base local: {str(e)}"
            print(error_msg)
            self.finished.emit(pd.DataFrame(), error_msg)


# --- INICIO: NUEVO WIDGET DE ANIMACIÓN MATPLOTLIB ---
class AnimationWidget(QWidget):
    def __init__(self, is_dark_mode=False, parent=None):
        super().__init__(parent)
        self.is_dark_mode = is_dark_mode
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Configuración del lienzo de Matplotlib
        self.fig = Figure(figsize=(5, 2), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet("background-color: transparent;") # <--- FIX: Fondo transparente en canvas
        layout.addWidget(self.canvas)

        # Hacemos el fondo de la figura y los ejes transparente
        self.fig.patch.set_alpha(0)
        self.ax = self.fig.add_subplot(111)
        self.ax.patch.set_alpha(0)

        # 2. Configuración de la animación
        self.ax.set_xlim(0, 2 * np.pi)
        self.ax.set_ylim(-1.5, 1.5)
        self.ax.axis("off")  # Ocultamos los ejes

        # 3. Líneas de onda con colores adaptables al tema
        self.x = np.linspace(0, 2 * np.pi, 1000)
        self.lines = []
        
        if self.is_dark_mode:
            # Colores neón para el tema oscuro
            colors = ['#00fff7', '#ff00e0', '#ffe600'] 
        else:
            # Colores profesionales para el tema claro
            colors = ['#4A90E2', '#34C759', '#FF9500']

        self.offsets = [0, np.pi / 4, np.pi / 2]

        for color in colors:
            line, = self.ax.plot([], [], lw=2.5, color=color, alpha=0.9)
            self.lines.append(line)
        
        # Guardamos la animación como un atributo de la clase para que no se detenga
        self.ani = FuncAnimation(self.fig, self.update_animation, frames=200, interval=33, blit=True)

    def update_animation(self, frame):
        for i, line in enumerate(self.lines):
            phase = (frame / 50.0) + self.offsets[i]
            y = np.sin(self.x * 2.5 + phase) * (0.8 + 0.2 * np.cos(phase * 0.5))
            line.set_data(self.x, y)
        return self.lines
# --- FIN: NUEVO WIDGET DE ANIMACIÓN ---

# --- MODIFIED: Processing Dialog with pure Animation ---
class ProcessingDialog(QDialog):
    def __init__(self, parent=None, is_dark_mode=False):
        super().__init__(parent)
        self.is_dark_mode = is_dark_mode # Recibimos el estado del tema
        
        # Estilo base del diálogo
        window = QWidget()
        #window.setWindowIcon(icon)

        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint)
        self.setWindowTitle("A.D.A. - Procesando...")
        # Si tienes un icono global ya definido:
        icon_path = os.path.join(BASE_DIR, 'iconBDVicTor_D.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setModal(True)
        self.setFixedSize(800, 200)

        self.init_ui()
        self.apply_dialog_style()

        if parent:
            self.move(parent.geometry().center() - self.rect().center())

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # --- REEMPLAZO DEL GIF POR LA NUEVA ANIMACIÓN ---
        # Creamos una instancia de nuestro widget animado
        self.animation_widget = AnimationWidget(is_dark_mode=self.is_dark_mode)
        layout.addWidget(self.animation_widget)
        # -----------------------------------------------

        self.message_label = QLabel("ADA se encuentra analizando tus datos, un momento por favor...")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        
        layout.addWidget(self.message_label)

    def apply_dialog_style(self):
        # Estilos adaptables al tema
        if self.is_dark_mode:
            self.setStyleSheet("""
                QDialog { background-color: #1e293b; border: 1px solid #334155; border-radius: 10px; }
                QLabel { color: #f1f5f9; }
            """)
        else:
            self.setStyleSheet("""
                QDialog { background-color: #f0f3f6; border: 1px solid #D1D9E6; border-radius: 10px; }
                QLabel { color: #34495E; }
            """)


# --- CLASE PARA EL BLOQUEO ---
# --- CLASE PARA EL BLOQUEO (VERSIÓN CORREGIDA) ---
class RemoteConfigChecker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        log_to_file("--- [RemoteConfig] Iniciando verificación remota vía API...")
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'A.D.A-App'})
            
            # Usamos un contexto SSL no verificado como medida redundante
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=10, context=context) as response:
                log_to_file(f"--- [RemoteConfig] Conexión a la API exitosa. Código: {response.status}")
                if response.status == 200:
                    api_response_str = response.read().decode('utf-8')
                    api_response_json = json.loads(api_response_str)
                    content_base64 = api_response_json['content']
                    content_decoded_bytes = base64.b64decode(content_base64)
                    content_decoded_str = content_decoded_bytes.decode('utf-8')
                    config_data = json.loads(content_decoded_str)
                    log_to_file("--- [RemoteConfig] Configuración remota cargada y decodificada.")
                    self.finished.emit(config_data) # Emitimos el diccionario con datos
                else:
                    log_to_file(f"--- [RemoteConfig] Respuesta no esperada: {response.status}")
                    self.finished.emit({})
        except Exception as e:
            msg = f"--- [RemoteConfig] ERROR: {e}"
            print(msg)
            log_to_file(msg)
            self.finished.emit({})
        
        log_to_file("--- [RemoteConfig] Verificación finalizada.")


# --- INICIO: VERSIÓN DEFINITIVA Y AUTÓNOMA DE BITACORAMANAGER (MEJORADA OFFLINE Y RESUMEN) ---
# --- INICIO: VERSIÓN ROBUSTA DE BITACORAMANAGER (STATE-SYNC) ---
class BitacoraManager(QThread):
    def __init__(self, initial_facilitator_mode=False):
        super().__init__()
        self.user_id = "Desconocido"
        self.pc_name = platform.node()
        self.user_is_set = False
        
        # Archivos locales para persistencia
        self.current_session_file = get_writable_path('session_current.json')
        self.pending_file = get_writable_path('session_pending.json')
        
        # Estado en memoria
        self.current_data = {}
        self.is_syncing = False

        # Inicialización
        self._initialize_session(initial_facilitator_mode)

    def _initialize_session(self, initial_facilitator_mode=False):
        """Maneja la lógica de inicio: archivar sesión anterior si existe y crear nueva."""
        # 1. Si existe una sesión "current" previa, es que la app se cerró o es una nueva ejecución.
        #    La movemos a "pending" para asegurarnos de que se suba su estado final.
        if os.path.exists(self.current_session_file):
            self._archive_current_session()

        # 2. Crear nueva sesión
        self.session_id = f"{self.pc_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.start_time = time.time()
        
        # Estructura base de datos
        self.current_data = {
            "SessionID": self.session_id,
            "PC_Name": self.pc_name,
            "Usuario": self.user_id,
            "VersionADA": VERSION,
            "VersionOS": platform.version() + " " + platform.release(),
            "Inicio_Sesion": datetime.fromtimestamp(self.start_time).isoformat(),
            "Cierre_Sesion": datetime.now().isoformat(),
            "Estado_Final": "En Curso",
            # Contadores
            "analisis_count": 0,
            "analisis_total_time": 0,
            "uso_visitas": False,
            "uso_facebook": False,
            "uso_metas": False,
            "clicks_visitas": 0,
            "clicks_facebook": 0,
            "clicks_metas": 0,
            "FacilitadorMode": "Usado por un Guerrero" if initial_facilitator_mode else "NO",
            "errores": []
        }
        
        # Guardado inicial inmediato
        self._save_local_current()
        
        # Intentar primera sincronización
        # self.start() # MODIFICADO: Se inicia manualmente desde main para evitar crash


    def _archive_current_session(self):
        """Mueve la sesión actual (del disco) a la lista de pendientes."""
        try:
            old_data = {}
            with open(self.current_session_file, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
            
            # Si quedó como "En Curso", la marcamos como "Cierre Inesperado" o simplemente finalizada
            if old_data.get("Estado_Final") == "En Curso":
                old_data["Estado_Final"] = "Finalizado (Recuperado)"
            
            # Cargar pendientes existentes
            pending = []
            if os.path.exists(self.pending_file):
                with open(self.pending_file, 'r', encoding='utf-8') as f:
                    pending = json.load(f)
            
            pending.append(old_data)
            
            # Guardar pending y eliminar current
            with open(self.pending_file, 'w', encoding='utf-8') as f:
                json.dump(pending, f, indent=4)
            
            os.remove(self.current_session_file)
            
        except Exception as e:
            print(f"[BITÁCORA] Error archivando sesión anterior: {e}")

    def _save_local_current(self):
        """Guarda el estado actual en disco (sobrescribe safe)."""
        try:
            with open(self.current_session_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_data, f, indent=4)
        except Exception as e:
            msg = f"[BITÁCORA] Error guardando local: {e}"
            print(msg)
            # Intentar registrar en log de emergencia si la función existe
            if 'log_to_file' in globals():
                log_to_file(msg)
                

    def set_facilitator_mode(self, enabled):
        """Marca el modo facilitador como usado si se activa."""
        if enabled:
            self.current_data['FacilitadorMode'] = "Usado por un Guerrero"
            self.log_intermediate_update()

    def update_user_id(self, user_id):
        if user_id:
            self.user_id = user_id
            self.current_data['Usuario'] = user_id
            self.user_is_set = True
            # Solo guardamos localmente, no iniciamos hilo de red para no chocar con el inicio
            self._recalc_totals()
            self._save_local_current()
            # self.log_intermediate_update()

    def track_activity(self, category, value=1):
        """Actualiza contadores en memoria y guarda en disco."""
        # 1. Actualizar memoria
        if category == 'analisis':
            self.current_data['analisis_count'] += 1
            self.current_data['uso_visitas'] = True
        elif category == 'analisis_time':
            self.current_data['analisis_total_time'] += value
        elif category == 'error':
            self.current_data['errores'].append(str(value))
            self.current_data['Estado_Final'] = "En Curso (Con Errores)"
        elif category == 'facebook_module':
            self.current_data['uso_facebook'] = True
        elif category == 'excel':
            # Podemos añadir un campo extra si quieres, o solo trackear que sigue viva
            pass 
        elif category.startswith('tab_click_'):
            tab = category.replace('tab_click_', '').lower()
            if 'visitas' in tab: 
                self.current_data['clicks_visitas'] += 1
                self.current_data['uso_visitas'] = True
            elif 'facebook' in tab: 
                self.current_data['clicks_facebook'] += 1
                self.current_data['uso_facebook'] = True
            elif 'metas' in tab: 
                self.current_data['clicks_metas'] += 1
                self.current_data['uso_metas'] = True

        # Actualizar timestamps y cálculos derivados
        self._recalc_totals()
        
        # 2. Guardar en disco inmediatamente
        self._save_local_current()

    def _recalc_totals(self):
        """Recalcula campos derivados antes de guardar/enviar."""
        duration_min = (time.time() - self.start_time) / 60
        avg_time = 0
        if self.current_data['analisis_count'] > 0:
            avg_time = self.current_data['analisis_total_time'] / self.current_data['analisis_count']

        self.current_data['Cierre_Sesion'] = datetime.now().isoformat()
        self.current_data['Duracion_Total_Min'] = round(duration_min, 2)
        self.current_data['Tiempo_Prom_Analisis_Seg'] = round(avg_time, 2)

    def log_intermediate_update(self):
        """Dispara una sincronización en segundo plano."""
        self._recalc_totals()
        self._save_local_current()
        if not self.isRunning():
            self.start()

    def log_session_end(self, sync=False):
        """Cierre final."""
        self._recalc_totals()
        
        current_status = self.current_data.get("Estado_Final", "")
        if "Errores" not in current_status:
            self.current_data["Estado_Final"] = "Finalizado"
        else:
             self.current_data["Estado_Final"] = "Finalizado con Errores"

        self._save_local_current()
        
        if sync:
            self.run() # Bloqueante
        else:
            if not self.isRunning():
                self.start()

    def log_event(self, event_data, flush=False):
        """Método de compatibilidad para registrar eventos críticos/errores."""
        msg = f"[{event_data.get('TipoEvento', 'evento')}] {event_data.get('MensajeError', '')}"
        
        # Agregamos a la lista de errores
        self.current_data['errores'].append(msg)
        
        # Actualizamos estado si es crítico
        state = event_data.get('Estado', '')
        if state:
             self.current_data['Estado_Final'] = state
        
        self.log_intermediate_update()
        
        if flush:
            self.wait(100) # Breve pausa para asegurar escritura en disco
            if not self.isRunning():
                self.start()

    def prepare_sheets_row(self, data_dict):
        """Convierte el diccionario de datos plano a la lista ordenada para Sheets."""
        # Definir orden EXACTO de columnas
        # Mapeamos los nombres internos a los headers del Excel
        # data_dict tiene claves internas (lowercase/underscore mixed), vamos a estandarizar
        
        errores_str = " | ".join(data_dict['errores'])[-500:] if isinstance(data_dict['errores'], list) else str(data_dict['errores'])

        # Diccionario plano final
        row_map = {
            "SessionID": data_dict.get('SessionID'),
            "PC_Name": data_dict.get('PC_Name'),
            "Usuario": data_dict.get('Usuario'),
            "VersionADA": data_dict.get('VersionADA'),
            "VersionOS": data_dict.get('VersionOS'),
            "Inicio_Sesion": data_dict.get('Inicio_Sesion'),
            "Cierre_Sesion": data_dict.get('Cierre_Sesion'),
            "Duracion_Total_Min": data_dict.get('Duracion_Total_Min'),
            "Cant_Analisis": data_dict.get('analisis_count'),
            "Tiempo_Prom_Analisis_Seg": data_dict.get('Tiempo_Prom_Analisis_Seg'),
            "Uso_Visitas": "SI" if data_dict.get('uso_visitas') else "NO",
            "Uso_Facebook": "SI" if data_dict.get('uso_facebook') else "NO",
            "Uso_Metas": "SI" if data_dict.get('uso_metas') else "NO",
            "Clicks_Visitas": data_dict.get('clicks_visitas'),
            "Clicks_Facebook": data_dict.get('clicks_facebook'),
            "Clicks_Metas": data_dict.get('clicks_metas'),
            "FacilitadorMode": data_dict.get('FacilitadorMode', "NO"),
            "Errores_Reportados": errores_str,
            "Estado_Final": data_dict.get('Estado_Final')
        }
        return row_map

    def run(self):
        """El Worker Thread: Sincroniza Pendientes + Actual."""
        if self.is_syncing:
            return
        
        self.is_syncing = True
        # Aumentamos el timeout a 30 segundos para redes lentas
        socket.setdefaulttimeout(30)
        
        # 1. Cargar Pendientes
        pending_sessions = []
        if os.path.exists(self.pending_file):
            try:
                with open(self.pending_file, 'r', encoding='utf-8') as f:
                    pending_sessions = json.load(f)
            except Exception as e:
                log_to_file(f"[BITÁCORA] Error leyendo pendientes: {e}")
        
        # 2. Preparar lista total a sincronizar (Pendientes + Actual)
        current_snapshot = self.current_data.copy()
        
        # Lista de tareas: (DataDict, es_la_actual)
        tasks = [(d, False) for d in pending_sessions]
        tasks.append((current_snapshot, True))
        
        if not tasks: 
            self.is_syncing = False
            return

        try:
            # --- CONEXIÓN GSPREAD ---
            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.file']
            creds_path = os.path.join(BASE_DIR, 'credentials.json')
            
            if not os.path.exists(creds_path):
                log_to_file("[BITÁCORA] ERROR: No se encontró credentials.json en BASE_DIR")
                self.is_syncing = False
                return

            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
            client = gspread.authorize(creds)
            
            URL_DE_LA_HOJA = "https://docs.google.com/spreadsheets/d/12GPBc0JAMRY2b7YMWcFDGiAP9xOrfDNgoZdiwQyuWdc/edit?usp=sharing"
            workbook = client.open_by_url(URL_DE_LA_HOJA)
            
            # --- INTENTAR ABRIR O CREAR PESTAÑA ---
            try:
                sheet = workbook.worksheet("BitUsoADA4.0")
            except gspread.exceptions.WorksheetNotFound:
                log_to_file("[BITÁCORA] Pestaña no encontrada. Creándola automáticamente...")
                # Crear la pestaña con 100 filas y 20 columnas iniciales (crece sola)
                sheet = workbook.add_worksheet(title="BitUsoADA4.0", rows="100", cols="20")
                # Los encabezados se añadirán en el bloque siguiente
            # -------------------------------------

            # Headers esperados
            headers = [
                "SessionID", "PC_Name", "Usuario", "VersionADA", "VersionOS",
                "Inicio_Sesion", "Cierre_Sesion", "Duracion_Total_Min",
                "Cant_Analisis", "Tiempo_Prom_Analisis_Seg",
                "Uso_Visitas", "Uso_Facebook", "Uso_Metas",
                "Clicks_Visitas", "Clicks_Facebook", "Clicks_Metas",
                "FacilitadorMode", "Errores_Reportados", "Estado_Final"
            ]
            
            # Verificar headers remotas (normalizando para quitar espacios)
            current_headers = [str(h).strip() for h in sheet.row_values(1)]
            if not current_headers or not any(current_headers):
                log_to_file("[BITÁCORA] Hoja vacía o sin encabezados. Insertando estructura...")
                sheet.update(range_name="A1", values=[headers])
                current_headers = headers
            
            # Mapa Header -> Index (0-based)
            header_map = {name: i for i, name in enumerate(current_headers)}
            
            # Cachear columna de IDs para búsquedas
            try:
                idx_sess = header_map.get("SessionID", 0) + 1
                remote_ids = sheet.col_values(idx_sess)
            except Exception as e:
                log_to_file(f"[BITÁCORA] Error cacheando IDs remotos: {e}")
                remote_ids = []

            # --- PROCESAR TAREAS ---
            new_pending = [] # Aquí caerán las que fallen
            
            for data_dict, is_current in tasks:
                try:
                    row_data_map = self.prepare_sheets_row(data_dict)
                    sess_id = row_data_map["SessionID"]
                    
                    row_values = [''] * len(current_headers)
                    for k, v in row_data_map.items():
                        if k in header_map:
                            row_values[header_map[k]] = str(v)

                    # Buscar si existe
                    if sess_id in remote_ids:
                        row_num = remote_ids.index(sess_id) + 1
                        sheet.update(range_name=f"A{row_num}", values=[row_values])
                        log_to_file(f"[BITÁCORA] Sesión {sess_id} ACTUALIZADA en fila {row_num}.")
                    else:
                        # INSERT (Inteligente)
                        # Si remote_ids solo tiene el header o está vacío, forzamos fila 2
                        if len(remote_ids) <= 1:
                            target_row = 2
                            sheet.update(range_name=f"A{target_row}", values=[row_values])
                            remote_ids.append(sess_id)
                        else:
                            # Append normal, pero guardamos registro
                            result = sheet.append_row(row_values)
                            remote_ids.append(sess_id)
                            # Intentar extraer fila del resultado de gspread si es posible, 
                            # si no, asumimos al final
                            target_row = len(remote_ids) 
                        
                        log_to_file(f"[BITÁCORA] Sesión {sess_id} INSERTADA en fila {target_row}.")

                except Exception as e:
                    log_to_file(f"[BITÁCORA] Error sincronizando sesión {data_dict.get('SessionID')}: {e}")
                    # Si falla, la guardamos para reintento (sea actual o vieja)
                    new_pending.append(data_dict)
            
            # --- GUARDAR PENDIENTES REMANENTES ---
            if not new_pending:
                if os.path.exists(self.pending_file):
                     os.remove(self.pending_file)
            else:
                with open(self.pending_file, 'w', encoding='utf-8') as f:
                    json.dump(new_pending, f, indent=4)

        except Exception as e:
            log_to_file(f"[BITÁCORA] Error crítico en hilo de conexión: {e}")
            # Si hay un error general (ej. sin internet), guardamos la actual como pendiente
            if tasks:
                current_in_tasks = [t[0] for t in tasks if t[1]] # Obtener la actual
                if current_in_tasks:
                   self._add_to_pending_safe(current_in_tasks[0])
        finally:
            self.is_syncing = False

    def _add_to_pending_safe(self, data_dict):
        """Añade una sesión a pendientes de forma segura sin duplicar."""
        try:
            pending = []
            if os.path.exists(self.pending_file):
                with open(self.pending_file, 'r', encoding='utf-8') as f:
                    pending = json.load(f)
            
            # Verificar si ya existe para no duplicar
            exists = any(p.get('SessionID') == data_dict.get('SessionID') for p in pending)
            if not exists:
                pending.append(data_dict)
                with open(self.pending_file, 'w', encoding='utf-8') as f:
                    json.dump(pending, f, indent=4)
        except: pass

# --- FIN VERSIÓN ROBUSTA ---

def get_persistent_path(relative_path):
    """
    Obtiene la ruta a un archivo de RECURSOS (lectura), priorizando el bundle de PyInstaller.
    NO USAR PARA ESCRIBIR ARCHIVOS.
    """
    if getattr(sys, 'frozen', False):
        # 1. Intentar primero dentro del bundle (archivos incluidos con --add-data)
        base_path = sys._MEIPASS
        ruta_bundle = os.path.join(base_path, relative_path)
        if os.path.exists(ruta_bundle):
            return ruta_bundle
        
        # 2. Si no está en el bundle, buscarlo en la misma carpeta que el .exe
        application_path = os.path.dirname(sys.executable)
    else:
        # Modo desarrollo
        application_path = os.path.dirname(os.path.abspath(__file__))
        
    return os.path.join(application_path, relative_path)

def get_writable_path(relative_path):
    """
    Obtiene una ruta segura para ESCRIBIR archivos (AppData/ADA_Nova).
    """
    # Usar AppData para asegurar permisos de escritura
    app_data = os.environ.get('APPDATA')
    if not app_data:
        app_data = os.path.expanduser("~")
    
    base_dir = os.path.join(app_data, "ADA_Nova")
    os.makedirs(base_dir, exist_ok=True)
    
    return os.path.join(base_dir, relative_path)

def log_to_file(message):
    """Escribe un mensaje en el archivo ada_debug.log con timestamp en AppData."""
    try:
        # Usar AppData para asegurar permisos de escritura
        log_dir = os.path.join(user_data_dir("ADA_Nova", "Infoplazas"), "Logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "ada_debug.log")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except:
        pass # Si falla el log, no podemos hacer mucho más

def global_exception_handler(exc_type, exc_value, exc_traceback):
    """
    Captura global de excepciones no controladas.
    Registra el error en archivo local y remotamente si es posible.
    """
    try:
        # 1. Formatear error
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        log_to_file(f"[CRASH] Excepción no controlada:\n{error_msg}")
        
        # Guardar también en el dump de crashes con fecha para unificar historial de muertes
        try:
            crash_dump_path = os.path.join(user_data_dir("ADA_Nova", "Infoplazas"), "Logs", "ada_crash_dump.log")
            with open(crash_dump_path, "a", encoding="utf-8") as f_crash:
                 f_crash.write(f"[{datetime.now()}] CRITICAL PYTHON EXCEPTION:\n{error_msg}\n")
        except: pass
        
        # 2. Intentar reporte remoto (Google Sheets)
        # Intentamos obtener la instancia de la aplicación si existe
        app_instance = QApplication.instance()
        bitacora = None
        
        # Buscar el manager en la ventana principal si está activa
        if app_instance:
            for widget in app_instance.topLevelWidgets():
                if isinstance(widget, InfoplazaAnalyzer):
                    if hasattr(widget, 'bitacora'):
                        bitacora = widget.bitacora
                        break
        
        # Si no encontramos bitácora activa (crash temprano), intentamos crear una temporal
        if not bitacora:
            try:
                log_to_file("[CRASH] Intentando instanciar BitacoraManager de emergencia...")
                # Importación local para evitar circulares si fuera necesario, aunque aquí ya está importado
                bitacora = BitacoraManager() 
            except Exception as e:
                log_to_file(f"[CRASH] Falló creación de Bitacora emergencia: {e}")

        # 3. Enviar reporte
        if bitacora:
            log_to_file("[CRASH] Iniciando reporte remoto...")
            bitacora.log_event({
                "TipoEvento": "CRASH_APP",
                "Estado": "Cierre Inesperado",
                "MensajeError": str(exc_value)[:200] # Mensaje corto para la celda
            }, flush=True) # flush=True fuerza la espera
            
    except Exception as e:
        log_to_file(f"[CRASH] Error dentro del manejador global: {e}")
    
    # 4. Llamar al excepthook original (para que python termine o imprima en consola)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


class UpdateDialog(QDialog):
    """Ventana que muestra el progreso de la descarga con mensajes motivadores."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Actualización Disponible")
        self.setModal(True)
        self.setFixedSize(600, 150) # Aumenté un poco la altura para los mensajes más largos
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)

        # --- NUEVA LISTA DE MENSAJES AMPLIADA ---
        self.mensajes = [
            # --- CLÁSICOS (Originales) ---
            "☕ Una taza de café siempre es buena. Ve por una mientras A.D.A. se actualiza...",
            "🌟 Grandes cosas vienen con paciencia. A.D.A. se prepara para servirte mejor.",
            "💡 Un respiro ahora, más productividad después. La actualización está en camino.",
            "🚀 Ajusta tu asiento, A.D.A. está despegando hacia una nueva versión.",
            "🎶 Pon tu canción favorita mientras esperas, A.D.A. se está afinando para ti.",
            "✨ Puliendo los detalles finales para darte la mejor experiencia...",
            "🔧 Ajustando las tuercas del motor de análisis. ¡Casi listo!",
            "🧠 A.D.A. está aprendiendo nuevos trucos para sorprenderte.",
            "⏳ El tiempo bien invertido en esperar es tiempo ganado en productividad.",
            "🌐 Conectando con el futuro... La nueva versión está a punto de aterrizar.",

            # --- NUEVOS: GRACIOSOS (Estilo ADA) ---
            "🧘 **ADA Zen:** Alineando mis chakras de datos... *Ommmm... SELECT * FROM PazInterior*.",
            "🚀 **ADA al Futuro:** Cargando mis propulsores... A donde vamos, no necesitamos carreteras.",
            "🏋️‍♀️ **ADA Fit:** Haciendo sentadillas con la base de datos para fortalecer mi sistema.",

            # --- NUEVOS: TEMÁTICOS (Metas y Facebook) ---
            "🎯 **En la mira:** A.D.A. está ajustando el sistema de Metas para ayudarte a romper tus propios récords.",
            "📢 **Escuchando a la audiencia:** Mejorando el análisis de publicaciones para entender mejor tu impacto en redes.",
            "📈 **Proyectando el éxito:** Integrando nuevas herramientas de estadística para visualizar tu crecimiento en Facebook."
        ]
        # Para evitar repeticiones, guardamos el último mensaje mostrado.
        self.ultimo_mensaje = ""

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Descargando nueva versión, por favor espera...", self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setTextVisible(True)

        # Seleccionamos el primer mensaje al iniciar
        self.mensaje_extra = QLabel(random.choice(self.mensajes), self)
        self.ultimo_mensaje = self.mensaje_extra.text() # Lo guardamos
        
        self.mensaje_extra.setAlignment(Qt.AlignCenter)
        self.mensaje_extra.setWordWrap(True)
        self.mensaje_extra.setStyleSheet("font-size: 14pt; padding-top: 10px;")

        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.mensaje_extra)
        layout.addStretch()

        # Temporizador para rotar mensajes
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._cambiar_mensaje)
        # Hacemos que cambie un poco más lento para dar tiempo a leer.
        self.timer.start(7000)  # Cambia cada 7 segundos

    def _cambiar_mensaje(self):
        """
        Selecciona un nuevo mensaje de la lista, asegurándose de que
        no sea el mismo que el anterior.
        """
        # Filtramos la lista para excluir el último mensaje mostrado
        mensajes_posibles = [m for m in self.mensajes if m != self.ultimo_mensaje]
        
        # Si por alguna razón la lista filtrada queda vacía, usamos la original
        if not mensajes_posibles:
            mensajes_posibles = self.mensajes
            
        nuevo_mensaje = random.choice(mensajes_posibles)
        self.ultimo_mensaje = nuevo_mensaje # Guardamos el nuevo mensaje como el último
        self.mensaje_extra.setText(nuevo_mensaje)

    def update_progress(self, downloaded, total):
        if total > 0:
            percent = int((downloaded / total) * 100)
            self.progress_bar.setValue(percent)
            self.status_label.setText(f"Descargando... {downloaded/1024/1024:.2f} MB / {total/1024/1024:.2f} MB")

class DownloaderThread(QThread):
    """Hilo para descargar el archivo en segundo plano sin congelar la UI."""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(bool, str) # Emite (éxito/fallo, ruta_del_archivo/mensaje_error)

    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path

    def run(self):
        try:
            # Añadimos verify=False para evitar errores de certificado SSL en la descarga
            response = requests.get(self.url, stream=True, timeout=30, verify=False)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total_size)
            
            self.finished.emit(True, self.save_path)
        except Exception as e:
            self.finished.emit(False, str(e))

# --- FIN: CÓDIGO PARA LA ACTUALIZACIÓN AUTOMÁTICA ---

def limpiar_caracteres_invalidos(df):
    """
    Recorre un DataFrame y elimina los caracteres de control inválidos para XML/Excel
    de todas las columnas de tipo string.
    """
    if df.empty:
        return df

    # Expresión regular para encontrar caracteres de control inválidos
    # (excluyendo tab, salto de línea y retorno de carro, que son válidos en Excel)
    regex_control_chars = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1F]')

    def limpiar_celda(valor):
        if isinstance(valor, str):
            return regex_control_chars.sub('', valor)
        return valor

    # Aplica la limpieza a cada columna de tipo 'object' (generalmente strings)
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).apply(limpiar_celda)
    
    return df



# --- BARRA LATERAL Y COMPONENTES ---


class WarriorHelpPopup(QFrame):
    """
    Ventana flotante con los atajos de teclado del Modo Guerrero.
    Se muestra al hacer clic en el botón '?' del sidebar.
    """
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("WarriorHelpPopup")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            QFrame#WarriorHelpPopup {
                background-color: #1e293b;
                border: 1px solid #f59e0b;
                border-radius: 12px;
            }
            QLabel#PopupTitle {
                color: #f59e0b;
                font-size: 16px;
                font-weight: bold;
                font-family: 'Segoe UI';
            }
            QLabel#PopupSubtitle {
                color: #94a3b8;
                font-size: 12px;
                font-family: 'Segoe UI';
            }
            QLabel#ShortcutLabel {
                color: #e2e8f0;
                font-size: 14px;
                font-family: 'Segoe UI';
            }
            QLabel#ShortcutKey {
                color: #1e293b;
                background-color: #f59e0b;
                font-size: 13px;
                font-weight: bold;
                font-family: 'Segoe UI Semibold', 'Segoe UI';
                border-radius: 4px;
                padding: 2px 6px;
            }
            QLabel#ShortcutNote {
                color: #64748b;
                font-size: 12px;
                font-style: italic;
                font-family: 'Segoe UI';
            }
        """)
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(4)

        # --- Título ---
        title_row = QHBoxLayout()
        lbl_icon = QLabel("⚔️")
        lbl_icon.setStyleSheet("font-size: 16px;")
        lbl_title = QLabel("MANUAL DEL GUERRERO")
        lbl_title.setObjectName("PopupTitle")
        lbl_subtitle = QLabel("   (para los que se olvidan de todo)")
        lbl_subtitle.setObjectName("PopupSubtitle")
        title_row.addWidget(lbl_icon)
        title_row.addWidget(lbl_title)
        title_row.addWidget(lbl_subtitle)
        title_row.addStretch()
        main_layout.addLayout(title_row)

        # Línea divisoria
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: rgba(245, 158, 11, 0.35); max-height: 1px; margin: 6px 0;")
        main_layout.addWidget(sep)

        # --- Atajos ---
        shortcuts = [
            {
                "emoji": "☁️",
                "title": "Sincronizar con Google Sheets",
                "key": "Ctrl + Shift + S",
                "desc": "Compara datos locales vs. la nube.",
                "joke": "Sin cambios = todo al día. ¡Eres un guerrero ordenado! ✅",
            },
            {
                "emoji": "💾",
                "title": "Restaurar Base de Datos",
                "key": "Ctrl + Shift + R",
                "desc": "Reinicia los datos de sincronización.",
                "joke": "Úsalo con cuidado... o con valor guerrero. 🗡️",
            },
            {
                "emoji": "🗡️",
                "title": "Activar / Desactivar Modo Guerrero",
                "key": "Ctrl + F",
                "desc": "Porque no todos merecen ver el cuadro.",
                "joke": "El poder, con gran responsabilidad. 🦸",
            },
        ]

        for i, sc in enumerate(shortcuts):
            block = QVBoxLayout()
            block.setSpacing(2)

            # Fila: emoji + título + atajo
            top_row = QHBoxLayout()
            top_row.setSpacing(6)

            lbl_emoji = QLabel(sc["emoji"])
            lbl_emoji.setStyleSheet("font-size: 14px;")
            lbl_emoji.setFixedWidth(22)

            lbl_name = QLabel(sc["title"])
            lbl_name.setObjectName("ShortcutLabel")

            lbl_key = QLabel(sc["key"])
            lbl_key.setObjectName("ShortcutKey")

            top_row.addWidget(lbl_emoji)
            top_row.addWidget(lbl_name)
            top_row.addStretch()
            top_row.addWidget(lbl_key)
            block.addLayout(top_row)

            # Descripción
            lbl_desc = QLabel(f"    {sc['desc']}")
            lbl_desc.setObjectName("ShortcutNote")
            block.addWidget(lbl_desc)

            # Chiste
            lbl_joke = QLabel(f"    {sc['joke']}")
            lbl_joke.setObjectName("ShortcutNote")
            lbl_joke.setStyleSheet("color: #f59e0b; font-size: 12px; font-style: italic;")
            block.addWidget(lbl_joke)

            main_layout.addLayout(block)

            # Separador entre bloques (no al final)
            if i < len(shortcuts) - 1:
                sep2 = QFrame()
                sep2.setFrameShape(QFrame.HLine)
                sep2.setStyleSheet("background-color: rgba(255,255,255,0.07); max-height:1px; margin: 4px 0;")
                main_layout.addWidget(sep2)
        # --- Nota de Exportación a Excel ---
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet("background-color: rgba(245, 158, 11, 0.35); max-height: 1px; margin: 8px 0;")
        main_layout.addWidget(sep3)

        lbl_export_title = QLabel("📊 Exportar Metas a Excel")
        lbl_export_title.setObjectName("ShortcutLabel")
        lbl_export_title.setStyleSheet("font-weight: bold; color: #f59e0b; font-size: 14px;")
        main_layout.addWidget(lbl_export_title)

        lbl_export_desc = QLabel(
            "Al usar el botón de exportar, se descargará el cuadro completo con las metas de todas las infoplazas. "
            "Si aplicas algún filtro en la tabla, el Excel generado respetará esos filtros y solo incluirá la información visible en ese momento."
        )
        lbl_export_desc.setObjectName("ShortcutNote")
        lbl_export_desc.setWordWrap(True)
        lbl_export_desc.setStyleSheet("color: #e2e8f0; font-size: 13px; margin-top: 2px;")
        main_layout.addWidget(lbl_export_desc)

        self.adjustSize()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
        super().keyPressEvent(event)



class SidebarButton(QPushButton):
    """Botón personalizado para la barra lateral (Ahora simplificado para usar QSS)."""
    def __init__(self, text, icon_name=None, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("SidebarButton") # Para QSS
        
        if icon_name:
            if isinstance(icon_name, QIcon):
                self.setIcon(icon_name)
            elif isinstance(icon_name, QStyle.StandardPixmap):
                 self.setIcon(self.style().standardIcon(icon_name))

        self.setIconSize(QSize(20, 20))

class Sidebar(QWidget):
    """Barra lateral principal de navegación (Premium Dark Style)."""
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.init_ui()

    def init_ui(self):
        self.setFixedWidth(260) # Ancho fijo ajustado
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True) # CRITICAL: Allows QSS background color
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0) # Espaciado controlado por margen de botones

        # 1. Header / Logo
        self.header_frame = QFrame()
        self.header_frame.setObjectName("SidebarHeader")
        header_layout = QVBoxLayout(self.header_frame)
        header_layout.setContentsMargins(0, 30, 0, 20)
        header_layout.setSpacing(0)
        
        title_label = QLabel("ADA 4.0")
        title_label.setObjectName("SidebarTitle")
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label)

        subtitle_label = QLabel("Analizador de Datos y Actividades")
        subtitle_label.setObjectName("SidebarSubtitle")
        subtitle_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(subtitle_label)
        
        layout.addWidget(self.header_frame)

        # 2. Navegación Principal
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_group.buttonClicked.connect(self.on_nav_clicked)

        layout.addWidget(self.create_section_label("MENU PRINCIPAL"))

        self.btn_visitas = self.create_nav_button("Dashboard", QStyle.SP_FileDialogInfoView, 0)
        self.btn_facebook = self.create_nav_button("Redes Sociales", QStyle.SP_ComputerIcon, 1)
        self.btn_metas = self.create_nav_button("Metas Mensuales", QStyle.SP_FileDialogListView, 2)
        
        # Cuadro de Metas (solo visible en Modo Guerrero)
        self.btn_cuadro_metas = self.create_nav_button("Cuadro de Metas", QStyle.SP_FileDialogDetailedView, 3)

        layout.addWidget(self.btn_visitas)
        layout.addWidget(self.btn_facebook)
        layout.addWidget(self.btn_metas)
        layout.addWidget(self.btn_cuadro_metas)
        
        # Ocultamos Cuadro de Metas por defecto
        self.btn_cuadro_metas.setVisible(False)

        # 3. Sección Guerrero (Diseño Premium)
        layout.addSpacing(25)
        self.warrior_container = QWidget()
        self.warrior_container.setObjectName("WarriorSection")
        self.warrior_layout = QVBoxLayout(self.warrior_container)
        self.warrior_layout.setContentsMargins(16, 16, 16, 16)
        self.warrior_layout.setSpacing(12)
        
        # Header con icono y título
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        icon_label = QLabel("⚔️")
        icon_label.setStyleSheet("font-size: 18px;")
        
        warrior_title = QLabel("MODO GUERRERO")
        warrior_title.setObjectName("WarriorBadge")
        warrior_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # Botón de ayuda de atajos
        self.btn_warrior_help = QPushButton("?")
        self.btn_warrior_help.setFixedSize(20, 20)
        self.btn_warrior_help.setCursor(Qt.PointingHandCursor)
        self.btn_warrior_help.setToolTip("Haga clic para ver más información")
        self.btn_warrior_help.setStyleSheet("""
            QPushButton {
                background-color: rgba(245, 158, 11, 0.25);
                color: #f59e0b;
                border: 1px solid #f59e0b;
                border-radius: 10px;
                font-size: 11px;
                font-weight: bold;
                font-family: 'Segoe UI';
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(245, 158, 11, 0.45);
            }
            QPushButton:pressed {
                background-color: rgba(245, 158, 11, 0.65);
            }
        """)
        self._warrior_help_popup = WarriorHelpPopup()
        self.btn_warrior_help.clicked.connect(self._mostrar_warrior_help)

        header_layout.addWidget(icon_label)
        header_layout.addWidget(warrior_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_warrior_help)
        
        self.warrior_layout.addLayout(header_layout)
        
        # Separador sutil
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); max-height: 1px;")
        self.warrior_layout.addWidget(separator)
        self.warrior_layout.addSpacing(8)

        # Label de carpeta activa con icono
        folder_header = QHBoxLayout()
        folder_icon = QLabel("📂")
        folder_icon.setStyleSheet("font-size: 14px;")
        
        self.label_carpeta_activa = QLabel("CARPETA ACTIVA:")
        self.label_carpeta_activa.setObjectName("FolderLabel")
        
        folder_header.addWidget(folder_icon)
        folder_header.addWidget(self.label_carpeta_activa)
        folder_header.addStretch()
        self.warrior_layout.addLayout(folder_header)

        # ComboBox de subcarpetas con contenedor
        combo_container = QWidget()
        combo_container.setObjectName("ComboContainer")
        combo_layout = QVBoxLayout(combo_container)
        combo_layout.setContentsMargins(0, 0, 0, 0)
        combo_layout.setSpacing(4)
        
        self.combo_subs = QComboBox()
        self.combo_subs.setPlaceholderText("Seleccionar subcarpeta...")
        self.combo_subs.setObjectName("WarriorCombo")
        self.combo_subs.setMinimumHeight(32)
        self.combo_subs.setMaxVisibleItems(20) 
        self.combo_subs.currentIndexChanged.connect(self.main_app.actualizar_ruta_desde_subcarpeta)
        combo_layout.addWidget(self.combo_subs)
        
        self.warrior_layout.addWidget(combo_container)
        self.main_app.sidebar_combo_subcarpetas = self.combo_subs 
        
        self.warrior_layout.addSpacing(4)

        # Botón cambiar regional con diseño mejorado
        btn_cambiar_regional = QPushButton("📁  Cambiar Regional")
        btn_cambiar_regional.setObjectName("ChangeRootBtn")
        btn_cambiar_regional.setCursor(Qt.PointingHandCursor)
        btn_cambiar_regional.setMinimumHeight(36)
        btn_cambiar_regional.clicked.connect(self.main_app.seleccionar_carpeta_raiz)
        self.warrior_layout.addWidget(btn_cambiar_regional)

        layout.addWidget(self.warrior_container)
        self.warrior_container.setVisible(False)
        
        # Referencia para actualizar el label desde main_app
        self.label_info_carpeta = self.label_carpeta_activa

        # 4. Espaciador
        layout.addStretch()

        # 5. Sección Novedades
        # layout.addWidget(self.create_section_label("EXTRAS"))
        
        self.btn_novedades = self.create_nav_button("Novedades", QStyle.SP_MessageBoxInformation, 99)
        # Desconectamos el comportamiento default del grupo para manejarlo como modal
        self.nav_group.removeButton(self.btn_novedades)
        self.btn_novedades.clicked.connect(self.main_app.mostrar_novedades)
        layout.addWidget(self.btn_novedades)
        
        layout.addSpacing(15)

        # 5. Sección Ayuda
        layout.addWidget(self.create_section_label("SOPORTE"))
        
        self.add_support_link("Manual de Usuario", self.main_app.abrir_manual)
        self.add_support_link("Acuerdo de Metas", self.abrir_acuerdo)
        self.add_support_link("Padlet", self.abrir_padlet)
        self.add_support_link("Formulario Registro", self.abrir_formulario)

        layout.addSpacing(15)
        
        # 6. Botón de Tema (al final del sidebar)
        self.theme_toggle_button = QPushButton("🌙")
        self.theme_toggle_button.setObjectName("ThemeToggleBtn")
        self.theme_toggle_button.setToolTip("Cambiar entre tema claro y oscuro")
        self.theme_toggle_button.setCursor(Qt.PointingHandCursor)
        self.theme_toggle_button.setFixedHeight(30)
        self.theme_toggle_button.clicked.connect(self.main_app.toggle_theme)
        layout.addWidget(self.theme_toggle_button)
        
        # Guardamos referencia para que main_app pueda actualizar el texto
        self.main_app.sidebar_theme_button = self.theme_toggle_button
        
        layout.addSpacing(10)

    def create_section_label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("SectionLabel")
        return lbl

    def create_nav_button(self, text, icon, index):
        btn = SidebarButton(text, icon)
        self.nav_group.addButton(btn, index)
        return btn

    def on_nav_clicked(self, btn):
        # Actualizamos propiedad 'active' para estilo solo en el seleccionado
        for button in self.nav_group.buttons():
            button.setProperty("active", "false")
            button.style().unpolish(button)
            button.style().unpolish(button) # Force update
        
        btn.setProperty("active", "true")
        btn.style().unpolish(btn)
        btn.style().polish(btn)

        index = self.nav_group.id(btn)
        if btn == self.btn_cuadro_metas:
            self.main_app.cambiar_pagina(3)
        else:
            self.main_app.cambiar_pagina(index)

    def add_support_link(self, text, slot):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setObjectName("SupportLink")
        btn.clicked.connect(slot)
        self.layout().addWidget(btn)

    def toggle_warrior(self, active):
        self.warrior_container.setVisible(active)
        self.btn_cuadro_metas.setVisible(active)

    def _mostrar_warrior_help(self):
        """Muestra el popup de atajos posicionado al lado del botón ?"""
        popup = self._warrior_help_popup
        popup.adjustSize()

        # Posición global del botón ?
        btn_pos = self.btn_warrior_help.mapToGlobal(QPoint(0, 0))
        btn_w = self.btn_warrior_help.width()

        # Mostrar a la derecha del botón, alineado verticalmente al centro
        popup_x = btn_pos.x() + btn_w + 6
        popup_y = btn_pos.y() - popup.height() // 2

        # Corregir si se sale de la pantalla por abajo
        screen_h = QApplication.primaryScreen().availableGeometry().height()
        if popup_y + popup.height() > screen_h:
            popup_y = screen_h - popup.height() - 10

        popup.move(popup_x, popup_y)
        popup.show()
        popup.raise_()

    def abrir_acuerdo(self):
        ruta = get_persistent_path("AcuerdoMetas.html")
        if os.path.exists(ruta):
            QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))
        else:
            QMessageBox.warning(self, "Error", "No se encontró el archivo del Acuerdo.")

    def abrir_padlet(self):
        QDesktopServices.openUrl(QUrl("https://padlet.com/cuatroguerrerospty/metas-2025-2026-ftbp38ng6o4w5uqm"))

    def abrir_formulario(self):
        QDesktopServices.openUrl(QUrl("https://www.cognitoforms.com/InfoplazasAIPDavid/RegistroMensualDeMetas20252026"))

    def set_novedades_badge(self, count):
        """Actualiza el badge de novedades en el botón."""
        if not hasattr(self, 'btn_novedades'):
            return

        # Inicializar Timer de Pulso si no existe
        if not hasattr(self, '_novedades_pulse_timer'):
            self._novedades_pulse_timer = QTimer(self)
            self._novedades_pulse_timer.timeout.connect(self._animate_novedades_pulse)
            self._pulse_state = False

        if count > 0:
            self.btn_novedades.setText(f"Novedades  ({count})")
            # Iniciar animación si no está corriendo
            if not self._novedades_pulse_timer.isActive():
                self._novedades_pulse_timer.start(800) # 800ms intervalo
        else:
            self.btn_novedades.setText("Novedades")
            self.btn_novedades.setStyleSheet("") # Restaurar estilo default
            if self._novedades_pulse_timer.isActive():
                self._novedades_pulse_timer.stop()
    
    def _animate_novedades_pulse(self):
        """Animación simple de parpadeo de color"""
        self._pulse_state = not self._pulse_state
        if self._pulse_state:
            # Estado "Encendido": Fondo suave rojo/naranja
            self.btn_novedades.setStyleSheet("""
                text-align: left; 
                padding-left: 20px; 
                font-weight: bold; 
                color: #c0392b;
                background-color: #fadbd8;
                border-left: 4px solid #c0392b;
            """)
        else:
            # Estado "Apagado": Estilo normal pero con texto destacado
            self.btn_novedades.setStyleSheet("""
                text-align: left; 
                padding-left: 20px; 
                font-weight: bold; 
                color: #e74c3c;
                background-color: transparent;
                border-left: 4px solid transparent;
            """)




from PyQt5.QtWidgets import QMainWindow  # si no está ya importado

class InfoplazaAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        log_to_file("Iniciando inicialización de InfoplazaAnalyzer...")
        
        # --- MIGRACIÓN DE VERSIÓN (RESET DE CACHÉ) ---
        # Si la versión cambió, reseteamos el caché local SQLite para evitar conflictos
        # con nuevas estructuras de columnas (como access_id).
        db.check_and_apply_version_migration(VERSION)
        
        self._limpiar_archivos_antiguos() #limpia los restos que dejan los .exe.bak
        self.app_start_time = time.time()
        self.db_path = DB_DEFAULT_PATH


        self.TITULOS_COLUMNAS_SERVICIOS = {
            'MES': 'Mes', 'COPIA': 'Copias', 'IMPRESIÓN': 'Impresiones',
            'SCAN': 'Escaneos', 'LT': 'Lev. de Texto', 'TEL': 'Trám. Línea',
            'CORREO': 'Email', 'VENTA': 'Ventas', 'TALLER': 'Talleres',
            'CONSULTA': 'Consultas', 'REUNIÓN': 'Reuniones', 'CINE': 'Cine',
            'OTROS': 'Otros', 'USO DE PC': 'Uso de PC', 'TOTAL MES': 'Total'
        }

        # 1. Cargar toda la configuración en un diccionario
        self.config = self.cargar_configuracion()

        # 2. Asignar los valores a las variables de la clase
        num_computadoras = self.config.get('computadoras', 6)
        self.meta_mensual = num_computadoras * 48
        self.modo_guerrero_activo = self.config.get('modo_guerrero_activo', False)
        self.carpeta_raiz = self.config.get('ultima_carpeta_raiz', None)
        self.is_dark_mode = self.config.get('dark_mode_enabled', False)
        
        # 3. Inicializar BitacoraManager con el estado inicial del modo facilitador
        self.bitacora = BitacoraManager(initial_facilitator_mode=self.modo_guerrero_activo)
        
        # 3.1 Inicializar Manager de Novedades
        self.novedades_manager = NovedadesManager()
        self.novedades_data = None # Cache para los datos de novedades (None = No cargado, [] = Sin novedades)
        
        # 4. Inicializar el resto de las variables
        self.data = pd.DataFrame()
        self.worker = None
        self.progress_dialog = None
        self.current_username = None  # Variable para almacenar el usuario actual
        
        # --- FIN DE LA NUEVA LÓGICA ---

        # --- INICIO DEL BLOQUE A AÑADIR ---
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._update_pulse_animation)
        self.pulse_visible = True
        # --- FIN DEL BLOQUE A AÑADIR ---

        # Atributos para los objetos de Matplotlib
        self.fig_rendimiento = None
        self.canvas_rendimiento = None
        self.fig_demografia_sexo = None
        self.canvas_demografia_sexo = None
        self.fig_demografia_tipo = None
        self.canvas_demografia_tipo = None
        self.fig_servicios = None
        self.canvas_servicios = None

        # Inicializa Matplotlib Style una única vez
        plt.style.use('seaborn-v0_8-darkgrid')

        self.init_ui()
        self.setup_icon()
        self.setup_shortcuts()

        # --- INICIO: VERIFICACIÓN REMOTA (PARA EL BLOQUEO) ---
        # PEGA AQUÍ LA URL "RAW" DE TU GIST DEL PASO 1
        # --- INICIO: VERIFICACIÓN REMOTA (con API de GitHub) ---
        # Esta es la URL de la API para tu archivo. Es la definitiva.
        config_url = "https://api.github.com/repos/vicmat04/ada-config/contents/ada_config.json"
        
        # Ya no necesitamos el "cachebust" porque la API siempre da datos frescos.
        self.config_checker = RemoteConfigChecker(config_url)
        self.config_checker.finished.connect(self._handle_remote_config_check)
        self.config_checker.start()
        # --- FIN: VERIFICACIÓN REMOTA ---

        QApplication.instance().aboutToQuit.connect(self.cleanup_on_exit)
        
        # --- CARGAR ÚLTIMO USERNAME ---
        # (Eliminado) Se unifica con actualizar_status_db para evitar doble petición al inicio
        # QTimer.singleShot(500, self.cargar_ultimo_username)

        # --- Limpiar archivos .bak de actualizaciones anteriores ---
        self._limpiar_archivos_antiguos()

        # --- INICIO DIFERIDO DE BITÁCORA PARA EVITAR CRASH ---
        # Esperamos 8 segundos para que RemoteConfig y ODBC terminen.
        QTimer.singleShot(8000, lambda: (log_to_file("Iniciando Bitacora (Delayed)..."), self.bitacora.start()))
        
        # --- CARGA PROACTIVA DE NOVEDADES (Sin bloquear) ---
        # 6 segundos después del inicio, forzamos la carga de datos globales (para tener badge de novedades listo)
        QTimer.singleShot(6000, lambda: self.tab_metas.refresh_data(require_user_id=False) if hasattr(self, 'tab_metas') else None)

        # --- POLLING AUTOMÁTICO DE NOVEDADES (Cada 30 min) ---
        # Mantiene la app actualizada si se deja abierta por largo tiempo
        self.novedades_polling_timer = QTimer(self)
        self.novedades_polling_timer.timeout.connect(
            lambda: self.tab_metas.refresh_data(require_user_id=False, silent=True) if hasattr(self, 'tab_metas') else None
        )
        self.novedades_polling_timer.start(1800000) # 30 minutos

        # --- Mostrar mensaje de bienvenida si es la primera vez después de actualizar ---
        QTimer.singleShot(2000, self._revisar_post_actualizacion)
        
        # Iniciar sincronización en segundo plano (no bloqueante)
        self.trigger_access_sync()

    def trigger_access_sync(self):
        """Inicia la sincronización incremental de Access en segundo plano."""
        # Usamos las constantes globales definidas en el módulo
        self.sync_thread = DataSyncThread(DB_DEFAULT_PATH, DB_PASSWORD)
        self.sync_thread.finished.connect(self.on_sync_finished)
        self.sync_thread.start()

    def on_sync_finished(self, count, error):
        """Maneja el resultado de la sincronización."""
        if error:
            # Loguear error pero no interrumpir al usuario (silencioso)
            print(f"[SYNC] Error background sync: {error}")
            if 'log_to_file' in globals():
                log_to_file(f"[SYNC] Error: {error}")
        else:
            if count > 0:
                msg = f"[SYNC] Sincronizados {count} nuevos registros de Access."
                print(msg)
                if 'log_to_file' in globals():
                    log_to_file(msg)
                # Opcional: Notificar en barra de estado si existe
                # self.statusBar().showMessage(msg, 5000)

    # ----------------------------------------------------------------------
    # MÉTODOS DE ACTUALIZACIÓN Y CIERRE
    # ----------------------------------------------------------------------

    def _revisar_post_actualizacion(self):
        """
        Revisa si la app acaba de ser actualizada y muestra un mensaje.
        Se ejecuta una sola vez, poco después de que la ventana principal aparece.
        """
        # CORRECCIÓN: Se elimina el QTimer.singleShot recursivo que creaba un bucle infinito.



        flag_file = get_writable_path("update_success.flag")
        if os.path.exists(flag_file):

            self._mostrar_mensaje(
                "¡Bienvenido a la Nueva Versión!",
                "🎉 <b>A.D.A. se ha actualizado con éxito.</b><br><br>Disfruta de las nuevas mejoras.",
                QMessageBox.Information
            )
            try:
                os.remove(flag_file) # Limpiamos la bandera para que no vuelva a aparecer
            except Exception as e:
                print(f"No se pudo eliminar el archivo de bandera: {e}")






    def _limpiar_archivos_antiguos(self):
        """Busca y elimina archivos .bak de actualizaciones anteriores al iniciar."""
        try:
            # sys.executable es la ruta completa del .exe actual
            directorio_actual = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
            for archivo in os.listdir(directorio_actual):
                if archivo.lower().endswith(".exe.bak"):
                    ruta_completa = os.path.join(directorio_actual, archivo)
                    print(f"[LIMPIEZA] Se encontró un archivo de actualización antiguo: {archivo}. Eliminando...")
                    os.remove(ruta_completa)
        except Exception as e:
            print(f"[LIMPIEZA] Error al intentar eliminar archivos antiguos: {e}")

    def cleanup_on_exit(self):
        """
        Esta función se ejecuta justo antes de que la aplicación se cierre.
        """
        print("[CIERRE] La aplicación se está cerrando...")
        
        # Paramos cualquier intento previo de hilo para tomar control manual
        if self.bitacora.isRunning():
            self.bitacora.terminate()
            self.bitacora.wait(500)
            
        # Llamamos al finalizador con sync=True para que bloquee el cierre hasta enviarlo
        self.bitacora.log_session_end(sync=True)
        
        print("[CIERRE] Proceso finalizado.")

    # [ELIMINADO] cargar_ultimo_username ha sido unificado con actualizar_status_db

    def _start_update_process(self, download_url, new_version_name=None):
        """
        Inicia la UI de actualización y el hilo de descarga de forma segura.
        
        Args:
            download_url (str): URL desde donde descargar la nueva versión
            new_version_name (str, optional): Nombre del nuevo ejecutable. Si no se provee, se extrae de la URL.
        """
        # [SEGURIDAD] Evitar actualización si se corre desde código fuente (.py)
        if not getattr(sys, 'frozen', False):
            print("[UPDATE] Actualización bloqueada: Ejecutando desde código fuente.")
            self._mostrar_mensaje("Modo Desarrollo", 
                                  "La actualización automática está desactivada en modo desarrollo (script .py) para evitar daños al intérprete de Python.", 
                                  QMessageBox.Warning)
            return

        self.hide()

        # [CAMBIO CLAVE] Determinamos el nombre del nuevo archivo desde la URL
        try:
            parsed_url = urlparse(download_url)
            # os.path.basename funciona bien con rutas de URL
            new_exe_name = os.path.basename(parsed_url.path)
            if not new_exe_name: # Fallback por si la URL es extraña
                raise ValueError("No se pudo extraer el nombre del archivo de la URL")
        except Exception as e:
            self._mostrar_mensaje("Error Crítico", f"La URL de actualización no es válida: {e}", QMessageBox.Critical)
            self.close()
            return

        # Guardamos el archivo como {nuevo_nombre}.tmp
        temp_save_path = get_writable_path(f"{new_exe_name}.tmp")

        self.update_dialog = UpdateDialog(None)

        # El hilo de descarga ahora usa la nueva ruta temporal
        self.downloader = DownloaderThread(download_url, temp_save_path)
        self.downloader.progress.connect(self.update_dialog.update_progress)
        self.downloader.finished.connect(self._on_download_finished)

        self.downloader.start()
        self.update_dialog.exec_()

    def _on_download_finished(self, success, result):
        """
        Maneja la finalización de la descarga y crea un .bat
        para actualizar A.D.A. con independencia del nombre de la versión.
        """
        # Siempre cerramos el diálogo de progreso
        if self.update_dialog:
            self.update_dialog.close()

        if success:
            # --- PREPARACIÓN DE NOMBRES Y RUTAS ---
            exe_dir = os.path.dirname(sys.executable)
            # El script updater sí puede estar en AppData, siempre que apunte bien al EXE
            updater_script_path = get_writable_path("updater.bat")

            # Nombre del ejecutable actual que se va a reemplazar (ej: ADA_V3.0.0.0.exe)
            current_exe_name = os.path.basename(sys.executable)

            # Nombre del archivo temporal descargado (ej: ADA_V3.1.1.exe.tmp)
            # 'result' contiene la ruta completa guardada por el DownloaderThread
            temp_update_path = result 
            temp_update_filename = os.path.basename(temp_update_path)

            # El nombre final que tendrá el nuevo ejecutable (ej: ADA_V3.1.1.exe)
            new_exe_name = temp_update_filename.replace(".tmp", "")

            # --- CREACIÓN DEL SCRIPT .BAT MEJORADO ---
            script_content = f"""
                @echo off
                chcp 65001 > nul
                echo.
                echo    ========================================================
                echo      Actualizando A.D.A. Por favor, no cierre esta ventana.
                echo    ========================================================
                echo.

                REM Eliminar archivo flag si existe
                if exist "update_success.flag" del "update_success.flag"

                REM Espera 3 segundos para dar tiempo a que el proceso principal se cierre.
                timeout /t 3 /nobreak > nul

                REM Intenta cerrar la version anterior por si acaso.
                echo Cerrando procesos residuales de A.D.A...
                taskkill /F /IM "{current_exe_name}" > nul 2>&1

                REM Cambiamos al directorio donde está el ejecutable.
                cd /d "{exe_dir}"

                REM [CAMBIO CLAVE 1] Renombramos el ejecutable antiguo a .bak. Es más seguro que borrarlo.
                echo Creando una copia de seguridad del ejecutable actual...
                if exist "{current_exe_name}" ren "{current_exe_name}" "{current_exe_name}.bak"

                REM [CAMBIO CLAVE 2] Traemos la nueva version desde la carpeta temporal.
                echo Moviendo la nueva version a la carpeta de instalacion...
                if exist "{temp_update_path}" move /Y "{temp_update_path}" "{new_exe_name}"

                echo.
                echo    ========================================================
                echo            Actualizacion completa. ¡Gracias por esperar!
                echo         Iniciando la nueva version de A.D.A...
                echo    ========================================================
                echo.

                REM [CAMBIO CLAVE 3] Inicia la nueva version con su nuevo nombre.
                start "" "{new_exe_name}"

                REM Truco mejorado para que el script se borre a sí mismo de forma segura.
                (goto) 2>nul & del "%~f0"
                """

            try:
                with open(updater_script_path, "w", encoding="utf-8") as f:
                    f.write(script_content)



                # Mostrar mensaje de confirmación
                self._mostrar_mensaje(
                    "Actualización Lista", 
                    "✅ La actualización se ha descargado correctamente.\n\n"
                    "La aplicación se cerrará ahora para completar el proceso.\n"
                    "Se reiniciará automáticamente con la nueva versión.",
                    QMessageBox.Information
                )

                # Creamos la bandera para el mensaje de bienvenida
                flag_file = get_writable_path("update_success.flag")
                with open(flag_file, "w") as f:
                    f.write("updated")

                # Ejecutamos el .bat y cerramos la app.
                # Usamos Popen para que se ejecute en un proceso separado e independiente.
                subprocess.Popen(updater_script_path, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                QApplication.instance().quit()

            except Exception as e:
                # Manejo de error si no se puede crear el script
                self._mostrar_mensaje(
                    "Error de Actualización",
                    f"No se pudo crear el script de actualización.\\n\\nError: {e}",
                    QMessageBox.Critical
                )
                self.show() # Mostramos la ventana principal de nuevo

        else:
            # Manejo de error de descarga
            self.bitacora.log_event({
                "TipoEvento": "descarga_fallida", "Estado": "fallido",
                "MensajeError": f"Error al descargar actualizacion: {result}"
            })
            self._mostrar_mensaje(
                "Error de Descarga",
                f"No se pudo descargar la nueva versión.\\n\\nError: {result}\\n\\nLa aplicación continuará normalmente.",
                QMessageBox.Warning
            )
            self.show() # Mostramos la ventana principal de nuevo
    
    def _mi_excepcion_global(self, exc_type, exc_value, exc_traceback):
            """
            Este es el nuevo "guardián" que captura todos los errores no controlados.
            Ahora es un método de la clase para poder acceder a la bitácora.
            """
            # 1. Formateamos la información completa del error en un texto legible
            error_info = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            msg_emergencia = f"[ERROR CRÍTICO] Capturado por el guardián global:\n{error_info}"
            print(msg_emergencia)
            log_to_file(msg_emergencia) # Guardar en el log de emergencia local

            # 2. Preparamos el evento para la bitácora
            self.bitacora.log_event({
                "TipoEvento": "error_critico",
                "Estado": "fallido",
                "MensajeError": error_info # Guardamos el traceback completo en esta columna
            }, flush=True) # Forzamos el envío inmediato

            # 3. Le damos tiempo al "cartero" para que envíe el reporte
            if self.bitacora.isRunning():
                print("[BITÁCORA] Esperando para enviar el reporte de error...")
                self.bitacora.wait(5000) # Espera un máximo de 5 segundos

            # 4. Mostramos un mensaje amigable al usuario final
            self._mostrar_mensaje(
                "Error Crítico",
                "Ha ocurrido un error inesperado y A.D.A. debe cerrarse.\n\n"
                "Se ha enviado un reporte al administrador del sistema con el error para ayudarnos a solucionarlo. "
                "Disculpa las molestias.",
                QMessageBox.Critical
            )
            
            # 5. Dejamos que el programa se cierre de forma normal
            sys.__excepthook__(exc_type, exc_value, exc_traceback)



    # -----PARA EL BLOQUEO Y ACTUALIZACIÓN ---
    def _handle_remote_config_check(self, remote_config):
        # --- INICIO: NUEVA LÓGICA DE BLOQUEO PERSISTENTE ---
        # 1. Verificación offline primero
        last_block_ts = self.config.get('last_known_status_ts', 0)
        # Si no hay config remota (sin internet) y el último bloqueo fue hace menos de 7 días...
        if not remote_config and last_block_ts != 0:
            # 604800 segundos = 7 días
            if (time.time() - last_block_ts) < 604800:
                self._mostrar_mensaje(
                    "Acceso Restringido (Offline)",
                    "Este equipo fue bloqueado en la última verificación en línea. Se requiere conexión a internet para revalidar el acceso.",
                    QMessageBox.Critical
                )
                self.close()
                return
        
        # Si no hay config remota y no había bloqueo previo, simplemente salimos.
        if not remote_config:
            return
        # --- FIN: LÓGICA DE BLOQUEO PERSISTENTE ---

        should_block = False
        block_message = "Aplicación deshabilitada."
        block_title = "Acceso Denegado"

        # 2. Verificación online (con la jerarquía que ya definimos)
        if remote_config.get('is_under_maintenance', False):
            should_block = True
            block_message = remote_config.get('maintenance_message', "App deshabilitada.")
            block_title = "Mantenimiento"
        else:
            local_pc_name = platform.node()
            blocked_pc_list = remote_config.get('blocked_pc_names', [])
            if local_pc_name in blocked_pc_list:
                should_block = True
                block_message = "El acceso a A.D.A. ha sido restringido para este equipo. Contacte al administrador."
                block_title = "Acceso Restringido"
        
        if not should_block:
            try:
                min_version_str = remote_config.get('minimum_required_version', '0.0.0.0')
                
                def clean_version_tuple(v_str):
                    parts = []
                    for p in v_str.split('.'):
                        match = re.match(r'^\d+', p.strip())
                        parts.append(int(match.group(0)) if match else 0)
                    return tuple(parts)

                app_version_tuple = clean_version_tuple(VERSION)
                min_version_tuple = clean_version_tuple(min_version_str)
                
                if app_version_tuple < min_version_tuple:
                    should_block = True
                    block_message = remote_config.get('update_message', "Versión desactualizada.")
                    block_title = "Actualización Requerida"
            except Exception as e:
                print(f"Error al procesar la configuración de versión: {e}")

        # 3. Guardamos el resultado de la verificación online en el archivo local
        if should_block:
            self.config['last_known_status_ts'] = int(time.time()) # Guardamos la fecha y hora del bloqueo
        else:
            self.config['last_known_status_ts'] = 0 # Reseteamos si ya no está bloqueado
        
        # --- ACTUALIZAR METAS DESDE CONFIG REMOTA ---
        if remote_config:
            if 'META_ORIGINALES' in remote_config:
                self.config['META_ORIGINALES'] = remote_config['META_ORIGINALES']
            if 'META_COMPARTIDAS' in remote_config:
                self.config['META_COMPARTIDAS'] = remote_config['META_COMPARTIDAS']
            
            # Si la pestaña de Facebook ya existe, le avisamos para que actualice sus valores
            if hasattr(self, 'tab_facebook') and hasattr(self.tab_facebook, 'update_params_from_config'):
                self.tab_facebook.update_params_from_config(self.config)

        self.guardar_configuracion()

        # 4. Actuamos en consecuencia
        if should_block:
            # (El resto de la función para iniciar la actualización o mostrar el mensaje de bloqueo permanece exactamente igual)
            if block_title == "Actualización Requerida":
                try:
                    update_url = remote_config.get('update_url')
                    if not update_url:
                        self._mostrar_mensaje("Error Crítico", "La aplicación requiere una actualización, pero no se encontró la URL de descarga.", QMessageBox.Critical)
                        self.close()
                        return
                    # CORRECCIÓN: Usamos urlparse (ya importado al inicio del archivo) en lugar de urllib.parse.urlparse
                    new_version_name = os.path.basename(urlparse(update_url).path)
                    self.hide()
                    self._start_update_process(update_url, new_version_name)
                except Exception as e:
                    msg_err = f"No se pudo iniciar la actualización automática: {e}"
                    print(msg_err)
                    log_to_file(msg_err)
                    self._mostrar_mensaje("Error de Actualización", msg_err, QMessageBox.Critical)
                    self.close()
                return

            self.bitacora.log_event({"TipoEvento": "app_bloqueada", "Estado": block_title, "MensajeError": block_message}, flush=True)
            if self.bitacora.isRunning():
                self.bitacora.wait(3000)
            self._mostrar_mensaje(block_title, block_message, QMessageBox.Warning)
            self.close()



    def abrir_manual(self):
        # Usamos get_persistent_path para encontrar el archivo junto al ejecutable
        # tanto en desarrollo como en el .exe empaquetado.
        self.bitacora.track_activity('manual')
        ruta_manual = get_persistent_path("manualADA4.html")

        if os.path.exists(ruta_manual):
            # Usamos QDesktopServices para abrir el archivo en el navegador por defecto
            QDesktopServices.openUrl(QUrl.fromLocalFile(ruta_manual))
        else:
            self._mostrar_mensaje("Error", f"No se pudo encontrar el archivo del manual en:\n{ruta_manual}", QMessageBox.Warning)


    def _update_pulse_animation(self):
        # Esta función simplemente alterna la visibilidad de la etiqueta
        self.pulse_visible = not self.pulse_visible
        self.pulse_label.setVisible(self.pulse_visible)

    def actualizar_pulso_rendimiento(self, total_porcentaje):
        self.pulse_timer.stop() # Detenemos cualquier animación anterior

        if total_porcentaje >= 30: # ✅ Cumple
            color = "#27ae60"  # Verde
            interval = 500     # Parpadeo rápido
        elif total_porcentaje >= 20: # ⚠️ Parcial
            color = "#f39c12"  # Naranja
            interval = 300     # Parpadeo medio
        else: # ❌ No cumple
            color = "#c0392b"  # Rojo
            interval = 200    # Parpadeo lento
        
        # Aplicamos el estilo y hacemos visible la etiqueta
        self.pulse_label.setStyleSheet(f"color: {color}; font-size: 20px; padding-bottom: 4px;")
        self.pulse_label.setVisible(True)
        self.pulse_visible = True
        
        # Iniciamos el temporizador con el nuevo intervalo
        self.pulse_timer.start(interval)



    def load_stylesheet(self):
        """Carga y aplica el arquivo QSS externo."""
        qss_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ada_nova.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        else:
            print(f"Advertencia: No se encontró {qss_path}")

    def toggle_theme(self):
        self.bitacora.track_activity('temas')

        # Invierte el estado actual del modo oscuro
        self.is_dark_mode = not self.is_dark_mode
        self.config['dark_mode_enabled'] = self.is_dark_mode
        self.guardar_configuracion()
        
        # Aplicamos el cambio de propiedad
        self._apply_current_theme()
        
        # Actualizar tablas, widgets globales, gráficos y filas de totales en cascada
        self._actualizar_tema_tablas()
        self._actualizar_tema_global()  # NUEVO: Propagación agresiva
        self._update_matplotlib_theme()
        self._reaplicar_estilos_totales()
        
        # ACTUALIZACIÓN: Nuevos tabs de metas
        if hasattr(self, 'tab_metas') and self.tab_metas:
            self.tab_metas.update_theme(self.is_dark_mode)
        if hasattr(self, 'tab_cuadro_metas') and self.tab_cuadro_metas:
            self.tab_cuadro_metas.update_theme(self.is_dark_mode)
            
        # [FIX] Forzar actualización de estilo en el contenedor principal
        self.content_container.style().unpolish(self.content_container)
        self.content_container.style().polish(self.content_container)
        
        # [FIX] Forzar redibujado de la ventana y todos sus hijos
        self.repaint()

    def _apply_current_theme(self):
        # Establecemos la propiedad dinámica en la ventana principal
        theme_value = "dark" if self.is_dark_mode else "light"
        self.setProperty("theme", theme_value)
        
        # Forzamos la actualización de estilos para que la propiedad surta efecto
        self.style().unpolish(self)
        self.style().polish(self)
        
        # Actualizamos texto del botón en el sidebar
        if hasattr(self, 'sidebar_theme_button'):
            if self.is_dark_mode:
                self.sidebar_theme_button.setText("Claro ☀️") 
            else:
                self.sidebar_theme_button.setText("Oscuro ☾")
            
        # IMPORTANTE: Actualizar Matplotlib si existe
        if hasattr(self, '_update_matplotlib_theme'):
             self._update_matplotlib_theme()
             
        # También forzamos update en el content container

    def _update_matplotlib_theme(self):
        """Actualiza los gráficos de Matplotlib según el tema actual."""
        is_dark = self.is_dark_mode
        
        # Colores
        bg_color = "#1e293b" if is_dark else "#ffffff"
        text_color = "#f1f5f9" if is_dark else "#334155"
        grid_color = "#334155" if is_dark else "#e2e8f0"
        
        # Lista de figuras a actualizar
        figures = [
            (self.fig_rendimiento, self.canvas_rendimiento),
            (self.fig_demografia_sexo, self.canvas_demografia_sexo),
            (self.fig_demografia_tipo, self.canvas_demografia_tipo),
            (self.fig_servicios, self.canvas_servicios)
        ]
        
        for fig, canvas in figures:
            if fig and canvas:
                fig.patch.set_facecolor(bg_color)
                
                for ax in fig.axes:
                    ax.set_facecolor(bg_color)
                    ax.tick_params(colors=text_color)
                    ax.yaxis.label.set_color(text_color)
                    ax.xaxis.label.set_color(text_color)
                    ax.title.set_color(text_color)
                    
                    # Update spines
                    for spine in ax.spines.values():
                        spine.set_edgecolor(grid_color)
                        
                    # Re-apply grid style if using seaborn or custom
                    ax.grid(True, color=grid_color)
                    
                    # Update legend if exists
                    legend = ax.get_legend()
                    if legend:
                        legend.get_frame().set_facecolor(bg_color)
                        legend.get_frame().set_edgecolor(grid_color)
                        for text in legend.get_texts():
                            text.set_color(text_color)
                            
                canvas.draw_idle()



    def _mostrar_mensaje(self, titulo, texto, icono=QMessageBox.Information):
        """
        Muestra un cuadro de diálogo personalizado con el ícono de la ventana principal.
        """
        # Crea una instancia del cuadro de mensaje, asociándolo a la ventana principal (self)
        msg_box = QMessageBox(self)
        
        # --- LA CLAVE ESTÁ AQUÍ ---
        # Establece el MISMO ícono de la ventana principal en el cuadro de diálogo
        msg_box.setWindowIcon(self.windowIcon())
        
        # Establece el ícono interno del mensaje (check, advertencia, error, etc.)
        msg_box.setIcon(icono)
        
        # Configura el título de la ventana del diálogo y el texto principal
        msg_box.setWindowTitle(f"A.D.A. - {titulo}")
        msg_box.setText(texto)
        msg_box.setTextFormat(Qt.RichText)
        
        # Muestra el diálogo y espera a que el usuario lo cierre
        msg_box.exec_()



    def get_config_path(self):
        # Usamos la misma carpeta base que get_writable_path para coherencia
        config_dir = Path(os.environ.get('APPDATA')) / 'ADA_Nova'
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / 'configADA.json'

    def cargar_configuracion(self):
            config_path = self.get_config_path()
            # Valores por defecto si el archivo no existe o una clave falta
            defaults = {
                'computadoras': 6,
                'modo_guerrero_activo': False, # Por defecto, el modo está desactivado
                'ultima_carpeta_raiz': '',
                'dark_mode_enabled': False,
                'last_known_status_ts': 0,  # <-- PARA EL BLOQUEO
                'META_ORIGINALES': 15,
                'META_COMPARTIDAS': 15
            }
            try:
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        # Asegurarse de que todas las claves existan, si no, usar el valor por defecto
                        defaults.update(config)
                        return defaults
            except Exception as e:
                print(f"Error cargando configuración: {e}")
            return defaults

    def guardar_configuracion(self):
        config_path = self.get_config_path()
        try:
            # Ahora guardamos el diccionario self.config completo
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error guardando configuración: {str(e)}")
            #traceback.print_exc()

    def setup_icon(self):
        icon_paths = [
            os.path.join(BASE_DIR, 'iconBDVicTor_D.ico'),
            'iconBDVicTor_D.ico',
            ':/icons/iconBDVicTor_D.ico'
        ]
        fallback_icon = self.style().standardIcon(QStyle.SP_ComputerIcon)

        for path in icon_paths:
            icon = QIcon(path)
            if not icon.isNull():
                self.setWindowIcon(icon)
                return
        self.setWindowIcon(fallback_icon)

    def limpiar_todas_tablas(self):
        # No limpiamos el usuario aquí para mantenerlo visible si ya se cargó
        for tabla in [self.tab_resumen, self.tab_rendimiento,
                      self.tab_registros, self.tab_servicios]:
            tabla.clear()
            tabla.setRowCount(0)
            tabla.setColumnCount(0)
            tabla.setHorizontalHeaderLabels([])
            self.pulse_label.setVisible(False) # ocultamos el pulso
        if hasattr(self, 'btn_exportar_pdf'):
            self.btn_exportar_pdf.setEnabled(False)
        
        # Limpiar y redibujar los gráficos a su estado inicial (vacío)
        if self.fig_rendimiento: 
            self.fig_rendimiento.clear()
            self.canvas_rendimiento.draw()
        if self.fig_demografia_sexo: 
            self.fig_demografia_sexo.clear()
            self.canvas_demografia_sexo.draw()
        if self.fig_demografia_tipo: 
            self.fig_demografia_tipo.clear()
            self.canvas_demografia_tipo.draw()
        if self.fig_servicios: 
            self.fig_servicios.clear()
            self.canvas_servicios.draw()

        self.pulse_timer.stop()
        self.pulse_label.setVisible(False)



    # --- LÓGICA DE NOVEDADES ---
    def actualizar_novedades(self, novedades_list):
        """
        Slot conectado a MetasCardWidget. Se dispara cuando el worker descarga novedades.
        """
        try:
            self.novedades_data = novedades_list
            
            # --- NUEVO: RESETEO AUTOMÁTICO DE HISTORIAL ---
            # Si la lista está vacía (Sheets limpio), borramos historial para permitir reuso de IDs.
            if not novedades_list:
                 self.novedades_manager.clear_history()
            # ----------------------------------------------

            unread_count = self.novedades_manager.count_unread(novedades_list)
            
            # Actualizar badge en Sidebar
            if hasattr(self, 'sidebar'):
                self.sidebar.set_novedades_badge(unread_count)
            
            # 1. VERIFICAR EVENTO ESPECIAL (Prioridad máxima, popup centrado exclusivo)
            evento_especial = self.novedades_manager.get_unread_event(novedades_list)
            if evento_especial:
                 QTimer.singleShot(2000, lambda: self.mostrar_evento_unico(evento_especial))
                 return # Si mostramos evento, no mostramos la ventana general aun
                
            # 2. Verificar alertas de alta prioridad (Popup general estándar)
            urgent_news = self.novedades_manager.get_unread_high_priority(novedades_list)
            if urgent_news:
                # Mostrar la ventana automáticamente si hay algo urgente NO LEÍDO
                QTimer.singleShot(2000, self.mostrar_novedades)
        except Exception as e:
            print(f"Error procesando novedades: {e}")

    def mostrar_evento_unico(self, evento_data):
        """Muestra un popup exclusivo para un evento importante."""
        try:
            dialog = SingleEventWindow(evento_data, self.novedades_manager, self)
            dialog.finished.connect(self.on_novedades_closed) # Actualizar badge al cerrar
            dialog.exec_()
        except Exception as e:
            print(f"Error mostrando evento único: {e}")

    def mostrar_novedades(self):
        """Abre la ventana de novedades."""
        # 1. Intentar recuperación pasiva desde cache
        if self.novedades_data is None:
            if hasattr(self, 'tab_metas') and hasattr(self.tab_metas, 'current_data'):
                data = self.tab_metas.current_data
                if data and 'novedades' in data:
                    self.novedades_data = data['novedades']
        
        # 2. Si sigue vacío, manejar el estado de carga
        if self.novedades_data is None:
            if hasattr(self, 'tab_metas'):
                # A) Si ya está cargando, avisar al usuario
                if self.tab_metas.worker and self.tab_metas.worker.isRunning():
                    self._mostrar_mensaje("Sincronizando", "⬇️ Obteniendo las últimas novedades...\n\nPor favor espera unos segundos y vuelve a intentar.", QMessageBox.Information)
                    return
                
                # B) Si no está cargando, forzar la carga (sin requerir usuario para obtener info global)
                print("[NOVEDADES] Forzando actualización de datos por petición de usuario...")
                self.tab_metas.refresh_data(require_user_id=False)
                self._mostrar_mensaje("Actualizando", "🔄 Iniciando descarga de novedades.\n\nPor favor, espera unos segundos mientras conectamos con la nube y vuelve a hacer clic.", QMessageBox.Information)
                return

            self._mostrar_mensaje("Sin Información", "No hay novedades disponibles y no se pudo iniciar la sincronización.\nAsegúrese de que se hayan cargado los datos de Metas.")
            return

        try:
            window = NovedadesWindow(self.novedades_data, self.novedades_manager, self)
            # Conectamos finished para actualizar badge al cerrar (ya que se marcan como leídos)
            window.finished.connect(self.on_novedades_closed)
            window.exec_()
        except Exception as e:
            print(f"Error abriendo ventana novedades: {e}")

    def on_novedades_closed(self, result=None):
        """Se llama al cerrar la ventana de novedades para refrescar el badge."""
        if self.novedades_data:
            unread_count = self.novedades_manager.count_unread(self.novedades_data)
            if hasattr(self, 'sidebar'):
                self.sidebar.set_novedades_badge(unread_count)
    # ---------------------------

    def init_ui(self):
        self.setWindowTitle(f"A.D.A. - Analizador de Datos y Actividades v{VERSION_UI}")
        self.setMinimumSize(1200, 800)
        self.showMaximized()

        # --- Layout Principal Global (Horizontal) ---
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 1. Sidebar (Barra Lateral)
        self.sidebar = Sidebar(self)
        main_layout.addWidget(self.sidebar)

        # 2. Área de Contenido (Stacked Widget)
        # Usamos un QFrame contenedor para el fondo del contenido
        self.content_container = QFrame()
        self.content_container.setObjectName("ContentContainer")
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.pages_widget = QStackedWidget()
        content_layout.addWidget(self.pages_widget)
        
        # --- Footer se mueve dentro del área de contenido, abajo ---
        # Pero primero añadimos las páginas
        
        main_layout.addWidget(self.content_container)

        # --- Pestaña 1: Visitas ---
        self.tab_visitas = QWidget()
        visitas_layout = QVBoxLayout()
        visitas_layout.setContentsMargins(20, 20, 20, 20)
        
        visitas_layout.addWidget(self._crear_panel_configuracion())
        visitas_layout.addLayout(self._crear_panel_acciones())
        visitas_layout.addWidget(self._crear_tabs_resultados())
        
        self.tab_visitas.setLayout(visitas_layout)
        self.pages_widget.addWidget(self.tab_visitas)
        
        # --- Pestaña 2: Analizador de Facebook ---
        self.tab_facebook = FacebookAnalyzerWidget(config=self.config, main_app=self)
        self.pages_widget.addWidget(self.tab_facebook)
        
        # --- Pestaña 3: Metas ---
        self.tab_metas = MetasCardWidget(main_app=self)
        self.tab_metas.novedades_available.connect(self.actualizar_novedades) # Conectar señal de novedades
        self.pages_widget.addWidget(self.tab_metas)

        # --- Pestaña 4: Cuadro de Metas (Facilitador) ---
        self.tab_cuadro_metas = MetasTableView(main_app=self)
        self.pages_widget.addWidget(self.tab_cuadro_metas)

        # --- Footer Global ---
        content_layout.addLayout(self._crear_footer())

        # --- Inicialización ---
        self.actualizar_visibilidad_guerrero()
        self.sidebar.btn_visitas.setChecked(True)
        
        # Alias para compatibilidad con métodos existentes
        self.combo_subcarpetas = self.sidebar.combo_subs
        self.label_info_carpeta = self.sidebar.label_info_carpeta

        # Restaurar carpeta raíz
        if self.carpeta_raiz and os.path.exists(self.carpeta_raiz):
            self.label_info_carpeta.setText(f"Raíz: {os.path.basename(self.carpeta_raiz)}")
            self.cargar_subcarpetas()



        self.load_stylesheet() # Cargar estilos externos
        self._apply_current_theme()
        self._actualizar_tema_global()  # CRÍTICO: Propagar tema a widgets iniciales
        self._update_matplotlib_theme() # CRÍTICO: Aplicar tema a gráficos desde inicio
        QTimer.singleShot(1000, self.actualizar_status_db)

    def actualizar_status_db(self):
        """
        Verifica la existencia de la base de datos y lanza la carga de usuario en HILO SEPARADO.
        Esto previene el crash 'Access Violation' al evitar conflictos COM/ODBC en el MainThread.
        """
        if 'OneDrive' in self.db_path and not os.path.exists(self.db_path):
             import time
             time.sleep(0.5)

        if not os.path.exists(self.db_path):
            self.label_ruta.setText(f"❌ DESCONECTADO: {self.db_path}")
            self.label_ruta.setProperty("status", "disconnected")
            self.label_ruta.style().unpolish(self.label_ruta)
            self.label_ruta.style().polish(self.label_ruta)
            self.current_username = None
            self.label_ultimo_user.setText("👤 Usuario: --")
        else:
            self.label_ruta.setText(f"✅ Conectado: {self.db_path}")
            self.label_ruta.setProperty("status", "connected")
            self.label_ruta.style().unpolish(self.label_ruta)
            self.label_ruta.style().polish(self.label_ruta)
            
            
            # --- CORRECCIÓN: Usar Hilo con COM Wrapper para evitar Access Violation ---
            self.label_ultimo_user.setText("👤 Usuario: Cargando...")
            
            # Instanciar y ejecutar el hilo
            self.user_loader_thread = UserLoaderThread(self.db_path, DB_PASSWORD)
            self.user_loader_thread.finished.connect(self._on_user_loaded)
            self.user_loader_thread.start()
            
            # Nota: El manejo de errores y actualización de UI se hace en _on_user_loaded
            # al recibir la señal finished.

    def _on_user_loaded(self, user):
        """Callback ejecutado cuando el hilo termina de buscar el usuario."""
        try:
            if user == "ONEDRIVE_NOT_DOWNLOADED":
                self.current_username = None
                self.label_ultimo_user.setText("👤 Usuario: OneDrive (no descargado)")
                QMessageBox.warning(self, "BD No Disponible", "Base de datos en OneDrive no descargada.")
                log_to_file("[INICIO] BD en OneDrive no disponible")
            elif user == "ERROR_LOAD":
                 self.current_username = None
                 self.label_ultimo_user.setText("👤 Usuario: Error")
                 log_to_file("[INICIO] Error al cargar usuario (hilo).")
            elif user:
                # ---------------------------------------------------------------
                # DETECCIÓN AUTOMÁTICA DE CAMBIO DE BASE DE DATOS
                # Compara el usuario que trae Access con el último usuario
                # guardado en el caché SQLite local. Si no coinciden significa
                # que se cargó una BD diferente → reset total + sync desde cero.
                # ---------------------------------------------------------------
                try:
                    rows_cache = db.execute_query(
                        "SELECT username FROM registros_ventas_cache "
                        "ORDER BY datetime DESC LIMIT 1"
                    )
                    cached_user = str(rows_cache[0]['username']).strip() if rows_cache else None

                    if cached_user and cached_user.lower() != user.strip().lower():
                        log_to_file(
                            f"[DB CHANGE] Cambio de base detectado. "
                            f"Caché='{cached_user}' → Access='{user}'. "
                            f"Reseteando caché y relanzando sync completo..."
                        )
                        db.reset_sync_data()
                        # Re-lanzar sync desde 0. Si hay un thread en curso le damos
                        # 3 seg para que termine antes de lanzar el nuevo.
                        if hasattr(self, 'sync_thread') and self.sync_thread.isRunning():
                            QTimer.singleShot(3000, self.trigger_access_sync)
                        else:
                            self.trigger_access_sync()
                except Exception as e_detect:
                    log_to_file(f"[DB CHANGE] Error en detección de cambio de BD: {e_detect}")
                # ---------------------------------------------------------------

                self.current_username = user
                self.label_ultimo_user.setText(f"👤Usuario: {user}")
                self.bitacora.update_user_id(user)
                log_to_file(f"[INICIO] Usuario detectado automáticamente: {user}")
                if hasattr(self, 'tab_metas') and self.tab_metas:
                    # Usamos require_user_id=True para que coincida exactamente con el comportamiento del menú
                    self.tab_metas.refresh_data(force_reload=False, require_user_id=True)
                
                # También actualizar el cuadro de metas si existe (pestaña 3)
                if hasattr(self, 'tab_cuadro_metas') and self.tab_cuadro_metas:
                    self.tab_cuadro_metas.refresh_data()
            else:
                self.current_username = None
                self.label_ultimo_user.setText("👤 Usuario: Sin datos")
                log_to_file("[INICIO] No se encontró ningún registro en la BD")
                # También refrescamos Metas para que muestre "Sin Datos" o limpie la vista
                if hasattr(self, 'tab_metas') and self.tab_metas:
                    self.tab_metas.refresh_data(force_reload=False, require_user_id=False)
                
                if hasattr(self, 'tab_cuadro_metas') and self.tab_cuadro_metas:
                     self.tab_cuadro_metas.refresh_data()
        except Exception as e:
            log_to_file(f"[ERROR] Error en callback de usuario: {e}")

    def ir_a_metas(self):
        """Abre el archivo de Google Sheets con las metas en el navegador."""
        url_metas = "https://docs.google.com/spreadsheets/d/1xqHRJU-tH82PU1jY57Zt3S5fCgmigy2X9rF5x9CvbFI/edit?usp=sharing"
        QDesktopServices.openUrl(QUrl(url_metas))
        log_to_file("[MODO GUERRERO] Abriendo Google Sheets de Metas en el navegador.")

    def ver_detalle_infoplaza(self, infoplaza_id):
        """
        Navega a la pestaña de Metas Mensuales y carga los datos de una Infoplaza específica.
        Invocado por doble clic en el Cuadro de Metas.
        """
        log_to_file(f"[NAVEGACIÓN] Abriendo detalle de Infoplaza {infoplaza_id}")
        
        # 1. Cambiar a la pestaña de Metas Mensuales
        if hasattr(self, 'tab_metas') and self.tab_metas:
            # Asegurarnos de que el widget de páginas muestre la pestaña correcta
            self.pages_widget.setCurrentWidget(self.tab_metas)
            
            # 2. Forzar la carga de datos para este ID específico
            # Nota: Esto requiere que MetasCardWidget.refresh_data acepte 'specific_id'
            if hasattr(self.tab_metas, 'refresh_data'):
                # Usamos un pequeño delay para asegurar que la UI se actualice primero
                QTimer.singleShot(100, lambda: self.tab_metas.refresh_data(
                    force_reload=False, 
                    require_user_id=False, # No requerimos usuario logueado porque estamos viendo otro
                    specific_id=str(infoplaza_id)
                ))

    def cambiar_pagina(self, index):
        """Cambia la página del QStackedWidget."""
        self.pages_widget.setCurrentIndex(index)
        # Simulamos evento de cambio de pestaña para logs
        nombres = ["Visitas", "Facebook", "Metas", "Cuadro de Metas"]
        if 0 <= index < len(nombres):
            self._on_tab_changed_by_name(nombres[index])
            
    def _on_tab_changed_by_name(self, tab_name):
        key = 'Otros'
        if "Visitas" in tab_name: 
            key = 'Visitas'
        elif "Facebook" in tab_name: 
            key = 'Facebook'
        elif "Cuadro de Metas" in tab_name:
            # Caso específico: Cuadro de Metas (General)
            key = 'Metas' # Usamos la misma categoría de métrica
            if hasattr(self, 'tab_metas') and hasattr(self.tab_metas, 'refresh_data'):
                # Refresh SIN requerir usuario
                self.tab_metas.refresh_data(require_user_id=False)
        elif "Metas" in tab_name:
            # Caso "Metas" (Individual) - si entra aquí es porque no entró en Cuadro de Metas
            key = 'Metas'
            if hasattr(self, 'tab_metas') and hasattr(self.tab_metas, 'refresh_data'):
                # Refresh ESTÁNDAR (requiere usuario)
                self.tab_metas.refresh_data(require_user_id=True)
        else: 
            key = 'Otros'
        
        self.bitacora.track_activity(f"tab_click_{key}")
    
    # --- Eliminamos métodos obsoletos ---
    # ir_a_metas se mantiene, _on_tab_changed original se elimina/reemplaza

    def _crear_panel_configuracion(self):
        config_group = QGroupBox("")
        config_group.setProperty("class", "Card")
        
        main_layout = QVBoxLayout(config_group)
        main_layout.setSpacing(15)

        # --- SECCIÓN: RUTA DE LA BASE DE DATOS ---
        ruta_layout = QHBoxLayout()
        labels_v_layout = QVBoxLayout()
        labels_v_layout.setSpacing(4)
        
        titulo_ruta = QLabel("Ruta de la Base de Datos")
        titulo_ruta.setProperty("class", "h2")
        
        self.label_ruta = QLabel(f"{self.db_path}")
        self.label_ruta.setObjectName("ConnectionStatus")
        self.label_ruta.setFont(QFont("Segoe UI", 10))
        self.label_ruta.setWordWrap(True)
        
        labels_v_layout.addWidget(titulo_ruta)
        labels_v_layout.addWidget(self.label_ruta)
        
        self.btn_cambiar = QPushButton("...")
        self.btn_cambiar.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.btn_cambiar.setIconSize(QSize(20, 20))
        self.btn_cambiar.setFixedSize(40, 40)
        self.btn_cambiar.setToolTip("Cambiar archivo de base de datos (.mdb)")
        self.btn_cambiar.clicked.connect(self.cambiar_ruta)
        
        ruta_layout.addLayout(labels_v_layout, 1) 
        ruta_layout.addWidget(self.btn_cambiar, 0, Qt.AlignVCenter)
        
        main_layout.addLayout(ruta_layout)

        # Separador sutil entre secciones
        linea_separadora = QFrame()
        linea_separadora.setFrameShape(QFrame.HLine)
        main_layout.addWidget(linea_separadora)

        # --- SECCIÓN: PARÁMETROS DEL REPORTE ---
        titulo_parametros = QLabel("Parámetros del Reporte")
        titulo_parametros.setProperty("class", "h2")
        main_layout.addWidget(titulo_parametros)
        
        # Grid de controles (Año, Computadoras, Meta, Usuario)
        controls_row_layout = QHBoxLayout()

        # Año
        año_label = QLabel("Año del Reporte:")
        año_label.setProperty("class", "h2")
        self.spin_anio = QSpinBox()
        self.spin_anio.setRange(2020, 2040)
        self.spin_anio.setValue(datetime.now().year)
        self.spin_anio.setObjectName("HighlightSpinBox")

        # Computadoras
        self.label_computadoras = QLabel("Computadoras:")
        self.label_computadoras.setProperty("class", "h2")
        self.spin_computadoras = QSpinBox()
        self.spin_computadoras.setRange(1, 30)
        self.spin_computadoras.setValue(self.config.get('computadoras', 6))
        self.spin_computadoras.valueChanged.connect(self.actualizar_meta)
        self.spin_computadoras.setObjectName("HighlightSpinBox")

        # Meta
        # Meta - Título y Valor separados
        lbl_meta_titulo = QLabel("META MENSUAL:")
        lbl_meta_titulo.setProperty("class", "h2")
        
        self.label_meta = QLabel(f"{self.meta_mensual}")
        self.label_meta.setAlignment(Qt.AlignCenter)
        self.label_meta.setStyleSheet("font-size: 14px; font-weight: bold; color: #0284c7; background-color: #e0f2fe; padding: 4px 10px; border-radius: 6px; border: 1px solid #7dd3fc;")
        
        
        
        self.label_ultimo_user = QLabel("👤 Usuario: Desconocido")
        self.label_ultimo_user.setAlignment(Qt.AlignCenter)
        self.label_ultimo_user.setStyleSheet("font-size: 14px; font-weight: bold; color: #0284c7; background-color: #e0f2fe; padding: 4px 10px; border-radius: 6px; border: 1px solid #7dd3fc;")

        self.pulse_label = QLabel("●")
        self.pulse_label.setToolTip("Pulso de Rendimiento General")
        self.pulse_label.setVisible(False)
        self.pulse_label.setObjectName("PulseLabel")

        self.btn_reset_db = QToolButton()
        self.btn_reset_db.setObjectName("ResetDbIcon")
        self.btn_reset_db.setAutoRaise(True)
        self.btn_reset_db.setIconSize(QSize(16, 16))
        self.btn_reset_db.setToolTip("Reestablecer Base de Datos Local (Ctrl+Shift+R)")
        self.btn_reset_db.clicked.connect(self.confirmar_reinicio_bd)
        self._update_reset_button_icon()

        controls_row_layout.addWidget(año_label)
        controls_row_layout.addWidget(self.spin_anio)
        controls_row_layout.addSpacing(45)
        controls_row_layout.addWidget(self.label_computadoras)
        controls_row_layout.addWidget(self.spin_computadoras)
        controls_row_layout.addSpacing(30)
        controls_row_layout.addWidget(lbl_meta_titulo)
        controls_row_layout.addWidget(self.label_meta)
        controls_row_layout.addSpacing(30)
        controls_row_layout.addWidget(self.label_ultimo_user)
        controls_row_layout.addWidget(self.btn_reset_db)
        controls_row_layout.addWidget(self.pulse_label)
        controls_row_layout.addStretch()

        main_layout.addLayout(controls_row_layout)
        
        # Meses Checkboxes
        self.meses_checkboxes = [QCheckBox(mes) for mes in MESES]
        meses_grid = QGridLayout()
        num_cols = 6
        for i, cb in enumerate(self.meses_checkboxes):
            cb.setFont(QFont("Segoe UI", 10))
            meses_grid.addWidget(cb, i // num_cols, i % num_cols)
        
        main_layout.addLayout(meses_grid)
        
        # Preseleccionar mes actual
        mes_actual = datetime.now().month - 1
        if 0 <= mes_actual < len(self.meses_checkboxes):
            self.meses_checkboxes[mes_actual].setChecked(True)

        # Botones rápidos
        btns_layout = QHBoxLayout()
        btn_definitions = [
            ("1er Cuatr.", range(4)), ("2do Cuatr.", range(4, 8)), ("3er Cuatr.", range(8, 12)),
            ("1er Sem.", range(6)), ("2do Sem.", range(6, 12)), ("Todo el Año", range(12)), ("Limpiar", [])
        ]
        for text, indices in btn_definitions:
            btn = QPushButton(text)
            btn.setProperty("class", "ghost")
            btn.clicked.connect(lambda _, ix=indices: self.seleccionar_meses(ix))
            btn.setMinimumHeight(35)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            btns_layout.addWidget(btn)

        main_layout.addLayout(btns_layout)
        return config_group
        
    def _crear_panel_acciones(self):
        btns_main = QHBoxLayout()
        self.btn_ejecutar = QPushButton("Ejecutar Análisis")
        self.btn_ejecutar.setObjectName("ExecuteBtn")
        self.btn_exportar = QPushButton("Exportar a Excel")
        self.btn_exportar.setObjectName("ExportBtn")
        
        self.btn_exportar_pdf = QPushButton("Exportar a PDF")
        self.btn_exportar_pdf.setObjectName("ExportPdfBtn")
        self.btn_exportar_pdf.setVisible(False)
        self.btn_exportar_pdf.setEnabled(False)
        self.btn_exportar_pdf.clicked.connect(self.exportar_pdf_ejecutivo)
        
        self.btn_ejecutar.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_exportar.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btn_exportar_pdf.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        
        for btn in [self.btn_ejecutar, self.btn_exportar, self.btn_exportar_pdf]:
            btn.setIconSize(QSize(24, 24))
            btn.setMinimumHeight(45)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.btn_ejecutar.clicked.connect(self.ejecutar_analisis)
        self.btn_exportar.clicked.connect(self.exportar_excel)
        
        btns_main.addStretch()
        btns_main.addWidget(self.btn_ejecutar)
        btns_main.addWidget(self.btn_exportar)
        btns_main.addWidget(self.btn_exportar_pdf)
        btns_main.addStretch()
        return btns_main
        
    # --- CONFIGURACIÓN UI GLOBAL ---
    def configurar_tabla(self, table):
        """Configura el estilo minimalista base para las tablas."""
        table.setShowGrid(False)
        table.setSortingEnabled(False)
        table.horizontalHeader().setHighlightSections(False)
        
        # CRÍTICO: Desactivar colores alternos para que el color de fondo manual (totales) tenga prioridad
        table.setAlternatingRowColors(False)
        
        # Selección de fila completa y sin foco visual individual
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setFocusPolicy(Qt.NoFocus)
        
        # NUEVO: Establecer tema inicial
        theme_value = "dark" if self.is_dark_mode else "light"
        table.setProperty("theme", theme_value)
        
        # Aseguramos que el estilo se refresque
        table.style().unpolish(table)
        table.style().polish(table)

    # --- GESTIÓN DE ESTILOS DE TABLAS (TOTALES) ---
    def _aplicar_estilo_total(self, item):
        """Aplica el estilo visual a la celda de totales basándose en el tema actual."""
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)  # Tamaño aumentado para destacar
        item.setFont(font)
        
        # Colores definidos para coincidir con el diseño solicitado
        # Claro: Azul suave (#e0f2fe) | Oscuro: Azul marino (#1e3a8a)
        bg_color = QColor("#1e3a8a") if self.is_dark_mode else QColor("#e0f2fe")
        text_color = QColor("#ffffff") if self.is_dark_mode else QColor("#000000")
        
        item.setBackground(bg_color)
        item.setForeground(text_color)

    def _reaplicar_estilos_totales(self):
        """Recorre todas las tablas y actualiza el estilo de las filas de totales al cambiar el tema."""
        tablas = [self.tab_resumen, self.tab_rendimiento, self.tab_servicios]
        
        for tabla in tablas:
            if not hasattr(tabla, 'rowCount') or tabla.rowCount() == 0:
                continue
                
            # Asumimos que la fila de totales es siempre la última si existe fila "TOTAL GENERAL"
            # Pero buscamos por contenido para ser seguros
            rows = tabla.rowCount()
            cols = tabla.columnCount()
            
            for r in range(rows):
                # Verificamos si es fila de total (usando la primera columna como referencia habitual)
                first_item = tabla.item(r, 0)
                if first_item and "TOTAL" in first_item.text().upper():
                    for c in range(cols):
                        item = tabla.item(r, c)
                        if item:
                            self._aplicar_estilo_total(item)

    def _actualizar_tema_tablas(self):
        """Propaga el tema actual a todas las tablas del Dashboard y fuerza actualización de estilo."""
        theme_value = "dark" if self.is_dark_mode else "light"
        tablas = [self.tab_resumen, self.tab_rendimiento, self.tab_servicios, self.tab_registros]
        
        for tabla in tablas:
            if hasattr(tabla, 'setProperty'):
                # Establecer propiedad de tema
                tabla.setProperty("theme", theme_value)
                # Forzar actualización de estilo completo
                tabla.style().unpolish(tabla)
                tabla.style().polish(tabla)
                # Redibujar tabla
                tabla.update()

    def _actualizar_tema_global(self):
        """Propaga el tema actual a TODOS los widgets de la aplicación de forma recursiva."""
        theme_value = "dark" if self.is_dark_mode else "light"
        
        # Lista de tipos de widgets que deben recibir la propiedad theme
        widget_types = (QWidget, QLabel, QPushButton, QCheckBox, QFrame, QGroupBox, QTabWidget)
        
        # Buscar todos los widgets hijos de forma recursiva
        all_widgets = self.findChildren(QWidget)
        
        for widget in all_widgets:
            # Establecer propiedad theme en cada widget
            widget.setProperty("theme", theme_value)
            # Forzar actualización de estilo
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        
        self._update_reset_button_icon()

    def _crear_tabs_resultados(self):
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Segoe UI", 11, QFont.Bold))

        # --- Pestaña Resumen Mensual con Ícono ---
        tab1_components = self.crear_tabla_con_filtros("Resumen Mensual", ["Todos"] + MESES, "Filtrar por Mes:")
        self.tab_resumen = tab1_components['tabla']
        self.tabs.addTab(tab1_components['widget'], "Resumen Mensual")

        # --- Pestaña Rendimiento Mensual con Ícono ---
        tab2_components = self.crear_tabla_con_filtros("Rendimiento Mensual", ["Todos"] + MESES, "Filtrar por Mes:")
        self.tab_rendimiento = tab2_components['tabla']
        self.tabs.addTab(tab2_components['widget'], "Rendimiento Mensual")

        # --- Pestaña Registros Detallados ---
        tab3_components = self.crear_tabla_con_filtros("Registros", ["Todos", "Fecha", "Mes", "Username", "ItemName","Servicio", "Sexo", "Tipo", "Observación"], "Filtrar por:")
        self.tab_registros = tab3_components['tabla']
        self.tabs.addTab(tab3_components['widget'], "Registros Detallados")

        # --- Pestaña Servicios por Mes ---
        tab4_components = self.crear_tabla_con_filtros("Servicios por Mes", ["Todos"] + MESES, "Filtrar por Mes:")
        self.tab_servicios = tab4_components['tabla']
        self.tabs.addTab(tab4_components['widget'], "Servicios")
        
        # --- INICIO DE LA MODIFICACIÓN: Iconos específicos para cada gráfico ---
        self.tabs.addTab(self._crear_panel_grafico_rendimiento(), self.style().standardIcon(QStyle.SP_ArrowUp), "Gráfico de Rendimiento")
        self.tabs.addTab(self._crear_panel_grafico_demografia_sexo(), self.style().standardIcon(QStyle.SP_DesktopIcon), "Gráfico de Género")
        self.tabs.addTab(self._crear_panel_grafico_demografia_tipo(), self.style().standardIcon(QStyle.SP_FileDialogNewFolder), "Gráfico de Tipo Usuario")
        self.tabs.addTab(self._crear_panel_grafico_servicios(), self.style().standardIcon(QStyle.SP_ToolBarHorizontalExtensionButton), "Gráfico de Servicios")
        # --- FIN DE LA MODIFICACIÓN ---

        return self.tabs
    
    # --- MÉTODOS PARA CREAR PANELES DE GRÁFICOS INDIVIDUALES ---
    def _crear_panel_grafico_rendimiento(self):
        widget = QWidget()
        layout = QVBoxLayout() 
        widget.setLayout(layout) 
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.fig_rendimiento = Figure(figsize=(10, 6), dpi=100)
        # Aplicar tema inmediatamente al crear la figura
        bg_color = "#1e293b" if self.is_dark_mode else "#ffffff"
        self.fig_rendimiento.patch.set_facecolor(bg_color)
        
        self.canvas_rendimiento = FigureCanvas(self.fig_rendimiento)
        layout.addWidget(self.canvas_rendimiento)

        btn_save = QPushButton("Guardar Gráfico")
        btn_save.setIcon(self.style().standardIcon(QStyle.SP_DriveFDIcon))
        btn_save.clicked.connect(lambda: self._save_graph(self.fig_rendimiento, "Rendimiento Mensual"))
        layout.addWidget(btn_save, 0, Qt.AlignRight)

        return widget

    def _crear_panel_grafico_demografia_sexo(self):
        widget = QWidget()
        layout = QVBoxLayout() 
        widget.setLayout(layout) 
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.fig_demografia_sexo = Figure(figsize=(10, 6), dpi=100)
        # Aplicar tema inmediatamente al crear la figura
        bg_color = "#1e293b" if self.is_dark_mode else "#ffffff"
        self.fig_demografia_sexo.patch.set_facecolor(bg_color)
        
        self.canvas_demografia_sexo = FigureCanvas(self.fig_demografia_sexo)
        layout.addWidget(self.canvas_demografia_sexo)

        btn_save = QPushButton("Guardar Gráfico")
        btn_save.setIcon(self.style().standardIcon(QStyle.SP_DriveFDIcon))
        btn_save.clicked.connect(lambda: self._save_graph(self.fig_demografia_sexo, "Visitas Mensuales por Género"))
        layout.addWidget(btn_save, 0, Qt.AlignRight)

        return widget

    def _crear_panel_grafico_demografia_tipo(self):
        widget = QWidget()
        layout = QVBoxLayout() 
        widget.setLayout(layout) 
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.fig_demografia_tipo = Figure(figsize=(10, 6), dpi=100)
        # Aplicar tema inmediatamente al crear la figura
        bg_color = "#1e293b" if self.is_dark_mode else "#ffffff"
        self.fig_demografia_tipo.patch.set_facecolor(bg_color)
        
        self.canvas_demografia_tipo = FigureCanvas(self.fig_demografia_tipo)
        layout.addWidget(self.canvas_demografia_tipo)

        btn_save = QPushButton("Guardar Gráfico")
        btn_save.setIcon(self.style().standardIcon(QStyle.SP_DriveFDIcon))
        btn_save.clicked.connect(lambda: self._save_graph(self.fig_demografia_tipo, "Visitas Mensuales por Tipo de Usuario"))
        layout.addWidget(btn_save, 0, Qt.AlignRight)

        return widget

    def _crear_panel_grafico_servicios(self):
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.fig_servicios = Figure(figsize=(10, 6), dpi=100)
        # Aplicar tema inmediatamente al crear la figura
        bg_color = "#1e293b" if self.is_dark_mode else "#ffffff"
        self.fig_servicios.patch.set_facecolor(bg_color)
        
        self.canvas_servicios = FigureCanvas(self.fig_servicios)
        layout.addWidget(self.canvas_servicios)

        btn_save = QPushButton("Guardar Gráfico")
        btn_save.setIcon(self.style().standardIcon(QStyle.SP_DriveFDIcon))
        btn_save.clicked.connect(lambda: self._save_graph(self.fig_servicios, "Uso Total de Servicios"))
        layout.addWidget(btn_save, 0, Qt.AlignRight)

        return widget

    def _save_graph(self, figure, default_name):
        """Guarda un gráfico Matplotlib en un archivo PNG."""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar Gráfico", f"{default_name}.png",
                                                  "Archivos PNG (*.png);;Todos los Archivos (*)", options=options)
        if file_path:
            try:
                figure.savefig(file_path, dpi=300, bbox_inches='tight') # Guardar con alta resolución
                self._mostrar_mensaje("Éxito", f"Gráfico guardado en:\n{file_path}")
            except Exception as e:
                self._mostrar_mensaje("Error al Guardar", f"No se pudo guardar el gráfico:\n{str(e)}", QMessageBox.Critical)

    def _crear_footer(self):
        footer_layout = QHBoxLayout()
        
        # Solo la etiqueta de información en el footer
        self.label_info = QLabel(f"{AUTOR} | Versión: {VERSION_UI} | {fechaVersion}")
        self.label_info.setFont(QFont("Segoe UI", 9))
        self.label_info.setStyleSheet("color: #95A5A6;")
        
        footer_layout.addStretch()
        footer_layout.addWidget(self.label_info)
        footer_layout.addStretch()
        return footer_layout
    
    def _update_reset_button_icon(self):
        """Actualiza el ícono del botón de reinicio según el tema actual."""
        if not hasattr(self, 'btn_reset_db'):
            return
            
        icon_name = "restore_db_dark.png" if self.is_dark_mode else "restore_db_light.png"
        icon_path = os.path.join(BASE_DIR, "icons", icon_name)
        
        if os.path.exists(icon_path):
            self.btn_reset_db.setIcon(QIcon(icon_path))
        else:
            # Fallback a ícono estándar si el personalizado no existe
            self.btn_reset_db.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
    
    def setup_shortcuts(self):
        QShortcut(QKeySequence("F5"), self, self.ejecutar_analisis)
        self.btn_ejecutar.setToolTip("Ejecutar el análisis (F5)")

        QShortcut(QKeySequence("Ctrl+E"), self, self.exportar_excel)
        self.btn_exportar.setToolTip("Exportar los resultados a un archivo Excel (Ctrl+E)")
        
        QShortcut(QKeySequence("Ctrl+F"), self, self.toggle_guerrero_mode)
        # El tooltip del modo guerrero ya lo explica

        # --- NUEVO: ATAJO SECRETO PARA REINICIAR BD (Ctrl+Shift+R) ---
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, self.confirmar_reinicio_bd)

        # --- NUEVO: ATAJO PARA ACTUALIZAR METAS CON VERIFICACIÓN (Ctrl+Shift+S) ---
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self.verificar_cambios_metas)
        
        # Ctrl+C se maneja con keyPressEvent para que sea contextual a la tabla
    
    def verificar_cambios_metas(self):
        """Atajo para forzar la actualización de metas y verificar cambios explícitamente."""
        if hasattr(self, 'tab_metas'):
            log_to_file("[SHORTCUT] Ctrl+Shift+S: Verificando cambios en metas...")
            # Forzamos recarga y activamos la bandera de verificación de cambios
            self.tab_metas.refresh_data(force_reload=True, check_changes=True)
            
    def toggle_guerrero_mode(self):
        """Alterna la visibilidad de los controles de facilitador (Modo Guerrero)."""
        self.modo_guerrero_activo = not self.modo_guerrero_activo
        
        self.bitacora.set_facilitator_mode(self.modo_guerrero_activo)
        self.actualizar_visibilidad_guerrero()
        
        self.config['modo_guerrero_activo'] = self.modo_guerrero_activo
        self.guardar_configuracion()

    def actualizar_visibilidad_guerrero(self):
        """Actualiza la visibilidad de los elementos basados en el estado del Modo Guerrero."""
        # Se actualiza el sidebar
        if hasattr(self, 'sidebar'):
            self.sidebar.toggle_warrior(self.modo_guerrero_activo)

        # Notificar a la pestaña Metas si es necesario (el botón flotante si existiera)
        if hasattr(self, 'tab_metas') and hasattr(self.tab_metas, 'update_facilitator_mode_visibility'):
            self.tab_metas.update_facilitator_mode_visibility(self.modo_guerrero_activo)

        if hasattr(self, 'btn_exportar_pdf'):
            self.btn_exportar_pdf.setVisible(self.modo_guerrero_activo)
            tiene_datos = getattr(self, 'data', None) is not None
            self.btn_exportar_pdf.setEnabled(tiene_datos)

    
    # Los métodos _get_light_theme_stylesheet y _get_dark_theme_stylesheet han sido removidos 
    # en favor de ada_nova.qss cargado vía self.load_stylesheet()


    # Old styles removed. Use ada_nova.qss


    # ... (métodos de manejo de carpetas, tablas, etc.) ...
    # Los métodos que cambian son los de mostrar las tablas para usar el PinnedRowItem
    def seleccionar_carpeta_raiz(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta Raíz", os.path.expanduser("~"))
        if carpeta:
            self.carpeta_raiz = carpeta
            self.label_info_carpeta.setText(f"Raíz: {os.path.basename(carpeta)}")
            self.cargar_subcarpetas()
            self.config['ultima_carpeta_raiz'] = self.carpeta_raiz
            self.guardar_configuracion()
        


    def cargar_subcarpetas(self):
        if not self.carpeta_raiz or not os.path.isdir(self.carpeta_raiz): return
        self.combo_subcarpetas.clear()
        self.combo_subcarpetas.addItem("Seleccionar...")
        subcarpetas = sorted([d for d in os.listdir(self.carpeta_raiz) if os.path.isdir(os.path.join(self.carpeta_raiz, d))])
        if not subcarpetas:
            self._mostrar_mensaje("Información", "La carpeta raíz no contiene subcarpetas.")
            return
        self.combo_subcarpetas.addItems(subcarpetas)

    def actualizar_ruta_desde_subcarpeta(self):
        if self.combo_subcarpetas.currentIndex() <= 0:
            self.label_ruta.setText(f"{DB_DEFAULT_PATH}")
            return
        subcarpeta = os.path.join(self.carpeta_raiz, self.combo_subcarpetas.currentText())
        archivos_bd = [os.path.join(subcarpeta, f) for f in os.listdir(subcarpeta) if f.lower().endswith(('.mdb', '.accdb'))]
        if not archivos_bd:
            self._mostrar_mensaje("Advertencia", f"No se encontraron bases de datos en: {os.path.basename(subcarpeta)}", QMessageBox.Warning)
            return
        ruta_mas_reciente = max(archivos_bd, key=os.path.getmtime)
        self.db_path = ruta_mas_reciente
        
        # --- RESETEAR CACHE PARA MODO GUERRERO ---
        print(f"[WARRIOR] Cambiando a BD: {self.db_path}")
        db.reset_sync_data()
        # -----------------------------------------
        
        self.limpiar_todas_tablas()
        # Cargar el último username de la nueva BD seleccionada y actualizar estado
        self.actualizar_status_db()
        
        # ELIMINADO: No refrescamos aquí para evitar race condition. 
        # Esperamos a que actualizar_status_db -> _on_user_loaded termine y refresque con el usuario correcto.

    def crear_tabla_con_filtros(self, nombre_tabla, opciones_filtro, texto_etiqueta):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        filtro_layout = QHBoxLayout()
        filtro_label = QLabel(texto_etiqueta)
        filtro_label.setProperty("class", "h2")
        combo_filtro = QComboBox()
        combo_filtro.addItems(opciones_filtro)
        filtro = QLineEdit()
        filtro.setPlaceholderText("Buscar en la tabla...")
        filtro.setClearButtonEnabled(True)

        filtro_layout.addWidget(filtro_label)
        filtro_layout.addWidget(combo_filtro)
        filtro_layout.addWidget(filtro, 1)
        
        tabla = QTableWidget()
        self.configurar_tabla(tabla)
        
        btn_copiar = QPushButton(f"Copiar Datos")
        btn_copiar.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        btn_copiar.setMinimumHeight(30)
        btn_copiar.clicked.connect(lambda: self.copiar_toda_tabla(tabla))
        
        layout.addLayout(filtro_layout)
        layout.addWidget(tabla)
        layout.addWidget(btn_copiar, 0, Qt.AlignRight)
        
        filtro.textChanged.connect(lambda text: self.filtrar_tabla(tabla, combo_filtro, text))
        combo_filtro.currentIndexChanged.connect(lambda: self.filtrar_tabla(tabla, combo_filtro, filtro.text()))
        
        return {'widget': widget, 'tabla': tabla}

    def configurar_tabla(self, table):
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.ExtendedSelection)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self.mostrar_menu_contextual)
        # DESHABILITADO: El ordenamiento automático causa que la fila TOTAL se mueva
        # y puede corromper datos. Los usuarios pueden copiar y ordenar en Excel.
        table.setSortingEnabled(False)

    # ... (mostrar_menu_contextual, copiar_seleccion, copiar_toda_tabla, keyPressEvent) sin cambios ...
    def mostrar_menu_contextual(self, pos):
        tabla = self.sender()
        menu = QMenu()
        if len(tabla.selectedItems()) > 0:
            menu.addAction(self.style().standardIcon(QStyle.SP_DialogSaveButton), "Copiar Selección", lambda: self.copiar_seleccion(tabla))
        menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogListView), "Copiar Toda la Tabla", lambda: self.copiar_toda_tabla(tabla))
        menu.addSeparator()
        menu.addAction(self.style().standardIcon(QStyle.SP_DialogYesButton), "Seleccionar Todo", tabla.selectAll)
        menu.exec_(tabla.viewport().mapToGlobal(pos))

    def copiar_seleccion(self, tabla):
        selection = tabla.selectedRanges()
        if not selection: return
        
        rows = sorted(list(set(index.row() for range in selection for index in tabla.selectedIndexes())))
        cols = sorted(list(set(index.column() for range in selection for index in tabla.selectedIndexes())))

        header_text = "\t".join([tabla.horizontalHeaderItem(c).text() for c in cols])
        
        data_text = ""
        for r in rows:
            row_data = [tabla.item(r, c).text() if tabla.item(r, c) else "" for c in cols]
            data_text += "\t".join(row_data) + "\n"

        full_text = header_text + "\n" + data_text.strip()
        QApplication.clipboard().setText(full_text)
        self._mostrar_mensaje("Copiado", f"{len(rows)} filas copiadas al portapapeles.")

    def copiar_toda_tabla(self, tabla):
        tabla.selectAll()
        self.copiar_seleccion(tabla)
        tabla.clearSelection()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
            tabla_actual = self.tabs.currentWidget().findChild(QTableWidget)
            if tabla_actual and len(tabla_actual.selectedItems()) > 0:
                self.copiar_seleccion(tabla_actual)
        else:
            super().keyPressEvent(event)
    
    def cambiar_ruta(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar BD", "", "Access Database (*.mdb *.accdb)")
        if path:
            self.db_path = path

            # --- NUEVO: Resetear cache al cambiar de BD ---
            self._mostrar_mensaje("Cambio de Base de Datos", 
                                "Al cambiar de base de datos, se reiniciará el caché local.\nEsto forzará una sincronización completa en el próximo análisis.",
                                QMessageBox.Information)
            
            # Resetear cache y timestamps
            db.reset_sync_data()
            
            self.limpiar_todas_tablas()
            # Cargar el último username y actualizar estado
            self.limpiar_todas_tablas()
            # Cargar el último username y actualizar estado
            self.actualizar_status_db()

    def confirmar_reinicio_bd(self):
        """
        [MECANISMO SECRETO]
        Solicita confirmación para borrar la base de datos local y reiniciar la sincronización.
        Se activa con Ctrl + Shift + R.
        """
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("⚠️ REINICIO DE FÁBRICA - BASE DE DATOS LOCAL")
        msg_box.setText("¿ESTÁS SEGURO DE QUE QUIERES REINICIAR LA BASE DE DATOS LOCAL?")
        msg_box.setInformativeText("Esta acción:\n"
                                   "1. Eliminará todo el caché local de ventas.\n"
                                   "2. Borrará el historial de sincronización.\n"
                                   "3. Forzará una descarga COMPLETA desde Access la próxima vez.\n\n"
                                   "La aplicación se cerrará automáticamente para garantizar la limpieza.")
        
        # Botones personalizados en español
        btn_si = msg_box.addButton("Sí, Reiniciar", QMessageBox.YesRole)
        btn_no = msg_box.addButton("Cancelar", QMessageBox.NoRole)
        msg_box.setDefaultButton(btn_no)

        msg_box.exec_()

        if msg_box.clickedButton() == btn_si:
            try:
                if db.reset_sync_data():
                    msg_success = QMessageBox(self)
                    msg_success.setIcon(QMessageBox.Information)
                    msg_success.setWindowTitle("Reinicio Exitoso")
                    msg_success.setText("La base de datos local ha sido reiniciada correctamente.")
                    msg_success.setInformativeText("La aplicación se cerrará ahora.\nPor favor, inicie ADA Nova nuevamente.")
                    msg_success.addButton("Aceptar", QMessageBox.AcceptRole)
                    msg_success.exec_()
                    
                    self.close() # Cerramos la app para asegurar que todo se recargue limpio
                else:
                    QMessageBox.critical(self, "Error", "No se pudo reiniciar la base de datos local.\nRevise los logs.")
            except Exception as e:
                QMessageBox.critical(self, "Error Crítico", f"Falló el reinicio: {e}")

    def seleccionar_meses(self, indices):
        for i, cb in enumerate(self.meses_checkboxes):
            cb.setChecked(i in indices)

    def actualizar_meta(self):
        num_computadoras = self.spin_computadoras.value()
        self.meta_mensual = num_computadoras * 48
        self.label_meta.setText(f"<b>Meta Mensual: {self.meta_mensual}</b>")
        
        # --- LÓGICA AÑADIDA ---
        # Actualizamos el valor en nuestro diccionario de configuración
        self.config['computadoras'] = num_computadoras
        # Guardamos el diccionario completo en el archivo
        self.guardar_configuracion()
        # --- FIN DE LA LÓGICA ---
        
        if not self.data.empty:
            self.mostrar_tabla_rendimiento(self.data)
            self._actualizar_grafico_rendimiento(self.data)

        if not self.data.empty:
            self.mostrar_tabla_rendimiento(self.data)
            self._actualizar_grafico_rendimiento(self.data)
            
            # --- BLOQUE AÑADIDO ---
            # Recalculamos y actualizamos el pulso si ya hay datos cargados
            total_visitas = len(self.data)
            num_meses_seleccionados = len([cb for cb in self.meses_checkboxes if cb.isChecked()])
            total_meta = self.meta_mensual * num_meses_seleccionados if num_meses_seleccionados > 0 else 0
            porcentaje_total = (total_visitas / total_meta) * 30 if total_meta > 0 else 0
            self.actualizar_pulso_rendimiento(porcentaje_total)

    def filtrar_tabla(self, tabla, combo_filtro, filtro_texto):
        filtro_texto = filtro_texto.lower()
        tipo_filtro = combo_filtro.currentText()
        
        col_map = { "Fecha": 0, "Mes": 1, "Username": 2, "ItemName": 3, "Servicio": 4, "Sexo": 5, "Tipo": 6, "Observación": 7 }
        for i in range(tabla.rowCount()):
            mostrar_fila = False
            item_mes = tabla.item(i, 0)
            
            if tipo_filtro == "Todos":
                if not filtro_texto:
                    mostrar_fila = True
                else:
                    for j in range(tabla.columnCount()):
                        if tabla.item(i, j) and filtro_texto in tabla.item(i, j).text().lower():
                            mostrar_fila = True
                            break
            elif tipo_filtro in MESES:
                if item_mes and tipo_filtro.lower() == item_mes.text().lower():
                    mostrar_fila = True
            elif tabla == self.tab_registros and tipo_filtro in col_map:
                 col_idx = col_map.get(tipo_filtro)
                 if tabla.item(i, col_idx) and filtro_texto in tabla.item(i, col_idx).text().lower():
                     mostrar_fila = True
            
            tabla.setRowHidden(i, not mostrar_fila)

    def ejecutar_analisis(self):

        #...CÁMARAS 2
        self.bitacora.track_activity('analisis')
        self.analysis_start_time = time.time()
        #....

        self.limpiar_todas_tablas()
        anio = self.spin_anio.value()
        meses = [i + 1 for i, cb in enumerate(self.meses_checkboxes) if cb.isChecked()]

        if not meses:
            self._mostrar_mensaje("Error", "Debe seleccionar al menos un mes.", QMessageBox.Warning)
            return

        fecha_inicio = datetime(anio, meses[0], 1)
        ultimo_dia = calendar.monthrange(anio, meses[-1])[1]
        fecha_fin = datetime(anio, meses[-1], ultimo_dia, 23, 59, 59)

        if not os.path.exists(self.db_path):
            self._mostrar_mensaje("Error", f"La base de datos no existe:\n{self.db_path} \n\nVerifique que está ejecutando la aplicación en el equipo principal de la Infoplaza", QMessageBox.Critical)
            return
        
       

        # Modificación para Sincronización Previa (Smart Sync)
        # En lugar de lanzar el Worker directamente, primero lanzamos el Sync para asegurar data fresca.
        
        # 1. Mostrar diálogo de "Procesando" (que ahora incluye la fase de sync)
        self.progress_dialog = ProcessingDialog(self, self.is_dark_mode)
        self.progress_dialog.message_label.setText("Sincronizando nuevos datos de Access...")
        self.progress_dialog.show()
        QCoreApplication.processEvents()
        
        # 2. Guardar parámetros para la fase 2
        self.pending_analysis_params = {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin
        }

        
        
        # --- DIAGNÓSTICO TEMPORAL: VERIFICACIÓN VISUAL ---
        count_cache = db.execute_query("SELECT count(*) as c FROM registros_ventas_cache")[0]['c']
        print(f"[DEBUG_ANALYSIS] Target DB: {self.db_path}")
        print(f"[DEBUG_ANALYSIS] Cache Inicial: {count_cache} (Debe ser >0 si ya sincronizó, o 0 si acaba de cambiar)")
        
        # 3. Iniciar Sync Thread (Siempre nuevo, siempre con la ruta actual)
        # Esto asegura que si el usuario cambió la ruta, el sync apunte al nuevo archivo.
        self.pre_analysis_sync = DataSyncThread(self.db_path, DB_PASSWORD)
        self.pre_analysis_sync.finished.connect(self._continue_analysis_after_sync)
        self.pre_analysis_sync.start()

    def _continue_analysis_after_sync(self, count, error):
        """Segunda fase del análisis: Se ejecuta tras terminar el sync."""
        if error:
            print(f"[WARN] Sync previo al análisis falló: {error}. Se usará data local existente.")
            # NUEVO: Avisar al usuario si falla el sync, para que sepa por qué podría no ver datos nuevos
            self._mostrar_mensaje("Advertencia de Sincronización", 
                                f"No se pudieron cargar nuevos datos de Access.\nError: {error}\n\nSe analizarán solo los datos guardados anteriormente.",
                                QMessageBox.Warning)
            
        if count > 0:
            print(f"[INFO] Se encontraron {count} registros nuevos antes de analizar.")
            
        # Actualizar mensaje del diálogo si sigue abierto
        if self.progress_dialog:
             self.progress_dialog.message_label.setText("Analizando datos locales...")
             QCoreApplication.processEvents()

        # Recuperar parámetros
        try:
            params = self.pending_analysis_params
            fecha_inicio = params['fecha_inicio']
            fecha_fin = params['fecha_fin']
            
            # Pre-cargar cuentas de usuario para clasificación y sexo
            try:
                ua_rows = db.execute_query("SELECT username, sex FROM useraccount_cache")
                self.useraccount_dict = {
                    row['username'].upper().strip(): str(row['sex'] or '').upper() 
                    for row in ua_rows
                }
                print(f"[INFO] {len(self.useraccount_dict)} cuentas de usuario cargadas en diccionario.")
            except Exception as e:
                print(f"[WARN] No se pudieron cargar cuentas de usuario: {e}")
                self.useraccount_dict = {}
            
            # Lanzar el Worker de análisis real (que lee de SQLite)
            self.worker = Worker(self.db_path, DB_PASSWORD, fecha_inicio, fecha_fin)
            self.worker.finished.connect(self.analysis_finished)
            self.worker.start()
            
        except AttributeError:
             print("[ERROR] No se encontraron parámetros de análisis pendientes.")
             if self.progress_dialog: self.progress_dialog.close()

    def analysis_finished(self, data, error):
        # Ya no registramos evento por cada análisis, solo actualizamos contadores
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        if error or data is None:
            self.bitacora.track_activity('errores')
            self.bitacora.update_user_id("Error en Análisis")
            self.bitacora.log_intermediate_update() # Actualizar bitácora en error
            self._mostrar_mensaje("Error en Análisis", f"Ocurrió un error:\n{error or 'No se obtuvieron datos.'}", QMessageBox.Critical)
            return

        # Se permite que el DataFrame vacío fluya normalmente para inicializar las tablas de la UI en cero.
        # En vez de retornar y limpiar destructivamente, dejamos que se muestren los meses seleccionados con contadores a 0.
        if data.empty:
            data = pd.DataFrame(columns=['DATETIME', 'USERNAME', 'ITEMNAME', 'SEXO', 'TIPO U', 'OBSERVACIÓN'])
            data['DATETIME'] = pd.to_datetime(data['DATETIME'])

        self.data = data.copy()
        
        # NUEVO: Registrar tiempo del análisis
        duration_sec = time.time() - self.analysis_start_time
        self.bitacora.track_activity('analisis_time', duration_sec) # Suma tiempo acumulado

        # Obtenemos el último usuario de los datos
        # ultimo_user = self.obtener_ultimo_username(data)
        # Solo mostramos el icono y el usuario, ya que tenemos un título "USUARIO:" al lado
        # self.label_ultimo_user.setText(f"👤 Usuario: {ultimo_user}")
        
        # --- CRÍTICO: Actualizar variable de estado y refescar metas ---
        # self.current_username = ultimo_user
        # if hasattr(self, 'tab_metas'):
            # Forzamos recarga usando el nuevo ID
            # self.tab_metas.refresh_data(force_reload=False, require_user_id=True)
        # -------------------------------------------------------------
        
        # self.bitacora.update_user_id(ultimo_user)
        
        self.mostrar_tabla_resumen(data)
        self.mostrar_tabla_rendimiento(data)
        self.mostrar_tabla_registros(data)
        self.mostrar_tabla_servicios(data)
        self.actualizar_graficos(data)
        self._update_matplotlib_theme()  # CR\u00cdTICO: Aplicar tema después de dibujar gráficos
        
        if hasattr(self, 'btn_exportar_pdf'):
            self.btn_exportar_pdf.setVisible(self.modo_guerrero_activo)
            self.btn_exportar_pdf.setEnabled(True)
            
        # Lógica del pulso de rendimiento
        total_visitas = len(self.data)
        num_meses_seleccionados = len([cb for cb in self.meses_checkboxes if cb.isChecked()])
        total_meta = self.meta_mensual * num_meses_seleccionados if num_meses_seleccionados > 0 else 0
        porcentaje_total = (total_visitas / total_meta) * 30 if total_meta > 0 else 0
        self.actualizar_pulso_rendimiento(porcentaje_total)

        # --- ACTUALIZACIÓN INTERMEDIA BITÁCORA ---
        self.bitacora.log_intermediate_update()
        # -----------------------------------------

        self._mostrar_mensaje("Análisis Completo", f"Se procesaron {len(data)} registros.")


    def mostrar_tabla_resumen(self, df):
        try:
            meses_seleccionados = [cb.text() for cb in self.meses_checkboxes if cb.isChecked()]

            df_copy = df.copy()
            df_copy['MES'] = df_copy['DATETIME'].dt.month.apply(lambda x: MESES[x - 1])
            categorias = {'P': 'Primaria', 'S': 'Secundaria', 'U': 'Universitarios', 'D': 'Docentes', 'TE': 'Tercera Edad', 'PG': 'Público General'}
            
            # Se calcula y se guarda en la variable 'resumen'
            resumen = df_copy.groupby('MES').agg(
                Masculino=('SEXO', lambda x: (x == 'M').sum()),
                Femenino=('SEXO', lambda x: (x == 'F').sum()),
                **{v: ('TIPO U', lambda x, k=k: (x == k).sum()) for k, v in categorias.items()}
            )
            
            # --- CORRECCIÓN ---
            # Ahora modificamos la misma variable 'resumen'
            resumen = resumen.reindex(meses_seleccionados, axis=0).fillna(0).reset_index()
            
            resumen['Total Género'] = resumen['Masculino'] + resumen['Femenino']
            resumen['TOTAL USUARIOS'] = resumen[list(categorias.values())].sum(axis=1)

            nuevo_orden = [
                'MES', 'Masculino', 'Femenino', 'Total Género',
                'Primaria', 'Secundaria', 'Universitarios', 'Docentes',
                'Tercera Edad', 'Público General', 'TOTAL USUARIOS'
            ]
            resumen = resumen[nuevo_orden]

            totales = resumen.select_dtypes(include='number').sum()
            totales['MES'] = 'TOTAL GENERAL'
            resumen = pd.concat([resumen, pd.DataFrame([totales])], ignore_index=True)
            
            self.tab_resumen.clear()
            self.tab_resumen.setRowCount(len(resumen))
            self.tab_resumen.setColumnCount(len(resumen.columns))
            self.tab_resumen.setHorizontalHeaderLabels(resumen.columns)
            
            # 1. Configuración Base Minimalista
            self.configurar_tabla(self.tab_resumen)

            for i, row in resumen.iterrows():
                is_total_row = (row['MES'] == 'TOTAL GENERAL')
                for j, val in enumerate(row):
                    if isinstance(val, (int, float)):
                        display_val = str(int(val))
                    else:
                        display_val = str(val)
                    item = PinnedRowItem(display_val) if is_total_row else QTableWidgetItem(display_val)
                    
                    # Alineación: Derecha si no es la columna 0 (MES), Centro/Izq para MES
                    if j > 0:
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    else:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                    if is_total_row:
                        self._aplicar_estilo_total(item)
                        
                    self.tab_resumen.setItem(i, j, item)
            
            # Forzar actualización de estilo
            self.tab_resumen.style().unpolish(self.tab_resumen)
            self.tab_resumen.style().polish(self.tab_resumen)

            self.tab_resumen.horizontalHeader().setStretchLastSection(True)
            self.tab_resumen.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        except Exception as e:
            traceback.print_exc()


    def mostrar_tabla_rendimiento(self, df):
            try:
                # --- INICIO DE LA MODIFICACIÓN ---
                # 1. Obtenemos la lista de meses que el usuario seleccionó en la UI
                meses_seleccionados = [cb.text() for cb in self.meses_checkboxes if cb.isChecked()]
                # --- FIN DE LA MODIFICACIÓN ---

                df_copy = df.copy()
                df_copy['MES'] = df_copy['DATETIME'].dt.month.apply(lambda x: MESES[x-1])
                
                # --- INICIO DE LA MODIFICACIÓN ---
                # 2. Agrupamos los datos existentes...
                rendimiento_agrupado = df_copy.groupby('MES').size()
                # ...y luego reindexamos con los meses seleccionados, rellenando con 0 los que no tengan datos.
                rendimiento = rendimiento_agrupado.reindex(meses_seleccionados, fill_value=0).reset_index()
                rendimiento.columns = ['MES', 'Total Visitas']
                # --- FIN DE LA MODIFICACIÓN ---

                rendimiento['Meta'] = self.meta_mensual
                # Usamos un try-except para la división por si la meta es cero
                try:
                    rendimiento['Porcentaje'] = (rendimiento['Total Visitas'] * 30) / rendimiento['Meta']
                except ZeroDivisionError:
                    rendimiento['Porcentaje'] = 0

                totales = {
                    'MES': 'TOTAL GENERAL',
                    'Total Visitas': rendimiento['Total Visitas'].sum(),
                    'Meta': rendimiento['Meta'].sum()
                }
                
                try:
                    totales['Porcentaje'] = (totales['Total Visitas'] / totales['Meta']) * 30 if totales['Meta'] > 0 else 0
                except ZeroDivisionError:
                    totales['Porcentaje'] = 0
                
                # Ya no necesitamos ordenar por MES_NUM porque 'meses_seleccionados' ya viene en orden
                rendimiento = pd.concat([rendimiento, pd.DataFrame([totales])], ignore_index=True)

                self.tab_rendimiento.clear()
                columns = ['MES', 'Total Visitas', 'Meta', 'Porcentaje', 'Observación']
                self.tab_rendimiento.setRowCount(len(rendimiento))
                self.tab_rendimiento.setColumnCount(len(columns))
                self.tab_rendimiento.setHorizontalHeaderLabels(columns)

                # 1. Configuración Base Minimalista
                self.configurar_tabla(self.tab_rendimiento)

                for i, row in rendimiento.iterrows():
                    is_total_row = (row['MES'] == 'TOTAL GENERAL')
                    item_class = PinnedRowItem if is_total_row else QTableWidgetItem

                    items = [
                        item_class(str(row['MES'])),
                        item_class(f"{int(row['Total Visitas'])}"),
                        item_class(f"{int(row['Meta'])}"),
                        item_class(f"{row['Porcentaje']:.2f}%")
                    ]
                    
                    porcentaje_val = row['Porcentaje']
                    if porcentaje_val >= 30:
                        obs_text, color = "✅ Cumple", "#27ae60"
                    elif porcentaje_val >= 20:
                        obs_text, color = "⚠️ No cumple (parcial)", "#f39c12"
                    else:
                        obs_text, color = "❌ No cumple", "#c0392b"
                    
                    # Color semántico se mantiene hardcoded para el TEXTO
                    items[3].setForeground(QColor(color))

                    obs_item = item_class(obs_text)
                    items.append(obs_item)

                    for j, item in enumerate(items):
                        # Alineación
                        if j == 0:
                            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                        elif j == 4: # Observación
                            item.setTextAlignment(Qt.AlignCenter)
                        else: # Números
                            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                        if is_total_row:
                            self._aplicar_estilo_total(item)
                            
                        self.tab_rendimiento.setItem(i, j, item)

                # Forzar actualización de estilo
                self.tab_rendimiento.style().unpolish(self.tab_rendimiento)
                self.tab_rendimiento.style().polish(self.tab_rendimiento)

                self.tab_rendimiento.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                self.tab_rendimiento.horizontalHeader().setSectionsMovable(False)

            except Exception as e:
                traceback.print_exc()

    def mostrar_tabla_registros(self, df):
        try:
            self.tab_registros.setSortingEnabled(False)
            df_copy = df.copy()
            df_copy['MES'] = df_copy['DATETIME'].dt.month.apply(lambda x: MESES[x-1])
            df_copy['FECHA'] = df_copy['DATETIME'].dt.strftime('%d/%m/%Y %H:%M:%S')

            # --- INICIO DE LA MODIFICACIÓN ---
            # 1. Creamos la nueva columna 'SERVICIO' usando la función existente
            df_copy['SERVICIO'] = df_copy['ITEMNAME'].apply(self.extraer_servicio)

            # 2. Añadimos 'SERVICIO' a la lista de columnas que se mostrarán
            columns = ['FECHA', 'MES', 'USERNAME', 'ITEMNAME', 'SERVICIO', 'SEXO', 'TIPO U', 'OBSERVACIÓN']
            # --- FIN DE LA MODIFICACIÓN ---

            df_display = df_copy[columns]

            self.tab_registros.clear()
            self.tab_registros.setRowCount(len(df_display))
            self.tab_registros.setColumnCount(len(columns))
            self.tab_registros.setHorizontalHeaderLabels(columns)

            for i, row in df_display.iterrows():
                for j, val in enumerate(row):
                    item = QTableWidgetItem(str(val))
                    # Ajustamos la alineación para la nueva columna también
                    if j in [4, 5, 6, 7]: # Índices de SERVICIO, SEXO, TIPO U, OBSERVACIÓN
                        item.setTextAlignment(Qt.AlignCenter)
                    self.tab_registros.setItem(i, j, item)
            
            # --- Ajuste de columnas actualizado ---
            header = self.tab_registros.horizontalHeader()
            # La columna 3 (ITEMNAME) se estira
            header.setSectionResizeMode(3, QHeaderView.Stretch)
            # El resto de columnas (incluida la nueva) se ajustan a su contenido
            for col in [0, 1, 2, 4, 5, 6, 7]:
                header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
            
            self.tab_registros.setSortingEnabled(True)
        except Exception as e:
            traceback.print_exc()



    def mostrar_tabla_servicios(self, df):
        try:
            meses_seleccionados = [cb.text() for cb in self.meses_checkboxes if cb.isChecked()]

            df_copy = df.copy()
            df_copy['MES'] = df_copy['DATETIME'].dt.month.apply(lambda x: MESES[x-1])
            df_copy['SERVICIO'] = df_copy['ITEMNAME'].apply(self.extraer_servicio)
            
            # Se calcula y se guarda en la variable 'servicios'
            servicios = df_copy.pivot_table(index='MES', columns='SERVICIO', aggfunc='size', fill_value=0)
            for servicio in SERVICIOS:
                if servicio not in servicios.columns:
                    servicios[servicio] = 0
            
            servicios['TOTAL MES'] = servicios.sum(axis=1)
            
            # --- CORRECCIÓN ---
            # Ahora modificamos la misma variable 'servicios'
            servicios = servicios.reindex(meses_seleccionados, axis=0).fillna(0).reset_index()
            
            otros_cols = [c for c in servicios.columns if c not in SERVICIOS + ['MES', 'TOTAL MES', 'USO DE PC']]
            servicios['OTROS'] = servicios[otros_cols].sum(axis=1)
            
            if 'USO DE PC' not in servicios.columns:
                servicios['USO DE PC'] = 0
            column_order = ['MES'] + SERVICIOS + ['OTROS', 'USO DE PC', 'TOTAL MES']
            servicios = servicios[column_order]

            total_row = servicios[servicios.columns.drop('MES')].sum()
            total_row['MES'] = 'TOTAL GENERAL'
            servicios = pd.concat([servicios, pd.DataFrame([total_row])], ignore_index=True)
            
            self.tab_servicios.clear()
            header_labels = [self.TITULOS_COLUMNAS_SERVICIOS.get(col, col) for col in column_order]
            self.tab_servicios.setRowCount(len(servicios))
            self.tab_servicios.setColumnCount(len(column_order))
            self.tab_servicios.setHorizontalHeaderLabels(header_labels)

            # 1. Configuración Base Minimalista
            self.configurar_tabla(self.tab_servicios)

            for i, row in servicios.iterrows():
                is_total_row = (row['MES'] == 'TOTAL GENERAL')
                item_class = PinnedRowItem if is_total_row else QTableWidgetItem
                for j, col in enumerate(column_order):
                    item = item_class(str(int(row[col])) if isinstance(row[col], (int, float)) else str(row[col]))
                    
                    # Alineación
                    if j > 0: 
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    else:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                    if is_total_row:
                        self._aplicar_estilo_total(item)
                        
                    self.tab_servicios.setItem(i, j, item)
            
            # Forzar actualización de estilo
            self.tab_servicios.style().unpolish(self.tab_servicios)
            self.tab_servicios.style().polish(self.tab_servicios)

            self.tab_servicios.horizontalHeader().setStretchLastSection(True)
            self.tab_servicios.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        except Exception as e:
            traceback.print_exc()

    # --- NUEVOS MÉTODOS PARA MANEJAR Y ACTUALIZAR GRÁFICOS ---
    def actualizar_graficos(self, df):
        """Actualiza todos los gráficos con los datos procesados."""
        # Si df está vacío, los sub-métodos de graficación ya manejan el estado vacío dibujando
        # placeholders o barras en cero sin mostrar advertencia emergente.
        self._actualizar_grafico_rendimiento(df.copy())
        self._actualizar_grafico_demografia_sexo(df.copy())
        self._actualizar_grafico_demografia_tipo_usuario(df.copy())
        self._actualizar_grafico_servicios(df.copy())


    def _actualizar_grafico_rendimiento(self, df):
        if self.fig_rendimiento is None or self.canvas_rendimiento is None: return

        # --- INICIO DE LA MODIFICACIÓN ---
        # 1. Obtenemos la lista de meses que el usuario seleccionó en la UI
        meses_seleccionados = [cb.text() for cb in self.meses_checkboxes if cb.isChecked()]
        # --- FIN DE LA MODIFICACIÓN ---

        df_copy = df.copy()
        df_copy['MES'] = df_copy['DATETIME'].dt.month.apply(lambda x: MESES[x-1])

        # --- INICIO DE LA MODIFICACIÓN ---
        # 2. Agrupamos y reindexamos para incluir meses con cero visitas
        rendimiento_agrupado = df_copy.groupby('MES').size()
        rendimiento = rendimiento_agrupado.reindex(meses_seleccionados, fill_value=0).reset_index()
        rendimiento.columns = ['MES', 'Total Visitas']
        # --- FIN DE LA MODIFICACIÓN ---

        rendimiento['Meta'] = self.meta_mensual
        try:
            rendimiento['Porcentaje'] = (rendimiento['Total Visitas'] * 30) / rendimiento['Meta']
        except ZeroDivisionError:
            rendimiento['Porcentaje'] = 0

        # El resto de la lógica para dibujar el gráfico no necesita cambios,
        # ya que ahora operará sobre el dataframe 'rendimiento' que está completo.
        
        self.fig_rendimiento.clear()
        ax1 = self.fig_rendimiento.add_subplot(111)

        colors = []
        for porcentaje in rendimiento['Porcentaje']:
            if porcentaje >= 30:
                colors.append('#27ae60')
            elif porcentaje >= 20:
                colors.append('#f39c12')
            else:
                colors.append('#c0392b')
        
        bars = ax1.bar(rendimiento['MES'], rendimiento['Total Visitas'], color=colors, label='Total Visitas')
        ax1.plot(rendimiento['MES'], rendimiento['Meta'], color='#E74C3C', linestyle='--', marker='o', label='Meta Mensual')
        
        for bar, porcentaje in zip(bars, rendimiento['Porcentaje']):
            height = bar.get_height()
            
            # Solo mostrar etiqueta si la altura es mayor a 0 para no saturar
            if height > 0:
                if porcentaje >= 30:
                    bbox_style = dict(facecolor='#e8f5e9', alpha=0.9, edgecolor='#27ae60', boxstyle='round,pad=0.3')
                elif porcentaje >= 20:
                    bbox_style = dict(facecolor='#fff8e1', alpha=0.9, edgecolor='#f39c12', boxstyle='round,pad=0.3')
                else:
                    bbox_style = dict(facecolor='#ffebee', alpha=0.9, edgecolor='#c0392b', boxstyle='round,pad=0.3')
                
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(height)}\n({porcentaje:.0f}%)',
                        ha='center', va='center',
                        fontsize=9, fontweight='bold',
                        bbox=bbox_style)

        for i, val in enumerate(rendimiento['Meta']):
            ax1.text(i, val + (rendimiento['Total Visitas'].max() * 0.05), f'{int(val)}', ha='center', va='bottom', fontsize=9, color='#E74C3C')

        ax1.set_xlabel('Mes')
        ax1.set_ylabel('Cantidad de Visitas', color='#4A90E2')
        ax1.tick_params(axis='y', labelcolor='#4A90E2')
        ax1.tick_params(axis='x', rotation=45) 
        plt.setp(ax1.get_xticklabels(), ha="right")

        ax2 = ax1.twinx()
        ax2.plot(rendimiento['MES'], rendimiento['Porcentaje'], color='#2ECC71', marker='x', linestyle='-', linewidth=2, label='Indicador de Cumplimiento')
        ax2.set_ylabel('Indicador de Cumplimiento (%)', color='#2ECC71')
        ax2.tick_params(axis='y', labelcolor='#2ECC71')
        ax2.set_ylim(0, max(35, rendimiento['Porcentaje'].max() * 1.1))

        formatter = mticker.FormatStrFormatter('%.0f%%')
        ax2.yaxis.set_major_formatter(formatter)

        self.fig_rendimiento.suptitle('Rendimiento Mensual vs. Meta', fontsize=14, fontweight='bold', color='#34495E')
        
        # Recolectar handles y labels de ambos ejes para una sola leyenda
        handles1, labels1 = ax1.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(handles1 + handles2, labels1 + labels2, loc='upper left', bbox_to_anchor=(0.0, 1.05), ncol=3, frameon=False, fontsize=9)

        self.fig_rendimiento.tight_layout(rect=[0, 0, 1, 0.95])
        self.canvas_rendimiento.draw()

    def _actualizar_grafico_demografia_sexo(self, df):
        if self.fig_demografia_sexo is None or self.canvas_demografia_sexo is None: return

        meses_seleccionados = [cb.text() for cb in self.meses_checkboxes if cb.isChecked()]

        df_copy = df.copy()
        df_copy['MES'] = df_copy['DATETIME'].dt.month.apply(lambda x: MESES[x-1])
        
        # --- VERSIÓN SIMPLIFICADA ---
        # 1. Agrupamos y guardamos directamente en 'resumen_sexo'
        resumen_sexo = df_copy.groupby('MES').agg(
            Masculino=('SEXO', lambda x: (x == 'M').sum()),
            Femenino=('SEXO', lambda x: (x == 'F').sum()) 
        )

        # 2. Modificamos la misma variable 'resumen_sexo'
        resumen_sexo = resumen_sexo.reindex(meses_seleccionados, axis=0).fillna(0).reset_index()
        # --- FIN DE LA SIMPLIFICACIÓN ---

        if resumen_sexo.empty:
            self.fig_demografia_sexo.clear()
            ax = self.fig_demografia_sexo.add_subplot(111)
            ax.text(0.5, 0.5, 'No hay datos de género para el período seleccionado', 
                    horizontalalignment='center', verticalalignment='center', 
                    transform=ax.transAxes, fontsize=12, color='gray',
                    bbox=dict(facecolor='#f5f5f5', edgecolor='#ddd', boxstyle='round,pad=0.5'))
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            self.canvas_demografia_sexo.draw()
            return

        self.fig_demografia_sexo.clear()
        ax = self.fig_demografia_sexo.add_subplot(111)

        colors = {'Masculino': '#3498DB', 'Femenino': '#E91E63'}
        bar_width = 0.7
        bottom = [0] * len(resumen_sexo['MES'])
        
        bars_m = ax.bar(resumen_sexo['MES'], resumen_sexo['Masculino'], 
                    width=bar_width, label='Masculino', 
                    color=colors['Masculino'], bottom=bottom,
                    edgecolor='white', linewidth=0.5)
        
        for bar in bars_m:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., bar.get_y() + height/2.,
                    f'{int(height)}', ha='center', va='center',
                    color='white', fontsize=9, fontweight='bold',
                    bbox=dict(facecolor=colors['Masculino'], alpha=0.7, 
                                edgecolor='none', boxstyle='round,pad=0.2'))

        bottom = [i + j for i, j in zip(bottom, resumen_sexo['Masculino'])]
        
        bars_f = ax.bar(resumen_sexo['MES'], resumen_sexo['Femenino'], 
                    width=bar_width, label='Femenino', 
                    color=colors['Femenino'], bottom=bottom,
                    edgecolor='white', linewidth=0.5)
        
        for bar in bars_f:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., bar.get_y() + height/2.,
                    f'{int(height)}', ha='center', va='center',
                    color='white', fontsize=9, fontweight='bold',
                    bbox=dict(facecolor=colors['Femenino'], alpha=0.7, 
                                edgecolor='none', boxstyle='round,pad=0.2'))

        totals = resumen_sexo['Masculino'] + resumen_sexo['Femenino']
        for i, total in enumerate(totals):
            if total > 0:
                ax.text(i, total + max(totals)*0.02, f'Total: {int(total)}',
                    ha='center', va='bottom', fontsize=8, color='#34495E',
                    bbox=dict(facecolor='white', alpha=0.8, 
                                edgecolor='#ddd', boxstyle='round,pad=0.3'))

        ax.set_xlabel('Mes', fontsize=10, labelpad=10)
        ax.set_ylabel('Número de Visitas', fontsize=10)
        ax.set_title('Visitas Mensuales por Género', 
                    fontsize=14, fontweight='bold', pad=20, color='#34495E')
        
        ax.tick_params(axis='x', rotation=45, labelsize=9)
        ax.tick_params(axis='y', labelsize=9)
        plt.setp(ax.get_xticklabels(), ha="right")
        
        ax.yaxis.grid(True, linestyle='--', alpha=0.4)
        ax.set_axisbelow(True)
        
        ax.legend(title='Género', frameon=False, 
                bbox_to_anchor=(1, 1), loc='upper left',
                fontsize=9, title_fontsize=10)
        
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%d'))
        
        for spine in ax.spines.values():
            spine.set_color('#dddddd')
            spine.set_linewidth(0.5)
        
        self.fig_demografia_sexo.tight_layout()
        self.canvas_demografia_sexo.draw()

    def _actualizar_grafico_demografia_tipo_usuario(self, df):
        if self.fig_demografia_tipo is None or self.canvas_demografia_tipo is None: return

        meses_seleccionados = [cb.text() for cb in self.meses_checkboxes if cb.isChecked()]

        df_copy = df.copy()
        df_copy['MES'] = df_copy['DATETIME'].dt.month.apply(lambda x: MESES[x-1])
        categorias = {'P': 'Primaria', 'S': 'Secundaria', 'U': 'Universitarios', 'D': 'Docentes', 'TE': 'Tercera Edad', 'PG': 'Público General'}
        
        # --- VERSIÓN SIMPLIFICADA: No usamos la variable 'resumen_tipo_agrupado' ---
        # 1. Agrupamos y guardamos directamente en 'resumen_tipo'
        resumen_tipo = df_copy.groupby('MES').agg(
            **{v: ('TIPO U', lambda x, k=k: (x == k).sum()) for k, v in categorias.items()}
        )
        
        # 2. Modificamos la misma variable 'resumen_tipo'
        resumen_tipo = resumen_tipo.reindex(meses_seleccionados, axis=0).fillna(0)
        
        # Filtramos columnas (tipos de usuario) que no tuvieron ningún uso para un gráfico más limpio
        resumen_tipo = resumen_tipo.loc[:, (resumen_tipo != 0).any(axis=0)]

        if resumen_tipo.empty: 
            self.fig_demografia_tipo.clear()
            ax = self.fig_demografia_tipo.add_subplot(111)
            ax.text(0.5, 0.5, 'No hay datos de tipo de usuario para el período seleccionado', horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=12, color='gray')
            ax.set_xticks([]); ax.set_yticks([])
            self.canvas_demografia_tipo.draw()
            return

        self.fig_demografia_tipo.clear()
        ax = self.fig_demografia_tipo.add_subplot(111)
        
        colores_tipo = {
            'Primaria': '#FF6347', 'Secundaria': '#4682B4', 'Universitarios': '#8A2BE2',
            'Docentes': '#3CB371', 'Tercera Edad': '#FFD700', 'Público General': '#6A5ACD'
        }

        # DIBUJAR LAS BARRAS
        resumen_tipo.plot(
            kind='bar',
            stacked=True,
            ax=ax,
            color=[colores_tipo.get(col, '#CCCCCC') for col in resumen_tipo.columns],
            width=0.7,
            edgecolor='white'
        )

        # AÑADIR ETIQUETAS DE VALOR DENTRO DE CADA SEGMENTO
        for container in ax.containers:
            umbral_altura = resumen_tipo.sum(axis=1).max() * 0.05
            ax.bar_label(
                container,
                label_type='center',
                fmt='%d',
                color='white',
                fontsize=9,
                fontweight='bold',
                labels=[f'{int(v.get_height())}' if v.get_height() > umbral_altura else '' for v in container]
            )

        # AJUSTES FINALES
        ax.set_xlabel('')
        ax.set_ylabel('Número de Visitas', fontsize=12)
        ax.set_title('Visitas Mensuales por Tipo de Usuario', fontsize=16, fontweight='bold', pad=20)
        ax.tick_params(axis='x', rotation=0, labelsize=11)
        ax.tick_params(axis='y', labelsize=10)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('lightgray')
        ax.spines['bottom'].set_color('lightgray')
        ax.yaxis.grid(True, linestyle='--', which='major', color='lightgrey', alpha=0.7)
        ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax.set_axisbelow(True)

        ax.legend(title='Tipo de Usuario', bbox_to_anchor=(1.04, 1), loc='upper left', frameon=False)
        self.fig_demografia_tipo.tight_layout(rect=[0, 0, 0.85, 1])
        
        self.canvas_demografia_tipo.draw()

    def _actualizar_grafico_servicios(self, df):
        if self.fig_servicios is None or self.canvas_servicios is None: return

        # --- INICIO DEL CÓDIGO DEL NUEVO GRÁFICO ---
        self.fig_servicios.clear()
        ax = self.fig_servicios.add_subplot(111)

        # 1. PREPARAR LOS DATOS
        df_copy = df.copy()
        df_copy['MES'] = df_copy['DATETIME'].dt.month.apply(lambda x: MESES[x-1])
        df_copy['SERVICIO'] = df_copy['ITEMNAME'].apply(self.extraer_servicio)
        
        meses_seleccionados = [cb.text() for cb in self.meses_checkboxes if cb.isChecked()]
        servicios_por_mes = df_copy.pivot_table(index='MES', columns='SERVICIO', aggfunc='size', fill_value=0)
        servicios_por_mes = servicios_por_mes.reindex(meses_seleccionados, fill_value=0)
        servicios_por_mes = servicios_por_mes.loc[:, (servicios_por_mes != 0).any(axis=0)]

        # --- LÍNEA AÑADIDA ---
        # Renombramos las columnas usando el diccionario para que la leyenda sea amigable
        servicios_por_mes.rename(columns=self.TITULOS_COLUMNAS_SERVICIOS, inplace=True)
        # --------------------

        if servicios_por_mes.empty:
            ax.text(0.5, 0.5, 'No hay datos de servicios para graficar', ha='center', va='center')
            self.canvas_servicios.draw()
            return
            
        # 2. CONFIGURACIÓN ESTÉTICA (NUEVA LÓGICA DE COLORES)
        # 1. Contamos cuántos servicios vamos a graficar
        num_servicios = len(servicios_por_mes.columns)
        
        # 2. Elegimos una paleta de colores de Matplotlib ('tab20' tiene 20 colores distintos)
        colormap = plt.get_cmap('tab20')

        # 3. Generamos una lista de colores única para la cantidad de servicios que tengamos
        colors = [colormap(i) for i in np.linspace(0, 1, num_servicios)]
        # 3. DIBUJAR LAS BARRAS APILADAS
        servicios_por_mes.plot(
            kind='bar', 
            stacked=True, 
            ax=ax, 
            color=colors,
            width=0.7,
            edgecolor='white'
        )

        # 4. AÑADIR ETIQUETAS DE VALOR DENTRO DE CADA SEGMENTO
        for container in ax.containers:
            ax.bar_label(
                container, 
                label_type='center',
                fmt='%d',
                color='white',
                fontsize=9,
                fontweight='bold',
                padding=-10,
                labels=[f'{int(v.get_height())}' if v.get_height() > (servicios_por_mes.sum().max() * 0.05) else '' for v in container]
            )

        # 5. AJUSTES FINALES DEL GRÁFICO ("BIEN BONITO")
        ax.set_title('Composición de Servicios por Mes', fontsize=16, fontweight='bold', pad=20)
        ax.set_ylabel('Cantidad de Usos', fontsize=12)
        ax.set_xlabel('')
        
        ax.tick_params(axis='x', rotation=0, labelsize=11)
        ax.tick_params(axis='y', labelsize=10)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('lightgray')
        ax.spines['bottom'].set_color('lightgray')

        ax.yaxis.grid(True, linestyle='--', which='major', color='lightgrey', alpha=0.7)
        ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax.set_axisbelow(True)

        ax.legend(title='Servicios', bbox_to_anchor=(1.04, 1), loc='upper left', frameon=False)
        
        self.fig_servicios.tight_layout(rect=[0, 0, 0.85, 1])
        
        self.canvas_servicios.draw()
        # --- FIN DEL CÓDIGO DEL NUEVO GRÁFICO ---

    # ... (resto de métodos: extraer_servicio, exportar_excel, get_dataframe, etc.) sin cambios ...
    
    def obtener_ultimo_username(self, df):
        if not df.empty:
            # La consulta SQL ordena por fecha descendente, así que el primer registro es el más reciente
            return df.iloc[0]['USERNAME']
        return "No disponible"
        
    def extraer_servicio(self, itemname):
        itemname_upper = str(itemname).upper()
        # Usamos replace y split para manejar múltiples separadores y espacios
        palabras_item = itemname_upper.replace('-', ' ').split()

        for servicio_info in LISTA_SERVICIOS_PRIORIZADA:
            categoria_actual = servicio_info['categoria']
            
            for variante in servicio_info['variantes']:
                # --- LÓGICA MEJORADA ---

                # Regla Estricta: Si el servicio es corto (como LT o TEL), busca coincidencia exacta.
                if categoria_actual in ['LT', 'TEL', 'SCAN']: 
                    if any(palabra == variante for palabra in palabras_item):
                        return categoria_actual
                
                # Regla Flexible: Para los demás servicios, usa startswith para admitir plurales.
                else:
                    if any(palabra.startswith(variante) for palabra in palabras_item):
                        return categoria_actual
                
                # --- FIN DE LA LÓGICA MEJORADA ---

        # --- REGLAS DE CLASIFICACIÓN 'USO DE PC' ---
        
        # Regla 1: Diccionario por patrones de palabra (RegEx)
        for palabra in palabras_item:
            for patron in PATRONES_USO_PC:
                if patron.match(palabra):
                    return 'USO DE PC'
        
        # Regla 2: Búsqueda en base de datos de cuentas de usuario
        if hasattr(self, 'useraccount_dict') and self.useraccount_dict:
            if itemname_upper.strip() in self.useraccount_dict:
                return 'USO DE PC'
        
        return 'OTROS'

    def exportar_excel(self):

        #... CÁMARAS 4
        self.bitacora.track_activity('excel')
        self.bitacora.log_intermediate_update()
        #...

        """Exporta todas las tablas a un archivo Excel"""
        path, _ = QFileDialog.getSaveFileName(
            self, 
            "Guardar como Excel", 
            "reporte.xlsx", 
            "Excel (*.xlsx)"
        )
        
        if not path:
            return
            
        try:
            with pd.ExcelWriter(path) as writer:
                # Exportar cada pestaña
                self.get_dataframe(self.tab_resumen).to_excel(
                    writer, 
                    sheet_name="Resumen Mensual", 
                    index=False
                )
                self.get_dataframe(self.tab_rendimiento).to_excel(
                    writer, 
                    sheet_name="Rendimiento", 
                    index=False
                )
                self.get_dataframe(self.tab_registros).to_excel(
                    writer, 
                    sheet_name="Registros", 
                    index=False
                )
                self.get_dataframe(self.tab_servicios).to_excel(
                    writer, 
                    sheet_name="Servicios", 
                    index=False
                )
                
            QMessageBox.information(
                self, 
                "Éxito", 
                "Exportación completada correctamente."
            )
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"No se pudo exportar el archivo:\n{str(e)}"
            )
    def get_dataframe(self, table):
        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        data = []
        for row in range(table.rowCount()):
            if table.isRowHidden(row): continue
            data.append([table.item(row, col).text() if table.item(row, col) else '' for col in range(table.columnCount())])

        # Limpiar todo el DataFrame de caracteres inválidos antes de devolverlo
        # Convertir a DataFrame solo para limpiar, luego regresar a lista
        df_temp = pd.DataFrame(data, columns=headers)
        df_temp = limpiar_caracteres_invalidos(df_temp)
        data = df_temp.values.tolist()
        
        
        return pd.DataFrame(data, columns=headers)

    def exportar_pdf_ejecutivo(self):
        """Exporta los resultados actuales a un informe ejecutivo en PDF (Exclusivo Modo Guerrero)."""
        if self.data is None:
            self._mostrar_mensaje("Error", "No hay datos para exportar.", QMessageBox.Warning)
            return
            
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel, QCheckBox

            
        # --- DIÁLOGO DE OPCIONES DE EXPORTACIÓN ---
        dialog = QDialog(self)
        dialog.setWindowTitle("Opciones de Exportación a PDF")
        dialog.setMinimumWidth(350)
        dialog.setStyleSheet("QDialog { background-color: #ffffff; } QLabel, QCheckBox { color: #333333; font-size: 13px; }")
        
        layout_dialog = QVBoxLayout(dialog)
        
        lbl_info = QLabel("¿Qué información desea incluir en el Informe Ejecutivo?")
        lbl_info.setWordWrap(True)
        layout_dialog.addWidget(lbl_info)
        
        cb_incluir_metas = QCheckBox("Incluir anexo con el estado de las Metas")
        cb_incluir_metas.setChecked(True)
        layout_dialog.addWidget(cb_incluir_metas)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout_dialog.addWidget(btn_box)
        
        if dialog.exec_() != QDialog.Accepted:
            return
            
        incluir_metas = cb_incluir_metas.isChecked()
        # ------------------------------------------

        try:
            import jinja2
            
            # En Windows Python 3.8+, hay que añadir la ruta de DLLs de GTK si está instalado
            import platform
            import os
            if platform.system() == 'Windows':
                gtk_path = r"C:\Program Files\GTK3-Runtime Win64\bin"
                if os.path.exists(gtk_path) and hasattr(os, 'add_dll_directory'):
                    os.add_dll_directory(gtk_path)
                    # También lo añadimos al PATH de ambiente por si acaso
                    os.environ['PATH'] = gtk_path + os.pathsep + os.environ.get('PATH', '')
                    
            import weasyprint
        except ImportError:
            self._mostrar_mensaje("Error", "Faltan librerías requeridas (jinja2, weasyprint). Asegúrese de instalarlas en su entorno.", QMessageBox.Critical)
            return
            
        try:
            import io
            import base64
            
            # 1. Preparar datos de Metadatos y KPIs
            meses_seleccionados = [cb.text() for cb in self.meses_checkboxes if cb.isChecked()]
            fecha_inicio = f"1 de {meses_seleccionados[0]} de {self.spin_anio.value()}" if meses_seleccionados else "N/A"
            # Calcular fin de mes simple para texto
            import calendar
            if meses_seleccionados:
                mes_str = meses_seleccionados[-1]
                mes_num = MESES.index(mes_str) + 1 if mes_str in MESES else 12
                ultimo_dia = calendar.monthrange(self.spin_anio.value(), mes_num)[1]
                fecha_fin = f"{ultimo_dia} de {mes_str} de {self.spin_anio.value()}"
            else:
                fecha_fin = "N/A"
            
            infoplaza_nombre = "Desconocida"
            if self.db_path:
                infoplaza_nombre = os.path.basename(os.path.dirname(self.db_path))
            
            total_pcs = f"{self.spin_computadoras.value():,}"
            meta_mensual_total = f"{self.meta_mensual:,}"
            
            kpis = {
                'Masculino': f"{int((self.data['SEXO'] == 'M').sum()):,}",
                'Femenino': f"{int((self.data['SEXO'] == 'F').sum()):,}",
                'Total_General': f"{len(self.data):,}"
            }
            
            # 2. Obtener datos de Tablas desde la UI
            # Resumen Mensual
            df_resumen = self.get_dataframe(self.tab_resumen)
            tabla_resumen = []
            for row in df_resumen.to_dict('records'):
                row_fmt = {}
                for k, v in row.items():
                    if k != 'MES':
                        try:
                            # Convertimos a número y formateamos con miles
                            val = int(str(v).replace(',', '').replace('.', ''))
                            row_fmt[k] = f"{val:,}"
                        except:
                            row_fmt[k] = v
                    else:
                        row_fmt[k] = v
                tabla_resumen.append(row_fmt)
            
            # Rendimiento Mensual
            df_rendimiento = self.get_dataframe(self.tab_rendimiento)
            tabla_rendimiento = []
            for _, row in df_rendimiento.iterrows():
                row_dict = row.to_dict()
                # Formatear números en columnas específicas (Visitas y Metas)
                for col in ['Total Visitas', 'Meta']:
                    if col in row_dict:
                        try:
                            val = int(str(row_dict[col]).replace(',', '').replace('.', ''))
                            row_dict[col] = f"{val:,}"
                        except:
                            pass
                
                # Procesar Porcentaje como float para el template (Jinja2 hace el resto)
                pct_str = str(row_dict.get('Porcentaje', '0')).replace('%', '')
                try:
                    row_dict['Porcentaje'] = float(pct_str)
                except ValueError:
                    row_dict['Porcentaje'] = 0.0
                
                tabla_rendimiento.append(row_dict)

            # 3. Cargar Template y Renderizar
            template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reporte_template.html')
            if not os.path.exists(template_path):
                self._mostrar_mensaje("Error", "No se encontró la plantilla HTML del reporte (reporte_template.html).", QMessageBox.Warning)
                return
                
            with open(template_path, 'r', encoding='utf-8') as f:
                template_source = f.read()
                
            template = jinja2.Template(template_source)
            
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons', 'LOGO INFOPLAZAS.png')
            logo_uri = f"file:///{logo_path.replace(os.sep, '/')}"
            
            # Recopilar datos de las metas si fue seleccionado
            datos_metas = None
            if incluir_metas and hasattr(self, 'tab_metas') and self.tab_metas.calculator:
                estado_global = self.tab_metas.calculator.calcular_estado_global()
                detalles_metas = []
                total_puntos = 0.0
                total_peso = 0.0
                
                # Usar la lista dinámica de actividades que carga el widget desde Google Sheets
                lista_actividades = self.tab_metas.current_data.get('actividades_config') or []
                
                for act in lista_actividades:
                    prog = self.tab_metas.calculator.calcular_progreso_actividad(act)
                    puntos, peso = self.tab_metas.calculator.calcular_puntos_ganados(act)
                    
                    porcentaje_real = prog['porcentaje']
                    # Regla: mostrar máximo 100% (igual que las tarjetas visuales)
                    porcentaje_display = min(porcentaje_real, 100.0)
                    
                    color_data = self.tab_metas.calculator._determinar_colores(porcentaje_display)
                    
                    # Calcular el extra (fueguito) solo si superó la meta
                    extra = ""
                    if porcentaje_real > 100:
                        extra = f"🔥 (+{int(prog['completado']) - int(prog['meta_total'])})"
                    
                    puntos_display = round(min(puntos, peso), 1)  # Puntos también capeados al máximo
                    total_puntos += puntos_display
                    total_peso += peso
                        
                    detalles_metas.append({
                        'nombre': act.display_name,
                        'completado': int(prog['completado']),
                        'total': int(prog['meta_total']),
                        'porcentaje': round(porcentaje_display, 1),
                        'puntos': puntos_display,
                        'peso': round(peso, 1),
                        'color': color_data['color'],
                        'extra': extra
                    })
                    
                # Estado por mes (si se subió o no el reporte)
                from metas_config import MESES_PERIODO, PERIODO_INICIO, PERIODO_FIN
                meses_estado = []
                for mes in MESES_PERIODO:
                    estado_mes = self.tab_metas.calculator.obtener_estado_mes(mes)
                    meses_estado.append({
                        'mes': mes,
                        'subido': estado_mes['subio_reporte'],
                        'simbolo': estado_mes['simbolo'],
                        'color': estado_mes['color_text']
                    })
                
                # Período formateado para el encabezado
                MESES_ES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                            'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
                periodo_str = (
                    f"{MESES_ES[PERIODO_INICIO.month - 1]} {PERIODO_INICIO.year} — "
                    f"{MESES_ES[PERIODO_FIN.month - 1]} {PERIODO_FIN.year}"
                )
                
                datos_metas = {
                    'porcentaje_global': round(estado_global['progreso'], 1),
                    'estado_general': estado_global['estado'],
                    'detalles': detalles_metas,
                    'total_puntos': round(total_puntos, 1),
                    'total_peso': round(total_peso, 1),
                    'infoplaza': infoplaza_nombre,
                    'periodo': periodo_str,
                    'meses_estado': meses_estado,
                } if detalles_metas else None
            
            html_content = template.render(
                logo_path=logo_uri,
                infoplaza_nombre=infoplaza_nombre,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                total_pcs=total_pcs,
                meta_mensual=meta_mensual_total,
                kpis=kpis,
                tabla_resumen=tabla_resumen,
                tabla_rendimiento=tabla_rendimiento,
                datos_metas=datos_metas
            )
            
            # 5. Guardar el PDF
            opciones = QFileDialog.Options()
            nombre_sugerido = f"Informe_Ejecutivo_{infoplaza_nombre}.pdf".replace(' ', '_')
            ruta_pdf, _ = QFileDialog.getSaveFileName(
                self, "Guardar Informe Ejecutivo (PDF)", 
                nombre_sugerido, 
                "Archivos PDF (*.pdf);;Todos los archivos (*)", 
                options=opciones
            )
            
            if ruta_pdf:
                self.progress_dialog = ProcessingDialog(self, getattr(self, 'is_dark_mode', False))
                self.progress_dialog.message_label.setText("Generando documento PDF...")
                self.progress_dialog.show()
                QCoreApplication.processEvents()
                
                def generar_pdf():
                    try:
                        import weasyprint
                        weasyprint.HTML(string=html_content, base_url=os.path.dirname(os.path.abspath(__file__))).write_pdf(ruta_pdf)
                        
                        if self.progress_dialog:
                            self.progress_dialog.close()
                        
                        self._mostrar_mensaje("Éxito", f"El Informe Ejecutivo PDF ha sido guardado exitosamente en:\n{ruta_pdf}")
                        QDesktopServices.openUrl(QUrl.fromLocalFile(ruta_pdf))
                        self.bitacora.track_activity('export_pdf_ejecutivo')
                        
                    except Exception as e_pdf:
                        if self.progress_dialog:
                            self.progress_dialog.close()
                        self._mostrar_mensaje("Error", f"Ha ocurrido un error al generar el PDF:\n{str(e_pdf)}", QMessageBox.Critical)
                
                # Usar QTimer para permitir que el diálogo se dibuje antes de congelar el hilo principal
                QTimer.singleShot(100, generar_pdf)
                    
        except Exception as e:
            traceback.print_exc()
            self._mostrar_mensaje("Error", f"Ha ocurrido un error al generar el PDF:\n{str(e)}", QMessageBox.Critical)
    







def analizar_itemname(data):
    # 1. Se inicializa el procesador, pasando el diccionario de cuentas
    # NOTA: Como esto es una función global y no un método de instancia,
    # 'self' no está disponible. Recuperamos el diccionario directamente de la DB.
    try:
        ua_rows = db.execute_query("SELECT username, sex FROM useraccount_cache")
        useraccount_dict = {
            row['username'].upper().strip(): str(row['sex'] or '').upper() 
            for row in ua_rows
        }
    except Exception:
        useraccount_dict = {}
    procesador = ProcesadorItemName(useraccount_dict)
    
    # 2. Se aplica el método de la instancia a cada fila del DataFrame.
    #    La instancia 'procesador' mantendrá la cuenta durante todo el proceso.
    data[['SEXO', 'TIPO U', 'OBSERVACIÓN']] = data.apply(procesador.procesar_fila, axis=1)
    
    return data

# --- INICIO: NUEVA CLASE DE PROCESADOR MEJORADA ---
class ProcesadorItemName:
    def __init__(self, useraccount_dict=None):
        self.rotary_sex_counter = 0
        self.OPCIONES_SEXO = ['M', 'F']
        self.OPCIONES_TIPO_U = ['P', 'S', 'U', 'D', 'TE', 'PG']
        self.useraccount_dict = useraccount_dict or {}

    def procesar_fila(self, row):
        itemname = str(row['ITEMNAME']).upper()
        
        # 1. NORMALIZACIÓN: Reemplazamos todos los posibles separadores por un solo espacio y dividimos
        # La expresión regular '[-._* ]+' busca uno o más caracteres de los que están entre corchetes
        parts = [p for p in re.split('[-._* ]+', itemname) if p]

        sexo_final = None
        tipo_u_final = None
        observacion = ''

        # 2. ANÁLISIS POSICIONAL: Nos enfocamos en las dos últimas partes
        last_part = parts[-1] if len(parts) > 1 else None # Usamos len > 1 para asegurar que hay al menos 2 partes
        second_last_part = parts[-2] if len(parts) > 1 else None
        
        # --- Motor de Reglas Mejorado ---

        # CASO 1: ORDEN CORRECTO (ej. ...-P-F)
        if second_last_part in self.OPCIONES_TIPO_U and last_part in self.OPCIONES_SEXO:
            tipo_u_final = second_last_part
            sexo_final = last_part
            observacion = 'OK'

        # CASO 2: ORDEN INVERTIDO (ej. ...-F-P)
        elif second_last_part in self.OPCIONES_SEXO and last_part in self.OPCIONES_TIPO_U:
            tipo_u_final = last_part
            sexo_final = second_last_part
            observacion = 'ORDEN CORREGIDO'

        # CASO 3: FALTA EL SEXO (ej. ...-P)
        elif last_part in self.OPCIONES_TIPO_U:
            tipo_u_final = last_part
            # Asignación rotativa para el sexo
            if self.rotary_sex_counter % 2 == 0: sexo_final = 'M'
            else: sexo_final = 'F'
            self.rotary_sex_counter += 1
            observacion = 'DEFAULT: SIN SEXO'
            
        # CASO 4: FALTA EL TIPO DE USUARIO (ej. ...-M)
        elif last_part in self.OPCIONES_SEXO:
            sexo_final = last_part
            tipo_u_final = 'PG' # Valor por defecto
            observacion = 'DEFAULT: TIPO DE USUARIO NO DEFINIDO'

        # CASO 5: DATOS INVÁLIDOS O INCOMPLETOS
        else:
            tipo_u_final = 'PG'
            # Asignación rotativa para el sexo
            if self.rotary_sex_counter % 2 == 0: sexo_final = 'M'
            else: sexo_final = 'F'
            self.rotary_sex_counter += 1
            observacion = 'DEFAULT: DATOS INVÁLIDOS'

        # --- CORRECCIÓN DE SEXO VIA DB ---
        if observacion in ['DEFAULT: SIN SEXO', 'DEFAULT: DATOS INVÁLIDOS']:
            # Usar itemname_original para asegurar coincidencia exacta
            itemname_original = itemname.strip()
            if itemname_original in self.useraccount_dict:
                sexo_db = self.useraccount_dict[itemname_original]
                if sexo_db in self.OPCIONES_SEXO:
                    sexo_final = sexo_db
                    observacion = 'CORREGIDO VIA DB'

        return pd.Series([sexo_final, tipo_u_final, observacion])
# --- FIN DE LA NUEVA CLASE ---

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

class PremiumSplashScreen(QDialog):
    def __init__(self, is_dark_mode=False):
        super().__init__()
        # 1. Configuración de ventana técnica
        self.setFixedSize(650, 420)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 2. Definición de colores
        self.primary_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e3a8a, stop:1 #3b82f6)"
        self.accent_neon = "#00fff7"

        # 3. Contenedor Maestro (El que lleva el fondo y la sombra)
        self.container = QFrame(self)
        self.container.setGeometry(10, 10, 630, 400)
        self.container.setStyleSheet(f"""
            QFrame {{
                background: {self.primary_gradient};
                border-radius: 25px;
                border: 1px solid rgba(255,255,255,0.15);
            }}
        """)
        
        # Sombra externa
        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(30)
        eff.setXOffset(0)
        eff.setYOffset(10)
        eff.setColor(QColor(0,0,0,180))
        self.container.setGraphicsEffect(eff)

        # 4. Layout y Elementos (IMPORTANTE: Sin parent directo en el constructor de los widgets)
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(40, 50, 40, 50)
        layout.setSpacing(0)

        # Encabezado
        self.header = QLabel("INGENIERÍA DE DATOS", self.container)
        self.header.setStyleSheet(f"color: {self.accent_neon}; font-weight: 800; letter-spacing: 10px; font-size: 16px; background: transparent; border: none;")
        self.header.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.header)

        layout.addSpacing(20)

        # Título ADA 4.0
        self.title_label = QLabel("ADA 4.0", self.container)
        self.title_label.setFont(QFont("Outfit", 70, QFont.ExtraBold))
        self.title_label.setStyleSheet("color: white; background: transparent; border: none;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        # Eslógan
        self.slogan = QLabel("Analizador de Datos y Actividades", self.container)
        self.slogan.setFont(QFont("Inter", 16, QFont.Medium))
        self.slogan.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent; border: none;")
        self.slogan.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.slogan)

        layout.addStretch()

        # Mensaje de progreso
        self.status_label = QLabel("Sincronizando datos...", self.container)
        self.status_label.setStyleSheet("color: white; font-size: 16px; font-weight: 400; background: transparent; border: none;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        layout.addSpacing(10)

        # Barra de progreso
        self.progress = QProgressBar(self.container)
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setStyleSheet(f"""
            QProgressBar {{ background-color: rgba(255,255,255,0.1); border-radius: 2px; border: none; }}
            QProgressBar::chunk {{ background-color: {self.accent_neon}; border-radius: 2px; }}
        """)
        layout.addWidget(self.progress)

        self._center_window()

        # Timer de simulación
        self.load_step = 0
        self.messages = ["Preparando motores...", "Cargando datos...", "Sincronizando...", "¡Listo!"]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_loading)
        self.timer.start(75)

    def _update_loading(self):
        self.load_step += 2
        if self.load_step <= 100:
            self.progress.setValue(self.load_step)
            if self.load_step % 25 == 0:
                idx = (self.load_step // 25) % len(self.messages)
                self.status_label.setText(self.messages[idx])
        else:
            self.timer.stop()

    def _center_window(self):
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)


if __name__ == "__main__":
    try:
        # 0. CONFIGURACIÓN TEMPRANA DE CAPTURA DE ERRORES
        sys.excepthook = global_exception_handler

        # 1. Cierre preventivo del splash de PyInstaller
        if pyi_splash:
            pyi_splash.close()

        log_to_file("--- INICIALIZANDO ADA 4.0 ---")
        myappid = f'infoplazas.ada.analizador.v{VERSION}'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        app = QApplication(sys.argv)

        # --- CARGAR ARCHIVO DE ESTILOS GLOBAL (QSS) ---
        qss_path = os.path.join(BASE_DIR, 'ada_nova.qss')
        if os.path.exists(qss_path):
            try:
                with open(qss_path, 'r', encoding='utf-8') as qss_file:
                    app.setStyleSheet(qss_file.read())
                log_to_file(f"✅ Estilos QSS cargados desde: {qss_path}")
            except Exception as e:
                error_msg = f"⚠️ Error cargando QSS: {e}"
                print(error_msg)
                log_to_file(error_msg)
        else:
            log_to_file(f"⚠️ Archivo QSS no encontrado en: {qss_path}")
        # ----------------------------------------------

        icon_path = os.path.join(BASE_DIR, 'iconBDVicTor_D.ico')
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

        # 2. Lanzar Splash Premium
        splash = PremiumSplashScreen()
        splash.show()
        app.processEvents()

        log_to_file("Instanciando ventana principal...")
        window = InfoplazaAnalyzer()
        # sys.excepthook ya está configurado globalmente, no reasignamos el método interno
        # sys.excepthook = window._mi_excepcion_global <-- REMOVED

        # Esperar 4 segundos para el despliegue visual
        QTimer.singleShot(4000, lambda: (splash.close(), window.show(), log_to_file("APP visible.")))

        sys.exit(app.exec_())

    except Exception as e:
        error_msg = f"ERROR CRÍTICO EN EL ARRANQUE: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        log_to_file(error_msg)
        
        # Intentar mostrar un mensaje de error incluso si falla todo
        try:
            temp_app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "Error Fatal en ADA", 
                               f"La aplicación no pudo iniciarse correctamente.\n\n"
                               f"Error: {str(e)}\n\n"
                               "Se ha guardado un reporte en 'ada_debug.log'.")
        except:
            pass
            
        input("Presiona Enter para salir...")


