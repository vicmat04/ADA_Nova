import os
import sys
import subprocess
import re
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QTextEdit, QFileDialog, QMessageBox, QFrame, QProgressBar)
from PyQt5.QtGui import QFont, QColor, QIcon, QDesktopServices
from PyQt5.QtCore import Qt, QSize, QUrl

from facebook_data_processor import FacebookDataProcessor, MissingColumnError
from facebook_report_builder import FacebookReportBuilder

# --- NATIVE WINDOWS DIALOG SUPPORT (CTYPES) ---
import ctypes
import ctypes.wintypes

class OPENFILENAME(ctypes.Structure):
    _fields_ = [
        ("lStructSize", ctypes.wintypes.DWORD),
        ("hwndOwner", ctypes.wintypes.HWND),
        ("hInstance", ctypes.wintypes.HINSTANCE),
        ("lpstrFilter", ctypes.wintypes.LPCWSTR),
        ("lpstrCustomFilter", ctypes.wintypes.LPWSTR),
        ("nMaxCustFilter", ctypes.wintypes.DWORD),
        ("nFilterIndex", ctypes.wintypes.DWORD),
        ("lpstrFile", ctypes.wintypes.LPWSTR),
        ("nMaxFile", ctypes.wintypes.DWORD),
        ("lpstrFileTitle", ctypes.wintypes.LPWSTR),
        ("nMaxFileTitle", ctypes.wintypes.DWORD),
        ("lpstrInitialDir", ctypes.wintypes.LPCWSTR),
        ("lpstrTitle", ctypes.wintypes.LPCWSTR),
        ("Flags", ctypes.wintypes.DWORD),
        ("nFileOffset", ctypes.wintypes.WORD),
        ("nFileExtension", ctypes.wintypes.WORD),
        ("lpstrDefExt", ctypes.wintypes.LPCWSTR),
        ("lCustData", ctypes.wintypes.LPARAM),
        ("lpfnHook", ctypes.c_void_p),
        ("lpTemplateName", ctypes.wintypes.LPCWSTR),
    ]

def native_open_file_dialog(title="Abrir archivo", filter_str="Todos los archivos (*.csv)\0*.csv\0\0", hwnd=None):
    """
    Abre un diálogo nativo de Windows usando ctypes.
    filter_str example: "CSV Files (*.csv)\0*.csv\0Text Files (*.txt)\0*.txt\0\0"
    """
    try:
        filename = ctypes.create_unicode_buffer(260)
        
        ofn = OPENFILENAME()
        ofn.lStructSize = ctypes.sizeof(OPENFILENAME)
        ofn.hwndOwner = hwnd  # Window Handle
        ofn.lpstrFile = ctypes.cast(filename, ctypes.wintypes.LPWSTR)
        ofn.nMaxFile = 260
        ofn.lpstrFilter = filter_str
        ofn.nFilterIndex = 1
        ofn.lpstrFileTitle = None
        ofn.nMaxFileTitle = 0
        ofn.lpstrInitialDir = None
        ofn.lpstrTitle = title
        ofn.Flags = 0x00080000 | 0x00001000 | 0x00000800  # OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST

        if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
            return filename.value
        return None
    except Exception as e:
        print(f"Error nativo dialog: {e}")
        return None
# ----------------------------------------------

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    Figure = None
    FigureCanvas = None

# ReportLab y Constantes de Meses movidos a sus respectivos módulos

def limpiar_nombre_archivo(nombre):
    """Limpia el nombre de archivo eliminando caracteres no permitidos."""
    import re
    # Reemplazar caracteres no permitidos por guiones bajos
    nombre_limpio = re.sub(r'[\\/*?:"<>|]', '_', nombre)
    # Reemplazar espacios por guiones bajos también para mayor limpieza
    return nombre_limpio.strip().replace(' ', '_')

# Values will be updated from config
META_ORIGINALES = 15
META_COMPARTIDAS = 15

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class FacebookAnalyzerWidget(QWidget):
    def __init__(self, parent=None, config=None, main_app=None):
        super().__init__(parent)
        self.config = config if config is not None else {}
        self.main_app = main_app # Referencia para acceder a la bitacora
        self.current_results = None # To store analysis results for export
        self.last_export_path = None # Para guardar la ruta del último PDF exportado
        
        # Update global constants from config
        global META_ORIGINALES, META_COMPARTIDAS
        META_ORIGINALES = self.config.get("META_ORIGINALES", 15)
        META_COMPARTIDAS = self.config.get("META_COMPARTIDAS", 15)
        
        self.data_processor = FacebookDataProcessor()
        self.report_builder = FacebookReportBuilder(META_ORIGINALES, META_COMPARTIDAS)
        
        self.init_ui()

        # --- DRAG & DROP: Activar en todo el widget ---
        self.setAcceptDrops(True)

    def update_params_from_config(self, new_config):
        """Actualiza las metas globales y la UI si la configuración remota cambia."""
        self.config.update(new_config)
        
        global META_ORIGINALES, META_COMPARTIDAS
        META_ORIGINALES = self.config.get("META_ORIGINALES", 15)
        META_COMPARTIDAS = self.config.get("META_COMPARTIDAS", 15)
        
        if hasattr(self, 'report_builder'):
            self.report_builder.update_metas(META_ORIGINALES, META_COMPARTIDAS)
            
        # Actualizar labels si ya existen
        if hasattr(self, 'MetaInfo'):
            meta_text = f"Meta del mes:\n• Publicaciones originales: {META_ORIGINALES}\n• Publicaciones compartidas: {META_COMPARTIDAS}"
            self.meta_lbl.setText(meta_text)

    def update_theme(self, is_dark):
        """Actualiza el tema visualmente y propaga a todos los widgets hijos"""
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
        
        # Actualizar color de fondo del gráfico
        if hasattr(self, 'fig') and self.fig:
            bg_color = "#1e293b" if is_dark else "#ffffff"
            self.fig.patch.set_facecolor(bg_color)
            if hasattr(self, 'canvas'):
                self.canvas.draw()

    def actualizar_grafico(self, originales, compartidas):
        """Dibuja el gráfico de barras con los datos de Facebook"""
        if not hasattr(self, 'fig') or not self.fig:
            return
        
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        
        # Configurar tema
        if hasattr(self, 'main_app') and self.main_app:
            is_dark = self.main_app.is_dark_mode
        else:
            is_dark = False
        
        bg_color = "#1e293b" if is_dark else "#ffffff"
        text_color = "#f1f5f9" if is_dark else "#0f172a"
        grid_color = "#475569" if is_dark else "#e2e8f0"
        
        self.fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)
        
        # Datos
        categorias = ['Originales', 'Compartidas']
        valores = [originales, compartidas]
        metas = [META_ORIGINALES, META_COMPARTIDAS]
        colores = ['#3b82f6', '#10b981']  # Azul y verde
        
        # Crear barras
        x_pos = [0, 1]
        bars = ax.bar(x_pos, valores, color=colores, alpha=0.8, width=0.6)
        
        # Línea de meta
        max_meta = max(metas)
        ax.axhline(y=max_meta, color='#f59e0b', linestyle='--', linewidth=2, label=f'Meta: {max_meta}')
        
        # Añadir valores sobre las barras
        for i, (bar, valor) in enumerate(zip(bars, valores)):
            height = bar.get_height()
            porcentaje = (valor / metas[i]) * 100
            ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                   f'{int(valor)}\n({int(porcentaje)}%)',
                   ha='center', va='bottom', color=text_color, fontweight='bold', fontsize=10)
        
        # Configurar ejes
        ax.set_ylabel('Cantidad', color=text_color, fontsize=11)
        ax.set_title('Rendimiento Mensual vs Meta', color=text_color, fontsize=12, fontweight='bold', pad=15)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(categorias, color=text_color, fontsize=10)
        ax.tick_params(axis='y', labelcolor=text_color)
        ax.tick_params(axis='x', colors=text_color)
        ax.spines['bottom'].set_color(grid_color)
        ax.spines['top'].set_color(grid_color)
        ax.spines['left'].set_color(grid_color)
        ax.spines['right'].set_color(grid_color)
        
        # Grid
        ax.grid(axis='y', alpha=0.3, color=grid_color)
        
        # Leyenda
        ax.legend(facecolor=bg_color, edgecolor=grid_color, labelcolor=text_color)
        
        self.fig.tight_layout()
        self.canvas.draw()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # --- ENCABEZADO ESTILO PREMIUM (Basado en Cuadro de Metas) ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)
        
        # Título y Créditos en un layout vertical
        title_credits_layout = QVBoxLayout()
        title_credits_layout.setSpacing(2)
        
        self.lbl_title = QLabel("📱 Analizador de Publicaciones de Facebook")
        self.lbl_title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        
        self.lbl_credits_header = QLabel("Lógica y Desarrollo por: Carlos Batista")
        self.lbl_credits_header.setFont(QFont("Segoe UI", 11, QFont.StyleItalic))
        self.lbl_credits_header.setStyleSheet("color: #64748b; margin-left: 5px;")
        
        title_credits_layout.addWidget(self.lbl_title)
        title_credits_layout.addWidget(self.lbl_credits_header)
        
        header_layout.addLayout(title_credits_layout)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # --- SECCIÓN DE METAS CON BOTÓN DE ESTADO AL LADO ---
        meta_container = QFrame()
        meta_container.setProperty("class", "MetaSection")  # Usar clase QSS
        meta_main_layout = QHBoxLayout(meta_container)
        
        # Layout izquierdo: Título y contenido de metas
        meta_left_layout = QVBoxLayout()
        
        meta_title = QLabel("METAS DEL MES")
        meta_title.setProperty("class", "h3")  # Usar h3
        
        meta_text_content = f"• Publicaciones originales: <b>{META_ORIGINALES}</b><br>• Publicaciones compartidas: <b>{META_COMPARTIDAS}</b>"
        self.meta_lbl = QLabel(meta_text_content)
        self.meta_lbl.setProperty("class", "body-large")  # 24px, sin negrita
        
        meta_left_layout.addWidget(meta_title)
        meta_left_layout.addWidget(self.meta_lbl)
        meta_main_layout.addLayout(meta_left_layout)
        
        meta_main_layout.addStretch()
        
        layout.addWidget(meta_container)

        # --- BOTONES DE ACCIÓN PRINCIPALES ---
        btn_layout = QHBoxLayout()
        
        self.btn_load = QPushButton("  CARGAR CSV")
        self.btn_load.setProperty("class", "MetaSuccessButton")  # Verde
        self.btn_load.clicked.connect(self.mostrar_resultado)
        self.btn_load.setFixedSize(200, 50)
        # Attempt to load icon
        csv_icon_path = os.path.join(BASE_DIR, "csv.png")
        if os.path.exists(csv_icon_path):
            self.btn_load.setIcon(QIcon(csv_icon_path))
            self.btn_load.setIconSize(QSize(24, 24))
            
        
        self.btn_export = QPushButton("  EXPORTAR PDF")
        self.btn_export.setProperty("class", "MetaActionButton")  # Azul
        self.btn_export.clicked.connect(self.exportar_pdf_action)
        self.btn_export.setFixedSize(200, 50)
        self.btn_export.setEnabled(False) # Disabled until data is loaded
        # Attempt to load icon
        pdf_icon_path = os.path.join(BASE_DIR, "pdf.png")
        if os.path.exists(pdf_icon_path):
            self.btn_export.setIcon(QIcon(pdf_icon_path))
            self.btn_export.setIconSize(QSize(24, 24))

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_load)
        btn_layout.addSpacing(15)
        btn_layout.addWidget(self.btn_export)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # --- CONTENEDOR HORIZONTAL: Resultados (izq) + Gráfico (der) ---
        content_layout = QHBoxLayout()
        
        # Columna izquierda: Área de resultados + Botones de acceso rápido
        left_column = QVBoxLayout()
        
        # --- ÁREA DE ERRORES (Solo visible en fallo) ---
        self.resultado_container = QFrame()
        self.resultado_container.setProperty("class", "ResultBox")
        resultado_container_layout = QVBoxLayout(self.resultado_container)
        self.resultado_text = QTextEdit()
        self.resultado_text.setReadOnly(True)
        self.resultado_text.setMinimumHeight(60)
        self.resultado_text.setStyleSheet("border: none; background: transparent;")
        resultado_container_layout.addWidget(self.resultado_text)
        self.resultado_container.hide() # Oculto por defecto
        left_column.addWidget(self.resultado_container)

        # --- CONTENEDOR DE RESULTADOS ELITE (UNIFICADO) ---
        self.elite_results_card = QFrame()
        self.elite_results_card.setObjectName("EliteCard")
        # Estilo premium (Glassmorphism/Elite)
        self.elite_results_card.setStyleSheet("""
            QFrame#EliteCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
                border: 1px solid #e2e8f0;
                border-radius: 15px;
            }
            [theme="dark"] QFrame#EliteCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #0f172a);
                border: 1px solid #334155;
            }
        """)
        
        card_layout = QVBoxLayout(self.elite_results_card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(15)
        
        # Cabecera Elite
        self.infoplaza_title = QLabel("📍 SELECCIONE UN ARCHIVO")
        self.infoplaza_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.infoplaza_title.setStyleSheet("color: #3b82f6;")
        card_layout.addWidget(self.infoplaza_title)
        
        self.periodo_lbl = QLabel("")
        self.periodo_lbl.setFont(QFont("Segoe UI", 10))
        self.periodo_lbl.setStyleSheet("color: #64748b;")
        card_layout.addWidget(self.periodo_lbl)

        # Stats Grid
        stats_layout = QHBoxLayout()
        def create_stat_box(title, icon):
            box = QVBoxLayout()
            lbl_icon = QLabel(icon)
            lbl_icon.setFont(QFont("Segoe UI", 18))
            val = QLabel("0")
            val.setFont(QFont("Segoe UI", 18, QFont.Bold))
            lbl_title = QLabel(title)
            lbl_title.setFont(QFont("Segoe UI", 8, QFont.Bold))
            lbl_title.setStyleSheet("color: #94a3b8; text-transform: uppercase;")
            box.addWidget(lbl_icon, 0, Qt.AlignCenter)
            box.addWidget(val, 0, Qt.AlignCenter)
            box.addWidget(lbl_title, 0, Qt.AlignCenter)
            return box, val

        box_orig, self.val_orig = create_stat_box("Originales", "📝")
        box_comp, self.val_comp = create_stat_box("Compartidas", "🔁")
        box_total, self.val_total = create_stat_box("Total", "📊")
        
        stats_layout.addLayout(box_orig)
        stats_layout.addLayout(box_comp)
        stats_layout.addLayout(box_total)
        card_layout.addLayout(stats_layout)
        
        # Barra de Progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        card_layout.addWidget(self.progress_bar)
        
        self.status_badge = QLabel("LISTO")
        self.status_badge.setFixedHeight(30)
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setFont(QFont("Segoe UI", 9, QFont.Bold))
        card_layout.addWidget(self.status_badge)
        
        self.elite_results_card.hide()
        left_column.addWidget(self.elite_results_card)

        # Indicador visual de zona de arrastre
        self.lbl_drop_hint = QLabel("📂  Suelta el archivo CSV aquí")
        self.lbl_drop_hint.setAlignment(Qt.AlignCenter)
        self.lbl_drop_hint.setFixedSize(600, 200)
        self.lbl_drop_hint.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.lbl_drop_hint.setStyleSheet("color: #3b82f6; background: rgba(59, 130, 246, 0.05); border: 2px dashed #3b82f6; border-radius: 15px;")
        self.lbl_drop_hint.hide()
        left_column.addWidget(self.lbl_drop_hint)
        
        # Botones de acceso rápido debajo del área de resultados
        self.post_export_layout = QHBoxLayout()
        
        self.btn_abrir_archivo = QPushButton("  📄  ABRIR REPORTE (PDF)")
        self.btn_abrir_archivo.setProperty("class", "MetaActionButton")  # Mismo estilo que EXPORTAR PDF
        self.btn_abrir_archivo.setFixedSize(250, 50)
        self.btn_abrir_archivo.clicked.connect(self.abrir_ultimo_archivo)
        self.btn_abrir_archivo.hide()

        self.btn_abrir_carpeta = QPushButton("  📂  ABRIR CARPETA")
        self.btn_abrir_carpeta.setProperty("class", "MetaActionButton")  # Mismo color azul unificado
        self.btn_abrir_carpeta.setFixedSize(250, 50)
        self.btn_abrir_carpeta.clicked.connect(self.abrir_ultima_carpeta)
        self.btn_abrir_carpeta.hide()

        self.post_export_layout.addStretch()
        self.post_export_layout.addWidget(self.btn_abrir_archivo)
        self.post_export_layout.addSpacing(15)
        self.post_export_layout.addWidget(self.btn_abrir_carpeta)
        self.post_export_layout.addStretch()
        left_column.addLayout(self.post_export_layout)
        
        # Espacio flexible para empujar el contenido hacia arriba
        left_column.addStretch()
        
        content_layout.addLayout(left_column, 1)  # Proporción 1
        
        # Columna derecha: Gráfico
        right_column = QVBoxLayout()
        
        # Gráfico de barras
        if Figure and FigureCanvas:
            self.fig = Figure(figsize=(6, 4), dpi=100)
            self.canvas = FigureCanvas(self.fig)
            self.canvas.setMinimumSize(400, 300)
            # Aplicar tema inmediatamente
            if hasattr(self, 'main_app') and self.main_app:
                bg_color = "#1e293b" if self.main_app.is_dark_mode else "#ffffff"
            else:
                bg_color = "#ffffff"
            self.fig.patch.set_facecolor(bg_color)
            right_column.addWidget(self.canvas)
        else:
            # Fallback si matplotlib no está disponible
            placeholder = QLabel("📊 Gráfico no disponible\n(matplotlib no instalado)")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setMinimumSize(400, 300)
            placeholder.setStyleSheet("border: 2px dashed #cbd5e1; border-radius: 8px;")
            right_column.addWidget(placeholder)
        
        content_layout.addLayout(right_column, 1)  # Proporción 1
        
        layout.addLayout(content_layout)

        self.setLayout(layout)

    # =========================================================
    # DRAG & DROP
    # =========================================================
    def dragEnterEvent(self, event):
        """Detecta si se arrastra un archivo CSV."""
        if event.mimeData().hasUrls():
            self.lbl_drop_hint.show()
            if hasattr(self, 'elite_results_card'):
                self.elite_results_card.hide()
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Ocurre cuando el mouse sale del widget."""
        self.lbl_drop_hint.hide()
        if hasattr(self, 'current_results') and self.current_results:
            self.elite_results_card.show()
        event.accept()

    def dropEvent(self, event):
        """Se dispara cuando el usuario suelta el archivo."""
        self.lbl_drop_hint.hide()
        if hasattr(self, 'performance_panel'):
            # This is legacy now, but let's keep it safe or move to elite_results_card
            pass
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ruta = url.toLocalFile()
                if ruta.lower().endswith('.csv'):
                    self._cargar_csv_desde_ruta(ruta)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def _reset_drop_visual(self):
        """Restaura el aspecto normal del recuadro después del arrastre."""
        if hasattr(self, 'lbl_drop_hint'):
            self.lbl_drop_hint.hide()
        if hasattr(self, 'elite_results_card') and self.current_results:
            self.elite_results_card.show()

    def _limpiar_vista(self):
        """Limpia completamente la vista: texto, etiquetas, estado y gráfica."""
        self.current_results = None
        if hasattr(self, 'elite_results_card'):
            self.elite_results_card.hide()
        if hasattr(self, 'resultado_text'):
            self.resultado_text.clear()
        self.infoplaza_title.setText("📍 SELECCIONE UN ARCHIVO")
        self.btn_abrir_archivo.hide()
        self.btn_abrir_carpeta.hide()
        self.btn_export.setEnabled(False)
        # Limpiar gráfica
        if hasattr(self, 'fig') and self.fig:
            self.fig.clear()
            if hasattr(self, 'canvas'):
                self.canvas.draw()

    def _cargar_csv_desde_ruta(self, ruta):
        """Procesa un CSV dado una ruta (igual que el botón CARGAR CSV)."""
        if hasattr(self, 'performance_panel'):
            self.performance_panel.hide()
        if hasattr(self, 'elite_results_card'):
            self.elite_results_card.hide()
            
        try:
            resultado = self.data_processor.analizar_csv(ruta)
            if not resultado:
                raise Exception("El archivo no contiene datos válidos para este módulo.")
        except Exception as e:
            self._limpiar_vista()
            if hasattr(self, 'resultado_text'):
                 self.resultado_container.show()
                 error_html = """
                 <div style='font-family: Segoe UI; font-size: 16px; color: #ef4444;'>
                    <b>⚠️ Información:</b><br>
                    El archivo no es compatible o está dañado.<br>
                    <span style='font-size: 13px; color: #94a3b8;'>(No se pudo leer el archivo CSV)</span>
                 </div>
                 """
                 self.resultado_text.setHtml(error_html)
            return

        self.current_results = resultado
        self._actualizar_ui_con_resultados(resultado)

    # =========================================================
    def analizar_csv(self, ruta_csv):
        try:
            df = pd.read_csv(ruta_csv)
            # Intentar parsear con diferentes formatos si es necesario, 
            # pero asumimos el formato estándar de Facebook que parece manejar el script original.
            df['Fecha'] = pd.to_datetime(df['Hora de publicación'], errors='coerce')

            # Mes y año desde la fecha (en español, completo)
            df['MesNum'] = df['Fecha'].dt.month
            df['Año'] = df['Fecha'].dt.year
            df['Mes'] = df['MesNum'].map(MESES_ES)

            if len(df) > 0:
                # Lógica para extraer nombre de infoplaza del CSV
                first_page_name = str(df['Nombre de la página'].iloc[0])
                parts = first_page_name.split('-')
                nombre_infoplaza = parts[0].strip()
                numero_infoplaza = parts[1].strip() if len(parts) > 1 else ""
            else:
                nombre_infoplaza = ""
                numero_infoplaza = ""

            # Limpieza para columnas calculadas
            df['Infoplaza'] = df['Nombre de la página'].apply(lambda x: str(x).split('-')[0].strip())
            
            # Check column 'Es una publicación cruzada' - Assuming index 10 based on original script 
            # or name if consistent. Original script uses iloc[:, 10]
            if df.shape[1] > 10:
                df['Es una publicación cruzada'] = pd.to_numeric(df.iloc[:, 10], errors='coerce').fillna(0)
            else:
                # Fallback or error handling
                 df['Es una publicación cruzada'] = 0

            total = len(df)
            compartidas = len(df[df['Es una publicación cruzada'] == 1])
            originales = len(df[df['Es una publicación cruzada'] == 0])

            mes = df['Mes'].iloc[0] if not df.empty else 'Desconocido'
            año = int(df['Año'].iloc[0]) if not df.empty else 'Desconocido'

            return {
                'nombre_infoplaza': nombre_infoplaza,
                'numero_infoplaza': numero_infoplaza,
                'total': total,
                'mes': mes,
                'año': año,
                'originales': originales,
                'compartidas': compartidas
            }
        except Exception as e:
            error_msg = str(e)
            if "tokenizing data" in error_msg or "Expected" in error_msg:
                return "El formato del archivo no es reconocido como un CSV de Facebook válido. Verifique el archivo."
            if "EmptyDataError" in error_msg:
                return "El archivo seleccionado está vacío."
            return f"No se pudo procesar el archivo: {error_msg}"

    def _actualizar_ui_con_resultados(self, resultado):
        """Actualiza todos los elementos de la EliteCard con los datos obtenidos."""
        nombre = resultado['nombre_infoplaza']
        numero = resultado['numero_infoplaza']
        total = resultado['total']
        mes = resultado['mes']
        año = resultado['año']
        originales = resultado['originales']
        compartidas = resultado['compartidas']
        
        # Calcular porcentajes
        porc_orig = int((originales / META_ORIGINALES) * 100) if META_ORIGINALES > 0 else 0
        porc_comp = int((compartidas / META_COMPARTIDAS) * 100) if META_COMPARTIDAS > 0 else 0
        
        # 1. Ocultar área de texto (si estaba mostrando errores previos)
        if hasattr(self, 'resultado_text'):
            self.resultado_text.clear()
            self.resultado_container.hide()
        
        # 2. Actualizar Elite Card
        self.infoplaza_title.setText(f"📍 {nombre.upper()} ({numero})")
        self.periodo_lbl.setText(f"Análisis correspondiente a {mes} {año}")
        self.val_orig.setText(str(originales))
        self.val_comp.setText(str(compartidas))
        self.val_total.setText(str(total))
        
        # Calcular Metas Globales
        total_meta = META_ORIGINALES + META_COMPARTIDAS
        total_logrado = originales + compartidas
        porc_total = int((total_logrado / total_meta) * 100) if total_meta > 0 else 0
        
        self.progress_bar.setValue(min(porc_total, 100))
        
        # Determinar Estado
        cumple_pub = originales >= META_ORIGINALES
        cumple_comp = compartidas >= META_COMPARTIDAS
        
        COLOR_ELITE   = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10b981, stop:1 #059669)"
        COLOR_WARNING = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f59e0b, stop:1 #d97706)"
        COLOR_ERROR   = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ef4444, stop:1 #dc2626)"
        
        if cumple_pub and cumple_comp:
            status_text = f"🏆 ¡META CUMPLIDA (ÉLITE)! - {porc_total}%"
            bg_style = COLOR_ELITE
        elif cumple_pub or cumple_comp:
            status_text = f"⚠️ META PARCIAL ALCANZADA - {porc_total}%"
            bg_style = COLOR_WARNING
        else:
            status_text = f"❌ META NO ALCANZADA - {porc_total}%"
            bg_style = COLOR_ERROR
            
        self.status_badge.setText(status_text)
        self.status_badge.setStyleSheet(f"QLabel {{ background: {bg_style}; color: white; border-radius: 10px; }}")
        
        self.elite_results_card.show()
        self.btn_export.setEnabled(True)
        self.actualizar_grafico(originales, compartidas)
        
        # Tracking
        if self.main_app and hasattr(self.main_app, 'bitacora'):
            self.main_app.bitacora.track_activity('facebook_module')
            self.main_app.bitacora.log_intermediate_update()

    def mostrar_resultado(self):
        # ... logic to get ruta ...
        hwnd_int = None
        try: hwnd_int = int(self.winId())
        except: pass
        
        ruta = native_open_file_dialog("Selecciona CSV de Facebook", "Archivos CSV (*.csv)\0*.csv\0\0", hwnd=hwnd_int)
        
        if ruta:
            if hasattr(self, 'elite_results_card'):
                self.elite_results_card.hide()
            try:
                resultado = self.data_processor.analizar_csv(ruta)
                if resultado:
                    self.current_results = resultado
                    self._actualizar_ui_con_resultados(resultado)
                else:
                    raise Exception("No se pudieron procesar los resultados.")
            except Exception as e:
                self._limpiar_vista()
                if hasattr(self, 'resultado_text'):
                    self.resultado_container.show()
                    error_html = """
                    <div style='font-family: Segoe UI; font-size: 16px; color: #ef4444;'>
                        <b>⚠️ Información:</b><br>
                        El archivo no es compatible o está dañado.<br>
                        <span style='font-size: 13px; color: #94a3b8;'>(No se pudo leer el archivo CSV)</span>
                    </div>
                    """
                    self.resultado_text.setHtml(error_html)

    def exportar_pdf_action(self):
        if not self.current_results:
            return
            
        # Generar nombre sugerido según formato solicitado
        nombre_infoplaza = self.current_results['nombre_infoplaza']
        numero_infoplaza = self.current_results['numero_infoplaza']
        mes = self.current_results['mes']
        año = self.current_results['año']

        nombre_sugerido = limpiar_nombre_archivo(
            f"{nombre_infoplaza}_{numero_infoplaza}_{mes}_{año}_AnalisisFacebook.pdf"
        )
            
        archivo_pdf, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", nombre_sugerido, "PDF Files (*.pdf)")
        if archivo_pdf:
            try:
                self.report_builder.generar_pdf(archivo_pdf, self.current_results)
                QMessageBox.information(self, "Éxito", "PDF generado correctamente.")
                
                # --- NUEVA LÓGICA: Guardar ruta y mostrar botones ---
                self.last_export_path = archivo_pdf
                self.btn_abrir_archivo.show()
                self.btn_abrir_carpeta.show()
                
                # --- TRACKING ---
                if self.main_app and hasattr(self.main_app, 'bitacora'):
                     self.main_app.bitacora.track_activity('excel') # Reusamos contador excel para exportaciones
                     self.main_app.bitacora.log_intermediate_update()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo generar el PDF:\n{e}")

    def abrir_ultimo_archivo(self):
        if self.last_export_path and os.path.exists(self.last_export_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_export_path))

    def abrir_ultima_carpeta(self):
        if self.last_export_path and os.path.exists(self.last_export_path):
            # En Windows, podemos usar explorer /select para resaltar el archivo
            path = os.path.normpath(self.last_export_path)
            subprocess.run(['explorer', '/select,', path])


