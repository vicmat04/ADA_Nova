import os
import urllib.parse
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional

import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QDialog, QComboBox, QFormLayout, QMessageBox, QLineEdit,
    QFileDialog, QInputDialog, QFrame, QTextBrowser
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt5.QtGui import QColor, QFont, QCursor, QPalette

from cuatrimestral_supabase_manager import supabase_manager, format_title_case
from database_manager import db

PROVINCIAS_PANAMA = [
    "Bocas del Toro", "Coclé", "Colón", "Chiriquí", "Darién", 
    "Herrera", "Los Santos", "Panamá", "Veraguas", 
    "Panamá Oeste", "Guna Yala", "Emberá-Wounaan", "Ngäbe-Buglé"
]

MESES_CUATRIMESTRE_NOMBRES = {
    1: "Enero a abril",
    2: "Mayo a agosto",
    3: "Septiembre a diciembre"
}


def get_persistent_path(relative_path: str) -> str:
    """Retorna la ruta absoluta segura para archivos empaquetados o en ejecución local."""
    import sys
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, relative_path)


def auto_determinar_cuatrimestre() -> tuple:
    """
    Retorna (año, cuatrimestre_sugerido) según la fecha actual del sistema:
    - Febrero a Junio (meses 2..6) -> C1 (Enero a abril) del año actual
    - Julio a Octubre (meses 7..10) -> C2 (Mayo a agosto) del año actual
    - Noviembre a Enero (meses 11, 12, 1) -> C3 (Septiembre a diciembre)
    """
    now = datetime.now()
    month = now.month
    year = now.year

    if 2 <= month <= 6:
        return year, 1
    elif 7 <= month <= 10:
        return year, 2
    elif month in (11, 12):
        return year, 3
    else:  # Enero
        return year - 1, 3


class SyncControlEntregaThread(QThread):
    finished_sync = pyqtSignal(object, object)  # cloud_data, err

    def __init__(self, anio, cuat, parent=None):
        super().__init__(parent)
        self.anio = anio
        self.cuat = cuat

    def run(self):
        try:
            cloud_data, err = supabase_manager.pull_control_entrega(self.anio, self.cuat)
            self.finished_sync.emit(cloud_data, err)
        except Exception as e:
            self.finished_sync.emit(None, str(e))


def es_infoplaza_cerrada(info: dict) -> bool:
    """Detecta si una Infoplaza está cerrada definitivamente por estatus, estado, condición o nombre."""
    for key in ['activo', 'activa', 'is_active', 'enabled']:
        val = info.get(key)
        if val is False or val == 0 or str(val).lower() == 'false':
            return True

    for key in ['estatus', 'estado', 'status', 'condicion', 'observaciones', 'observacion', 'nombre']:
        val = str(info.get(key, '') or '').lower()
        if 'cerrad' in val or 'inactiv' in val or 'baja' in val or 'definitiv' in val:
            return True

    return False


class InformeCuatrimestralPreviewModal(QDialog):
    """Modal amplio para visualizar la vista previa del informe cuatrimestral de una Infoplaza y permitir generar el PDF."""
    def __init__(self, parent=None, numero=0, anio=2026, cuatrimestre=1, payload_pdf=None, html_content="", is_dark_mode=False):
        super().__init__(parent)
        self.parent_widget = parent
        self.numero = numero
        self.anio = anio
        self.cuatrimestre = cuatrimestre
        self.payload_pdf = payload_pdf or {}
        self.html_content = html_content
        self.is_dark_mode = is_dark_mode
        
        cuat_nombre = MESES_CUATRIMESTRE_NOMBRES.get(cuatrimestre, f"C{cuatrimestre}")
        self.setWindowTitle(f"Vista Previa — Informe Cuatrimestral #{numero} ({cuat_nombre} {anio})")
        self.resize(960, 780)
        self.setMinimumSize(800, 600)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # 1. Cabecera del modal
        header_layout = QHBoxLayout()
        cuat_nombre = MESES_CUATRIMESTRE_NOMBRES.get(self.cuatrimestre, f"Cuatrimestre {self.cuatrimestre}")
        lbl_titulo = QLabel(f"<b>Informe Cuatrimestral — Infoplaza #{self.numero}</b> ({cuat_nombre} {self.anio})")
        lbl_titulo.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(lbl_titulo)
        
        header_layout.addStretch()
        
        lbl_badge = QLabel("☁️ Datos de Supabase")
        lbl_badge.setStyleSheet("font-size: 12px; font-weight: bold; color: #0284c7; background-color: #e0f2fe; border: 1px solid #7dd3fc; border-radius: 6px; padding: 4px 10px;")
        header_layout.addWidget(lbl_badge)
        
        layout.addLayout(header_layout)
        
        # 2. Visor HTML
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        
        # Paleta fija de texto oscuro para QTextBrowser
        browser_palette = self.browser.palette()
        browser_palette.setColor(QPalette.Base, QColor("#ffffff"))
        browser_palette.setColor(QPalette.Text, QColor("#0f172a"))
        browser_palette.setColor(QPalette.WindowText, QColor("#0f172a"))
        self.browser.setPalette(browser_palette)
        
        self.browser.setHtml(self.html_content)
        layout.addWidget(self.browser)
        
        # 3. Pie de página con botones de acción
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(12)
        
        self.btn_generar_pdf = QPushButton("Generar Informe en PDF")
        self.btn_generar_pdf.setCursor(Qt.PointingHandCursor)
        self.btn_generar_pdf.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.btn_generar_pdf.clicked.connect(self.generar_pdf)
        
        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.setCursor(Qt.PointingHandCursor)
        self.btn_cerrar.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        self.btn_cerrar.clicked.connect(self.accept)
        
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_generar_pdf)
        footer_layout.addWidget(self.btn_cerrar)
        
        layout.addLayout(footer_layout)
        
        self.update_theme(self.is_dark_mode)

    def update_theme(self, is_dark: bool = False):
        """La vista previa del informe cuatrimestral se mantiene siempre en Tema Claro para máxima fidelidad visual con el papel/PDF."""
        dialog_bg = "#f1f5f9"
        browser_bg = "#e2e8f0"
        browser_border = "#cbd5e1"
        text_color = "#0f172a"
        
        # Asegurar paleta clara en el diálogo completo
        dlg_palette = self.palette()
        dlg_palette.setColor(QPalette.Window, QColor(dialog_bg))
        dlg_palette.setColor(QPalette.WindowText, QColor(text_color))
        dlg_palette.setColor(QPalette.Base, QColor("#ffffff"))
        dlg_palette.setColor(QPalette.Text, QColor(text_color))
        self.setPalette(dlg_palette)
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {dialog_bg};
                color: {text_color};
            }}
            QLabel {{
                color: {text_color};
            }}
            QTextBrowser {{
                background-color: {browser_bg};
                color: {text_color};
                border: 1px solid {browser_border};
                border-radius: 8px;
                padding: 12px;
            }}
            QScrollBar:vertical {{
                background: #e2e8f0;
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: #94a3b8;
                border-radius: 5px;
                min-height: 25px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #64748b;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

    def generar_pdf(self):
        """Genera el PDF del informe cuatrimestral usando WeasyPrint."""
        app = None
        curr = self.parent_widget
        while curr is not None:
            if hasattr(curr, 'generar_pdf_cuatrimestral') and callable(getattr(curr, 'generar_pdf_cuatrimestral')):
                app = curr
                break
            if hasattr(curr, 'main_app') and hasattr(curr.main_app, 'generar_pdf_cuatrimestral') and callable(getattr(curr.main_app, 'generar_pdf_cuatrimestral')):
                app = curr.main_app
                break
            curr = getattr(curr, 'parent_app', None) or (curr.parent() if hasattr(curr, 'parent') else None)
            
        if app:
            app.generar_pdf_cuatrimestral(self.payload_pdf)
        else:
            self._generar_pdf_directo()

    def _generar_pdf_directo(self):
        try:
            import weasyprint
            import re
            
            infoplaza_id = str(self.payload_pdf.get('infoplaza_id', self.numero))
            infoplaza_info = self.payload_pdf.get('infoplaza_info', {})
            nombre_raw = infoplaza_info.get('nombre') or ''
            nombre_clean = re.sub(r'[\\/*?:"<>|]', '', str(nombre_raw)).strip().replace(' ', '_') or "Infoplaza"
            
            anio = self.payload_pdf.get('anio', self.anio)
            cuat = self.payload_pdf.get('cuatrimestre', self.cuatrimestre)
            
            now_dt = datetime.now()
            meses_abr = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}
            dia_str = now_dt.strftime("%d")
            mes_str = meses_abr.get(now_dt.month, now_dt.strftime("%b"))
            hora_str = now_dt.strftime("%I%M%p").lower()
            stamp = f"{dia_str}{mes_str}-{hora_str}"
            
            nombre_sugerido = f"Informe_{infoplaza_id}_{nombre_clean}_C{cuat}-{anio}_{stamp}.pdf"
            
            ruta_pdf, _ = QFileDialog.getSaveFileName(
                self, "Guardar Informe Cuatrimestral (PDF)",
                nombre_sugerido,
                "Archivos PDF (*.pdf);;Todos los archivos (*)"
            )
            if ruta_pdf:
                base_dir = os.path.dirname(get_persistent_path('informe_cuatrimestral_template.html'))
                weasyprint.HTML(string=self.html_content, base_url=base_dir).write_pdf(ruta_pdf)
                QMessageBox.information(self, "PDF Generado", f"El informe se generó exitosamente en:\n{ruta_pdf}")
        except Exception as e:
            QMessageBox.critical(self, "Error al generar PDF", f"No se pudo generar el PDF:\n{str(e)}")



class InfoplazaEditModal(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.data = data or {}
        self.setWindowTitle(f"Editar Infoplaza #{self.data.get('numero', '')}")
        self.setMinimumWidth(550)
        
        is_dark = False
        if parent:
            if hasattr(parent, 'is_dark_mode'):
                is_dark = parent.is_dark_mode
            elif hasattr(parent, 'property') and parent.property("theme") == "dark":
                is_dark = True
                
        text_color = "#f1f5f9" if is_dark else "#334155"
        combo_bg = "#1e293b" if is_dark else "#ffffff"
        combo_border = "#475569" if is_dark else "#cbd5e1"
        btn_cancel_bg = "#334155" if is_dark else "#e2e8f0"
        btn_cancel_hover = "#475569" if is_dark else "#cbd5e1"
        dialog_bg = "#0f172a" if is_dark else "#ffffff"
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {dialog_bg};
            }}
            QLabel {{
                font-size: 15px;
                color: {text_color};
            }}
            QComboBox {{
                font-size: 14px;
                padding: 6px;
                min-height: 30px;
                color: {text_color};
                background-color: {combo_bg};
                border: 1px solid {combo_border};
                border-radius: 4px;
            }}
            QPushButton {{
                font-size: 14px;
                font-weight: bold;
                padding: 8px 20px;
                min-width: 130px;
                border-radius: 6px;
            }}
            QPushButton#btn_save {{
                background-color: #10b981;
                color: white;
                border: none;
            }}
            QPushButton#btn_save:hover {{
                background-color: #059669;
            }}
            QPushButton#btn_cancel {{
                background-color: {btn_cancel_bg};
                color: {text_color};
                border: none;
            }}
            QPushButton#btn_cancel:hover {{
                background-color: {btn_cancel_hover};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Info header
        lbl_info = QLabel(f"<b>{self.data.get('nombre', '')}</b>")
        lbl_info.setAlignment(Qt.AlignCenter)
        header_font = QFont()
        header_font.setPointSize(13)
        lbl_info.setFont(header_font)
        lbl_info.setContentsMargins(0, 0, 0, 10)
        layout.addWidget(lbl_info)
        
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # Provincia (ComboBox normal)
        self.combo_provincia = QComboBox()
        self.combo_provincia.addItems([""] + sorted(PROVINCIAS_PANAMA))
        prov = self.data.get('provincia') or ""
        if prov in PROVINCIAS_PANAMA:
            self.combo_provincia.setCurrentText(prov)
        else:
            self.combo_provincia.setCurrentText("")
            
        # Distrito (ComboBox editable)
        self.combo_distrito = QComboBox()
        self.combo_distrito.setEditable(True)
        self.combo_distrito.setCurrentText(self.data.get('distrito') or "")
        
        # Corregimiento (ComboBox editable)
        self.combo_corregimiento = QComboBox()
        self.combo_corregimiento.setEditable(True)
        self.combo_corregimiento.setCurrentText(self.data.get('corregimiento') or "")
        
        form_layout.addRow("Provincia:", self.combo_provincia)
        form_layout.addRow("Distrito:", self.combo_distrito)
        form_layout.addRow("Corregimiento:", self.combo_corregimiento)
        
        layout.addLayout(form_layout)
        layout.addSpacing(10)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        btn_save = QPushButton("Guardar Cambios")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self.accept)
        btn_save.setDefault(True) 
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
    def get_data(self):
        return {
            "provincia": self.combo_provincia.currentText().strip(),
            "distrito": self.combo_distrito.currentText().strip(),
            "corregimiento": self.combo_corregimiento.currentText().strip()
        }


class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class NoScrollComboBox(QComboBox):
    """QComboBox que ignora el evento de la rueda del mouse (wheelEvent) para evitar cambios accidentales al hacer scroll en la tabla."""
    def wheelEvent(self, event):
        event.ignore()


class InfoplazasTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.regional = ""
        self.all_infoplazas = []
        self.current_displayed_list = []
        self.control_data = {}  # {infoplaza_numero: {'estado': 'Pendiente', 'motivo': ''}}
        self.cerradas_count = 0
        self.showing_only_incomplete = False
        self.is_dark_mode = False
        
        # Período por defecto
        sug_anio, sug_cuat = auto_determinar_cuatrimestre()
        self.selected_anio = sug_anio
        self.selected_cuat = sug_cuat
        
        self.setup_ui()
        
        # Temporizador para sincronización periódica en segundo plano con Supabase (cada 12s)
        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(12000)
        self.sync_timer.timeout.connect(self._sync_control_entrega_silencioso)
        self.sync_timer.start()
        
    def showEvent(self, event):
        super().showEvent(event)
        old_anio = getattr(self, 'selected_anio', 0)
        old_cuat = getattr(self, 'selected_cuat', 0)
        
        self.selected_anio = self.get_selected_anio()
        self.selected_cuat = self.get_selected_cuat()
        
        period_changed = (old_anio != self.selected_anio or old_cuat != self.selected_cuat)
        
        if not self.all_infoplazas or self.table.rowCount() == 0 or period_changed:
            self.load_data()
            QTimer.singleShot(150, self._sync_control_entrega_silencioso)
        else:
            # Refresh control statuses without rebuilding rows (0 ms)
            self._cargar_control_entrega_local()
            is_dark = getattr(self, 'is_dark_mode', False)
            for row in range(self.table.rowCount()):
                item_num = self.table.item(row, 0)
                if not item_num:
                    continue
                try:
                    num = int(item_num.text())
                except ValueError:
                    continue
                
                ctrl = self.control_data.get(num, {'estado': 'Pendiente', 'motivo': ''})
                estado = ctrl.get('estado', 'Pendiente')
                motivo = ctrl.get('motivo', '')
                
                widget_combo = self.table.cellWidget(row, 7)
                if isinstance(widget_combo, QComboBox) and widget_combo.currentText() != estado:
                    widget_combo.blockSignals(True)
                    widget_combo.setCurrentText(estado)
                    self._aplicar_estilo_combo_status(widget_combo, estado, is_dark)
                    widget_combo.blockSignals(False)
                    
                item_motivo = self.table.item(row, 8)
                if item_motivo and item_motivo.text() != motivo:
                    item_motivo.setText(motivo)
                    
            self.actualizar_kpis()
            QTimer.singleShot(150, self._sync_control_entrega_silencioso)

    def _crear_kpi_card(self, titulo: str, valor: str, kpi_type: str = "total") -> QFrame:
        """Crea una tarjeta KPI equilibrada, compacta y sin recortes."""
        card = QFrame()
        card.setObjectName(f"KpiCard_{kpi_type}")
        card.setProperty("kpi_type", kpi_type)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(1)
        layout.setAlignment(Qt.AlignCenter)
        
        lbl_t = QLabel(titulo)
        lbl_t.setAlignment(Qt.AlignCenter)
        lbl_t.setStyleSheet("font-size: 10.5px; font-weight: 800; text-transform: uppercase;")
        
        lbl_v = QLabel(valor)
        lbl_v.setAlignment(Qt.AlignCenter)
        lbl_v.setStyleSheet("font-size: 17px; font-weight: bold;")
        
        layout.addWidget(lbl_t)
        layout.addWidget(lbl_v)
        
        card.lbl_t = lbl_t
        card.lbl_v = lbl_v
        return card

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # =========================================================================
        # HEADER BAR: TÍTULO, KPIS Y BOTONES (Filtros de Período gobernados por Header Principal)
        # =========================================================================
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        header_layout.setAlignment(Qt.AlignVCenter)
        
        # 1. Título Regional
        self.lbl_title = QLabel("Catálogo Maestro de Infoplazas")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(self.lbl_title)
        
        header_layout.addSpacing(10)
        
        # 2. KPIs Superiores
        self.card_total = self._crear_kpi_card("Total Infoplazas", "0", "total")
        self.card_entregan = self._crear_kpi_card("Entregan Informe", "0", "entregan")
        self.card_no_entregan = self._crear_kpi_card("No Entregan", "0", "no_entregan")
        self.card_entregados = self._crear_kpi_card("Entregados", "0", "entregados")
        self.card_pendientes = self._crear_kpi_card("Pendientes", "0", "pendientes")
        
        # Grupo 1: Universo de Infoplazas (Total, Entregan, No Entregan)
        header_layout.addWidget(self.card_total)
        header_layout.addWidget(self.card_entregan)
        header_layout.addWidget(self.card_no_entregan)
        
        # Separador visual entre grupos de KPIs
        self.kpi_separator = QFrame()
        self.kpi_separator.setFrameShape(QFrame.VLine)
        self.kpi_separator.setFrameShadow(QFrame.Plain)
        self.kpi_separator.setFixedWidth(2)
        self.kpi_separator.setStyleSheet("background-color: #cbd5e1; margin: 4px 6px;")
        header_layout.addWidget(self.kpi_separator)
        
        # Grupo 2: Estados de Entrega con Porcentaje (Entregados, Pendientes)
        header_layout.addWidget(self.card_entregados)
        header_layout.addWidget(self.card_pendientes)
        
        header_layout.addStretch()
        
        # 3. Warning Label de Incompletos
        self.lbl_warning = ClickableLabel("")
        self.lbl_warning.setStyleSheet("color: #ef4444; font-weight: bold; background-color: #fee2e2; padding: 5px; border-radius: 4px;")
        self.lbl_warning.setVisible(False)
        self.lbl_warning.clicked.connect(self.toggle_incomplete_filter)
        header_layout.addWidget(self.lbl_warning)
        
        # 4. Botones de Acción: Exportar y Actualizar
        self.btn_exportar = QPushButton("📥 Exportar")
        self.btn_exportar.setCursor(Qt.PointingHandCursor)
        self.btn_exportar.setToolTip("Exportar el cuadro actual a un archivo Excel (.xlsx)")
        self.btn_exportar.clicked.connect(self.exportar_excel)
        header_layout.addWidget(self.btn_exportar)
        
        self.btn_refresh = QPushButton("🔄 Actualizar")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setToolTip("Recargar la lista de Infoplazas y el control de entrega")
        self.btn_refresh.clicked.connect(self.load_data)
        header_layout.addWidget(self.btn_refresh)
        
        layout.addLayout(header_layout)
        
        # =========================================================================
        # TABLA DE CATÁLOGO Y CONTROL DE ENTREGA
        # =========================================================================
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Número", "Nombre", "Regional", "Provincia", "Distrito", "Corregimiento",
            "Año y Cuatrimestre", "Estatus del Informe", "Motivo No Entrega", "Informe"
        ])
        
        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.Interactive)
        h_header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Número
        h_header.setSectionResizeMode(1, QHeaderView.Stretch)          # Nombre
        h_header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Regional
        h_header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Provincia
        h_header.setSectionResizeMode(4, QHeaderView.ResizeToContents) # Distrito
        h_header.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Corregimiento
        h_header.setSectionResizeMode(6, QHeaderView.ResizeToContents) # Año y Cuatrimestre
        h_header.setSectionResizeMode(7, QHeaderView.ResizeToContents) # Estatus
        h_header.setSectionResizeMode(8, QHeaderView.Stretch)          # Motivo
        h_header.setSectionResizeMode(9, QHeaderView.ResizeToContents) # Botón Ver
        
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.on_row_double_clicked)
        
        layout.addWidget(self.table)
        self.update_theme(getattr(self, 'is_dark_mode', False))

    def get_selected_anio(self) -> int:
        if self.parent_app and hasattr(self.parent_app, 'current_anio'):
            return self.parent_app.current_anio
        return getattr(self, 'selected_anio', datetime.now().year)

    def get_selected_cuat(self) -> int:
        if self.parent_app and hasattr(self.parent_app, 'current_cuatrimestre'):
            return self.parent_app.current_cuatrimestre
        return getattr(self, 'selected_cuat', 1)

    def get_periodo_texto(self) -> str:
        anio = self.get_selected_anio()
        cuat = self.get_selected_cuat()
        cuat_nombre = MESES_CUATRIMESTRE_NOMBRES.get(cuat, "Mayo a agosto")
        return f"{anio}, {cuat_nombre}"

    def _on_periodo_changed(self):
        """Maneja el cambio de filtro de año o cuatrimestre disparado desde el Header Principal."""
        self.selected_anio = self.get_selected_anio()
        self.selected_cuat = self.get_selected_cuat()
        self._cargar_control_entrega_local()
        if self.current_displayed_list:
            self.populate_table(self.current_displayed_list)
        elif self.all_infoplazas:
            self.populate_table(self.all_infoplazas)

    def _cargar_control_entrega_local(self):
        """Carga inmediata del control de entregas desde SQLite local (Cache-First, 0 ms de lag)."""
        try:
            self.control_data = db.get_control_entrega_local(self.selected_anio, self.selected_cuat)
        except Exception as e:
            print(f"[CONTROL_ENTREGA_WARN] Error cargando control local: {e}")
            self.control_data = {}

    def _sync_control_entrega_silencioso(self):
        """
        Inicia la consulta a Supabase en un hilo en segundo plano para no bloquear la UI.
        """
        if not self.isVisible() or not getattr(self, 'all_infoplazas', []):
            return

        # Evitar crear múltiples hilos si ya hay uno corriendo
        if hasattr(self, '_sync_thread') and self._sync_thread.isRunning():
            return

        self._sync_thread = SyncControlEntregaThread(self.selected_anio, self.selected_cuat, self)
        self._sync_thread.finished_sync.connect(self._on_sync_finished)
        self._sync_thread.start()

    def _on_sync_finished(self, cloud_data, err):
        """Procesa los datos recibidos del hilo en el hilo principal de la UI."""
        if err or not cloud_data:
            return

        try:
            hay_cambios = False
            for num, item in cloud_data.items():
                nuevo_estado = item.get('estado', 'Pendiente')
                nuevo_motivo = item.get('motivo', '')
                prev = self.control_data.get(num, {})
                prev_estado = prev.get('estado', 'Pendiente')
                prev_motivo = prev.get('motivo', '')

                if nuevo_estado != prev_estado or nuevo_motivo != prev_motivo:
                    hay_cambios = True
                    self.control_data[num] = {'estado': nuevo_estado, 'motivo': nuevo_motivo}
                    db.save_control_entrega_local(num, self.selected_anio, self.selected_cuat, nuevo_estado, nuevo_motivo)

            if hay_cambios:
                is_dark = getattr(self, 'is_dark_mode', False)
                for row in range(self.table.rowCount()):
                    item_num = self.table.item(row, 0)
                    if not item_num:
                        continue
                    try:
                        num = int(item_num.text())
                    except ValueError:
                        continue

                    ctrl = self.control_data.get(num, {'estado': 'Pendiente', 'motivo': ''})
                    estado = ctrl.get('estado', 'Pendiente')
                    motivo = ctrl.get('motivo', '')

                    widget_combo = self.table.cellWidget(row, 7)
                    if isinstance(widget_combo, QComboBox):
                        if widget_combo.currentText() != estado:
                            widget_combo.blockSignals(True)
                            widget_combo.setCurrentText(estado)
                            self._aplicar_estilo_combo_status(widget_combo, estado, is_dark)
                            widget_combo.blockSignals(False)

                    item_motivo = self.table.item(row, 8)
                    if item_motivo:
                        if item_motivo.text() != motivo:
                            item_motivo.setText(motivo)
                    else:
                        self.table.setItem(row, 8, QTableWidgetItem(motivo))

                self.actualizar_kpis()
        except Exception as e:
            print(f"[SYNC_SILENCIOSO_WARN] Error procesando sincronización: {e}")

    def update_theme(self, is_dark: bool = False):
        """Aplica la hoja de estilo según Modo Claro/Oscuro a la cabecera, KPIs, tabla y componentes."""
        self.is_dark_mode = is_dark
        table_bg = "#0f172a" if is_dark else "#ffffff"
        border_card = "#334155" if is_dark else "#cbd5e1"
        text_main = "#f8fafc" if is_dark else "#0f172a"
        text_sub = "#94a3b8" if is_dark else "#475569"
        table_header_bg = "#1e293b" if is_dark else "#f1f5f9"
        table_header_fg = "#38bdf8" if is_dark else "#0284c7"
        table_grid = "#334155" if is_dark else "#e2e8f0"
        selection_bg = "rgba(2, 132, 199, 0.25)" if is_dark else "#e0f2fe"
        selection_fg = "#f8fafc" if is_dark else "#0369a1"
        
        combo_bg = "#1e293b" if is_dark else "#ffffff"
        combo_border = "#475569" if is_dark else "#cbd5e1"
        btn_bg = "#334155" if is_dark else "#f1f5f9"
        btn_border = "#475569" if is_dark else "#cbd5e1"
        btn_hover = "#475569" if is_dark else "#e2e8f0"

        # Estilo de Tabla
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {table_bg};
                color: {text_main};
                gridline-color: {table_grid};
                border: 1px solid {border_card};
                border-radius: 8px;
                font-size: 13px;
            }}
            QHeaderView::section {{
                background-color: {table_header_bg};
                color: {table_header_fg};
                padding: 8px 10px;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid {border_card};
            }}
            QTableWidget::item {{
                padding: 4px 6px;
                color: {text_main};
                border-bottom: 1px solid {table_grid};
            }}
            QTableWidget::item:selected {{
                background-color: {selection_bg};
                color: {selection_fg};
            }}
        """)

        # Estilo de Título de Cabecera
        if hasattr(self, 'lbl_title'):
            self.lbl_title.setStyleSheet(f"color: {text_main}; font-size: 16px; font-weight: bold;")

        # Estilos de Botones de Cabecera
        btn_style = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {text_main};
                border: 1px solid {btn_border};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
        """
        if hasattr(self, 'btn_exportar'):
            self.btn_exportar.setStyleSheet(btn_style)
        if hasattr(self, 'btn_refresh'):
            self.btn_refresh.setStyleSheet(btn_style)

        # Estilos de Tarjetas KPI
        kpi_styles = {
            "total": {
                "dark": {"bg": "#1e293b", "border": "#38bdf8", "text": "#94a3b8", "val": "#38bdf8"},
                "light": {"bg": "#e0f2fe", "border": "#7dd3fc", "text": "#0369a1", "val": "#0284c7"}
            },
            "entregan": {
                "dark": {"bg": "#0f2f3d", "border": "#0284c7", "text": "#7dd3fc", "val": "#38bdf8"},
                "light": {"bg": "#f0fdfa", "border": "#5eead4", "text": "#0f766e", "val": "#0d9488"}
            },
            "entregados": {
                "dark": {"bg": "#064e3b", "border": "#059669", "text": "#a7f3d0", "val": "#4ade80"},
                "light": {"bg": "#dcfce7", "border": "#86efac", "text": "#166534", "val": "#15803d"}
            },
            "no_entregan": {
                "dark": {"bg": "#450a0a", "border": "#991b1b", "text": "#fecaca", "val": "#f87171"},
                "light": {"bg": "#fee2e2", "border": "#fca5a5", "text": "#991b1b", "val": "#b91c1c"}
            },
            "pendientes": {
                "dark": {"bg": "#451a03", "border": "#78350f", "text": "#fde68a", "val": "#fbbf24"},
                "light": {"bg": "#fef3c7", "border": "#fcd34d", "text": "#92400e", "val": "#b45309"}
            }
        }

        cards = [
            ("total", getattr(self, 'card_total', None)),
            ("entregan", getattr(self, 'card_entregan', None)),
            ("entregados", getattr(self, 'card_entregados', None)),
            ("no_entregan", getattr(self, 'card_no_entregan', None)),
            ("pendientes", getattr(self, 'card_pendientes', None))
        ]

        # Estilo del Separador de KPIs
        sep_color = "#334155" if is_dark else "#cbd5e1"
        if hasattr(self, 'kpi_separator') and self.kpi_separator:
            self.kpi_separator.setStyleSheet(f"background-color: {sep_color}; margin: 4px 6px;")

        mode_key = "dark" if is_dark else "light"
        for kpi_key, card in cards:
            if card:
                style_def = kpi_styles[kpi_key][mode_key]
                min_w = "140px" if kpi_key in ("entregados", "pendientes") else "115px"
                card.setStyleSheet(f"""
                    QFrame#KpiCard_{kpi_key} {{
                        background-color: {style_def['bg']};
                        border: 1px solid {style_def['border']};
                        border-radius: 8px;
                        min-width: {min_w};
                    }}
                """)
                if hasattr(card, 'lbl_t'):
                    card.lbl_t.setStyleSheet(f"color: {style_def['text']}; font-size: 10.5px; font-weight: 800; text-transform: uppercase;")
                if hasattr(card, 'lbl_v'):
                    card.lbl_v.setStyleSheet(f"color: {style_def['val']}; font-size: 17px; font-weight: bold;")

        # Re-render de la tabla si ya contiene datos
        if hasattr(self, 'current_displayed_list') and self.current_displayed_list:
            self.populate_table(self.current_displayed_list)
        elif hasattr(self, 'all_infoplazas') and self.all_infoplazas:
            self.populate_table(self.all_infoplazas)

    def set_regional_from_path(self, db_path: str):
        """Mapea la ruta de la base de datos a una regional específica."""
        old_regional = getattr(self, 'regional', "")
        
        if not db_path:
            self.regional = ""
        else:
            path_lower = db_path.lower()
            if "bd_chiriqui" in path_lower or "chiriqui" in path_lower:
                self.regional = "Chiriquí"
            elif "bd_azuero" in path_lower or "azuero" in path_lower:
                self.regional = "Los Santos" 
            elif "bd_veraguas" in path_lower or "veraguas" in path_lower:
                self.regional = "Veraguas"
            elif "bd_panama" in path_lower or "panama" in path_lower or "panamá" in path_lower:
                self.regional = "Panamá"
            else:
                self.regional = ""
                
        if self.regional == old_regional:
            return
            
        if self.regional:
            self.lbl_title.setText(f"Catálogo Maestro - Regional: {self.regional}")
        else:
            self.lbl_title.setText("Catálogo Maestro de Infoplazas (Todas)")
            
        self.load_data()

    def load_data(self):
        """Descarga las Infoplazas desde Supabase (vía caché RAM en 0 ms) y carga los estados de control de entrega."""
        self.table.setRowCount(0)
        self.showing_only_incomplete = False
        
        data, err = supabase_manager.get_infoplazas_by_regional(self.regional)
        if err:
            err_str = str(err)
            if any(x in err_str for x in ("getaddrinfo", "11001", "urlopen", "ConnectionRefused", "timeout")):
                return
            QMessageBox.warning(self, "Error al cargar catálogo",
                "No se pudo obtener el listado de Infoplazas.\n"
                "Verificá tu conexión a internet e intentá nuevamente.")
            return
            
        if self.regional == "Los Santos":
            data_herrera, _ = supabase_manager.get_infoplazas_by_regional("Herrera")
            if data_herrera:
                existing_nums = {x.get('numero') for x in data}
                for h in data_herrera:
                    if h.get('numero') not in existing_nums:
                        data.append(h)
                
        # Filtrar Infoplazas cerradas definitivamente
        activas = [info for info in data if not es_infoplaza_cerrada(info)]
        self.cerradas_count = len(data) - len(activas)
        self.all_infoplazas = sorted(activas, key=lambda x: x.get('numero', 0))
        
        self._cargar_control_entrega_local()
        self.populate_table(self.all_infoplazas)

    def populate_table(self, data_list):
        """Llena la tabla con la información de las Infoplazas, controles de estatus, motivos y botón Ver."""
        self.current_displayed_list = data_list
        self.table.setUpdatesEnabled(False)
        incomplete_count = 0
        try:
            self.table.setRowCount(0)
            is_dark = getattr(self, 'is_dark_mode', False)
            periodo_str = self.get_periodo_texto()
            
            for row_idx, info in enumerate(data_list):
                self.table.insertRow(row_idx)
            
                num = str(info.get('numero', ''))
                num_int = int(info.get('numero', 0)) if str(info.get('numero', '')).isdigit() else 0
                nombre = info.get('nombre', '') or ''
                reg = info.get('regional', '') or ''
                prov = info.get('provincia', '') or ''
                dist = info.get('distrito', '') or ''
                corr = info.get('corregimiento', '') or ''
                
                # Check datos geográficos incompletos
                is_incomplete = not prov or not dist or not corr
                if is_incomplete:
                    incomplete_count += 1
                    
                # Recuperar estado de entrega y motivo guardados localmente
                ctrl_info = self.control_data.get(num_int, {})
                estado_actual = ctrl_info.get('estado', 'Pendiente')
                motivo_actual = ctrl_info.get('motivo', '')
                
                items = [
                    QTableWidgetItem(num),
                    QTableWidgetItem(nombre),
                    QTableWidgetItem(reg),
                    QTableWidgetItem(prov),
                    QTableWidgetItem(dist),
                    QTableWidgetItem(corr),
                    QTableWidgetItem(periodo_str),
                    QTableWidgetItem(""), # Columna 7: Contendrá el QComboBox
                    QTableWidgetItem(motivo_actual),
                    QTableWidgetItem("")  # Columna 9: Contendrá el botón Ver
                ]
                
                for col_idx, item in enumerate(items):
                    if col_idx == 0:
                        item.setData(Qt.UserRole, info)
                    
                    # Resaltar filas incompletas o normales con estilo acorde al tema
                    if is_incomplete:
                        if is_dark:
                            item.setBackground(QColor("#451a03"))
                            item.setForeground(QColor("#fef3c7"))
                        else:
                            item.setBackground(QColor("#fffbeb"))
                            item.setForeground(QColor("#b45309"))
                    else:
                        if is_dark:
                            item.setForeground(QColor("#f8fafc"))
                        else:
                            item.setForeground(QColor("#0f172a"))
                        
                    self.table.setItem(row_idx, col_idx, item)
                
                # Crear y configurar el QComboBox inline para el estatus de entrega (sin scroll de rueda de ratón)
                combo_status = self._crear_combo_status(row_idx, num_int, estado_actual, is_dark)
                self.table.setCellWidget(row_idx, 7, combo_status)
                
                # Crear y configurar el botón Ver (sin íconos)
                btn_ver = QPushButton("Ver")
                btn_ver.setCursor(Qt.PointingHandCursor)
                btn_ver.setToolTip(f"Ver vista previa del informe de la Infoplaza #{num} en Supabase")
                self._aplicar_estilo_btn_ver(btn_ver, is_dark)
                btn_ver.clicked.connect(lambda _, n=num_int, inf=info: self.ver_informe_infoplaza(n, inf))
                self.table.setCellWidget(row_idx, 9, btn_ver)
        finally:
            self.table.setUpdatesEnabled(True)
            
        # Actualizar warning de datos geográficos incompletos
        if incomplete_count > 0:
            self.lbl_warning.setText(f"⚠️ Hay {incomplete_count} Infoplaza(s) con datos incompletos. Clic para filtrar.")
            self.lbl_warning.setVisible(True)
        else:
            self.lbl_warning.setVisible(False)
            
        # Actualizar los KPIs
        self.actualizar_kpis()
        
        if self.parent_app and hasattr(self.parent_app, '_reaplicar_estilos_totales') and hasattr(self.parent_app, 'tab_resumen'):
            self.parent_app._reaplicar_estilos_totales()

    def _aplicar_estilo_btn_ver(self, btn: QPushButton, is_dark: bool):
        """Aplica estilo limpio y acorde al tema al botón Ver de cada fila."""
        bg = "#1e293b" if is_dark else "#e0f2fe"
        fg = "#38bdf8" if is_dark else "#0284c7"
        border = "#38bdf8" if is_dark else "#7dd3fc"
        hover_bg = "#0369a1" if is_dark else "#bae6fd"
        hover_fg = "#ffffff" if is_dark else "#0369a1"
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1.5px solid {border};
                border-radius: 5px;
                padding: 3px 12px;
                font-weight: bold;
                font-size: 12px;
                min-width: 50px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                color: {hover_fg};
            }}
        """)

    def _calcular_visitas_y_rendimiento(self, numero: int, anio: int, cuatrimestre: int, cant_pcs: int) -> tuple:
        """
        Calcula visitas_mes, rendimiento y kpis_cuatrimestre para el informe de la Infoplaza.
        Si hay datos cargados en la aplicación para esta infoplaza o general, los procesa;
        si no, genera la cuadrícula canónica de los 4 meses del cuatrimestre con sus metas y totales.
        """
        meses_cuat = {
            1: ["Enero", "Febrero", "Marzo", "Abril"],
            2: ["Mayo", "Junio", "Julio", "Agosto"],
            3: ["Septiembre", "Octubre", "Noviembre", "Diciembre"]
        }.get(cuatrimestre, ["Mayo", "Junio", "Julio", "Agosto"])

        mes_map_es = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }

        cols = ["MES", "Masculino", "Femenino", "Primaria", "Secundaria", "Universitarios", "Docentes", "Tercera Edad", "Público General", "TOTAL USUARIOS"]
        categorias = {'P': 'Primaria', 'S': 'Secundaria', 'U': 'Universitarios', 'D': 'Docentes', 'TE': 'Tercera Edad', 'PG': 'Público General'}

        # 1. Intentar obtener dataframe de visitas
        df = None
        curr = self.parent_app
        while curr is not None:
            if hasattr(curr, 'data') and curr.data is not None and not curr.data.empty:
                df = curr.data
                break
            if hasattr(curr, 'main_app') and hasattr(curr.main_app, 'data') and curr.main_app.data is not None and not curr.main_app.data.empty:
                df = curr.main_app.data
                break
            curr = getattr(curr, 'parent_app', None) or (curr.parent() if hasattr(curr, 'parent') else None)

        if df is None or df.empty:
            try:
                conn = db.get_connection()
                query = "SELECT datetime as DATETIME, username as USERNAME, itemname as ITEMNAME FROM registros_ventas_cache ORDER BY datetime DESC"
                df_cache = pd.read_sql_query(query, conn)
                conn.close()
                if df_cache is not None and not df_cache.empty:
                    df = df_cache
            except Exception:
                df = None

        df_cuat = None
        if df is not None and not df.empty and 'DATETIME' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['DATETIME']):
                df['DATETIME'] = pd.to_datetime(df['DATETIME'], errors='coerce')
            df_cuat = df[df['DATETIME'].dt.year == anio].copy()
            if not df_cuat.empty and ('SEXO' not in df_cuat.columns or 'TIPO U' not in df_cuat.columns) and 'ITEMNAME' in df_cuat.columns:
                try:
                    from ADA_Nova import analizar_itemname
                    df_cuat = analizar_itemname(df_cuat)
                except Exception:
                    pass

        # 2. Generar visitas_mes y rendimiento
        visitas_mes = []
        rendimiento = []
        tot_visitas = 0
        meta_mensual = cant_pcs * 48
        tot_meta = 0

        totales_cols = {col: 0 for col in cols if col != "MES"}

        for m in meses_cuat:
            row_vals = {col: 0 for col in cols if col != "MES"}
            visitas_m = 0

            if df_cuat is not None and not df_cuat.empty:
                df_m = df_cuat[df_cuat['DATETIME'].dt.month.map(mes_map_es) == m]
                if not df_m.empty:
                    if 'SEXO' in df_m.columns:
                        row_vals["Masculino"] = int((df_m['SEXO'] == 'M').sum())
                        row_vals["Femenino"] = int((df_m['SEXO'] == 'F').sum())
                    if 'TIPO U' in df_m.columns:
                        for k, v in categorias.items():
                            row_vals[v] = int((df_m['TIPO U'] == k).sum())
                    row_vals["TOTAL USUARIOS"] = sum(row_vals[v] for v in categorias.values())
                    if row_vals["TOTAL USUARIOS"] == 0 and len(df_m) > 0:
                        row_vals["TOTAL USUARIOS"] = len(df_m)
                    visitas_m = row_vals["TOTAL USUARIOS"]

            for c in row_vals:
                totales_cols[c] += row_vals[c]

            visitas_mes.append({
                "mes": m,
                "masculino": str(row_vals["Masculino"]),
                "femenino": str(row_vals["Femenino"]),
                "primaria": str(row_vals["Primaria"]),
                "secundaria": str(row_vals["Secundaria"]),
                "universitarios": str(row_vals["Universitarios"]),
                "docentes": str(row_vals["Docentes"]),
                "tercera_edad": str(row_vals["Tercera Edad"]),
                "publico_general": str(row_vals["Público General"]),
                "total_usuarios": str(row_vals["TOTAL USUARIOS"])
            })

            tot_visitas += visitas_m
            tot_meta += meta_mensual
            pct_m = (visitas_m * 30.0) / meta_mensual if meta_mensual > 0 else 0.0

            if pct_m >= 30:
                obs_text = "✅ Cumple"
            elif pct_m >= 20:
                obs_text = "⚠️ Parcial"
            else:
                obs_text = "❌ No cumple"

            rendimiento.append({
                "mes": m,
                "visitas": f"{visitas_m:,}",
                "meta": f"{meta_mensual:,}",
                "porcentaje": f"{pct_m:.2f}%",
                "estado": obs_text
            })

        # Fila TOTAL GENERAL en visitas
        visitas_mes.append({
            "mes": "TOTAL GENERAL",
            "masculino": f"{totales_cols['Masculino']:,}",
            "femenino": f"{totales_cols['Femenino']:,}",
            "primaria": f"{totales_cols['Primaria']:,}",
            "secundaria": f"{totales_cols['Secundaria']:,}",
            "universitarios": f"{totales_cols['Universitarios']:,}",
            "docentes": f"{totales_cols['Docentes']:,}",
            "tercera_edad": f"{totales_cols['Tercera Edad']:,}",
            "publico_general": f"{totales_cols['Público General']:,}",
            "total_usuarios": f"{totales_cols['TOTAL USUARIOS']:,}"
        })

        # Fila TOTAL CUATRIMESTRE en rendimiento
        tot_pct = (tot_visitas / tot_meta) * 30.0 if tot_meta > 0 else 0.0
        if tot_pct >= 30:
            tot_obs_text = "✅ CUMPLE"
        elif tot_pct >= 20:
            tot_obs_text = "⚠️ PARCIAL"
        else:
            tot_obs_text = "❌ NO CUMPLE"

        rendimiento.append({
            "mes": "TOTAL CUATRIMESTRE",
            "visitas": f"{tot_visitas:,}",
            "meta": f"{tot_meta:,}",
            "porcentaje": f"{tot_pct:.2f}%",
            "estado": tot_obs_text
        })

        kpis_cuatrimestre = {
            "masculino": f"{totales_cols['Masculino']:,}",
            "femenino": f"{totales_cols['Femenino']:,}",
            "total_visitas": f"{totales_cols['TOTAL USUARIOS']:,}",
            "cumplimiento_pct": f"{tot_pct:.2f}%",
            "cumplimiento_sub": "Cumplimiento 30% según fórmula cuatrimestral"
        }

        return visitas_mes, rendimiento, kpis_cuatrimestre

    def ver_informe_infoplaza(self, numero: int, info: dict):
        """Descarga de Supabase y muestra la vista previa del informe cuatrimestral con formato idéntico al PDF."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            import jinja2
            anio = self.get_selected_anio()
            cuat = self.get_selected_cuat()
            
            # 1. Obtener datos desde Supabase
            data_informe, _ = supabase_manager.pull_informe_full(numero, anio, cuat)
            master_info, _ = supabase_manager.get_infoplaza(numero)
            
            # Combinar metadatos de la infoplaza
            infoplaza_meta = {
                "numero": numero,
                "nombre": (master_info or {}).get('nombre') or info.get('nombre') or f"Infoplaza #{numero}",
                "provincia": (master_info or {}).get('provincia') or info.get('provincia') or "",
                "distrito": (master_info or {}).get('distrito') or info.get('distrito') or "",
                "corregimiento": (master_info or {}).get('corregimiento') or info.get('corregimiento') or "",
                "regional": (master_info or {}).get('regional') or info.get('regional') or ""
            }
            
            hdr = (data_informe or {}).get('header') or {}
            caps = (data_informe or {}).get('capacitaciones') or []
            srvs = (data_informe or {}).get('servicios') or []
            acts = (data_informe or {}).get('otras_actividades') or []
            
            cant_pcs = int(hdr.get('cant_computadoras', 6)) if hdr else 6
            
            # Totales de capacitaciones
            def _safe_int(v):
                try: return int(v)
                except: return 0
            def _safe_float(v):
                try: return float(v)
                except: return 0.0

            tot_caps = len(caps)
            tot_part = sum(_safe_int(c.get('participantes', 0)) for c in caps)
            tot_hrs = sum(_safe_float(c.get('horas', 0)) for c in caps)
            
            now_dt = datetime.now()
            fecha_generacion_str = now_dt.strftime("%d/%m/%Y a las %I:%M %p")
            
            # 2. Calcular estadísticas de visitas y rendimiento mensual
            visitas_mes, rendimiento, kpis_cuatrimestre = self._calcular_visitas_y_rendimiento(
                numero=numero,
                anio=anio,
                cuatrimestre=cuat,
                cant_pcs=cant_pcs
            )
            
            payload_pdf = {
                "infoplaza_id": numero,
                "infoplaza_info": infoplaza_meta,
                "anio": anio,
                "cuatrimestre": cuat,
                "header": {
                    "cant_computadoras": cant_pcs,
                    "asociado_nombre": hdr.get('asociado_nombre', '') if hdr else '',
                    "asociado_cedula": hdr.get('asociado_cedula', '') if hdr else '',
                    "dinamizador_nombre": hdr.get('dinamizador_nombre', '') if hdr else '',
                    "dinamizador_cedula": hdr.get('dinamizador_cedula', '') if hdr else '',
                    "observaciones_generales": hdr.get('observaciones_generales', '') if hdr else ''
                },
                "fecha_generacion": fecha_generacion_str,
                "capacitaciones": caps,
                "totales_capacitaciones": {
                    "total_actividades": tot_caps,
                    "total_participantes": tot_part,
                    "total_horas": tot_hrs
                },
                "servicios": srvs,
                "otras_actividades": acts,
                "kpis_cuatrimestre": kpis_cuatrimestre,
                "visitas_mes": visitas_mes,
                "rendimiento": rendimiento
            }
            
            # Renderizar plantilla HTML
            template_path = get_persistent_path('informe_cuatrimestral_template.html')
            if not os.path.exists(template_path):
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(self, "Plantilla No Encontrada", "No se encontró el archivo informe_cuatrimestral_template.html.")
                return
                
            with open(template_path, 'r', encoding='utf-8') as f:
                template_source = f.read()
                
            template = jinja2.Template(template_source)
            
            logo_path = get_persistent_path(os.path.join('icons', 'LOGO INFOPLAZAS.png'))
            logo_uri = f"file:///{logo_path.replace(os.sep, '/')}" if os.path.exists(logo_path) else ""
            
            html_content = template.render(
                logo_path=logo_uri,
                infoplaza_id=payload_pdf.get('infoplaza_id'),
                infoplaza_info=payload_pdf.get('infoplaza_info', {}),
                anio=payload_pdf.get('anio'),
                cuatrimestre=payload_pdf.get('cuatrimestre'),
                header=payload_pdf.get('header', {}),
                capacitaciones=payload_pdf.get('capacitaciones', []),
                totales_capacitaciones=payload_pdf.get('totales_capacitaciones', {}),
                servicios=payload_pdf.get('servicios', []),
                otras_actividades=payload_pdf.get('otras_actividades', []),
                kpis_cuatrimestre=payload_pdf.get('kpis_cuatrimestre', {}),
                visitas_mes=payload_pdf.get('visitas_mes', []),
                rendimiento=payload_pdf.get('rendimiento', []),
                fecha_generacion=payload_pdf.get('fecha_generacion', '')
            )
            
            QApplication.restoreOverrideCursor()
            
            modal = InformeCuatrimestralPreviewModal(
                parent=self,
                numero=numero,
                anio=anio,
                cuatrimestre=cuat,
                payload_pdf=payload_pdf,
                html_content=html_content,
                is_dark_mode=getattr(self, 'is_dark_mode', False)
            )
            modal.exec_()
            
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Error al Cargar Vista Previa", f"Ocurrió un error al obtener la vista previa:\n{str(e)}")

    def _crear_combo_status(self, row: int, numero: int, estado: str, is_dark: bool) -> NoScrollComboBox:
        """Crea y estiliza el selector desplegable de estatus de entrega para la fila sin responder al scroll del mouse."""
        combo = NoScrollComboBox()
        combo.addItems(["Pendiente", "Entregado", "No entrega"])
        
        idx = combo.findText(estado)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(0)
            
        combo.setProperty("row", row)
        combo.setProperty("numero", numero)
        self._aplicar_estilo_combo_status(combo, combo.currentText(), is_dark)
        
        # Conectar cambio de estado
        combo.currentTextChanged.connect(lambda nuevo_est, c=combo: self._on_status_changed(c, nuevo_est))
        return combo

    def _aplicar_estilo_combo_status(self, combo: NoScrollComboBox, estado: str, is_dark: bool):
        """Aplica colores distintivos según el estatus de entrega."""
        if estado == "Entregado":
            bg = "#064e3b" if is_dark else "#dcfce7"
            fg = "#4ade80" if is_dark else "#15803d"
            border = "#059669" if is_dark else "#86efac"
        elif estado == "No entrega":
            bg = "#450a0a" if is_dark else "#fee2e2"
            fg = "#f87171" if is_dark else "#b91c1c"
            border = "#991b1b" if is_dark else "#fca5a5"
        else:  # Pendiente
            bg = "#451a03" if is_dark else "#fef3c7"
            fg = "#fbbf24" if is_dark else "#b45309"
            border = "#78350f" if is_dark else "#fcd34d"
            
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {bg};
                color: {fg};
                border: 1.5px solid {border};
                border-radius: 5px;
                padding: 2px 6px;
                font-weight: bold;
                font-size: 12px;
                min-width: 100px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 16px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {"#1e293b" if is_dark else "#ffffff"};
                color: {"#f8fafc" if is_dark else "#0f172a"};
                border: 1px solid {"#475569" if is_dark else "#cbd5e1"};
                selection-background-color: {"#0284c7" if is_dark else "#e0f2fe"};
            }}
        """)

    def _on_status_changed(self, combo: NoScrollComboBox, nuevo_estado: str):
        """Maneja el cambio de estatus de entrega, solicita motivo si es No entrega y guarda en SQLite."""
        row = combo.property("row")
        numero = combo.property("numero")
        if numero is None:
            return
            
        is_dark = getattr(self, 'is_dark_mode', False)
        self._aplicar_estilo_combo_status(combo, nuevo_estado, is_dark)
        
        # Recuperar o inicializar registro previo
        ctrl_prev = self.control_data.get(numero, {})
        motivo_actual = ctrl_prev.get('motivo', '')
        
        if nuevo_estado == "No entrega":
            # Si no tiene motivo o el facilitador lo cambia a No entrega, solicitar motivo
            prompt_texto = f"Ingrese el motivo por el cual la Infoplaza #{numero} no entrega el informe:"
            nuevo_motivo, ok = QInputDialog.getText(
                self,
                "Motivo de No Entrega",
                prompt_texto,
                QLineEdit.Normal,
                motivo_actual
            )
            if ok:
                motivo_actual = nuevo_motivo.strip()
            elif not motivo_actual:
                motivo_actual = "No entrega informe"
        elif nuevo_estado in ("Entregado", "Pendiente"):
            # Si se marca como Entregado o Pendiente, se limpia el motivo de no entrega
            motivo_actual = ""
            
        # Actualizar celda de motivo en la tabla
        item_motivo = self.table.item(row, 8)
        if item_motivo:
            item_motivo.setText(motivo_actual)
        else:
            self.table.setItem(row, 8, QTableWidgetItem(motivo_actual))
            
        # Guardar en SQLite local
        anio = self.get_selected_anio()
        cuat = self.get_selected_cuat()
        db.save_control_entrega_local(numero, anio, cuat, nuevo_estado, motivo_actual)
        
        # Sincronizar en Supabase en la nube
        try:
            supabase_manager.push_control_entrega(numero, anio, cuat, nuevo_estado, motivo_actual)
        except Exception as e:
            print(f"[CONTROL_ENTREGA_WARN] Error enviando a Supabase: {e}")
        
        # Actualizar memoria local de control_data
        self.control_data[numero] = {
            'estado': nuevo_estado,
            'motivo': motivo_actual
        }
        
        # Recalcular KPIs en tiempo real
        self.actualizar_kpis()

    def actualizar_kpis(self):
        """Calcula y actualiza los 5 indicadores KPI superiores según los estatus actuales."""
        total_infoplazas = len(self.current_displayed_list) if self.current_displayed_list else len(self.all_infoplazas)
        
        entregan_count = 0
        entregados_count = 0
        no_entregan_count = 0
        pendientes_count = 0
        
        for info in (self.current_displayed_list or self.all_infoplazas):
            num = int(info.get('numero', 0)) if str(info.get('numero', '')).isdigit() else 0
            ctrl = self.control_data.get(num, {})
            estado = ctrl.get('estado', 'Pendiente')
            
            if estado == "Entregado":
                entregados_count += 1
                entregan_count += 1
            elif estado == "No entrega":
                no_entregan_count += 1
            else:  # Pendiente
                pendientes_count += 1
                entregan_count += 1

        # Base de cálculo para porcentajes (total de infoplazas que deben entregar informe)
        base_calc = entregan_count if entregan_count > 0 else total_infoplazas
        
        if base_calc > 0:
            pct_ent = (entregados_count / base_calc) * 100.0
            pct_pend = (pendientes_count / base_calc) * 100.0
            pct_ent_str = f"{pct_ent:.1f}%".replace(".0%", "%")
            pct_pend_str = f"{pct_pend:.1f}%".replace(".0%", "%")
        else:
            pct_ent_str = "0%"
            pct_pend_str = "0%"
                
        if hasattr(self, 'card_total') and hasattr(self.card_total, 'lbl_v'):
            self.card_total.lbl_v.setText(str(total_infoplazas))
        if hasattr(self, 'card_entregan') and hasattr(self.card_entregan, 'lbl_v'):
            self.card_entregan.lbl_v.setText(str(entregan_count))
        if hasattr(self, 'card_no_entregan') and hasattr(self.card_no_entregan, 'lbl_v'):
            self.card_no_entregan.lbl_v.setText(str(no_entregan_count))
        if hasattr(self, 'card_entregados') and hasattr(self.card_entregados, 'lbl_v'):
            self.card_entregados.lbl_v.setText(f'{entregados_count}&nbsp;&nbsp;<span style="font-size: 12px; font-weight: 700;">({pct_ent_str})</span>')
        if hasattr(self, 'card_pendientes') and hasattr(self.card_pendientes, 'lbl_v'):
            self.card_pendientes.lbl_v.setText(f'{pendientes_count}&nbsp;&nbsp;<span style="font-size: 12px; font-weight: 700;">({pct_pend_str})</span>')

    def exportar_excel(self):
        """Exporta el cuadro completo de Infoplazas y control de entregas a un archivo Excel (.xlsx)."""
        if not self.table.rowCount():
            QMessageBox.warning(self, "Sin datos", "No hay registros en la tabla para exportar.")
            return
            
        anio = self.get_selected_anio()
        cuat = self.get_selected_cuat()
        reg_nombre = self.regional if self.regional else "Todas"
        default_filename = f"Control_Entrega_Informe_{reg_nombre}_{anio}_C{cuat}.xlsx"
        
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Control de Entrega a Excel",
            default_filename,
            "Archivos de Excel (*.xlsx)"
        )
        
        if not path:
            return
            
        try:
            filas = []
            for row in range(self.table.rowCount()):
                num_item = self.table.item(row, 0)
                num = num_item.text() if num_item else ""
                nom = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
                reg = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
                prov = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
                dist = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
                corr = self.table.item(row, 5).text() if self.table.item(row, 5) else ""
                per = self.table.item(row, 6).text() if self.table.item(row, 6) else ""
                
                # Obtener valor del combo widget
                widget_combo = self.table.cellWidget(row, 7)
                estatus = widget_combo.currentText() if isinstance(widget_combo, QComboBox) else "Pendiente"
                
                motivo = self.table.item(row, 8).text() if self.table.item(row, 8) else ""
                
                filas.append({
                    "Número": int(num) if num.isdigit() else num,
                    "Nombre de Infoplaza": nom,
                    "Regional": reg,
                    "Provincia": prov,
                    "Distrito": dist,
                    "Corregimiento": corr,
                    "Año y Cuatrimestre": per,
                    "Estatus de Entrega": estatus,
                    "Motivo No Entrega": motivo
                })
                
            df = pd.DataFrame(filas)
            
            with pd.ExcelWriter(path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="Control de Entrega", index=False)
                
            QMessageBox.information(
                self,
                "Exportación Exitosa",
                f"El cuadro de Control de Entrega ha sido exportado correctamente en:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error al Exportar",
                f"Ocurrió un error al intentar exportar el archivo Excel:\n{str(e)}"
            )

    def toggle_incomplete_filter(self):
        """Alterna el filtro para visualizar únicamente Infoplazas con datos geográficos faltantes."""
        self.showing_only_incomplete = not self.showing_only_incomplete
        
        if self.showing_only_incomplete:
            filtered = [
                info for info in self.all_infoplazas 
                if not info.get('provincia') or not info.get('distrito') or not info.get('corregimiento')
            ]
            self.populate_table(filtered)
            self.lbl_warning.setText("⚠️ Mostrando SOLO incompletos. Clic para ver todos.")
        else:
            self.populate_table(self.all_infoplazas)

    def on_row_double_clicked(self, index):
        """Abre el diálogo modal de edición de datos geográficos o de motivo según la columna."""
        row = index.row()
        col = index.column()
        
        item = self.table.item(row, 0)
        if not item:
            return
            
        info = item.data(Qt.UserRole)
        numero = info.get('numero')
        if not numero:
            return
            
        # Si hace doble clic en la columna de Motivo (Columna 8) y está en "No entrega"
        if col == 8:
            widget_combo = self.table.cellWidget(row, 7)
            if isinstance(widget_combo, QComboBox) and widget_combo.currentText() == "No entrega":
                motivo_actual = self.table.item(row, 8).text() if self.table.item(row, 8) else ""
                nuevo_motivo, ok = QInputDialog.getText(
                    self,
                    "Editar Motivo de No Entrega",
                    f"Motivo por el cual la Infoplaza #{numero} no entrega informe:",
                    QLineEdit.Normal,
                    motivo_actual
                )
                if ok:
                    motivo_actual = nuevo_motivo.strip()
                    self.table.setItem(row, 8, QTableWidgetItem(motivo_actual))
                    anio = self.get_selected_anio()
                    cuat = self.get_selected_cuat()
                    db.save_control_entrega_local(numero, anio, cuat, "No entrega", motivo_actual)
                    self.control_data[int(numero)] = {'estado': 'No entrega', 'motivo': motivo_actual}
                    try:
                        supabase_manager.push_control_entrega(int(numero), anio, cuat, "No entrega", motivo_actual)
                    except Exception as e:
                        print(f"[CONTROL_ENTREGA_WARN] Error enviando motivo a Supabase: {e}")
                return
                
        # Si hace doble clic en la columna de Informe (Columna 9), abre la vista previa
        if col == 9:
            num_int = int(numero) if str(numero).isdigit() else 0
            self.ver_informe_infoplaza(num_int, info)
            return
            
        # Doble clic en cualquier otra celda abre el modal de datos geográficos
        modal = InfoplazaEditModal(self, data=info)
        if modal.exec_() == QDialog.Accepted:
            new_data = modal.get_data()
            
            success, err = supabase_manager.update_infoplaza_master(
                numero=numero,
                provincia=new_data['provincia'],
                distrito=new_data['distrito'],
                corregimiento=new_data['corregimiento']
            )
            
            if success:
                QMessageBox.information(self, "Éxito", f"Infoplaza #{numero} actualizada correctamente.")
                self.load_data()
            else:
                QMessageBox.critical(self, "Error", f"No se pudo actualizar la Infoplaza:\n{err}")

