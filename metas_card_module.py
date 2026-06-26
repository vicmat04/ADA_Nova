import re
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QFrame, QMessageBox, QGroupBox, QLayout, QSizePolicy,
    QProgressBar, QGridLayout, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QStyledItemDelegate, QStyle, QLineEdit,
    QFileDialog
)
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QBrush, QDesktopServices
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect, QSize, QPoint, QUrl
import pandas as pd

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Importar módulos de la nueva arquitectura
from metas_config import (
    ACTIVIDADES, MESES_PERIODO,
    obtener_actividades_normales, obtener_actividades_bonus,
    get_mes_actual, get_year_for_month, get_fechas_periodo, # NUEVO getter
    crear_mapeo_display_a_columna,  # NUEVO: Para convertir nombres de Metas
    save_fechas_config # Función para guardar fechas dinámicas
)
from metas_validator import MetasDataValidator
from metas_calculator import MetasCalculator
from metas_cache_manager import MetasCacheManager
from metas_connection_manager import MetasConnectionManager, ConnectionStatus


# Configuración
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_persistent_path(relative_path):
    """
    Obtiene la ruta a un archivo, priorizando el bundle de PyInstaller si existe, 
    o de lo contrario lo busca junto al ejecutable o script.
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


# ============================================================================
# CLASE FLOW LAYOUT (Para Grid Responsivo)
# ============================================================================
class FlowLayout(QLayout):
    """Layout que acomoda los items en cuadrícula fléxible"""
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        size += QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        spacing = self.spacing()

        for item in self.itemList:
            wid = item.widget()
            spaceX = spacing + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal)
            spaceY = spacing + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical)
            
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()


# ============================================================================
# WIDGET DE INDICADOR DE ESTADO DE CONEXIÓN
# ============================================================================
class ConnectionStatusWidget(QWidget):
    """Widget que muestra el estado de conexión actual (Online/Offline)"""
    
    def __init__(self, manager=None, parent=None):
        super().__init__(parent)
        self.current_status = ConnectionStatus.OFFLINE_NO_DATA
        self.last_update = None
        self.init_ui()
        
        # Conectar al manager si se proporciona
        if manager:
            # Safely get properties using getattr to avoid crashes if manager interface changes or is incomplete
            last_update = getattr(manager, 'last_update_str', "---")
            self.set_status(manager.current_status, last_update)
            
            # Connect only if signal exists
            if hasattr(manager, 'connection_changed'):
                manager.connection_changed.connect(self.set_status)
    
    def init_ui(self):
        """Inicializa la interfaz del indicador"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        
        # Ícono de estado
        self.icon_label = QLabel("⚫")
        self.icon_label.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.icon_label)
        
        # Texto de estado
        self.status_label = QLabel("Inicializando...")
        self.status_label.setFont(QFont("Segoe UI", 9))
        layout.addWidget(self.status_label)
        
        # Ícono de información (solo visible en offline)
        self.info_icon = QLabel("ℹ️")
        self.info_icon.setFont(QFont("Segoe UI", 9))
        self.info_icon.setCursor(Qt.PointingHandCursor)
        self.info_icon.setVisible(False)
        self.info_icon.mousePressEvent = self.show_details
        layout.addWidget(self.info_icon)
        
        # Estilo base
        self.setFixedHeight(28)
        self.update_style()
    
    def set_status(self, status: ConnectionStatus, last_update: str = None):
        """
        Actualiza el estado visual del indicador
        
        Args:
            status: Estado de conexión
            last_update: Fecha/hora de última actualización
        """
        self.current_status = status
        self.last_update = last_update
        
        # Actualizar ícono y texto según el estado
        if status == ConnectionStatus.ONLINE_FRESH:
            self.icon_label.setText("🟢")
            self.status_label.setText("Conectado")
            self.info_icon.setVisible(False)
            tooltip = f"Conectado a Google Sheets\nÚltima actualización: {last_update or 'Ahora'}"
            
        elif status == ConnectionStatus.ONLINE_CACHED:
            self.icon_label.setText("🟡")  
            self.status_label.setText("Conectado (caché)")
            self.info_icon.setVisible(False)
            tooltip = f"Conectado - Usando datos recientes\nÚltima actualización: {last_update or 'Desconocida'}"
            
        elif status == ConnectionStatus.OFFLINE_CACHED:
            self.icon_label.setText("🔴")
            self.status_label.setText("Sin conexión")
            self.info_icon.setVisible(True)
            tooltip = f"Sin conexión a Google Sheets\nMostrando datos locales del: {last_update or 'Desconocida'}"
            
        elif status == ConnectionStatus.OFFLINE_NO_DATA:
            self.icon_label.setText("⚫")
            self.status_label.setText("Sin datos")
            self.info_icon.setVisible(True)
            tooltip = "Sin conexión y sin datos locales disponibles"
            
        else:  # ERROR
            self.icon_label.setText("❌")
            self.status_label.setText("Error")
            self.info_icon.setVisible(True)
            tooltip = "Error de conexión. Haga clic en ℹ️ para más detalles"
        
        self.setToolTip(tooltip)
        self.update_style()
    
    def update_style(self):
        """Actualiza el estilo visual según el estado usando QSS"""
        # Mapeo de estado a valor de propiedad para QSS
        status_map = {
            ConnectionStatus.ONLINE_FRESH: "online_fresh",
            ConnectionStatus.ONLINE_CACHED: "online_cached",
            ConnectionStatus.OFFLINE_CACHED: "offline_cached",
            ConnectionStatus.OFFLINE_NO_DATA: "offline_no_data",
            ConnectionStatus.ERROR: "error"
        }
        
        status_value = status_map.get(self.current_status, "error")
        
        # Aplicar propiedad para que QSS lo maneje
        self.setProperty("status", status_value)
        self.style().unpolish(self)
        self.style().polish(self)
    
    def show_details(self, event):
        """Muestra diálogo con detalles del estado de conexión"""
        if self.current_status == ConnectionStatus.OFFLINE_CACHED:
            message = (
                f"<h3>🔴 Modo Sin Conexión</h3>"
                f"<p>ADA no puede conectarse a Google Sheets en este momento.</p>"
                f"<p><b>Datos mostrados:</b><br>"
                f"Última actualización: {self.last_update or 'Desconocida'}</p>"
                f"<p><b>¿Qué hacer?</b><br>"
                f"• Verifique su conexión a Internet<br>"
                f"• Haga clic en el botón de actualizar cuando tenga conexión<br>"
                f"• Los datos locales son válidos por 24 horas</p>"
            )
        elif self.current_status == ConnectionStatus.OFFLINE_NO_DATA:
            message = (
                f"<h3>⚫ Sin Datos Disponibles</h3>"
                f"<p>No hay conexión a Google Sheets y no hay datos locales guardados.</p>"
                f"<p><b>¿Qué hacer?</b><br>"
                f"• Verifique su conexión a Internet<br>"
                f"• Conéctese a Internet y actualice los datos<br>"
                f"• Una vez descargados, podrá ver los datos sin conexión</p>"
            )
        else:  # ERROR
            message = (
                f"<h3>❌ Error de Conexión</h3>"
                f"<p>Ocurrió un error al intentar conectar con Google Sheets.</p>"
                f"<p><b>Posibles causas:</b><br>"
                f"• Sin conexión a Internet<br>"
                f"• Problema con las credenciales<br>"
                f"• Google Sheets temporalmente no disponible</p>"
                f"<p><b>Solución:</b><br>"
                f"Verifique su conexión y vuelva a intentar.</p>"
            )
        
        QMessageBox.information(self, "Estado de Conexión", message)


class GoogleSheetsWorker(QThread):
    """Worker thread para cargar datos de Google Sheets en segundo plano"""
    finished = pyqtSignal(dict, str, str)  # (datos, error, estado_conexion)
    progress = pyqtSignal(str)  # Para reportar progreso de retry
    
    def __init__(self, infoplaza_id, cache_manager=None, connection_manager=None):
        super().__init__()
        self.infoplaza_id = infoplaza_id
        self.cache_manager = cache_manager or MetasCacheManager()
        self.connection_manager = connection_manager or MetasConnectionManager()
    
    
    @staticmethod
    def _normalizar_nombre_columna(nombre):
        """
        Normaliza el nombre de una columna eliminando saltos de línea y espacios extra
        
        Args:
            nombre: Nombre original de la columna
        
        Returns:
            str: Nombre normalizado
        
        Ejemplos:
            "P.V.\n USUARIO" -> "P.V. USUARIO"
            "Otras\n CAPACIT." -> "Otras CAPACIT."
            "  Espacios  Extra  " -> "Espacios Extra"
        """
        if not nombre:
            return nombre
        
        # Reemplazar saltos de línea por espacios
        nombre = nombre.replace('\n', ' ').replace('\r', ' ')
        
        # Eliminar espacios múltiples
        nombre = ' '.join(nombre.split())
        
        return nombre
    
    
    def _download_from_sheets(self):
        """
        Intenta descargar datos de Google Sheets
        
        Returns:
            Tuple[dict, Optional[str]]: (datos, error)
        """
        # Conectar a Google Sheets
        scope = ['https://www.googleapis.com/auth/spreadsheets', 
                 'https://www.googleapis.com/auth/drive.file']
        creds_path = os.path.join(BASE_DIR, 'credentials.json')
        
        if not os.path.exists(creds_path):
            return {}, "No se encontró el archivo de credenciales"
        
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        client = gspread.authorize(creds)
        
        # Abrir el libro de Metas
        URL_DE_LA_HOJA = "https://docs.google.com/spreadsheets/d/1xqHRJU-tH82PU1jY57Zt3S5fCgmigy2X9rF5x9CvbFI/edit?usp=sharing"
        workbook = client.open_by_url(URL_DE_LA_HOJA)
        
        # Leer hoja "ResultadoMetas" - TODAS LAS FILAS
        sheet_resultados = workbook.worksheet("ResultadoMetas")
        all_rows = sheet_resultados.get_all_values()
        
        if not all_rows or len(all_rows) < 2:
            return {}, "La hoja ResultadoMetas está vacía"
        
        # NORMALIZAR nombres de columnas (eliminar saltos de línea, espacios extra)
        headers_raw = all_rows[0]
        headers = [self._normalizar_nombre_columna(h) for h in headers_raw]
        
        # Convertir TODAS las filas a diccionarios (para el caché)
        todas_infoplazas = []
        infoplaza_data = None
        
        for row in all_rows[1:]:
            if len(row) > 0:
                row_dict = dict(zip(headers, row))  # Usar headers normalizados
                todas_infoplazas.append(row_dict)
                
                # Identificar la fila de la infoplaza solicitada
                if str(row[0]) == str(self.infoplaza_id):
                    infoplaza_data = row_dict
        
        if not infoplaza_data:
            # Si no se encuentra, NO es un error crítico para el worker, 
            # ya que queremos devolver 'todas_infoplazas' para el cuadro maestro.
            # Simplemente dejamos infoplaza_data como None.
            pass
        
        # Leer hoja "Metas"
        sheet_metas = workbook.worksheet("Metas")
        metas_rows = sheet_metas.get_all_values()
        
        if not metas_rows or len(metas_rows) < 2:
            return {}, "La hoja Metas está vacía"
        
        # Crear mapeo de nombres descriptivos a nombres de columna
        mapeo_display_a_columna = crear_mapeo_display_a_columna()
        
        metas_headers = metas_rows[0]
        metas_data = {}
        actividades_config = []  # NUEVO: Lista de ActividadConfig dinámicas
        
        # Detectar si existen las nuevas columnas (formato extendido)
        has_extended_format = len(metas_headers) >= 10  # Meta, Total/mes, Total, %, Nombre, Icon, Tipo, Grupo, Freq, Eventos
        print(f"[WORKER] Columnas en Metas: {len(metas_headers)} | Formato extendido: {has_extended_format}")
        if has_extended_format:
            print(f"[WORKER] Headers: {metas_headers[:10]}")
        
        for idx, row in enumerate(metas_rows[1:], 1):
            if len(row) >= 4:  # Mínimo: Meta, Total por mes, Total, Porcentaje
                # NORMALIZAR nombre de la actividad/meta
                meta_nombre_raw = self._normalizar_nombre_columna(row[0])
                
                # CONVERTIR de display_name a column_name si es necesario
                if meta_nombre_raw in mapeo_display_a_columna:
                    meta_nombre = mapeo_display_a_columna[meta_nombre_raw]
                else:
                    meta_nombre = meta_nombre_raw
                
                # Guardar metas (siempre)
                metas_data[meta_nombre] = {
                    'meta_mensual': row[1],
                    'meta_total': row[2],
                    'porcentaje': row[3]
                }
                
                # NUEVO: Parsear configuración extendida si existe
                if has_extended_format:
                    try:
                        from metas_config import ActividadConfig
                        display_name = row[4] if len(row) > 4 and row[4].strip() else meta_nombre
                        icon = row[5] if len(row) > 5 and row[5].strip() else "📋"
                        card_type = row[6] if len(row) > 6 and row[6].strip() else "standard"
                        group_id = row[7] if len(row) > 7 and row[7].strip() else ""
                        frequency = row[8] if len(row) > 8 and row[8].strip() else "monthly"
                        events = row[9] if len(row) > 9 and row[9].strip() else ""
                        
                        # Crear ActividadConfig
                        actividades_config.append(ActividadConfig(
                            column_name=meta_nombre,
                            display_name=display_name,
                            es_bonus=(card_type == "bonus"),
                            orden=idx,  # Usar orden de aparición
                            icon=icon,
                            card_type=card_type,
                            group_id=group_id,
                            frequency=frequency,
                            events=events
                        ))
                        # NUEVO: Log para debugging
                        print(f"[WORKER] Actividad parseada: column='{meta_nombre}', display='{display_name}', icon='{icon}'")
                    except Exception as e:
                        # Si falla el parsing, ignorar esta actividad y continuar
                        print(f"[WORKER] Error parseando actividad '{meta_nombre}': {e}")
        
        # Obtener última actualización de la hoja "config" (E1 fecha, F1 hora)
        try:
            sheet_config = workbook.worksheet("config")
            fecha_actualizacion = sheet_config.acell('E1').value or "N/A"
            hora_actualizacion = sheet_config.acell('F1').value or "N/A"
        except Exception as e:
            # Si no existe la hoja config o falla la lectura, usar valores por defecto
            print(f"[WORKER] Error leyendo fecha de hoja config: {e}")
            fecha_actualizacion = "N/A"
            hora_actualizacion = "N/A"
        
        # LOGGING: Mostrar actividades parseadas
        if has_extended_format:
            print(f"[WORKER] Actividades dinámicas parseadas: {len(actividades_config)}")
            for act in actividades_config:
                print(f"  - {act.column_name}: tipo={act.card_type}, grupo={act.group_id}, freq={act.frequency}")
        
        # Preparar datos completos PROCESADOS (incluyendo datos para el caché)
        resultado = {
            'infoplaza': infoplaza_data,
            'metas': metas_data,
            'actividades_config': actividades_config if has_extended_format else None,  # NUEVO
            'fecha_actualizacion': fecha_actualizacion,
            'hora_actualizacion': hora_actualizacion,
            # Datos adicionales para el caché
            'todas_infoplazas': todas_infoplazas  # TODAS las infoplazas
        }
        
        # --- NUEVO: Cargar Configuración de Fechas (Si existe hoja 'Config') ---
        try:
            # Búsqueda insensible a mayúsculas/minúsculas de la hoja "Config" y "NovedadesConfig"
            sheet_config = None
            sheet_novedades = None
            available_sheets = workbook.worksheets()
            
            for ws in available_sheets:
                title_clean = ws.title.strip().lower()
                if title_clean == "config":
                    sheet_config = ws
                elif title_clean == "novedadesconfig":
                    sheet_novedades = ws
            
            # 1. Procesar CONFIG (Fechas)
            config_rows = []
            if sheet_config:
                config_rows = sheet_config.get_all_values()
                # Convertir a diccionario clave-valor (normalizando claves)
                remote_config = {}
                for row in config_rows:
                    if len(row) >= 2:
                        key = str(row[0]).strip().upper()
                        val = str(row[1]).strip()
                        remote_config[key] = val
                
                inicio_remoto = remote_config.get('INICIO_PERIODO')
                fin_remoto = remote_config.get('FIN_PERIODO')
                
                if inicio_remoto and fin_remoto:
                    save_fechas_config(inicio_remoto, fin_remoto)
            else:
                pass # No es crítico
                
            # 2. Procesar NOVEDADES (News Feed)
            novedades_data = []
            if sheet_novedades:
                msgs_rows = sheet_novedades.get_all_records() # get_all_records usa la primera fila como header
                # Filtrar filas vacías o corruptas
                novedades_data = [row for row in msgs_rows if str(row.get('ID','')).strip()]
                print(f"[WORKER] Novedades descargadas: {len(novedades_data)}")
            else:
                # Si no existe, INTENTAR CREARLA para facilitar al usuario
                try:
                    print("[WORKER] Hoja 'NovedadesConfig' no encontrada. Creando...")
                    new_sheet = workbook.add_worksheet(title="NovedadesConfig", rows=100, cols=10)
                    headers = ["ID", "FECHA", "TITULO", "DESCRIPCION", "TIPO", "URL_LINK", "URL_IMAGEN", "PRIORIDAD", "ACTIVO", "VENCE"]
                    new_sheet.append_row(headers)
                    # Agregar ejemplo
                    ejemplo = ["NOV-001", datetime.now().strftime("%d/%m/%Y"), "Bienvenido a Novedades", "Aquí verás noticias importantes.", "INFO", "", "", "NORMAL", "SI", ""]
                    new_sheet.append_row(ejemplo)
                    print("[WORKER] Hoja 'NovedadesConfig' creada exitosamente.")
                    
                    # Devolver el ejemplo para que no salga vacío la primera vez
                    novedades_data = [dict(zip(headers, ejemplo))]
                except Exception as e_create:
                    print(f"[WORKER] No se pudo crear la hoja NovedadesConfig: {e_create}")

        except Exception as e:
            print(f"[WORKER] Error cargando config/novedades: {e}")
            novedades_data = [] # Fallback
        # -----------------------------------------------------------------------
        
        # Inyectar novedades al resultado (modificamos el diccionario 'resultado' que se retorna)
        resultado['novedades'] = novedades_data
        
        return resultado, None
    
    def run(self):
        """Ejecuta la descarga de datos con retry logic y caché"""
        try:
            # Intentar descargar con retry logic
            datos, error, estado = self.connection_manager.try_connect_with_retry(
                self._download_from_sheets,
                progress_callback=lambda msg: self.progress.emit(msg)
            )
            
            # Si descargamos exitosamente, guardar en caché
            if not error and datos:
                self.cache_manager.save_to_cache(datos, self.infoplaza_id)
                print(f"[WORKER] ✅ Datos descargados y guardados en caché")
                # DEBUG: Verificar qué estamos enviando
                print(f"[WORKER] DEBUG: Keys en datos a emitir: {list(datos.keys())}")
                print(f"[WORKER] DEBUG: actividades_config presente: {'actividades_config' in datos}")
                if 'actividades_config' in datos:
                    print(f"[WORKER] DEBUG: actividades_config es None: {datos['actividades_config'] is None}")
                self.finished.emit(datos, "", ConnectionStatus.ONLINE_FRESH.value)
                return
            
            # Si falla la descarga, intentar cargar desde caché
            print(f"[WORKER] ⚠️ Descarga falló, intentando caché...")
            cached_data, cache_msg = self.cache_manager.load_from_cache()
            
            if cached_data:
                print(f"[WORKER] ✅ Datos cargados desde caché: {cache_msg}")
                print(f"[WORKER] DEBUG: Keys en cached_data: {list(cached_data.keys())}")
                
                # CRÍTICO: Filtrar datos por infoplaza_id si está definido
                if self.infoplaza_id and 'todas_infoplazas' in cached_data:
                    print(f"[WORKER] Buscando infoplaza_id: '{self.infoplaza_id}'")
                    print(f"[WORKER] Total de infoplazas en cache: {len(cached_data['todas_infoplazas'])}")
                    
                    infoplaza_data = None
                    for i, row_dict in enumerate(cached_data['todas_infoplazas']):
                        # Debug: mostrar primeras 3 infoplazas
                        if i < 3:
                            info_id = row_dict.get('# Info', 'N/A')
                            nombre = row_dict.get('Infoplaza', 'N/A')
                            print(f"[WORKER]   [{i}] ID='{info_id}' (type={type(info_id)}), Nombre={nombre}")
                        
                        if str(row_dict.get('# Info', '')) == str(self.infoplaza_id):
                            infoplaza_data = row_dict
                            print(f"[WORKER] ✅ ¡Infoplaza {self.infoplaza_id} ENCONTRADA en índice {i}!")
                            break
                    
                    # Asignar la infoplaza específica a los datos
                    if infoplaza_data:
                        cached_data['infoplaza'] = infoplaza_data
                        print(f"[WORKER] ✅ cached_data['infoplaza'] asignado")
                    else:
                        # La infoplaza no existe en el caché, pero es válido
                        # (puede ser usuario inválido o nuevo)
                        cached_data['infoplaza'] = None
                        print(f"[WORKER] ⚠️ Infoplaza {self.infoplaza_id} NO encontrada en caché")
                else:
                    print(f"[WORKER] No se filtra - infoplaza_id={self.infoplaza_id}")
                
                self.finished.emit(cached_data, "", ConnectionStatus.OFFLINE_CACHED.value)
                return
            
            # No hay datos ni en descarga ni en caché
            print(f"[WORKER] ❌ Sin datos disponibles")
            error_final = f"No se pudo conectar y no hay caché disponible.\n{error}"
            self.finished.emit({}, error_final, ConnectionStatus.OFFLINE_NO_DATA.value)
            
        except Exception as e:
            print(f"[WORKER] ❌ Excepción crítica: {e}")
            # Intentar caché como último recurso
            try:
                cached_data, _ = self.cache_manager.load_from_cache()
                if cached_data:
                    # Aplicar el mismo filtrado que arriba
                    if self.infoplaza_id and 'todas_infoplazas' in cached_data:
                        infoplaza_data = None
                        for row_dict in cached_data['todas_infoplazas']:
                            if str(row_dict.get('# Info', '')) == str(self.infoplaza_id):
                                infoplaza_data = row_dict
                                break
                        cached_data['infoplaza'] = infoplaza_data
                    
                    self.finished.emit(cached_data, "", ConnectionStatus.OFFLINE_CACHED.value)
                    return
            except:
                pass
            
            self.finished.emit({}, f"Error crítico: {str(e)}", ConnectionStatus.ERROR.value)



class CircularProgressWidget(QWidget):
    """Widget circular que muestra el porcentaje de progreso global"""
    def __init__(self, percentage=0, parent=None):
        super().__init__(parent)
        self.percentage = percentage
        self.setFixedSize(80, 80)
    
    def set_percentage(self, value):
        self.percentage = value
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Dimensiones dinámicas basadas en el tamaño del widget
        mw = min(self.width(), self.height())
        margin = 5
        diametro = mw - (margin * 2)
        rect = self.rect().adjusted(margin, margin, -margin, -margin)
        
        # Fondo del círculo
        painter.setBrush(QColor(255, 255, 255, 150))
        painter.setPen(QColor(200, 200, 200))
        painter.drawEllipse(rect)
        
        # Progreso (arco)
        if self.percentage >= 80:
            color = QColor(40, 167, 69)  # Verde
        elif self.percentage >= 50:
            color = QColor(255, 193, 7)  # Amarillo
        else:
            color = QColor(220, 53, 69)  # Rojo
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        
        # Dibujar arco de progreso
        start_angle = 90 * 16  # Empezar desde arriba
        span_angle = int(-(self.percentage * 360 / 100) * 16)  # Convertir a int
        painter.drawPie(rect, start_angle, span_angle)
        
        # Círculo blanco interior (proporcional)
        ancho_anillo = int(diametro * 0.15)  # Ancho del anillo es 15% del diámetro
        margin_inner = margin + ancho_anillo
        rect_inner = self.rect().adjusted(margin_inner, margin_inner, -margin_inner, -margin_inner)
        
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(rect_inner)
        
        # Texto del porcentaje (proporcional)
        painter.setPen(QColor(44, 62, 80))
        font_size = max(12, int(diametro * 0.25))  # Fuente es 25% del diámetro
        font = QFont("Segoe UI", font_size, QFont.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, f"{int(self.percentage)}%")


class MetasCardWidget(QWidget):
    """Widget principal que muestra la tarjeta de metas de Infoplaza"""
    
    # Cache compartido entre todas las instancias (datos de Google Sheets)
    _sheets_cache = {
        'metas_totales': None,  # Datos de la hoja "Metas"
        'todas_infoplazas': None,  # Todas las filas de "ResultadoMetas"
        'ultima_actualizacion': None,  # Fecha y hora de actualización
        'actividades_config': None  # NUEVO: Configuración de actividades desde Google Sheets
    }
    
    # NUEVA SEÑAL: Para notificar novedades a la App Principal
    novedades_available = pyqtSignal(list)

    def __init__(self, main_app=None, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.current_data = {}
        self.infoplaza_id = None
        self.worker = None
        self.showing_info_message = False  # Flag para recordar si estamos mostrando mensaje de error
        self.invalid_username = None  # Guardar username inválido para mostrarlo en mensaje de error
        
        # Aplicar clase CSS para estilos automáticos del QSS
        self.setProperty("class", "MetasTableView")
        
        # NUEVO: Instancias de validador y calculador
        self.validator = MetasDataValidator()
        self.calculator = None  # Se crea cuando se cargan datos
        
        # NUEVO: Gestores de caché y conexión
        self.cache_manager = MetasCacheManager()
        self.connection_manager = MetasConnectionManager()
        self.status_widget = None  # Se crea en init_ui
        self.checking_changes = False # Flag para modo de verificación de cambios
        
        self.init_ui(); self._apply_theme_styles()
    
    def init_ui(self):
        """Inicializa la interfaz de usuario"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # NUEVO: Header con indicador de estado de conexión
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_layout.addStretch()
        
        self.status_widget = ConnectionStatusWidget()
        header_layout.addWidget(self.status_widget)
        main_layout.addLayout(header_layout)
        
        # Área de scroll para la tarjeta
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame) # Estilo más limpio
        
        # Eliminar fondo blanco (hacer transparente para que herede color de fondo)
        # Usar clase QSS en lugar de estilo hardcoded
        self.scroll.setProperty("class", "MetasScrollArea")
        
        # Widget contenedor de la tarjeta
        self.card_container = QWidget()
        # Asegurar transparencia también aquí
        self.card_container.setAttribute(Qt.WA_TranslucentBackground)
        # Usar clase QSS en lugar de estilo hardcoded
        self.card_container.setProperty("class", "MetasCardContainer")
        
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setAlignment(Qt.AlignTop)
        
        self.scroll.setWidget(self.card_container)
        main_layout.addWidget(self.scroll)
        
        # Aplicar tema inicial
        self._apply_theme_styles()
        
        # Mostrar mensaje inicial
        self.show_initial_message()

    def update_facilitator_mode_visibility(self, is_facilitator_mode_active):
        """Actualiza la visibilidad según el modo facilitador"""
        pass # Botón de actualizar eliminado

    def update_theme(self, is_dark):
        """Actualiza el tema visualmente y propaga a todos los widgets hijos"""
        self._apply_theme_styles()
        
        # CRÍTICO: Propagar tema a todos los widgets hijos
        theme_value = "dark" if is_dark else "light"
        all_widgets = self.findChildren(QWidget)
        
        for widget in all_widgets:
            widget.setProperty("theme", theme_value)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        
        # Actualizar el widget raíz también
        self.setProperty("theme", theme_value)
        self.style().unpolish(self)
        self.style().polish(self)
        
        # Reconstruir la vista manteniendo el estado actual
        if self.showing_info_message:
            if self.infoplaza_id:
                # Si tenemos ID, mostramos el mensaje de "No encontrado"
                self.show_elegant_not_found_message(self.infoplaza_id)
            else:
                # Si no, el genérico de "Configuración Necesaria"
                self.show_elegant_info_message()
        elif self.current_data:
            self.build_card()
        else:
            self.show_initial_message()

    def _apply_theme_styles(self):
        """Aplica los estilos base mediante propiedades dinámicas"""
        self.setProperty("class", "Container")
        
        # Estilo botón refresh eliminado
        pass

    # _get_theme_colors REMOVED - using QSS

    
    def show_initial_message(self):
        """Muestra un mensaje de bienvenida inicial"""
        self.showing_info_message = False  # Resetear el flag
        self.clear_card()
        
        label = QLabel("📊 Bienvenido al Módulo de Metas\n\n"
                      "Cargando la información de tu Infoplaza...")
        label.setAlignment(Qt.AlignCenter)
        label.setProperty("class", "h2")
        self.card_layout.addWidget(label)
    
    def clear_card(self):
        """Limpia el contenido de la tarjeta"""
        while self.card_layout.count():
            child = self.card_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def refresh_data(self, force_reload=False, require_user_id=True, specific_id=None, silent=False, check_changes=False):
        """Actualiza los datos de la tarjeta
        
        Args:
            force_reload (bool): Si es True, fuerza la recarga desde Google Sheets.
            require_user_id (bool): Si es True, intenta obtener el ID del usuario. 
                                  Si es False, carga solo datos generales (Cuadro de Metas).
            specific_id (str, optional): Si se proporciona, carga los datos para este ID
                                       ignorando el usuario logueado.
            silent (bool): Si es True, no muestra el mensaje de carga (ideal para background polling).
            check_changes (bool): Si es True, compara los datos nuevos con el caché y avisa si hubo cambios.
        """
        self.checking_changes = check_changes
        infoplaza_id = specific_id
        
        if not infoplaza_id and require_user_id:
            # Obtener ID de Infoplaza del username
            infoplaza_id = self.extract_infoplaza_id()
        
        # Si no se encuentra ID (o no se requirió), seguimos adelante con None
        self.infoplaza_id = infoplaza_id
        
        # Verificar si ya tenemos datos en caché y no es recarga forzada
        if not force_reload and self._sheets_cache['metas_totales'] is not None:
            # Usar datos del caché
            self.load_from_cache()
            return
        
        # Mostrar mensaje de carga (Solo si no es silencioso)
        if not silent:
            self.show_loading_message()
        
        # Iniciar worker thread para cargar desde Google Sheets (solo si no hay uno ya corriendo)
        if self.worker and self.worker.isRunning():
            return
            
        self.worker = GoogleSheetsWorker(
            self.infoplaza_id, 
            self.cache_manager, 
            self.connection_manager
        )
        self.worker.finished.connect(self.on_data_loaded)
        self.worker.progress.connect(self.on_worker_progress)
        self.worker.start()
    
    def load_from_cache(self):
        """Carga los datos desde el caché en lugar de Google Sheets"""
        try:
            # Buscar datos de esta Infoplaza en el caché
            todas_infoplazas = self._sheets_cache['todas_infoplazas']
            
            infoplaza_data = None
            for row_dict in todas_infoplazas:
                if str(row_dict.get('# Info', '')) == str(self.infoplaza_id):
                    infoplaza_data = row_dict
                    break
            
            # ACTUALIZAR CUADRO MAESTRO (Siempre que haya datos globales)
            if hasattr(self.main_app, 'tab_cuadro_metas') and self._sheets_cache['todas_infoplazas']:
                self.main_app.tab_cuadro_metas.set_data(
                    self._sheets_cache['todas_infoplazas'], 
                    self._sheets_cache['metas_totales'],
                    self._sheets_cache.get('ultima_actualizacion')
                )

            if not infoplaza_data:
                # Intentar obtener el username para mostrarlo en el mensaje
                if not self.invalid_username:
                    self.extract_infoplaza_id()  # Esto guardará el username inválido si existe
                
                # --- NUEVA LÓGICA SIMÉTRICA ---
                if self.infoplaza_id:
                    # Caso A: Tenemos un ID (formato correcto) pero no está en el caché
                    self.show_elegant_not_found_message(self.infoplaza_id)
                else:
                    # Caso B: No se pudo identificar ID alguno
                    self.show_elegant_info_message()
                return
            
            # Preparar datos completos
            resultado = {
                'infoplaza': infoplaza_data,
                'metas': self._sheets_cache['metas_totales'],
                'fecha_actualizacion': self._sheets_cache['ultima_actualizacion']['fecha'],
                'hora_actualizacion': self._sheets_cache['ultima_actualizacion']['hora'],
                # NUEVO: Incluir actividades_config desde el caché
                'actividades_config': self._sheets_cache.get('actividades_config')
            }
            
            # IMPORTANTE: Crear calculator antes de build_card
            self.calculator = MetasCalculator(
                resultado['infoplaza'],
                resultado['metas']
            )
            
            self.current_data = resultado
            self.build_card()
            
        except Exception as e:
            self.show_error_message(f"Error al cargar desde caché: {str(e)}")
    
    def extract_infoplaza_id(self):
        """Extrae el ID de Infoplaza del nombre de usuario"""
        username = None
        
        # 1. INTENTO PRIMARIO: Usar la variable segura del main_app
        if hasattr(self.main_app, 'current_username') and self.main_app.current_username:
            username = self.main_app.current_username
            
        # 2. INTENTO SECUNDARIO (Fallback): Obtener del label (por compatibilidad)
        if not username and hasattr(self.main_app, 'label_ultimo_user'):
            label_text = self.main_app.label_ultimo_user.text()
            # Buscamos "Usuario:" independientemente del icono
            if "Usuario:" in label_text:
                # Separamos por "Usuario:" y tomamos la parte derecha
                parts = label_text.split("Usuario:")
                if len(parts) > 1:
                    candidate = parts[1].strip()
                    if candidate and candidate not in ["Sin datos", "Error", ""]:
                        username = candidate
        
        # 3. INTENTO TERCIARIO (Fallback final): DataFrame
        if not username and hasattr(self.main_app, 'data') and not self.main_app.data.empty:
            if 'USERNAME' in self.main_app.data.columns:
                username = self.main_app.data['USERNAME'].iloc[-1]
        
        # Verificar si debemos silenciar las alertas (ej. estamos en Cuadro de Metas - Índice 3)
        silenciar_alertas = False
        if hasattr(self.main_app, 'pages_widget'):
            # Índice 3 corresponde a 'Cuadro de Metas' según la inicialización en ADA_Nova.py
            if self.main_app.pages_widget.currentIndex() == 3:
                silenciar_alertas = True

        if not username:
            if not silenciar_alertas:
                # Si no hay username, simplemente retornamos None sin alertas escandalosas
                # El usuario verá "Sin Datos" en la UI principal
                pass
            return None
            
        # --- NUEVO: Ignorar estados temporales de sincronización ---
        # Si el username es un mensaje de estado, lo ignoramos silenciosamente
        estados_temporales = ["Esperando Sincronización...", "Cargando...", "Sin datos", "Error"]
        if any(estado in username for estado in estados_temporales):
            return None
        # -----------------------------------------------------------
        
        # Extraer número del username (formato: ###@dominio.com)
        match = re.match(r'^(\d+)@', username)
        
        if match:
            return match.group(1)
        else:
            # 🛡️ FIX ARCHITECTURAL: Si ya teníamos una infoplaza en vista y el nuevo usuario 
            # (ej. último clic en el cyber) es "ADMIN" o no válido, retenemos nuestro ID
            # para no destruir la pantalla actual del módulo de Metas.
            if self.infoplaza_id and self.current_data:
                return self.infoplaza_id
                
            # Guardar username inválido para mostrarlo en el mensaje elegante (sólo si no había datos)
            self.invalid_username = username
            if not silenciar_alertas:
                QMessageBox.critical(
                    self,
                    "Error de Formato en el nombre de usuario utilizado en el Cyber Cafe OneRoof",
                    f"<html>El formato del nombre de usuario no es válido:<br><b>'{username}'</b><br><br>"
                    f"Se esperaba el formato: <b>###@infoplazas.org.pa</b><br><br>"
                    f"⚠️ <b>ACCIÓN REQUERIDA:</b><br>"
                    f"Por favor, <b>tome una foto o captura de este mensaje</b> y envíela de inmediato a su "
                    f"<b>Facilitador o Enlace Regional</b> para corregir el usuario en la base de datos de Cyber Cafe OneRoof.</html>"
                )
            return None
    
    def show_loading_message(self):
        """Muestra mensaje de carga"""
        self.clear_card()
        
        
        label = QLabel("🔄 Sincronizando con la nube...\n\n(Esto puede tomar unos segundos)")
        label.setAlignment(Qt.AlignCenter)
        label.setProperty("class", "h2")
        self.card_layout.addWidget(label)
    
    def on_worker_progress(self, message):
        """Callback para mensajes de progreso del worker"""
        print(f"[PROGRESS] {message}")
        # Opcional: actualizar UI con progreso si lo deseas
    
    def on_data_loaded(self, data, error, connection_status):
        """Callback cuando se cargan los datos con nuevo estado de conexión"""
        # DEBUG: Ver qué datos recibimos
        print(f"[ON_DATA_LOADED] DEBUG: Keys recibidas: {list(data.keys()) if data else 'None'}")
        
        # --- EMITIR NOVEDADES (Si existen) ---
        if data and 'novedades' in data:
            self.novedades_available.emit(data['novedades'])
        
        if data:
            print(f"[ON_DATA_LOADED] DEBUG: tiene 'actividades_config': {'actividades_config' in data}")
            if 'actividades_config' in data:
                config = data.get('actividades_config')
                print(f"[ON_DATA_LOADED] DEBUG: actividades_config es None: {config is None}")
                if config:
                    print(f"[ON_DATA_LOADED] DEBUG: Cantidad: {len(config)}")
        
        # Actualizar indicador visual de estado
        try:
            status_enum = ConnectionStatus(connection_status)
            self.connection_manager.set_status(status_enum)
            
            # Obtener información de caché para el tooltip
            cache_info = self.cache_manager.get_cache_info()
            last_update = cache_info.get('last_updated_formatted', 'Desconocida')
            
            # Actualizar widget visual
            self.status_widget.set_status(status_enum, last_update)
            
            # Mostrar notificaciones si es offline
            if status_enum == ConnectionStatus.OFFLINE_CACHED:
                print(f"[METAS] Mostrando datos locales del: {last_update}")
            elif status_enum == ConnectionStatus.OFFLINE_NO_DATA:
                self.show_error_message(
                    "⚠️ Sin Conexión a Internet\n\n"
                    "No se puede conectar a Google Sheets y no hay datos locales disponibles.\n\n"
                    "Por favor, conéctese a Internet e intente nuevamente."
                )
                return
        except Exception as e:
            print(f"[ERROR] Error actualizando estado de conexión: {e}")
        
        if error:
            self.show_error_message(error)
            return
        
        if not data:
            self.show_error_message("No se recibieron datos")
            return
        
        # ============================================================
        # 1. ACTUALIZACIÓN INMEDIATA DEL CUADRO MAESTRO (Prioridad Global)
        # ============================================================
        from PyQt5.QtWidgets import QMessageBox
        import json

        # --- VALIDACIÓN DE CAMBIOS (Ctrl+Shift+S) ---
        if self.checking_changes:
            has_changes = False
            try:
                # Comparamos solo si tenemos caché previo y es un diccionario/lista válido
                old_data = self._sheets_cache.get('todas_infoplazas')
                new_data = data.get('todas_infoplazas')
                
                if old_data and new_data:
                    # Serializamos para comparar contenido profundo de manera estable
                    js_old = json.dumps(old_data, sort_keys=True, default=str)
                    js_new = json.dumps(new_data, sort_keys=True, default=str)
                    has_changes = (js_old != js_new)
                else:
                    has_changes = True # Primera carga o datos vacíos cuentan como cambio
            except Exception as e:
                print(f"[METAS] Error comparando cambios: {e}")
                has_changes = True # Asumir cambios por defecto en error
            
            self.checking_changes = False # Reset flag
            
            msg = "✅ Se actualizaron los datos con cambios detectados." if has_changes else "👌 Todo está actualizado. No hubo cambios."
            
            # Usar QTimer para mostrar el mensaje después de que la UI se actualice
            from PyQt5.QtCore import QTimer
            from PyQt5.QtGui import QIcon, QPixmap

            def show_custom_message():
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Sincronización de Metas")
                
                # Texto grande usando HTML
                msg_box.setText(f"<h3 style='font-size: 14pt; font-weight: bold;'>{msg}</h3>")
                msg_box.setTextFormat(Qt.RichText)
                
                # Ícono personalizado más grande (64x64)
                icon_std = msg_box.style().standardIcon(QStyle.SP_MessageBoxInformation)
                pixmap = icon_std.pixmap(QSize(64, 64)) 
                msg_box.setIconPixmap(pixmap)
                
                msg_box.exec_()

            QTimer.singleShot(500, show_custom_message)

        # Actualizamos el cuadro general ANTES de cualquier validación individual
        if hasattr(self.main_app, 'tab_cuadro_metas') and 'todas_infoplazas' in data:
            update_info = {
                'fecha': data.get('fecha_actualizacion'),
                'hora': data.get('hora_actualizacion')
            }
            self.main_app.tab_cuadro_metas.set_data(data['todas_infoplazas'], data.get('metas', {}), update_info)
            
            # Guardamos también en caché los datos globales
            self._sheets_cache['todas_infoplazas'] = data['todas_infoplazas']
            self._sheets_cache['metas_totales'] = data.get('metas', {})
            # NUEVO: Guardar actividades_config en caché
            self._sheets_cache['actividades_config'] = data.get('actividades_config')
            if 'fecha_actualizacion' in data:
                self._sheets_cache['ultima_actualizacion'] = {
                    'fecha': data['fecha_actualizacion'],
                    'hora': data['hora_actualizacion']
                }

        infoplaza_data = data.get('infoplaza')

        # ============================================================
        # 2. VALIDACIÓN (Solo si hay intento de cargar datos individuales)
        # ============================================================
        # Si NO hay datos de infoplaza (ej. usuario inválido), saltamos la validación estricta
        if infoplaza_data:
            es_valido, errores = self.validator.validar_datos_completos(data)
            
            if not es_valido:
                mensaje_error = "❌ Datos inválidos descargados de Google Sheets:\n\n"
                mensaje_error += "\n".join(f"• {error}" for error in errores[:5])
                if len(errores) > 5:
                    mensaje_error += f"\n... y {len(errores) - 5} errores más"
                self.show_error_message(mensaje_error)
                return
        
        # ============================================================
        # 3. CREAR CALCULADOR (Con datos o vacío)
        # ============================================================
        # Si no hay datos específicos, usamos dict vacío para evitar errores en calculator
        self.calculator = MetasCalculator(
            infoplaza_data if infoplaza_data else {},
            data.get('metas', {})
        )
        
        # Si no hay infoplaza, mostramos mensaje elegante
        if not infoplaza_data:
            if self.infoplaza_id:
                # Caso A: Tenemos un ID (formato correcto) pero no está en el Excel
                self.show_elegant_not_found_message(self.infoplaza_id)
            else:
                # Caso B: No se pudo identificar ID alguno
                self.show_elegant_info_message()
            return # Terminamos aquí success

        # Validar consistencia de los datos (Solo si hay datos)
        if infoplaza_data:
            es_consistente, advertencias = self.calculator.validar_consistencia()
            if advertencias:
                print("[ADVERTENCIA] Inconsistencias en los datos:")
                for adv in advertencias:
                    print(f"  - {adv}")
        
        # DEBUG CRÍTICO: Verificar qué estamos asignando a current_data
        print(f"[ON_DATA_LOADED] DEBUG ANTES DE ASIGNAR: 'actividades_config' in data: {'actividades_config' in data}")
        self.current_data = data
        print(f"[ON_DATA_LOADED] DEBUG DESPUÉS DE ASIGNAR: 'actividades_config' in current_data: {'actividades_config' in self.current_data}")
        self.build_card()
    
    def clear_card(self):
        """Limpia todos los widgets de la tarjeta de forma recursiva"""
        if self.card_layout:
            self.clear_layout_recursive(self.card_layout)
            
    def clear_layout_recursive(self, layout):
        """Limpia un layout recursivamente"""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout():
                self.clear_layout_recursive(item.layout())
    
    def show_error_message(self, error):
        """Muestra mensaje de error"""
        self.clear_card()
        
        label = QLabel(f"❌ Error al cargar datos:\n\n{error}")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setProperty("class", "h2")
        # Podemos añadir un estilo específico para error si queremos, pero h2 sirve de base
        # Usar clase QSS para errores
        label.setProperty("class", "ErrorLabel")

        self.card_layout.addWidget(label)
    
    def show_elegant_info_message(self):
        """Muestra un mensaje informativo elegante cuando no se puede identificar la Infoplaza"""
        self.showing_info_message = True  # Marcar que estamos mostrando este mensaje
        self.clear_card()
        
        # Obtener el username actual (puede ser el inválido guardado o el actual)
        display_username = self.invalid_username
        if not display_username and hasattr(self.main_app, 'current_username'):
            display_username = self.main_app.current_username
        if not display_username:
            display_username = "Desconocido"
        
        # Contenedor principal con padding
        container = QFrame()
        container.setObjectName("InfoMessageContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(60, 40, 60, 40)
        container_layout.setSpacing(25)
        
        # Título principal con icono amigable - MÁS GRANDE
        title_label = QLabel("🔍 Configuración de Usuario Necesaria")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont("Segoe UI", 24, QFont.DemiBold)  # Aumentado de 20 a 24
        title_label.setFont(title_font)
        title_label.setProperty("class", "InfoTitle")
        container_layout.addWidget(title_label)
        
        # Subtítulo explicativo - MÁS GRANDE
        subtitle = QLabel("No pudimos identificar tu Infoplaza con el usuario actual")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 14))  # Aumentado de 12 a 14
        subtitle.setWordWrap(True)
        subtitle.setProperty("class", "InfoSubtitle")
        container_layout.addWidget(subtitle)
        
        # NUEVO: Mostrar el usuario erróneo de forma destacada
        username_card = QFrame()
        username_card.setObjectName("UsernameErrorCard")
        username_card_layout = QVBoxLayout(username_card)
        username_card_layout.setContentsMargins(20, 15, 20, 15)
        username_card_layout.setSpacing(5)
        
        username_label_title = QLabel("⚠️ Usuario detectado:")
        username_label_title.setAlignment(Qt.AlignCenter)
        username_label_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        username_label_title.setProperty("class", "UsernameErrorTitle")
        username_card_layout.addWidget(username_label_title)
        
        username_label_value = QLabel(f"<b style='font-size: 16px;'>{display_username}</b>")
        username_label_value.setAlignment(Qt.AlignCenter)
        username_label_value.setFont(QFont("Segoe UI", 14))
        username_label_value.setProperty("class", "UsernameErrorValue")
        username_label_value.setWordWrap(True)
        username_card_layout.addWidget(username_label_value)
        
        container_layout.addWidget(username_card)
        
        # Espaciador
        container_layout.addSpacing(10)
        
        # Sección: ¿Qué significa esto?
        explanation_card = QFrame()
        explanation_card.setObjectName("ExplanationCard")
        explanation_layout = QVBoxLayout(explanation_card)
        explanation_layout.setContentsMargins(25, 20, 25, 20)
        explanation_layout.setSpacing(12)
        
        explanation_title = QLabel("💡 ¿Qué significa esto?")
        explanation_title.setFont(QFont("Segoe UI", 15, QFont.Bold))  # Aumentado de 13 a 15
        explanation_title.setProperty("class", "SectionTitle")
        explanation_layout.addWidget(explanation_title)
        
        explanation_text = QLabel(
            "Tu nombre de usuario debe comenzar con el <b>número de tu Infoplaza</b> "
            "seguido de <b>@infoplazas.org.pa</b><br><br>"
            "<span style='font-size: 15px;'>📋 Ejemplo: Si tu Infoplaza es la <b>#123</b>, "  # Aumentado a 15px
            "el usuario correcto es:<br><b style='color: #3498db; font-size: 16px;'>123@infoplazas.org.pa</b></span>"  # Más grande y en nueva línea
        )
        explanation_text.setWordWrap(True)
        explanation_text.setFont(QFont("Segoe UI", 13))  # Aumentado de 11 a 13
        explanation_text.setProperty("class", "InfoText")
        explanation_layout.addWidget(explanation_text)
        
        container_layout.addWidget(explanation_card)
        
        # Sección: ¿Qué debes hacer?
        action_card = QFrame()
        action_card.setObjectName("ActionCard")
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(25, 20, 25, 20)
        action_layout.setSpacing(12)
        
        action_title = QLabel("✅ ¿Qué debes hacer?")
        action_title.setFont(QFont("Segoe UI", 15, QFont.Bold))  # Aumentado de 13 a 15
        action_title.setProperty("class", "SectionTitle")
        action_layout.addWidget(action_title)
        
        # Detectar tema para el color del HTML
        is_dark = self.main_app.is_dark_mode if hasattr(self.main_app, 'is_dark_mode') else False
        html_color = "#ffffff" if is_dark else "#34495e"
        
        steps_text = QLabel(
            f"<ol style='margin: 0; padding-left: 20px; line-height: 1.8; color: {html_color};'>"
            "<li>Toma una captura de esta pantalla</li>"
            "<li>Contacta a tu <b>Facilitador</b> o <b>Enlace Regional</b></li>"
            "<li>Solicita que verifiquen tu usuario en el sistema <b>Cyber Cafe (OneRoof)</b></li>"
            "</ol>"
        )
        steps_text.setWordWrap(True)
        steps_text.setFont(QFont("Segoe UI", 13))  # Aumentado de 11 a 13
        steps_text.setProperty("class", "InfoText")
        action_layout.addWidget(steps_text)
        
        container_layout.addWidget(action_card)
        
        # Mensaje final tranquilizador - MÁS GRANDE
        footer_label = QLabel("Mientras tanto, puedes seguir usando las demás funciones de ADA ✨")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setFont(QFont("Segoe UI", 13, QFont.StyleItalic))  # Aumentado de 11 a 13
        footer_label.setProperty("class", "InfoFooter")
        footer_label.setWordWrap(True)
        container_layout.addWidget(footer_label)
        
        container_layout.addStretch()
        
        # Estilos adaptables al tema - MEJORADO PARA MODO OSCURO
        container.setStyleSheet("""
            QFrame#InfoMessageContainer {
                background: transparent;
            }
            
            QFrame#ExplanationCard, QFrame#ActionCard {
                background-color: rgba(52, 152, 219, 0.08);
                border: 1px solid rgba(52, 152, 219, 0.2);
                border-radius: 12px;
            }
            
            QFrame#UsernameErrorCard {
                background-color: rgba(231, 76, 60, 0.08);
                border: 2px solid rgba(231, 76, 60, 0.3);
                border-radius: 12px;
            }
            
            QLabel.UsernameErrorTitle {
                color: #c0392b;
            }
            
            QLabel.UsernameErrorValue {
                color: #e74c3c;
            }
            
            QLabel.InfoTitle {
                color: #3498db;
            }
            
            QLabel.InfoSubtitle {
                color: #7f8c8d;
            }
            
            QLabel.SectionTitle {
                color: #2c3e50;
            }
            
            QLabel.InfoText {
                color: #34495e;
            }
            
            QLabel.InfoFooter {
                color: #95a5a6;
            }
            
            /* Modo Oscuro - MEJORADO CON MEJOR CONTRASTE */
            QFrame#ExplanationCard[theme="dark"], QFrame#ActionCard[theme="dark"] {
                background-color: rgba(52, 152, 219, 0.15);
                border: 1px solid rgba(52, 152, 219, 0.4);
            }
            
            QLabel.InfoTitle[theme="dark"] {
                color: #5dade2;
            }
            
            QLabel.SectionTitle[theme="dark"] {
                color: #f8f9fa;  /* Casi blanco para excelente contraste */
            }
            
            QLabel.InfoText[theme="dark"] {
                color: #ffffff;  /* Blanco puro para máxima legibilidad en modo oscuro */
            }
            
            QLabel.InfoSubtitle[theme="dark"] {
                color: #c5cdd4;  /* Más claro que antes */
            }
            
            QLabel.InfoFooter[theme="dark"] {
                color: #95a5a6;
            }
            
            QFrame#UsernameErrorCard[theme="dark"] {
                background-color: rgba(231, 76, 60, 0.15);
                border: 2px solid rgba(231, 76, 60, 0.5);
            }
            
            QLabel.UsernameErrorTitle[theme="dark"] {
                color: #ec7063;
            }
            
            QLabel.UsernameErrorValue[theme="dark"] {
                color: #f1948a;
            }
        """)
        
        self.card_layout.addWidget(container)

    def show_elegant_not_found_message(self, infoplaza_id):
        """Muestra un mensaje elegante cuando el ID es correcto pero no está en la BD de Google Sheets"""
        self.showing_info_message = True
        self.clear_card()
        
        # Contenedor principal
        container = QFrame()
        container.setObjectName("InfoMessageContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(60, 40, 60, 40)
        container_layout.setSpacing(25)
        
        # Título principal
        title_label = QLabel("📋 Infoplaza no encontrada en el Sistema de Metas")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Segoe UI", 22, QFont.DemiBold))
        title_label.setProperty("class", "InfoTitle")
        container_layout.addWidget(title_label)
        
        # Subtítulo
        subtitle = QLabel("No se hallaron registros para la Infoplaza indicada")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 14))
        subtitle.setProperty("class", "InfoSubtitle")
        container_layout.addWidget(subtitle)
        
        # Card del ID detectado (Usamos el estilo de error para destacar)
        id_card = QFrame()
        id_card.setObjectName("UsernameErrorCard")
        id_layout = QVBoxLayout(id_card)
        id_layout.setContentsMargins(20, 15, 20, 15)
        
        id_title = QLabel("📍 Número de Infoplaza detectada:")
        id_title.setAlignment(Qt.AlignCenter)
        id_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        id_title.setProperty("class", "UsernameErrorTitle")
        id_layout.addWidget(id_title)
        
        id_value = QLabel(f"<b style='font-size: 20px;'>#{infoplaza_id}</b>")
        id_value.setAlignment(Qt.AlignCenter)
        id_value.setProperty("class", "UsernameErrorValue")
        id_layout.addWidget(id_value)
        
        container_layout.addWidget(id_card)
        
        # Sección: ¿Qué significa esto?
        explanation_card = QFrame()
        explanation_card.setObjectName("ExplanationCard")
        explanation_layout = QVBoxLayout(explanation_card)
        explanation_layout.setContentsMargins(25, 20, 25, 20)
        explanation_layout.setSpacing(10)
        
        explanation_title = QLabel("💡 ¿Qué significa esto?")
        explanation_title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        explanation_title.setProperty("class", "SectionTitle")
        explanation_layout.addWidget(explanation_title)
        
        explanation_text = QLabel(
            "Esta Infoplaza aún no aparece en la base de datos del Sistema de Metas. "
            "Es posible que no hayas subido las metas mensuales para esta Infoplaza, "
            "o no hayan sido cargados todavía."
        )
        explanation_text.setWordWrap(True)
        explanation_text.setFont(QFont("Segoe UI", 13))
        explanation_text.setProperty("class", "InfoText")
        explanation_layout.addWidget(explanation_text)
        
        container_layout.addWidget(explanation_card)
        
        # Sección: ¿Qué debes hacer?
        action_card = QFrame()
        action_card.setObjectName("ActionCard")
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(25, 20, 25, 20)
        action_layout.setSpacing(12)
        
        action_title = QLabel("✅ ¿Qué debes hacer?")
        action_title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        action_title.setProperty("class", "SectionTitle")
        action_layout.addWidget(action_title)
        
        # Detectar tema para el color del HTML
        is_dark = self.main_app.is_dark_mode if hasattr(self.main_app, 'is_dark_mode') else False
        html_color = "#ffffff" if is_dark else "#34495e"
        
        steps_text = QLabel(
            f"<ul style='margin: 0; padding-left: 20px; line-height: 1.6; color: {html_color};'>"
            "<li>Contacta a tu <b>Facilitador Regional</b>.</li>"
            "<li>Si ya subiste tu formulario de metas, espera hasta que se haga una nueva actualización.</li>"
            "<li>Una vez registrada, los datos se verán aquí automáticamente al actualizar.</li>"
            "<li>Puedes seguir usando todas las funciones de ADA. ✨</li>"
            "</ul>"
        )
        steps_text.setWordWrap(True)
        steps_text.setFont(QFont("Segoe UI", 13))
        steps_text.setProperty("class", "InfoText")
        action_layout.addWidget(steps_text)
        
        container_layout.addWidget(action_card)
        
        # Mensaje final
        footer_label = QLabel("Puedes seguir usando todas las funciones de ADA. ✨")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setFont(QFont("Segoe UI", 13, QFont.StyleItalic))
        footer_label.setProperty("class", "InfoFooter")
        container_layout.addWidget(footer_label)
        
        container_layout.addStretch()
        
        # Configurar tema (claro/oscuro)
        is_dark = self.main_app.is_dark_mode if hasattr(self.main_app, 'is_dark_mode') else False
        theme_val = "dark" if is_dark else "light"
        
        for w in [container, title_label, subtitle, id_card, id_title, id_value, 
                   explanation_card, explanation_title, explanation_text,
                   action_card, action_title, steps_text, footer_label]:
            w.setProperty("theme", theme_val)
            
        # Reusamos el mismo CSS que show_elegant_info_message para consistencia
        container.setStyleSheet("""
            QFrame#InfoMessageContainer { background: transparent; }
            QFrame#ExplanationCard, QFrame#ActionCard {
                background-color: rgba(52, 152, 219, 0.08);
                border: 1px solid rgba(52, 152, 219, 0.2);
                border-radius: 12px;
            }
            QFrame#UsernameErrorCard {
                background-color: rgba(231, 76, 60, 0.08);
                border: 2px solid rgba(231, 76, 60, 0.3);
                border-radius: 12px;
            }
            QLabel.UsernameErrorTitle { color: #c0392b; }
            QLabel.UsernameErrorValue { color: #e74c3c; }
            QLabel.InfoTitle { color: #3498db; }
            QLabel.InfoSubtitle { color: #7f8c8d; }
            QLabel.SectionTitle { color: #2c3e50; }
            QLabel.InfoText { color: #34495e; }
            QLabel.InfoFooter { color: #95a5a6; }
            
            /* Modo Oscuro */
            QFrame#ExplanationCard[theme="dark"], QFrame#ActionCard[theme="dark"] {
                background-color: rgba(52, 152, 219, 0.15); border: 1px solid rgba(52, 152, 219, 0.4);
            }
            QLabel.InfoTitle[theme="dark"] { color: #5dade2; }
            QLabel.SectionTitle[theme="dark"] { color: #f8f9fa; }
            QLabel.InfoText[theme="dark"] { color: #ffffff; }
            QLabel.InfoSubtitle[theme="dark"] { color: #c5cdd4; }
            QLabel.InfoFooter[theme="dark"] { color: #95a5a6; }
            QFrame#UsernameErrorCard[theme="dark"] {
                background-color: rgba(231, 76, 60, 0.15); border: 2px solid rgba(231, 76, 60, 0.5);
            }
            QLabel.UsernameErrorTitle[theme="dark"] { color: #ec7063; }
            QLabel.UsernameErrorValue[theme="dark"] { color: #f1948a; }
        """)
        
        self.card_layout.addWidget(container)
    
    def build_card(self):
        """Construye la tarjeta completa con los datos cargados"""
        self.showing_info_message = False  # Resetear el flag
        self.clear_card()
        
        # Crear la tarjeta principal (full width)
        card = QFrame()
        card.setProperty("class", "Card")
        # Ya no necesitamos styleSheet manual para bg/border
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        
        # 1. ENCABEZADO
        header = self.create_header()
        card_layout.addWidget(header)
        
        # 2. TIMELINE UNIFICADO (meses + info actual)
        timeline_unificado = self.create_timeline_unificado()
        card_layout.addWidget(timeline_unificado)
        
        # 4. PROGRESO POR ACTIVIDAD
        actividades = self.create_actividades_section()
        card_layout.addWidget(actividades)
        
        # Agregar la tarjeta al layout principal (full width)
        self.card_layout.addWidget(card)
        self.card_layout.addStretch()
    

    # Sección de enlaces eliminada (movida al sidebar)

    def create_header(self):
        """Crea el encabezado compacto con información de la Infoplaza"""
        from datetime import datetime
        
        header = QFrame()
        header.setProperty("class", "Header")

        
        main_layout = QHBoxLayout(header)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        
        # === ZONA IZQUIERDA: Información de Infoplaza ===
        left_layout = QVBoxLayout()
        left_layout.setSpacing(2)  # Mas compacto
        
        infoplaza_data = self.current_data.get('infoplaza', {})
        infoplaza_id = infoplaza_data.get('# Info', 'N/A')
        nombre = infoplaza_data.get('Nombre de la Infoplaza', 'Metas Infoplazas AIP')
        regional = infoplaza_data.get('Regional', '')
        provincia = infoplaza_data.get('Provincia / Comarca', '')
        
        # === DISEÑO PREMIUM: ID Dual-Tone | Tipografía Refinada ===
        header_info_layout = QHBoxLayout()
        header_info_layout.setSpacing(12)
        header_info_layout.setContentsMargins(0, 2, 0, 5)
        
        # 1. ID GIGANTE CON ESTILO DUAL-TONE
        # Usamos labels separados para permitir stilo via QSS
        id_container = QWidget()
        id_layout = QHBoxLayout(id_container)
        id_layout.setContentsMargins(0,0,0,0)
        id_layout.setSpacing(0)
        
        lbl_hash = QLabel("#")
        lbl_hash.setProperty("class", "IdSymbol")  # Estilos en QSS
        
        lbl_val = QLabel(f"{infoplaza_id}")
        lbl_val.setProperty("class", "IdValue")  # Estilos en QSS
        
        id_layout.addWidget(lbl_hash, 0, Qt.AlignBottom)
        id_layout.addWidget(lbl_val, 0, Qt.AlignBottom)
        
        header_info_layout.addWidget(id_container)
        
        # 2. LÍNEA DIVISORIA SUTIL
        linea_div = QFrame()
        linea_div.setFrameShape(QFrame.VLine)
        linea_div.setProperty("class", "Divider")
        linea_div.setFixedWidth(2)
        header_info_layout.addWidget(linea_div)
        
        # 3. CONTENEDOR VERTICAL (Nombre + Subtítulo)
        info_vertical = QVBoxLayout()
        info_vertical.setSpacing(2) # Muy pegaditos para formar bloque
        info_vertical.setContentsMargins(0, 0, 0, 0)
        info_vertical.setAlignment(Qt.AlignVCenter)
        
        # Nombre de la Infoplaza
        lbl_nombre = QLabel(nombre)
        lbl_nombre.setProperty("class", "h1")  # Estilos en QSS
        info_vertical.addWidget(lbl_nombre)
        
        # Subtítulo: Regional y Provincia (Sofisticado)
        subtitulo_parts = []
        if regional:
            reg_clean = regional.replace("Regional:", "").strip()
            # Usamos un color suavizado para la etiqueta y uno sutilmente más oscuro para el valor si quisiéramos, 
            # pero todo en gris medio con tracking alto se ve muy Pro.
            subtitulo_parts.append(f"REGIONAL {reg_clean.upper()}")
        if provincia:
            prov_clean = provincia.replace("Provincia:", "").strip()
            subtitulo_parts.append(f"PROVINCIA {prov_clean.upper()}")
        
        if subtitulo_parts:
            # Separador estilizado
            subtitulo_text = "  |  ".join(subtitulo_parts)
            lbl_subtitulo = QLabel(subtitulo_text)
            lbl_subtitulo.setProperty("class", "subtitle")  # Estilos en QSS
            info_vertical.addWidget(lbl_subtitulo)
        
        header_info_layout.addLayout(info_vertical)
        header_info_layout.addStretch()
        
        # Agregar al layout principal de la zona izquierda
        left_layout.addLayout(header_info_layout)
        
        # ITEMS DE PERÍODO (horizontal)
        periodo_layout = QHBoxLayout()
        periodo_layout.setSpacing(8)  # Spacing horizontal entre items
        periodo_layout.setContentsMargins(0, 2, 0, 0)  # Margin superior reducido
        
        # Item 1: Período (Dinámico)
        from metas_config import get_fechas_periodo # Import local just in case or rely on top level
        f_inicio, f_fin = get_fechas_periodo()
        # Formato "Nov 2025 - Ago 2026"
        mes_ini = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"][f_inicio.month]
        mes_fin = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"][f_fin.month]
        texto_periodo = f"{mes_ini} {f_inicio.year} - {mes_fin} {f_fin.year}"
        
        periodo_widget = self._create_periodo_item("Período", texto_periodo)
        periodo_layout.addWidget(periodo_widget)
        
        # Item 2: Mes Actual  
        from metas_config import get_mes_actual
        mes_num, mes_nombre = get_mes_actual()
        # Calcular número de mes en el período (Dinámico)
        mes_en_periodo = MESES_PERIODO.index(mes_nombre) + 1 if mes_nombre in MESES_PERIODO else 1
        
        mes_actual_text = f"{mes_nombre} ({mes_en_periodo}/{len(MESES_PERIODO)})"
        mes_widget = self._create_periodo_item("Mes Actual", mes_actual_text)
        periodo_layout.addWidget(mes_widget)
        
        # Item 3: Actualizado al (desde Google Sheets - hoja config, celdas E1 y F1)
        try:
            # Leer fecha y hora desde current_data
            if hasattr(self, 'current_data') and self.current_data:
                fecha_raw = self.current_data.get('fecha_actualizacion', '')
                hora_raw = self.current_data.get('hora_actualizacion', '')
                
                if fecha_raw and hora_raw and fecha_raw != "N/A" and hora_raw != "N/A":
                    # Combinar fecha y hora
                    fecha_texto = f"{fecha_raw} {hora_raw}"
                else:
                    # Fallback si no hay datos válidos
                    fecha_texto = datetime.now().strftime("%d %b %Y %H:%M")
            else:
                # Fallback si no hay datos cargados
                fecha_texto = datetime.now().strftime("%d %b %Y %H:%M")
        except Exception as e:
            # En caso de error, usar fecha actual
            fecha_texto = datetime.now().strftime("%d %b %Y %H:%M")
        
        fecha_widget = self._create_periodo_item("Actualizado al", fecha_texto)
        periodo_layout.addWidget(fecha_widget)
        
        periodo_layout.addStretch()
        left_layout.addLayout(periodo_layout)
        
        main_layout.addLayout(left_layout, stretch=7)  # 7/8 del espacio
        
        # === ZONA DERECHA: Avance Global ===
        avance_widget = QFrame()
        
        # Calcular progreso global y su estado dinámico (Regla 8/5 por mes)
        estado_global = {
            'progreso': 0.0,
            'color': '#ff1744', # Rojo por defecto
            'bg': '#ffebee',
            'border': '#e83e8c'
        }
        
        if self.calculator:
            estado_global = self.calculator.calcular_estado_global()
            
        color_bg = estado_global['color']
        text_color = "#2c3e50" if color_bg == '#ffc107' else "white"
            
        avance_widget.setStyleSheet(f"""
            QFrame {{
                background: {color_bg};
                border-radius: 8px;
                padding: 8px 15px;
            }}
        """)
        avance_widget.setFixedWidth(300)
        
        avance_layout = QVBoxLayout(avance_widget)
        avance_layout.setContentsMargins(0, 0, 0, 0)
        avance_layout.setSpacing(4)
        
        progreso_global = estado_global['progreso']
        lbl_porcentaje = QLabel(f"{progreso_global:.1f}%")
        lbl_porcentaje.setAlignment(Qt.AlignCenter)
        lbl_porcentaje.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-size: 56px;
                font-weight: 700;
                line-height: 1;
                background: transparent;
                border: none;
            }}
        """)
        avance_layout.addWidget(lbl_porcentaje)
        
        # Label "Avance Global" (DEBAJO)
        lbl_avance_label = QLabel("AVANCE GLOBAL")
        lbl_avance_label.setAlignment(Qt.AlignCenter)
        lbl_avance_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.3px;
                background: transparent;
                border: none;
                opacity: 0.9;
            }
        """)
        avance_layout.addWidget(lbl_avance_label)
        
        main_layout.addWidget(avance_widget)  # Ancho fijo de 220px
        
        return header
    
    def _create_periodo_item(self, label_text, value_text):
        """Crea un item del período (método auxiliar)"""
        widget = QFrame()
    def _create_periodo_item(self, label_text, value_text):
        """Crea un item del período (método auxiliar)"""
        widget = QFrame()
        widget.setProperty("class", "TimelineItem")
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)  # Spacing muy compacto entre label y valor
        
        # Label
        lbl_label = QLabel(label_text.upper())
        lbl_label.setAlignment(Qt.AlignLeft)
        lbl_label.setProperty("class", "subtitle")
        layout.addWidget(lbl_label)
        
        # Value
        lbl_value = QLabel(value_text)
        lbl_value.setAlignment(Qt.AlignLeft)
        lbl_value.setProperty("class", "body")  # Estilos en QSS
        layout.addWidget(lbl_value)
        
        return widget


    def create_timeline_unificado(self):
        """Timeline compacto y minimalista"""
    def create_timeline_unificado(self):
        """Timeline compacto y minimalista"""
        widget = QFrame()
        widget.setProperty("class", "Card")
        # Removing manual stylesheet
        
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)
        
        # Título compacto
        timeline_layout = QHBoxLayout()
        timeline_layout.setSpacing(6)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        
        meses = MESES_PERIODO
        mes_actual_num, _ = get_mes_actual()
        infoplaza_data = self.current_data.get('infoplaza', {})
        
        for i, mes in enumerate(meses, 1):
            mes_widget = self.create_mes_box_compact(mes, mes_actual_num, i, infoplaza_data)
            timeline_layout.addWidget(mes_widget)
        
        main_layout.addLayout(timeline_layout)
        
        return widget
    
    def create_mes_box_compact(self, mes_nombre, mes_actual, mes_num, infoplaza_data):
            """
            Versión COMPACTA del item de línea de tiempo.
            - Menor altura vertical mediante márgenes ajustados.
            - Fuerza bordes visibles en modo claro y oscuro.
            - Mantiene la integración con QSS para fondos.
            """
            # 1. Contenedor Principal
            container = QFrame()
            container.setProperty("class", "TimelineItem")
            # Ancho mínimo ligeramente reducido para el look compacto
            container.setMinimumWidth(60) 

            # --- CORRECCIÓN DE BORDES ---
            # Detectamos el modo y forzamos el color del borde para asegurar visibilidad
            # en modo claro, sobrescribiendo el 'border: none' del QSS si existe.
            is_dark = self.main_app.is_dark_mode if self.main_app else False
            border_color = "#334155" if is_dark else "#e2e8f0" # Slate 700 (Dark) vs Slate 200 (Light)
            container.setStyleSheet(f"border: 1px solid {border_color};")

            # Layout interno COMPACTO
            layout = QVBoxLayout(container)
            # Márgenes drásticamente reducidos para menor altura (Top/Bottom: 6px)
            layout.setContentsMargins(6, 6, 6, 6)
            # Espaciado entre elementos reducido (2px)
            layout.setSpacing(2)
            layout.setAlignment(Qt.AlignCenter)

            # --- Lógica de Estados y Colores (Igual, pero ajustando tamaños de fuente) ---
            # Estado por defecto (Futuro)
            simbolo = "•"
            status_color = is_dark and "#64748b" or "#94a3b8"
            accent_color = None
            font_weight_icon = QFont.Normal
            # Tamaño base del icono reducido ligeramente
            font_size_icon = 20 

            if self.calculator:
                estado_mes = self.calculator.obtener_estado_mes(mes_nombre)

                if estado_mes['subio_reporte']:
                    # Completado
                    simbolo = "✓"
                    status_color = "#10b981"
                    accent_color = "#10b981"
                    font_weight_icon = QFont.Bold
                    font_size_icon = 24 # Reducido de 22
                elif mes_num < mes_actual:
                    # Vencido
                    simbolo = "✕"
                    status_color = "#ef4444"
                    accent_color = "#ef4444"
                    font_weight_icon = QFont.Bold
                    font_size_icon = 20 # Reducido de 20
                elif mes_num == mes_actual:
                    # Actual
                    simbolo = "◴"
                    status_color = "#f59e0b"
                    accent_color = "#f59e0b"
                    font_weight_icon = QFont.Bold
                    font_size_icon = 24 # Reducido de 22

            # 2. Icono de Estado Principal
            lbl_icon = QLabel(simbolo)
            lbl_icon.setAlignment(Qt.AlignCenter)
            font_icon = QFont("Segoe UI Symbol", font_size_icon, font_weight_icon)
            lbl_icon.setFont(font_icon)
            # Eliminado margen inferior extra
            lbl_icon.setStyleSheet(f"color: {status_color}; border: none; background: transparent; margin: 0;")
            layout.addWidget(lbl_icon)

            # 3. Etiqueta del Mes
            from metas_config import get_year_for_month
            year = get_year_for_month(mes_num)
            year_short = str(year)[-2:] # '25'
            mes_abrev = f"{mes_nombre[:3].upper()} '{year_short}"
            lbl_mes = QLabel(mes_abrev)
            lbl_mes.setProperty("class", "subtitle")
            lbl_mes.setAlignment(Qt.AlignCenter)
            # Fuente ligeramente más pequeña (10px) para el look compacto
            lbl_mes.setStyleSheet("font-weight: 700; letter-spacing: 1px; font-size: 14px; border: none; background: transparent;")
            layout.addWidget(lbl_mes)

            # 4. Barra de Acento Inferior (Más delgada y pegada)
            if accent_color:
                # Espacio reducido antes de la barra (3px)
                layout.addSpacing(3)
                accent_bar = QFrame()
                # Altura de barra reducida (2px)
                accent_bar.setFixedHeight(2)
                accent_bar.setStyleSheet(f"background-color: {accent_color}; border-radius: 1px; border: none;")
                layout.addWidget(accent_bar)
            else:
                # Espaciador invisible ajustado a la nueva altura
                layout.addSpacing(5)

            return container


    def create_actividades_section(self):
        """Crea la sección de actividades en Grid Responsivo (Full Width)"""
        # Contenedor principal
        widget = QWidget()
        
        # Usar QGridLayout para asegurar que ocupe todo el ancho con columnas iguales
        layout = QGridLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)  # Compacto
        
        # Configurar 5 columnas para que se estiren igual
        # NOTA: Para volver a 4 columnas, cambiar MAX_COLS=5 a MAX_COLS=4 y eliminar la línea con (4, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(3, 1)
        layout.setColumnStretch(4, 1)
        
        # NUEVO: Determinar origen de actividades (dinámico vs. hardcoded)
        # DEBUG: Verificar qué datos tenemos disponibles
        print(f"[CARDS] DEBUG: current_data keys: {list(self.current_data.keys()) if self.current_data else 'None'}")
        if self.current_data:
            has_config = 'actividades_config' in self.current_data
            config_value = self.current_data.get('actividades_config')
            print(f"[CARDS] DEBUG: tiene 'actividades_config': {has_config}")
            if has_config:
                print(f"[CARDS] DEBUG: actividades_config es None: {config_value is None}")
                print(f"[CARDS] DEBUG: Cantidad de actividades en config: {len(config_value) if config_value else 0}")
        
        if self.current_data and self.current_data.get('actividades_config'):
            # Modo dinámico: usar configuración desde Google Sheets
            actividades = self.current_data['actividades_config']
            print(f"[CARDS] ✅ Usando actividades DINÁMICAS del Sheet ({len(actividades)} actividades)")
        else:
            # Modo legacy: usar lista hardcoded
            actividades_normales = obtener_actividades_normales()
            actividades_bonus = obtener_actividades_bonus()
            actividades = actividades_normales + actividades_bonus
            print(f"[CARDS] ⚠️ Usando actividades HARDCODED legacy ({len(actividades)} actividades)")
        
        # Procesar agrupaciones
        grupos = {}
        singles = []
        procesadas = set()  # Para modo legacy
        
        # MODO LEGACY: Agrupar RS-* manualmente
        if not (self.current_data and self.current_data.get('actividades_config')):
            rs_acts = [act for act in actividades if "RS-" in act.column_name]
            if len(rs_acts) >= 2:
                grupos["REDES_LEGACY"] = rs_acts
                for act in rs_acts:
                    procesadas.add(act.column_name)
        
        for act in sorted(actividades, key=lambda a: a.orden):
            # Skip si ya fue procesada en modo legacy
            if act.column_name in procesadas:
                continue
                
            if act.card_type == "grouped" and act.group_id:
                if act.group_id not in grupos:
                    grupos[act.group_id] = []
                grupos[act.group_id].append(act)
            else:
                singles.append(act)
        
        # Crear tarjetas CON ORDEN
        cards_with_order = []
        
        # Añadir tarjetas individuales con su orden
        for act in singles:
            if act.card_type == "special_mesas":
                card = self.create_card_mesas(act)
            elif act.card_type == "bonus":
                card = self.create_card_bonus(act)
            elif act.frequency == "event":
                card = self.create_card_event(act)
            elif act.frequency == "once":
                card = self.create_card_once(act)
            else:  # standard + monthly
                card = self.create_card_standard(act)
            cards_with_order.append((act.orden, card))
        
        # Añadir tarjetas agrupadas con el orden del primer elemento del grupo
        print(f"[CARDS] Grupos detectados: {list(grupos.keys())}")
        for group_id, group_acts in grupos.items():
            print(f"[CARDS] Creando tarjeta agrupada '{group_id}' con {len(group_acts)} actividades")
            # Usar orden del primer elemento del grupo
            orden_grupo = min(act.orden for act in group_acts)
            
            # Usar método legacy para redes sociales si está disponible
            if group_id == "REDES_LEGACY" and len(group_acts) == 2:
                act_pub = next((a for a in group_acts if "Publicar" in a.column_name), None)
                act_comp = next((a for a in group_acts if "Compartir" in a.column_name), None)
                if act_pub and act_comp:
                    card = self.create_card_redes(act_pub, act_comp)
                else:
                    card = self.create_card_grouped(group_acts)
            else:
                card = self.create_card_grouped(group_acts)
            cards_with_order.append((orden_grupo, card))
        
        # Ordenar todas las tarjetas por el campo orden
        cards_with_order.sort(key=lambda x: x[0])
        cards_to_add = [card for orden, card in cards_with_order]
        
        print(f"[CARDS] Total de tarjetas a mostrar: {len(cards_to_add)}")

        # 2. Agregar al Grid (5 columnas)
        # NOTA: Para volver a 4 columnas, cambiar MAX_COLS=5 a MAX_COLS=4
        row = 0
        col = 0
        MAX_COLS = 5
        
        for card in cards_to_add:
            layout.addWidget(card, row, col)
            col += 1
            if col >= MAX_COLS:
                col = 0
                row += 1

        return widget


    def create_card_base(self, titulo, icon_char="📋"):
        """Crea la estructura base de una tarjeta del dashboard"""
        card = QFrame()
        # Mínimo ancho 300, pero expandable
        card.setMinimumWidth(300)
        # Remove setFixedHeight - let CSS min-height handle it for flexibility
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        card.setProperty("class", "ActivityItem")
        # Inline stylesheet removed - handled by QSS .ActivityItem and .ActivityItem:hover
        
        l = QVBoxLayout(card)
        l.setContentsMargins(12, 12, 12, 12)  # Slightly more padding
        l.setSpacing(8)  # More breathing room
        
        # Header: Icono + Título
        lbl_tit = QLabel(f"{icon_char} {titulo}")
        lbl_tit.setProperty("class", "h2")
        lbl_tit.setWordWrap(True)
        l.addWidget(lbl_tit)
        
        # Espacio de separación entre título y gráfico
        l.addSpacing(12)
        
        return card, l

    def create_card_standard(self, actividad):
        """Tarjeta estándar con barra de progreso"""
        progreso = self.calculator.calcular_progreso_actividad(actividad) if self.calculator else {'completado':0, 'meta_total':1, 'porcentaje':0}
        
        # Icono según actividad (simple heurística por nombre)
        icono = "📋"
        if "Cert" in actividad.display_name: icono = "🎓"
        elif "Capacit" in actividad.display_name: icono = "💻"
        elif "Actividades" in actividad.display_name: icono = "🎪"
        
        card, layout = self.create_card_base(actividad.display_name, icono)
        
        # Lógica de sobrecumplimiento
        if progreso['porcentaje'] > 100:
            surplus_porcentaje = progreso['porcentaje'] - 100
            completado = float(progreso['completado'])
            meta = float(progreso['meta_total'])
            puntos_extra = int(completado - meta) if completado - meta > 0 else (completado - meta)
            
            tooltip_text = f"Superaste la meta por {puntos_extra} puntos, +{surplus_porcentaje:.1f}% sobre la meta."
        else:
            tooltip_text = f"Progreso: {progreso['porcentaje']:.1f}%"
            
        # Barra de progreso usando helper (colores dinámicos + CSS)
        bar = self._create_progress_bar(progreso)
        bar.setToolTip(tooltip_text)
        layout.addWidget(bar)
        
        # Etiquetas de rango y valor central (CONSOLIDADO EN UNA LÍNEA)
        range_layout = QHBoxLayout()
        range_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_0 = QLabel("0%")
        # Valor centrado ELIMINADO por redundancia
        lbl_100 = QLabel("100%")
        
        for lbl in [lbl_0, lbl_100]:
            lbl.setProperty("class", "subtitle")
            lbl.setAlignment(Qt.AlignCenter)
        
        range_layout.addWidget(lbl_0)
        range_layout.addStretch()
        range_layout.addWidget(lbl_100)
        layout.addLayout(range_layout)
        
        # Espacio flexible
        layout.addStretch()
        
        # Datos numéricos grandes
        completado = int(progreso['completado'])
        meta = int(progreso['meta_total'])
        unidad = "items"
        
        # Mapeo de unidades dinámicas según actividad
        if "Plataformas Virtuales" in actividad.display_name:
            unidad = "certificados"
        elif "Buenas Acciones" in actividad.display_name or "Internet" in actividad.display_name:
            unidad = "actividades"
        elif "Cert" in actividad.display_name: 
            unidad = "certificados"
        elif "Capacit" in actividad.display_name: 
            unidad = "capacitaciones"
        elif "Actividades" in actividad.display_name: 
            unidad = "actividades"
            
        # NUEVO: Usar clase CSS para valor principal CON COLOR DINÁMICO
        lbl_info = QLabel(f"{completado}/{meta} {unidad}")
        lbl_info.setProperty("class", "MetaMainValue")
        lbl_info.setAlignment(Qt.AlignCenter)
        
        # Aplicar color dinámico basado en el estado del calculator
        if self.calculator and 'estado' in progreso:
            # Mapear el estado del calculator a propiedad CSS
            status_map = {
                'excelente': 'success',      # Verde
                'bueno': 'warning',          # Amarillo
                'necesita_atencion': 'danger' # Rojo
            }
            css_status = status_map.get(progreso['estado'], 'danger')
            lbl_info.setProperty("status", css_status)
            # Forzar actualización del estilo
            lbl_info.style().unpolish(lbl_info)
            lbl_info.style().polish(lbl_info)
        
        layout.addWidget(lbl_info)
        
        # NUEVO: Usar clase CSS para texto secundario CON COLOR DINÁMICO
        if self.calculator:
            puntos, peso_max = self.calculator.calcular_puntos_ganados(actividad)
            texto_puntos = f"{puntos:.1f}% de {peso_max:.1f}% ganados"
            
            if progreso['porcentaje'] > 100:
                texto_puntos += " (🔥)"
                
            lbl_perc = QLabel(texto_puntos)
            if progreso['porcentaje'] > 100:
                lbl_perc.setToolTip(tooltip_text)
            
            # Aplicar mismo estado de color que el label principal
            if 'estado' in progreso:
                status_map = {
                    'excelente': 'success',
                    'bueno': 'warning',
                    'necesita_atencion': 'danger'
                }
                css_status = status_map.get(progreso['estado'], 'danger')
        lbl_perc.setProperty("class", "MetaSecondaryText")
        lbl_perc.setAlignment(Qt.AlignCenter)
        
        # Forzar actualización del estilo para que tome la clase y el estado
        lbl_perc.style().unpolish(lbl_perc)
        lbl_perc.style().polish(lbl_perc)
        
        layout.addWidget(lbl_perc)
        
        return card

    def create_card_redes(self, act_pub, act_comp):
        """Tarjeta combinada para Redes Sociales"""
        # colors = removed
        card, layout = self.create_card_base("Redes Sociales", "📱")
        
        if self.calculator:
            # Usar el método combinado del calculator
            redes_data = self.calculator.calcular_redes_sociales_combinadas()
            prog_pub = redes_data['publicaciones']
            prog_comp = redes_data['compartidas']
            porcentaje_global = redes_data['promedio']
        else:
            prog_pub = prog_comp = {'completado':0, 'meta_total':1, 'porcentaje':0}
            porcentaje_global = 0.0

        # Sub-función para cada barra interna
        def add_sub_bar(label, p_data, color):
            # Label pequeño: "Publicaciones:"
            l_tit = QLabel(label)
            l_tit.setFont(QFont("Segoe UI", 13))  # Aumentado más
            is_dark = self.main_app.is_dark_mode if self.main_app else False
            color_tit = "#BBBBBB" if is_dark else "#546e7a"
            l_tit.setStyleSheet(f"color: {color_tit}; border: none; background: transparent;")
            layout.addWidget(l_tit)
            
            # Barra
            bar = QProgressBar()
            bar.setRange(0, 100)
            # LIMITAR VALOR A 100
            bar.setValue(min(100, int(p_data['porcentaje'])))
            bar.setFixedHeight(8) # Un poco más delgada en redes para que quepan dos
            bar.setTextVisible(False)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #f5f5f5; border-radius: 4px; border: none;
                }}
                QProgressBar::chunk {{
                    background-color: {color}; border-radius: 4px;
                }}
            """)
            layout.addWidget(bar)
            
            # Etiquetas de rango y valor (CONSOLIDADO EN UNA LÍNEA)
            range_layout = QHBoxLayout()
            range_layout.setContentsMargins(0, 0, 0, 0)
            
            lbl_0 = QLabel("0%")
            # Valor centrado
            texto_val = f"{int(p_data['completado'])} / {int(p_data['meta_total'])}"
            if p_data['porcentaje'] > 100:
                texto_val += " 🔥"
            lbl_val = QLabel(texto_val)
            
            if p_data['porcentaje'] > 100:
                puntos_extra = int(p_data['completado']) - int(p_data['meta_total'])
                lbl_val.setToolTip(f"Superaste la meta por {puntos_extra} puntos.")
                
            lbl_100 = QLabel("100%")
            
            for lbl in [lbl_0, lbl_val, lbl_100]:
                size = 9 if lbl != lbl_val else 11
                is_dark = self.main_app.is_dark_mode if self.main_app else False
                color_l = ("#AAAAAA" if is_dark else "#90a4ae") if lbl != lbl_val else ("#EAEAEA" if is_dark else "#455a64")
                lbl.setStyleSheet(f"color: {color_l}; font-size: {size}px; font-weight: bold; border: none; background: transparent;")
            
            range_layout.addWidget(lbl_0)
            range_layout.addStretch()
            range_layout.addWidget(lbl_val)
            range_layout.addStretch()
            range_layout.addWidget(lbl_100)
            layout.addLayout(range_layout)

        add_sub_bar("Publicaciones:", prog_pub, "#2979ff") # Azul
        add_sub_bar("Compartidas:", prog_comp, "#29b6f6") # Celeste
        
        # AGREGAR PORCENTAJE TOTAL PESADO (NUEVO)
        if self.calculator:
            # Sumamos los puntos individuales para esta tarjeta combinada
            puntos_pub, peso_pub = self.calculator.calcular_puntos_ganados(act_pub)
            puntos_comp, peso_comp = self.calculator.calcular_puntos_ganados(act_comp)
            puntos_total = puntos_pub + puntos_comp
            peso_total = peso_pub + peso_comp
            lbl_total = QLabel(f"{puntos_total:.1f}% de {peso_total:.1f}% ganados")
            
            # Usar la lógica de color combinada (promedio de los dos para el color del bloque)
            cumpl_promedio = (prog_pub['porcentaje'] + prog_comp['porcentaje']) / 2
            # El calculator ya nos da el color correcto basado en el ritmo para cada una
            # Como es una tarjeta combinada, usamos el color de la que vaya peor para alertar
            color_total = prog_pub['color']['color'] if prog_pub['porcentaje'] < prog_comp['porcentaje'] else prog_comp['color']['color']
        else:
            lbl_total = QLabel(f"0.0% completado")
            color_total = "#ff1744"
            
        layout.addSpacing(8)
        lbl_total.setAlignment(Qt.AlignCenter)
        # Unificado: Usar clase CSS en lugar de estilos hardcoded
        lbl_total.setProperty("class", "MetaSecondaryText")
        
        # Aplicar estado de color basado en el peor de los dos (o promedio)
        if self.calculator:
            # Determinamos estado simplificado para las redes
            # Mapeamos color_total de vuelta a un estado de success/warning/danger
            if color_total == "#ff1744" or color_total == "#ef5350": status = "danger"
            elif color_total == "#ffb300" or color_total == "#ffc107": status = "warning"
            else: status = "success"
            lbl_total.setProperty("status", status)
            
        # Forzar actualización del estilo
        lbl_total.style().unpolish(lbl_total)
        lbl_total.style().polish(lbl_total)
            
        layout.addWidget(lbl_total)
        
        return card

    def create_card_mesas(self, actividad):
        """Tarjeta especial para Mesas de Transformación"""
    def create_card_mesas(self, actividad):
        """Tarjeta especial para Mesas de Transformación (Dinámica)"""
        # colors = removed
        card, layout = self.create_card_base(actividad.display_name, actividad.icon) # Usar icono de config
        
        # Obtener valor numérico de mesas (0, 1, 2, 3...)
        num_mesas = 0
        color_ms = "#dc3545" # Rojo por defecto
        if self.calculator:
            prog = self.calculator.calcular_progreso_actividad(actividad)
            num_mesas = int(prog['completado'])
            color_ms = prog.get('color', {}).get('color', color_ms)
            
        # Obtener lista de mesas dinámica desde configuración (Eventos: "Mesa 1|Mesa 2|Mesa 3")
        eventos_texto = actividad.events
        if eventos_texto:
            lista_mesas = [e.strip() for e in eventos_texto.split('|') if e.strip()]
        else:
            # Fallback legacy si no hay config
            lista_mesas = ["Mesa 1", "Mesa 2", "Mesa 3"]
            
        # Generar lista de mesas
        for i, nombre_mesa in enumerate(lista_mesas, 1):
            cumplida = i <= num_mesas
            icon = "✓" if cumplida else "⏳"
            color = "#00c853" if cumplida else "#ffb300" # Verde vs Ambar
            texto_estado = "Completada" if cumplida else "Pendiente"
            
            row = QHBoxLayout()
            row.setContentsMargins(0,0,0,0)
            
            l_nombre = QLabel(f"{nombre_mesa}:")
            is_dark = self.main_app.is_dark_mode if self.main_app else False
            color_nom = "#AAAAAA" if is_dark else "#546e7a"
            l_nombre.setStyleSheet(f"color: {color_nom}; font-size: 12px; border: none; background: transparent;")
            #l_nombre.setWordWrap(True) # Permitir que nombres largos bajen
            
            l_status = QLabel(f"{icon} {texto_estado}")
            l_status.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px; border: none; background: transparent;")
            
            row.addWidget(l_nombre)
            row.addWidget(l_status)
            row.addStretch()
            layout.addLayout(row)
            
        layout.addStretch()
        
        # Contribución de mesas
        if self.calculator:
            puntos, peso_max = self.calculator.calcular_puntos_ganados(actividad)
            lbl_p = QLabel(f"{puntos:.1f}% de {peso_max:.1f}% ganados")
        else:
            total_mesas = len(lista_mesas) if lista_mesas else 3
            percent = min(100, (num_mesas / total_mesas) * 100) if total_mesas > 0 else 0
            lbl_p = QLabel(f"{percent:.0f}% completado")

        lbl_p.setAlignment(Qt.AlignCenter) 
        # Unificado: Usar clase CSS en lugar de estilos hardcoded
        lbl_p.setProperty("class", "MetaSecondaryText")
        
        # Color dinámico basado en el estado
        if self.calculator:
            if color_ms == "#dc3545" or color_ms == "#ef5350": status = "danger"
            elif color_ms == "#ffb300" or color_ms == "#ffc107": status = "warning"
            else: status = "success"
            lbl_p.setProperty("status", status)
            
        # Forzar actualización del estilo
        lbl_p.style().unpolish(lbl_p)
        lbl_p.style().polish(lbl_p)
            
        layout.addWidget(lbl_p)
        
        return card

    def create_card_bonus(self, actividad):
        """Tarjeta para Bonus"""
    def create_card_bonus(self, actividad):
        """Tarjeta para Bonus"""
        # colors = removed
        card, layout = self.create_card_base(actividad.display_name, "⭐")
        
        progreso = self.calculator.calcular_progreso_actividad(actividad) if self.calculator else {'completado':0}
        cumplido = progreso['completado'] > 0
        
        layout.addStretch()
        
        icon = "✓" if cumplido else ""
        lbl_icon = QLabel(icon)
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setFont(QFont("Segoe UI", 30))
        lbl_icon.setStyleSheet("color: #00c853; border: none; background: transparent;")
        layout.addWidget(lbl_icon)
        
        is_dark = self.main_app.is_dark_mode if self.main_app else False
        color_bonus = ("#00c853" if cumplido else "#718096") if not is_dark else ("#00c853" if cumplido else "#AAAAAA") # Gris opaco para no realizado
        
        if self.calculator:
            puntos, peso_max = self.calculator.calcular_puntos_ganados(actividad)
            texto_bonus = f"{puntos:.1f}% de {peso_max:.1f}% ganados" if cumplido else "No realizado"
            # Si el calculator nos da un color específico solo si se ha cumplido
            if cumplido:
                prog = self.calculator.calcular_progreso_actividad(actividad)
                color_bonus = prog.get('color', {}).get('color', color_bonus)
        else:
            texto_bonus = "Cumplido +10%" if cumplido else "No realizado"

        lbl_text = QLabel(texto_bonus)
        lbl_text.setAlignment(Qt.AlignCenter)
        # Unificado: Usar clase CSS en lugar de estilos hardcoded
        lbl_text.setProperty("class", "MetaSecondaryText")
        
        if cumplido:
            # Aplicar estado dinámico si está cumplido
            if color_bonus == "#00c853" or color_bonus == "#28a745": status = "success"
            elif color_bonus == "#ffb300": status = "warning"
            else: status = "danger"
            lbl_text.setProperty("status", status)
        else:
            lbl_text.setProperty("status", "danger") # O neutral
            
        # Forzar actualización del estilo
        lbl_text.style().unpolish(lbl_text)
        lbl_text.style().polish(lbl_text)
            
        layout.addWidget(lbl_text)
        
        layout.addStretch()
        return card

    def create_card_grouped(self, actividades):
        """Tarjeta agrupada para múltiples actividades relacionadas (ej: Redes Sociales)"""
        if not actividades:
            return QWidget()
        
        # Usar título e icono del primer elemento del grupo
        titulo = actividades[0].display_name
        icon = actividades[0].icon
        
        card, layout = self.create_card_base(titulo, icon)
        
        # Crear sub-barra para cada actividad del grupo
        for act in actividades:
            progreso = self.calculator.calcular_progreso_actividad(act) if self.calculator else {'completado':0, 'meta_total':1, 'porcentaje':0}
            
            # Etiqueta de la actividad individual
            col_name_clean = act.column_name.replace("RS-", "").replace("P.V.", "")
            lbl_sub = QLabel(f"{col_name_clean}:")
            lbl_sub.setProperty("class", "subtitle")
            layout.addWidget(lbl_sub)
            
            if progreso['porcentaje'] > 100:
                surplus_porcentaje = progreso['porcentaje'] - 100
                completado = float(progreso['completado'])
                meta = float(progreso['meta_total'])
                puntos_extra = int(completado - meta) if completado - meta > 0 else (completado - meta)
                tooltip_text = f"Superaste la meta por {puntos_extra} puntos, +{surplus_porcentaje:.1f}% sobre la meta."
            else:
                tooltip_text = f"Progreso: {progreso['porcentaje']:.1f}%"
            
            # Barra de progreso
            pbar = self._create_progress_bar(progreso)
            pbar.setToolTip(tooltip_text)
            layout.addWidget(pbar)
            
            # Texto descriptivo
            completado = int(progreso['completado'])
            meta = int(progreso['meta_total'])
            texto_desc = f"{completado}/{meta} logrados"
            
            if progreso['porcentaje'] > 100:
                texto_desc += " 🔥"
                
            lbl_desc = QLabel(texto_desc)
            if progreso['porcentaje'] > 100:
                lbl_desc.setToolTip(tooltip_text)
                
            lbl_desc.setProperty("class", "body")
            lbl_desc.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl_desc)
            
            layout.addSpacing(8)
        
        # AGREGAR TOTAL PARA EL GRUPO
        if self.calculator:
            puntos_totales = sum(self.calculator.calcular_puntos_ganados(a)[0] for a in actividades)
            peso_maximo = sum(self.calculator.calcular_puntos_ganados(a)[1] for a in actividades)
            
            texto_totales = f"{puntos_totales:.1f}% de {peso_maximo:.1f}% ganados"
            
            lbl_totales = QLabel(texto_totales)
            lbl_totales.setAlignment(Qt.AlignCenter)
            lbl_totales.setProperty("class", "MetaSecondaryText")
            
            # Aplicar estado dinámico (promedio del grupo)
            total_perc = (puntos_totales / peso_maximo * 100) if peso_maximo > 0 else 0
            if total_perc >= 80: status = "success"
            elif total_perc >= 50: status = "warning"
            else: status = "danger"
            lbl_totales.setProperty("status", status)
            
            # Forzar actualización del estilo
            lbl_totales.style().unpolish(lbl_totales)
            lbl_totales.style().polish(lbl_totales)
            
            layout.addWidget(lbl_totales)

        layout.addStretch()
        return card

    def create_card_event(self, actividad):
        """Tarjeta para actividades multi-evento (ej: Mesa 1, Mesa 2, Mesa 3)"""
        card, layout = self.create_card_base(actividad.display_name, actividad.icon)
        
        # Obtener datos de progreso
        infoplaza_data = self.current_data.get('infoplaza', {})
        valor_raw = infoplaza_data.get(actividad.column_name, "0/0/0")
        
        # Parsear eventos
        eventos = actividad.events.split("|") if actividad.events else []
        
        # Parsear valores
        estados = str(valor_raw).split("/") if "/" in str(valor_raw) else []
        
        # Mostrar cada evento
        for idx, evento_nombre in enumerate(eventos):
            estado_val = int(estados[idx]) if idx < len(estados) else 0
            
            if estado_val > 0:
                icono_estado = "✓"
                color_estado = "#10b981"
            else:
                icono_estado = "•"
                color_estado = "#94a3b8"
            
            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0, 0, 0, 0)
            
            lbl_icono = QLabel(icono_estado)
            lbl_icono.setStyleSheet(f"color: {color_estado}; font-size: 18px; font-weight: bold; border: none;")
            lbl_icono.setFixedWidth(30)
            h_layout.addWidget(lbl_icono)
            
            lbl_nombre = QLabel(evento_nombre)
            lbl_nombre.setProperty("class", "body")
            h_layout.addWidget(lbl_nombre)
            h_layout.addStretch()
            
            layout.addLayout(h_layout)
        
        layout.addStretch()
        return card

    def create_card_once(self, actividad):
        """Tarjeta para actividades de una sola vez (Dinámica con fecha)"""
        card, layout = self.create_card_base(actividad.display_name, actividad.icon)
        
        infoplaza_data = self.current_data.get('infoplaza', {})
        valor = infoplaza_data.get(actividad.column_name, 0)
        
        try:
            completado = int(valor) > 0
        except:
            completado = False
            
        # Lógica de visualización dinámica basada en Eventos (Fecha)
        texto_evento = actividad.events.strip() # Ej: "abril 2026"
        
        if completado:
            color = "#10b981" # Verde
            icon = "✓"
            if texto_evento:
                texto_principal = texto_evento
                texto_secundario = "Cumplido"
            else:
                texto_principal = "Cumplido"
                texto_secundario = ""
        else:
            color = "#f59e0b" # Ambar (Pendiente) en lugar de gris
            icon = "⏳"
            if texto_evento:
                texto_principal = texto_evento
                texto_secundario = "Pendiente"
            else:
                texto_principal = "Pendiente" # Cambiado de "No realizado" a "Pendiente"
                texto_secundario = ""
        
        
        # Centrado Vertical: añadir spacer superior
        layout.addStretch()

        # Icono gigante (Reducido)
        lbl_icon = QLabel(icon)
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setFont(QFont("Segoe UI Symbol", 28)) # Reducido de 40 a 28
        lbl_icon.setStyleSheet(f"color: {color}; border: none; background: transparent;")
        layout.addWidget(lbl_icon)
        
        # Texto Principal (Fecha o Estado)
        lbl_main = QLabel(texto_principal)
        lbl_main.setAlignment(Qt.AlignCenter)
        lbl_main.setWordWrap(True)
        lbl_main.setFont(QFont("Segoe UI", 14, QFont.Bold))
        lbl_main.setStyleSheet(f"color: {color}; border: none; background: transparent;")
        layout.addWidget(lbl_main)
        
        # Texto Secundario (Opcional)
        if texto_secundario:
            lbl_sec = QLabel(texto_secundario.upper())
            lbl_sec.setAlignment(Qt.AlignCenter)
            lbl_sec.setFont(QFont("Segoe UI", 10, QFont.Bold))
            lbl_sec.setStyleSheet(f"color: {color}; border: none; background: transparent; letter-spacing: 1px;")
            layout.addWidget(lbl_sec)
        
        # PORCENTAJE GANADO
        if self.calculator:
            puntos, peso_max = self.calculator.calcular_puntos_ganados(actividad)
            texto_puntos = f"{puntos:.1f}% de {peso_max:.1f}% ganados"
            
            lbl_puntos = QLabel(texto_puntos)
            lbl_puntos.setAlignment(Qt.AlignCenter)
            lbl_puntos.setProperty("class", "MetaSecondaryText")
            lbl_puntos.setStyleSheet(f"color: {color}; border: none; background: transparent; font-weight: bold; margin-top: 5px;")
            layout.addWidget(lbl_puntos)

        layout.addStretch()
        return card

    def _create_progress_bar(self, progreso):
        """Helper: crea una barra de progreso"""
        pbar = QProgressBar()
        pbar.setMinimum(0)
        pbar.setMaximum(100)
        # CRÍTICO: Limitar visualmente a 100 para evitar que la barra "desaparezca" o se renderice mal
        pbar.setValue(min(100, int(progreso['porcentaje'])))
        pbar.setTextVisible(True)
        perc_display = min(100.0, progreso['porcentaje'])
        pbar.setFormat(f"{perc_display:.1f}%")
        # Height controlado por CSS: .ActivityItem QProgressBar { height: 12px; }
        
        # Usar color dinámico del calculator si existe
        if 'color' in progreso and 'color' in progreso['color']:
            color = progreso['color']['color']
        else:
            # Fallback: colores por porcentaje
            if progreso['porcentaje'] >= 80.0:
                color = "#10b981"
            elif progreso['porcentaje'] >= 50.0:
                color = "#f59e0b"
            else:
                color = "#ef4444"
        
        # Determinar color de fondo según tema
        is_dark = self.main_app.is_dark_mode if self.main_app else False
        bg_color = "#334155" if is_dark else "#e5e7eb" # Dark Slate vs Light Gray
        text_color = "#ffffff" if is_dark else "#000000" # Texto variable según tema
        
        # Opcional: Si la barra está llena, el texto queda sobre el color.
        # Como los colores de barra (Verde/Ambar/Rojo) son vibrantes, 
        # el blanco suele leerse bien en Verde/Rojo, y Negro en Ambar/Gris.
        # Para simplificar y asegurar contraste, usaremos texto negro por defecto en modo claro
        # y texto blanco en modo oscuro, confiando en que el "chunk" no oscurezca demasiado.
        
        pbar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: {bg_color};
                text-align: center;
                color: {text_color}; /* Forzar color de texto */
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)
        
        return pbar

# ============================================================================
# NUEVA CLASE: DELEGADO PARA PINTAR BARRAS DE PROGRESO (Optimización)
# ============================================================================

class ProgressDelegate(QStyledItemDelegate):
    """
    Pinta una barra de progreso directamente sobre la celda sin usar widgets pesados.
    Esto hace que la tabla soporte cientos de filas sin lag.
    """
    def paint(self, painter, option, index):
        if index.column() == 4: # Columna de Progreso
            # 1. Obtener datos (guardados en UserRole o EditRole)
            progreso = index.data(Qt.EditRole)
            if progreso is None:
                super().paint(painter, option, index)
                return
            
            # Obtener color pre-calculado
            color_hex = index.data(Qt.UserRole) or "#3182ce"
            color = QColor(color_hex)

            # 2. Dibujar fondo de la celda (selección, etc)
            self.parent().style().drawControl(QStyle.CE_ItemViewItem, option, painter)

            # 3. Configurar dimensiones de la barra
            margin_h = 10
            text_width = 55
            spacing = 10
            
            # Rectángulo para el texto del porcentaje (Centrado vertical)
            text_rect = QRect(option.rect.left() + margin_h, option.rect.top(), text_width, option.rect.height())
            
            painter.save()
            painter.setPen(color)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, f"{progreso:.1f}%")
            painter.restore()

            # Rectángulo para la barra (Centrado vertical)
            bar_height = 10
            # Calculamos bar_x relativo al inicio de la celda
            rel_bar_x = margin_h + text_width + spacing
            bar_width = option.rect.width() - rel_bar_x - margin_h
            
            if bar_width > 0:
                bar_x = option.rect.left() + rel_bar_x
                bar_y = option.rect.top() + (option.rect.height() - bar_height) // 2
                
                bar_rect = QRect(bar_x, bar_y, bar_width, bar_height)
                
                # Dibujar fondo de la barra
                painter.setRenderHint(QPainter.Antialiasing)
                is_dark = self.parent().main_app.is_dark_mode if hasattr(self.parent(), "main_app") else False
                bg_bar_color = "#4D4D4D" if is_dark else "#edf2f7"
                painter.setBrush(QBrush(QColor(bg_bar_color)))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(bar_rect, 5, 5)
                
                # Dibujar relleno de la barra
                fill_width = int(bar_width * (min(100, progreso) / 100.0))
                if fill_width > 0:
                    fill_rect = QRect(bar_x, bar_y, fill_width, bar_height)
                    painter.setBrush(QBrush(color))
                    painter.drawRoundedRect(fill_rect, 5, 5)
        else:
            super().paint(painter, option, index)

# ============================================================================
# NUEVA CLASE: CUADRO MAESTRO DE METAS (Vista Facilitador)
# ============================================================================

class MetasTableView(QWidget):
    """
    Vista de tabla masiva para todas las Infoplazas (Solo Facilitadores)
    Permite filtrar por regional, provincia y ordenar por progreso.
    """
    def __init__(self, main_app=None, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.all_data = [] # Lista de diccionarios (todas las infoplazas)
        self.metas_config = {} # Configuración de metas
        self.init_ui()
        self.update_theme()

    def update_theme(self, is_dark=None):
        """Actualiza el tema de la tabla de cuadro maestro
        
        MIGRADO A QSS: Los estilos ahora se aplican automáticamente desde ada_nova.qss
        Este método solo fuerza el re-renderizado para aplicar los cambios de tema.
        """
        # Forzar actualización del estilo desde QSS
        if hasattr(self, 'table') and self.table:
            self.table.style().unpolish(self.table)
            self.table.style().polish(self.table)


    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. TÍTULO Y FILTROS
        header_layout = QHBoxLayout()
        
        self.lbl_title = QLabel("📊 Cuadro Maestro de Metas")
        self.lbl_title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        header_layout.addWidget(self.lbl_title)
        
        # --- NUEVO: Fecha de actualización sutil ---
        self.lbl_actualizado = QLabel("")
        self.lbl_actualizado.setFont(QFont("Segoe UI", 12))
        self.lbl_actualizado.setStyleSheet("color: #718096; margin-left: 15px; margin-bottom: 5px;")
        header_layout.addWidget(self.lbl_actualizado, 0, Qt.AlignBottom)
        # -------------------------------------------
        
        header_layout.addStretch()
        
        # --- BOTÓN DE ESTADO DE CONEXIÓN ---
        # Reutilizamos el connection_manager de la pestaña de Metas si existe
        if self.main_app and hasattr(self.main_app, 'tab_metas') and hasattr(self.main_app.tab_metas, 'connection_manager'):
            self.connection_status = ConnectionStatusWidget(self.main_app.tab_metas.connection_manager)
            header_layout.addWidget(self.connection_status)
        # -----------------------------------
        # self.btn_refresh_table = QPushButton("🔄 Actualizar Tabla")
        # self.btn_refresh_table.setStyleSheet("""
        #     QPushButton {
        #         background-color: #3182ce; color: white; border-radius: 6px; padding: 8px 15px; font-weight: bold;
        #     }
        #     QPushButton:hover { background-color: #2b6cb0; }
        # """)
        # self.btn_refresh_table.clicked.connect(self.request_data_refresh)
        # header_layout.addWidget(self.btn_refresh_table)

        layout.addLayout(header_layout)

        # Título y Filtros
        controls_layout = QHBoxLayout()
        
        # Filtro Regional
        self.lbl_reg = QLabel("Regional:")
        # Usar clase QSS para label
        self.lbl_reg.setProperty("class", "FilterLabel")
        controls_layout.addWidget(self.lbl_reg)
        self.combo_reg = QComboBox()
        self.combo_reg.setMinimumWidth(200)
        self.combo_reg.setFont(QFont("Segoe UI", 13))
        self.combo_reg.setMaxVisibleItems(15) # Un poco más de visión también aquí
        self.combo_reg.addItems(["TODAS"])
        self.combo_reg.currentTextChanged.connect(self.actualizar_provincias)
        controls_layout.addWidget(self.combo_reg)
        
        # Filtro Provincia
        self.lbl_prov = QLabel("Provincia:")
        # Usar clase QSS para label
        self.lbl_prov.setProperty("class", "FilterLabel")
        controls_layout.addWidget(self.lbl_prov)
        self.combo_prov = QComboBox()
        self.combo_prov.setMinimumWidth(200)
        self.combo_prov.setFont(QFont("Segoe UI", 13))
        self.combo_prov.setMaxVisibleItems(30) # Mostrar muchas opciones al desplegar
        self.combo_prov.addItems(["TODAS"])
        self.combo_prov.currentTextChanged.connect(self.aplicar_filtros)
        controls_layout.addWidget(self.combo_prov)
        
        # BUSCADOR POR NOMBRE/ID
        controls_layout.addSpacing(20)
        self.lbl_bus = QLabel("Buscar:")
        # Usar clase QSS para label
        self.lbl_bus.setProperty("class", "FilterLabel")
        controls_layout.addWidget(self.lbl_bus)
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Nombre o # Infoplaza")
        self.txt_search.setFixedWidth(200)
        self.txt_search.textChanged.connect(self.aplicar_filtros)
        controls_layout.addWidget(self.txt_search)
        
        # --- NUEVO: Botón Limpiar Filtros (Dinámico) ---
        self.btn_clear_filters = QPushButton("🧹 Limpiar")
        self.btn_clear_filters.setFixedWidth(100)
        self.btn_clear_filters.setCursor(Qt.PointingHandCursor)
        self.btn_clear_filters.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #e53e3e;
                font-weight: bold;
                border: 1px solid #e53e3e;
                border-radius: 5px;
                padding: 4px;
            }
            QPushButton:hover { background-color: #fff5f5; }
        """)
        self.btn_clear_filters.setVisible(False)
        self.btn_clear_filters.clicked.connect(self.clear_filters)
        controls_layout.addWidget(self.btn_clear_filters)
        # -----------------------------------------------
        
        controls_layout.addStretch()
        
        # BOTÓN EXPORTAR EXCEL
        self.btn_export = QPushButton("📥 Exportar Metas a Excel")
        self.btn_export.setFixedWidth(200)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        self.btn_export.clicked.connect(self.exportar_excel)
        controls_layout.addWidget(self.btn_export)
        
        layout.addLayout(controls_layout)

        # 2. TABLA
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Infoplaza", "Regional", "Provincia", "Progreso (%)", 
            "Estado", "Meses Subidos", "Metas al 100%"
        ])
        # Textos de ayuda en cabeceras
        self.table.horizontalHeaderItem(6).setToolTip("Muestra la cantidad de meses que el dinamizador ha subido.\nPara ver más detalles debe hacer clic en el botón Ver metas.")
        self.table.horizontalHeaderItem(7).setToolTip("Indica cuántas metas ha cumplido la infoplaza al 100%.\nPara ver más detalles ir al botón ver metas.")
        
        # Configuración de columnas
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 60)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 280)
        
        # Anchos fijos para columnas finales
        self.table.setColumnWidth(6, 120) 
        self.table.setColumnWidth(7, 120)
        
        # Delegado para barra de progreso
        self.table.setItemDelegateForColumn(4, ProgressDelegate(self.table))
        
        # Conectar doble clic para ver detalles
        self.table.cellDoubleClicked.connect(self.on_table_double_click)
        
        layout.addWidget(self.table)

        
        # Info Pie
        self.lbl_info_pie = QLabel("Mostrando 0 de 0 infoplazas")
        # Usar clase QSS para footer info
        self.lbl_info_pie.setProperty("class", "TableInfoFooter")
        layout.addWidget(self.lbl_info_pie)

    def set_data(self, all_infoplazas, metas_config, update_info=None):
        """Puebla la tabla con los datos proporcionados"""
        # --- NUEVO: Guardar selección actual para preservarla ---
        prev_reg = self.combo_reg.currentText()
        
        self.all_data = all_infoplazas
        self.metas_config = metas_config
        
        # Actualizar fecha de actualización si se proporciona
        if update_info:
            fecha = update_info.get('fecha', '')
            hora = update_info.get('hora', '')
            if fecha and hora and fecha != "N/A":
                self.lbl_actualizado.setText(f"Actualizado al: {fecha} {hora}")
            else:
                self.lbl_actualizado.setText("")
        
        # Actualizar combos de filtros sin disparar eventos
        self.combo_reg.blockSignals(True)
        self.combo_prov.blockSignals(True)
        
        regionales = sorted(list(set(str(d.get('Regional', '')).strip() for d in all_infoplazas if d.get('Regional'))))
        self.combo_reg.clear()
        self.combo_reg.addItem("TODAS")
        self.combo_reg.addItems(regionales)
        
        # --- NUEVO: Restaurar selección Regional si aún existe ---
        idx_reg = self.combo_reg.findText(prev_reg)
        if idx_reg >= 0:
            self.combo_reg.setCurrentIndex(idx_reg)
        
        self.actualizar_provincias()
        
        self.combo_reg.blockSignals(False)
        self.combo_prov.blockSignals(False)
        
        self.aplicar_filtros()

    def actualizar_provincias(self):
        # --- NUEVO: Guardar selección actual de provincia para preservarla ---
        prev_prov = self.combo_prov.currentText()
        self.combo_prov.blockSignals(True)
        
        sel_reg = self.combo_reg.currentText()
        provincias = set()
        for d in self.all_data:
            reg = str(d.get('Regional', '')).strip()
            prov = str(d.get('Provincia / Comarca', '')).strip()
            if prov and (sel_reg == "TODAS" or reg == sel_reg):
                provincias.add(prov)
        
        self.combo_prov.clear()
        self.combo_prov.addItem("TODAS")
        self.combo_prov.addItems(sorted(list(provincias)))
        
        # --- NUEVO: Restaurar selección de Provincia si aún existe ---
        idx_prov = self.combo_prov.findText(prev_prov)
        if idx_prov >= 0:
            self.combo_prov.setCurrentIndex(idx_prov)
            
        self.combo_prov.blockSignals(False)
        self.aplicar_filtros() # Aplicar filtros después de actualizar provincias

    def aplicar_filtros(self):
        sel_reg = self.combo_reg.currentText()
        sel_prov = self.combo_prov.currentText()
        
        search_text = self.txt_search.text().lower().strip()
        
        filtered = []
        for d in self.all_data:
            reg_val = str(d.get('Regional', d.get('regional', ''))).upper()
            prov_val = str(d.get('Provincia / Comarca', d.get('provincia_/_comarca', d.get('provincia', '')))).upper()
            nombre_val = str(d.get('Nombre de la Infoplaza', d.get('nombre_de_la_infoplaza', d.get('nombre', '')))).lower()
            id_val = str(d.get('# Info', d.get('#_info', d.get('id', '')))).lower()
            
            match_reg = (sel_reg == "TODAS" or reg_val == sel_reg.upper())
            match_prov = (sel_prov == "TODAS" or prov_val == sel_prov.upper())
            
            # Match buscador (ID o Nombre)
            match_search = True
            if search_text:
                match_search = (search_text in nombre_val or search_text in id_val)
            
            if match_reg and match_prov and match_search:
                filtered.append(d)
        
        # Actualizar visibilidad del botón limpiar
        any_filter = (sel_reg != "TODAS" or sel_prov != "TODAS" or search_text != "")
        self.btn_clear_filters.setVisible(any_filter)
        
        self.rebuild_table(filtered)

    def rebuild_table(self, data_list):
        self.filtered_data = data_list  # Guardar los datos filtrados para exportar
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        for row, data in enumerate(data_list):
            self.table.insertRow(row)
            
            # 1. ID e Info
            idx_val = data.get('# Info', data.get('#_info', data.get('id', '')))
            nombre = data.get('Nombre de la Infoplaza', data.get('nombre_de_la_infoplaza', data.get('nombre', 'S/N')))
            regional = data.get('Regional', data.get('regional', 'S/R'))
            provincia = data.get('Provincia / Comarca', data.get('provincia_/_comarca', data.get('provincia', 'S/P')))
            
            item_id = QTableWidgetItem(str(idx_val))
            item_id.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, item_id)
            
            item_nombre = QTableWidgetItem(str(nombre))
            item_nombre.setToolTip(str(nombre))
            self.table.setItem(row, 1, item_nombre)
            
            item_reg = QTableWidgetItem(str(regional))
            self.table.setItem(row, 2, item_reg)
            
            item_prov = QTableWidgetItem(str(provincia))
            self.table.setItem(row, 3, item_prov)
            
            # CÁLCULOS
            calculator = MetasCalculator(data, self.metas_config)
            estado_global = calculator.calcular_estado_global()
            progreso = estado_global['progreso']
            color = estado_global['color']
            
            # 4. Progreso
            item_prog = QTableWidgetItem()
            item_prog.setData(Qt.EditRole, progreso)
            item_prog.setData(Qt.UserRole, color)
            self.table.setItem(row, 4, item_prog)
            
            # 5. Estado
            estado_txt = estado_global.get('estado', 'PENDIENTE').replace('_', ' ').upper()
            item_estado = QTableWidgetItem(estado_txt)
            item_estado.setTextAlignment(Qt.AlignCenter)
            item_estado.setForeground(QColor(color))
            self.table.setItem(row, 5, item_estado)
            
            # 6. Meses Subidos
            m_sub, m_tot = calculator.calcular_meses_subidos()
            item_meses = QTableWidgetItem(f"{m_sub}/{m_tot}")
            item_meses.setTextAlignment(Qt.AlignCenter)
            item_meses.setData(Qt.UserRole, m_sub)
            item_meses.setToolTip("Muestra la cantidad de meses que el dinamizador ha subido.\nPara ver más detalles debe hacer clic en el botón Ver metas.")
            self.table.setItem(row, 6, item_meses)
            
            # 7. Metas al 100%
            c_comp, c_tot = calculator.calcular_actividades_completadas()
            item_metas = QTableWidgetItem(f"{c_comp}/{c_tot}")
            item_metas.setTextAlignment(Qt.AlignCenter)
            item_metas.setData(Qt.UserRole, c_comp)
            item_metas.setToolTip("Indica cuántas metas ha cumplido la infoplaza al 100%.\nPara ver más detalles ir al botón ver metas.")
            self.table.setItem(row, 7, item_metas)

        # ORDENAR POR DEFECTO: PROGRESO (Col 4) DESCENDENTE
        self.table.sortItems(4, Qt.DescendingOrder)
        
        self.table.setSortingEnabled(True)
        self.lbl_info_pie.setText(f"Mostrando {len(data_list)} de {len(self.all_data)} infoplazas")

    def on_table_double_click(self, row, column):
        """Maneja el doble clic en la tabla para abrir el detalle"""
        # Obtenemos el ítem de la primera columna (ID)
        item_id = self.table.item(row, 0)
        if item_id:
            infoplaza_id = item_id.text()
            print(f"[MATRIZ] Doble clic en Infoplaza {infoplaza_id}")
            
            if self.main_app and hasattr(self.main_app, 'ver_detalle_infoplaza'):
                self.main_app.ver_detalle_infoplaza(infoplaza_id)
            else:
                print("[MATRIZ] Error: main_app no tiene el método ver_detalle_infoplaza")

    def request_data_refresh(self):
        """Solicita una actualización de datos al componente principal"""
        if self.main_app and hasattr(self.main_app, 'tab_metas'):
            # Reutilizamos el fetcher centralizado en tab_metas
            # Este ya está configurado para cargar 'todas_infoplazas' incluso si no hay ID
            self.main_app.tab_metas.refresh_data(force_reload=True, require_user_id=False)
            pass
            
    def exportar_excel(self):
        """Exporta todos los datos del Google Sheets filtrados según la vista activa."""

        def _try_numeric(value):
            """Convierte un valor a int o float si es posible, si no lo deja como string."""
            if isinstance(value, (int, float)):
                return value
            if isinstance(value, str):
                v = value.strip()
                if v == '':
                    return None
                try:
                    as_int = int(v)
                    return as_int
                except ValueError:
                    pass
                try:
                    as_float = float(v.replace(',', '.'))
                    return as_float
                except ValueError:
                    pass
            return value

        filtered = getattr(self, 'filtered_data', [])
        if not filtered:
            QMessageBox.information(self, "Exportar", "No hay datos para exportar.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Excel",
            f"Metas_ADA_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not path:
            return

        try:
            data_export = []
            for data in filtered:
                # --- Columnas calculadas ---
                calculator = MetasCalculator(data, self.metas_config)
                estado_global = calculator.calcular_estado_global()
                progreso = estado_global.get('progreso', 0)
                estado_txt = estado_global.get('estado', 'PENDIENTE').replace('_', ' ').upper()
                m_sub, m_tot = calculator.calcular_meses_subidos()
                c_comp, c_tot = calculator.calcular_actividades_completadas()

                # --- Columnas base de la vista (siempre primero) ---
                idx_val = data.get('# Info', data.get('#_info', data.get('id', '')))
                nombre = data.get('Nombre de la Infoplaza', data.get('nombre_de_la_infoplaza', data.get('nombre', 'S/N')))
                regional = data.get('Regional', data.get('regional', 'S/R'))
                provincia = data.get('Provincia / Comarca', data.get('provincia_/_comarca', data.get('provincia', 'S/P')))

                row_export = {
                    'ID': _try_numeric(str(idx_val)),
                    'Infoplaza': str(nombre),
                    'Regional': str(regional),
                    'Provincia': str(provincia),
                    'Progreso (%)': round(progreso / 100, 6),  # decimal para formato % de Excel
                    'Estado': estado_txt,
                    'Meses Subidos': m_sub,
                    'Total Meses': m_tot,
                    'Metas al 100%': c_comp,
                    'Total Metas': c_tot,
                }

                # --- Columnas extra del Google Sheets (nombres normalizados) ---
                # Excluir las columnas que ya se mapearon arriba para no duplicar
                columnas_base = {
                    '# info', '#_info', 'id',
                    'nombre de la infoplaza', 'nombre_de_la_infoplaza', 'nombre',
                    'regional',
                    'provincia / comarca', 'provincia_/_comarca', 'provincia',
                }
                for key, value in data.items():
                    if key.lower() not in columnas_base:
                        row_export[key] = _try_numeric(value)

                data_export.append(row_export)

            df = pd.DataFrame(data_export)

            # Escribir con openpyxl para aplicar formato % a la columna Progreso
            with pd.ExcelWriter(path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Metas')
                ws = writer.sheets['Metas']

                # Encontrar el índice de la columna 'Progreso (%)' (1-based en openpyxl)
                col_progreso = None
                for col_idx, col_name in enumerate(df.columns, 1):
                    if col_name == 'Progreso (%)':
                        col_progreso = col_idx
                        break

                if col_progreso:
                    for row_idx in range(2, len(df) + 2):  # fila 1 = cabecera
                        ws.cell(row=row_idx, column=col_progreso).number_format = '0.00%'

            QMessageBox.information(self, "Exportar", f"Archivo guardado exitosamente en:\n{path}")

            # Preguntar si quiere abrirlo
            if QMessageBox.question(
                self, "Abrir Archivo",
                "¿Desea abrir el archivo ahora?",
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al exportar: {str(e)}")

    def clear_filters(self):
        """Resetea todos los filtros a su estado inicial"""
        self.combo_reg.blockSignals(True)
        self.combo_reg.setCurrentText("TODAS")
        self.combo_reg.blockSignals(False)
        
        self.combo_prov.blockSignals(True)
        self.combo_prov.setCurrentText("TODAS")
        self.combo_prov.blockSignals(False)
        
        self.txt_search.blockSignals(True)
        self.txt_search.clear()
        self.txt_search.blockSignals(False)
        
        # actualizar_provincias hará el resto (limpiar combo_prov y aplicar_filtros)
        self.actualizar_provincias()

    def refresh_data(self):
        """Método de compatibilidad para ADA_Nova.py"""
        self.request_data_refresh()

    def request_data_refresh(self):
        """Solicita al Tab de Metas que recargue los datos globales"""
        if hasattr(self.main_app, 'tab_metas'):
            self.main_app.tab_metas.refresh_data(force_reload=True)

