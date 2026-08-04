"""
Módulo de Interfaz de Usuario para Informe Cuatrimestral
=========================================================
Proporciona la interfaz gráfica completa en PySide6 para que los Dinamizadores
de las Infoplazas alimenten y consulten sus informes cuatrimestrales.
Sombra, responsive, soporte para Modo Claro / Oscuro, cálculo de rendimiento,
sincronización con Supabase y respaldo/restauración cloud post-formateo.
"""

import os
import sys
import re
from datetime import datetime
from typing import Dict, List, Any, Optional

from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer, QUrl
from PyQt5.QtGui import QColor, QFont, QDesktopServices
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QSpinBox, QCheckBox, QTabWidget, QGroupBox, QMessageBox, QFrame,
    QSplitter, QScrollArea, QFileDialog, QSizePolicy, QDialog
)

from database_manager import db
from cuatrimestral_supabase_manager import supabase_manager, format_title_case
from infoplazas_tab_module import InfoplazasTabWidget


DEFAULT_SERVICIOS = [
    "Impresiones a color y blanco y negro",
    "Copias a color y blanco y negro",
    "Capacitaciones presenciales y en línea",
    "Trámites en línea, becas, Panamá Solidario, entre otras",
    "Scanner",
    "Levantamiento de texto"
]

MESES_CUATRIMESTRE = {
    1: ["Enero", "Febrero", "Marzo", "Abril"],
    2: ["Mayo", "Junio", "Julio", "Agosto"],
    3: ["Septiembre", "Octubre", "Noviembre", "Diciembre"]
}


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
    else:  # Enero (month == 1)
        return year - 1, 3


class InformeCuatrimestralPreloaderThread(QThread):
    """Hilo para precargar los datos del informe cuatrimestral en segundo plano al iniciar la app."""
    datos_cargados = pyqtSignal(dict)

    def __init__(self, infoplaza_id: str, anio: int, cuatrimestre: int, parent=None):
        super().__init__(parent)
        self.infoplaza_id = infoplaza_id
        self.anio = anio
        self.cuatrimestre = cuatrimestre

    def run(self):
        try:
            if not self.infoplaza_id:
                return
            data_local = db.get_informe_cuatrimestral_local(
                infoplaza_id=self.infoplaza_id,
                anio=self.anio,
                cuatrimestre=self.cuatrimestre
            )
            self.datos_cargados.emit(data_local or {})
        except Exception as e:
            print(f"[PRELOAD_THREAD_WARN] Error precargando informe cuatrimestral: {e}")


class InformeCuatrimestralSyncThread(QThread):
    """Hilo secundario para realizar la sincronización cloud con Supabase en segundo plano sin congelar la UI."""
    def __init__(self, infoplaza_id: str, anio: int, cuatrimestre: int, header_data: dict, caps: list, srvs: list, acts: list, parent=None):
        super().__init__(parent)
        self.infoplaza_id = infoplaza_id
        self.anio = anio
        self.cuatrimestre = cuatrimestre
        self.header_data = header_data
        self.caps = caps
        self.srvs = srvs
        self.acts = acts

    def run(self):
        try:
            if not self.infoplaza_id:
                return
            num = int(self.infoplaza_id)
            supabase_manager.update_infoplaza_config(
                numero=num,
                cant_computadoras=self.header_data.get('cant_computadoras', 6),
                asociado_nombre=self.header_data.get('asociado_nombre', ''),
                asociado_cedula=self.header_data.get('asociado_cedula', ''),
                dinamizador_nombre=self.header_data.get('dinamizador_nombre', ''),
                dinamizador_cedula=self.header_data.get('dinamizador_cedula', '')
            )
            supabase_manager.push_informe_full(
                infoplaza_numero=num,
                anio=self.anio,
                cuatrimestre=self.cuatrimestre,
                header_data=self.header_data,
                capacitaciones=self.caps,
                servicios=self.srvs,
                otras_actividades=self.acts
            )
        except Exception as e:
            print(f"[BG_SYNC_WARN] Error sincronizando en segundo plano con Supabase: {e}")


def aplicar_estilo_checkbox_srv(chk: QCheckBox, is_dark: bool):
    """Aplica la estilización visual estricta para los checkboxes de la tabla de servicios."""
    border_color = "#475569" if is_dark else "#94a3b8"
    bg_unchecked = "#1e293b" if is_dark else "#ffffff"
    bg_hover = "#334155" if is_dark else "#f0f9ff"

    chk.setStyleSheet(f"""
        QCheckBox {{
            spacing: 0px;
            background: transparent;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
        }}
        QCheckBox::indicator:unchecked {{
            background-color: {bg_unchecked} !important;
            border: 2px solid {border_color} !important;
        }}
        QCheckBox::indicator:unchecked:hover {{
            border-color: #0284c7 !important;
            background-color: {bg_hover} !important;
        }}
        QCheckBox::indicator:checked {{
            background-color: #0284c7 !important;
            border: 2px solid #0284c7 !important;
            image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='3.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='20 6 9 17 4 12'%3E%3C/polyline%3E%3C/svg%3E");
        }}
        QCheckBox::indicator:checked:hover {{
            background-color: #0369a1 !important;
            border-color: #0369a1 !important;
        }}
    """)


class NuevoServicioDialog(QDialog):
    """Diálogo estilizado para agregar/editar un servicio personalizado (Soporta Modo Oscuro/Claro)."""
    def __init__(self, parent=None, is_dark_mode=False, nombre_inicial="", obs_inicial="", es_edicion=False):
        super().__init__(parent)
        self.is_dark_mode = is_dark_mode
        self.es_edicion = es_edicion
        self.servicio_nombre = nombre_inicial
        self.servicio_obs = obs_inicial
        
        self.setWindowTitle("Editar Servicio Personalizado" if self.es_edicion else "Agregar Nuevo Servicio")
        self.setFixedSize(460, 300)
        self.setModal(True)
        
        if self.is_dark_mode:
            bg_dialog = "#0f172a"
            border_dialog = "#334155"
            text_color = "#f8fafc"
            subtext_color = "#94a3b8"
            input_bg = "#1e293b"
            input_border = "#475569"
            btn_cancel_bg = "#334155"
            btn_cancel_text = "#f8fafc"
            btn_cancel_hover = "#475569"
        else:
            bg_dialog = "#ffffff"
            border_dialog = "#cbd5e1"
            text_color = "#0f172a"
            subtext_color = "#64748b"
            input_bg = "#f8fafc"
            input_border = "#cbd5e1"
            btn_cancel_bg = "#f1f5f9"
            btn_cancel_text = "#334155"
            btn_cancel_hover = "#e2e8f0"
            
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_dialog};
                border: 1.5px solid {border_dialog};
                border-radius: 12px;
            }}
            QLabel {{
                color: {text_color};
            }}
            QLineEdit {{
                background-color: {input_bg};
                color: {text_color};
                border: 1.5px solid {input_border};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 500;
            }}
            QLineEdit:focus {{
                border-color: #0284c7;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)
        
        # Header / Título
        title_box = QHBoxLayout()
        icon_lbl = QLabel("✏️" if self.es_edicion else "✨")
        icon_lbl.setStyleSheet("font-size: 22px;")
        
        lbl_title = QLabel(f"<b>{'Editar Servicio Personalizado' if self.es_edicion else 'Agregar Servicio Personalizado'}</b>")
        lbl_title.setStyleSheet(f"font-size: 16px; color: {text_color};")
        title_box.addWidget(icon_lbl)
        title_box.addWidget(lbl_title)
        title_box.addStretch()
        layout.addLayout(title_box)
        
        # Subtítulo descriptivo
        lbl_desc = QLabel("Modificá el nombre u observaciones del servicio personalizado:" if self.es_edicion else "Ingresá el nombre y observaciones del nuevo servicio ofrecido:")
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {subtext_color};")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)
        
        # Campo Nombre del servicio
        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText("Nombre: Ej. Mantenimiento Preventivo de PCs / Asesoría Virtual")
        if nombre_inicial:
            self.txt_nombre.setText(nombre_inicial)
        self.txt_nombre.editingFinished.connect(lambda: self.txt_nombre.setText(format_title_case(self.txt_nombre.text())))
        layout.addWidget(self.txt_nombre)

        # Campo Observaciones del servicio
        self.txt_obs = QLineEdit()
        self.txt_obs.setPlaceholderText("Observaciones (opcional): Ej. Atención los fines de semana")
        if obs_inicial:
            self.txt_obs.setText(obs_inicial)
        self.txt_obs.editingFinished.connect(lambda: self.txt_obs.setText(format_title_case(self.txt_obs.text())))
        layout.addWidget(self.txt_obs)
        
        layout.addSpacing(6)
        
        # Botones de Acción
        btn_box = QHBoxLayout()
        btn_box.setSpacing(12)
        btn_box.addStretch()
        
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_cancel_bg};
                color: {btn_cancel_text};
                font-weight: 600;
                font-size: 13px;
                padding: 8px 18px;
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {btn_cancel_hover};
            }}
        """)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_text = "✔ Guardar Cambios" if self.es_edicion else "➕ Agregar Servicio"
        self.btn_accept = QPushButton(btn_text)
        self.btn_accept.setCursor(Qt.PointingHandCursor)
        self.btn_accept.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: 700;
                font-size: 13px;
                padding: 8px 20px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton:pressed {
                background-color: #075985;
            }
        """)
        self.btn_accept.clicked.connect(self.on_accept)
        
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_accept)
        layout.addLayout(btn_box)

    def on_accept(self):
        text = self.txt_nombre.text().strip()
        obs = self.txt_obs.text().strip()
        if text:
            self.servicio_nombre = format_title_case(text)
            self.servicio_obs = format_title_case(obs)
            self.accept()
        else:
            self.txt_nombre.setFocus()


class ConfirmarPcsDialog(QDialog):
    """Diálogo estilizado para confirmar la cantidad de computadoras antes de emitir el PDF (Modo Oscuro/Claro)."""
    def __init__(self, pcs_actuales=6, parent=None, is_dark_mode=False):
        super().__init__(parent)
        self.is_dark_mode = is_dark_mode
        self.pcs_confirmadas = pcs_actuales
        
        self.setWindowTitle("Confirmar Equipos de la Infoplaza")
        self.setFixedSize(490, 300)
        self.setModal(True)
        
        if self.is_dark_mode:
            bg_dialog = "#0f172a"
            border_dialog = "#334155"
            text_color = "#f8fafc"
            subtext_color = "#94a3b8"
            card_bg = "#1e293b"
            card_border = "#334155"
            badge_bg = "#0369a1"
            badge_text = "#e0f2fe"
            btn_cancel_bg = "#334155"
            btn_cancel_text = "#f8fafc"
            btn_cancel_hover = "#475569"
        else:
            bg_dialog = "#ffffff"
            border_dialog = "#cbd5e1"
            text_color = "#0f172a"
            subtext_color = "#64748b"
            card_bg = "#f8fafc"
            card_border = "#cbd5e1"
            badge_bg = "#e0f2fe"
            badge_text = "#0369a1"
            btn_cancel_bg = "#f1f5f9"
            btn_cancel_text = "#334155"
            btn_cancel_hover = "#e2e8f0"
            
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_dialog};
                border: 1.5px solid {border_dialog};
                border-radius: 12px;
            }}
            QLabel {{
                color: {text_color};
            }}
            QSpinBox {{
                background-color: {card_bg};
                color: {text_color};
                border: 1.5px solid {card_border};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 15px;
                font-weight: bold;
            }}
            QSpinBox:focus {{
                border-color: #0284c7;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        
        # Header / Título
        title_box = QHBoxLayout()
        icon_lbl = QLabel("🖥️")
        icon_lbl.setStyleSheet("font-size: 24px;")
        
        lbl_title = QLabel("<b>Confirmar Cantidad de Computadoras</b>")
        lbl_title.setStyleSheet(f"font-size: 16px; color: {text_color};")
        title_box.addWidget(icon_lbl)
        title_box.addWidget(lbl_title)
        title_box.addStretch()
        layout.addLayout(title_box)
        
        # Explicación de la importancia del 30%
        lbl_desc = QLabel(
            "<b>¡Atención!</b> La cantidad de computadoras operativas define la Meta Mensual "
            "(48 visitas por equipo) y es la base fundamental para el cálculo de la tasa del <b>30% de cumplimiento</b>."
        )
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {subtext_color}; line-height: 1.4;")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)
        
        # Tarjeta de selección de PCs y Meta Live
        card = QFrame()
        card.setStyleSheet(f"background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 10px; padding: 10px;")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        
        lbl_spin_txt = QLabel("<b>Equipos PCs:</b>")
        lbl_spin_txt.setStyleSheet("font-size: 13px;")
        
        self.spin_pcs = QSpinBox()
        self.spin_pcs.setRange(1, 100)
        self.spin_pcs.setValue(pcs_actuales)
        self.spin_pcs.valueChanged.connect(self._actualizar_badge)
        
        self.lbl_badge_meta = QLabel()
        self.lbl_badge_meta.setAlignment(Qt.AlignCenter)
        self.lbl_badge_meta.setStyleSheet(f"background-color: {badge_bg}; color: {badge_text}; font-weight: bold; font-size: 12px; padding: 6px 12px; border-radius: 6px;")
        self._actualizar_badge(pcs_actuales)
        
        card_layout.addWidget(lbl_spin_txt)
        card_layout.addWidget(self.spin_pcs)
        card_layout.addSpacing(10)
        card_layout.addWidget(self.lbl_badge_meta)
        
        layout.addWidget(card)
        
        layout.addSpacing(4)
        
        # Botones
        btn_box = QHBoxLayout()
        btn_box.setSpacing(12)
        btn_box.addStretch()
        
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_cancel_bg};
                color: {btn_cancel_text};
                font-weight: 600;
                font-size: 13px;
                padding: 8px 18px;
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {btn_cancel_hover};
            }}
        """)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_confirm = QPushButton("📄 Confirmar y Generar PDF")
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: 700;
                font-size: 13px;
                padding: 8px 20px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            QPushButton:pressed {
                background-color: #065f46;
            }
        """)
        self.btn_confirm.clicked.connect(self.on_confirm)
        
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_confirm)
        layout.addLayout(btn_box)

    def _actualizar_badge(self, val):
        meta = val * 48
        self.lbl_badge_meta.setText(f"Meta Mensual: {meta:,} visitas")
    def on_confirm(self):
        self.pcs_confirmadas = self.spin_pcs.value()
        self.accept()

    def obtener_pcs(self) -> int:
        return self.pcs_confirmadas


class PdfExitoDialog(QDialog):
    """Diálogo modal moderno de confirmación de exportación de PDF con soporte para tema Claro/Oscuro y aviso de Anexos."""
    def __init__(self, ruta_pdf: str, parent=None, is_dark_mode=False):
        super().__init__(parent)
        self.ruta_pdf = ruta_pdf
        self.is_dark_mode = is_dark_mode

        self.setWindowTitle("Informe PDF Exportado con Éxito")
        self.setMinimumSize(680, 480)
        self.setModal(True)

        if self.is_dark_mode:
            bg_dialog = "#0f172a"
            border_dialog = "#334155"
            text_color = "#f8fafc"
            subtext_color = "#94a3b8"
            path_bg = "#1e293b"
            path_border = "#334155"
            banner_bg = "rgba(245, 158, 11, 0.10)"
            banner_border = "#f59e0b"
            banner_title_color = "#fbbf24"
            banner_text_color = "#cbd5e1"
            btn_sec_bg = "#1e293b"
            btn_sec_fg = "#f8fafc"
            btn_sec_border = "#334155"
            btn_sec_hover = "#334155"
        else:
            bg_dialog = "#ffffff"
            border_dialog = "#cbd5e1"
            text_color = "#0f172a"
            subtext_color = "#475569"
            path_bg = "#f8fafc"
            path_border = "#cbd5e1"
            banner_bg = "#fffbeb"
            banner_border = "#f59e0b"
            banner_title_color = "#b45309"
            banner_text_color = "#78350f"
            btn_sec_bg = "#f1f5f9"
            btn_sec_fg = "#334155"
            btn_sec_border = "#cbd5e1"
            btn_sec_hover = "#e2e8f0"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_dialog};
                border: 1.5px solid {border_dialog};
                border-radius: 12px;
            }}
            QLabel {{
                color: {text_color};
                border: none;
                background: transparent;
            }}
            QPushButton {{
                font-size: 13px;
                font-weight: bold;
                padding: 8px 22px;
                border-radius: 6px;
                min-height: 32px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(20)

        # 1. Encabezado de Éxito con Ícono Destacado
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)
        lbl_icon = QLabel("📄")
        lbl_icon.setStyleSheet("font-size: 38px; border: none;")
        
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        lbl_title = QLabel("¡Informe Cuatrimestral Generado con Éxito!")
        lbl_title.setStyleSheet(f"font-size: 19px; font-weight: bold; color: {text_color}; border: none;")
        lbl_subtitle = QLabel("El archivo PDF fue generado y guardado con éxito.")
        lbl_subtitle.setStyleSheet(f"font-size: 14px; font-weight: 500; color: {subtext_color}; border: none;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_subtitle)

        header_layout.addWidget(lbl_icon)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # 2. Caja estilizada con la Ruta de Guardado
        path_frame = QFrame()
        path_frame.setObjectName("PathFrame")
        path_frame.setStyleSheet(f"""
            QFrame#PathFrame {{
                background-color: {path_bg};
                border: 1px solid {path_border};
                border-radius: 8px;
            }}
        """)
        path_layout = QVBoxLayout(path_frame)
        path_layout.setContentsMargins(14, 12, 14, 12)
        path_layout.setSpacing(6)

        lbl_path_title = QLabel("📍 RUTA DE EXPORTACIÓN DEL DOCUMENTO:")
        lbl_path_title.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {subtext_color}; border: none;")
        
        lbl_path_val = QLabel(self.ruta_pdf)
        lbl_path_val.setWordWrap(True)
        lbl_path_val.setStyleSheet(f"font-size: 12px; font-family: 'Consolas', 'Segoe UI', monospace; color: {text_color}; border: none;")
        
        path_layout.addWidget(lbl_path_title)
        path_layout.addWidget(lbl_path_val)

        layout.addWidget(path_frame)

        # 3. Anuncio / Recordatorio Visual de Anexos Físicos
        banner_frame = QFrame()
        banner_frame.setObjectName("BannerFrame")
        banner_frame.setStyleSheet(f"""
            QFrame#BannerFrame {{
                background-color: {banner_bg};
                border: 1.5px solid {banner_border};
                border-radius: 10px;
            }}
        """)
        banner_layout = QVBoxLayout(banner_frame)
        banner_layout.setContentsMargins(16, 14, 16, 14)
        banner_layout.setSpacing(8)

        lbl_banner_head = QLabel("📌 RECORDATORIO IMPORTANTE PARA ANEXOS FÍSICOS:")
        lbl_banner_head.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {banner_title_color}; border: none;")

        text_anexos = (
            f"Una vez impreso este informe, recuerda adjuntar lo siguiente:<br>"
            f"&nbsp;&nbsp;• <b>Listas de asistencia</b> de las capacitaciones o talleres realizados.<br>"
            f"&nbsp;&nbsp;• <b>Evidencias fotográficas</b> de las capacitaciones y otras actividades relevantes, máximo 2 por actividad.<br>"
            f"&nbsp;&nbsp;• Cualquier otra evidencia que consideres."
        )
        lbl_banner_body = QLabel()
        lbl_banner_body.setTextFormat(Qt.RichText)
        lbl_banner_body.setText(text_anexos)
        lbl_banner_body.setWordWrap(True)
        lbl_banner_body.setStyleSheet(f"font-size: 13px; color: {banner_text_color}; border: none;")

        banner_layout.addWidget(lbl_banner_head)
        banner_layout.addWidget(lbl_banner_body)

        layout.addWidget(banner_frame)

        # 4. Botones de Acción
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        btn_open_folder = QPushButton("📁 Abrir Carpeta")
        btn_open_folder.setCursor(Qt.PointingHandCursor)
        btn_open_folder.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_sec_bg};
                color: {btn_sec_fg};
                border: 1px solid {btn_sec_border};
            }}
            QPushButton:hover {{
                background-color: {btn_sec_hover};
            }}
        """)
        btn_open_folder.clicked.connect(self.abrir_carpeta)

        btn_open_pdf = QPushButton("📖 Abrir PDF")
        btn_open_pdf.setCursor(Qt.PointingHandCursor)
        btn_open_pdf.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                border: 1px solid #059669;
            }
            QPushButton:hover {
                background-color: #047857;
                border-color: #047857;
            }
        """)
        btn_open_pdf.clicked.connect(self.abrir_pdf)

        btn_close = QPushButton("Entendido")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_sec_bg};
                color: {btn_sec_fg};
                border: 1px solid {btn_sec_border};
            }}
            QPushButton:hover {{
                background-color: {btn_sec_hover};
            }}
        """)
        btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(btn_open_folder)
        btn_layout.addWidget(btn_open_pdf)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def abrir_pdf(self):
        if os.path.exists(self.ruta_pdf):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.ruta_pdf))

    def abrir_carpeta(self):
        folder = os.path.dirname(self.ruta_pdf)
        if os.path.exists(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


class _CatalogoSyncWorker(QThread):
    """Worker en background: sincroniza el catálogo con Supabase (fuente de verdad) sin bloquear la UI."""
    sync_done = pyqtSignal()

    def run(self):
        try:
            supabase_manager.sincronizar_catalogo_categorias()
        except Exception as e:
            print(f"[CATALOGO_SYNC] Error en sync background: {e}")
        self.sync_done.emit()


class CatalogoCategoriasDialog(QDialog):
    """
    Modal amplio para administrar el catálogo de categorías de Capacitaciones y Actividades.
    Permite a los Facilitadores (Modo Guerrero) agregar, editar o deshabilitar categorías
    sincronizando directamente con Supabase y el almacenamiento SQLite local.
    """
    def __init__(self, parent=None, is_dark_mode=False, tipo_inicial='CAPACITACION'):
        super().__init__(parent)
        self.parent_module = parent
        self.is_dark_mode = is_dark_mode
        self.tipo_inicial = tipo_inicial
        self.setWindowTitle("⚙️ Gestión del Catálogo de Categorías — Modo Facilitador")
        self.resize(980, 640)
        self.editing_id_cap = None
        self.editing_id_act = None

        self._setup_ui()
        self.cargar_datos()

    def _setup_ui(self):

        is_dark = self.is_dark_mode
        bg_color = "#0f172a" if is_dark else "#f8fafc"
        text_color = "#f8fafc" if is_dark else "#0f172a"
        card_bg = "#1e293b" if is_dark else "#ffffff"
        border_color = "#334155" if is_dark else "#cbd5e1"
        selection_bg = "rgba(2, 132, 199, 0.25)" if is_dark else "#e0f2fe"
        selection_fg = "#38bdf8" if is_dark else "#0369a1"
        table_grid = border_color
        table_bg = card_bg
        text_main = text_color
        header_bg = "#1e293b" if is_dark else "#e2e8f0"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
                font-family: 'Segoe UI', system-ui, sans-serif;
            }}
            QTabWidget::pane {{
                border: 1px solid {border_color};
                border-radius: 8px;
                background: {card_bg};
            }}
            QTabBar::tab {{
                background: {"#1e293b" if self.is_dark_mode else "#e2e8f0"};
                color: {text_color};
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                min-width: 240px;
            }}

            QTabBar::tab:selected {{
                background: #0284c7;
                color: white;
            }}
            QGroupBox {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 8px;
                margin-top: 10px;
                font-weight: bold;
                color: {text_color};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QLineEdit, QSpinBox {{
                padding: 6px 10px;
                border-radius: 4px;
                border: 1px solid {border_color};
                background: {"#0f172a" if self.is_dark_mode else "#ffffff"};
                color: {text_color};
                font-size: 13px;
            }}
            QTableWidget {{
                background-color: {table_bg};
                border: 1px solid {border_color};
                gridline-color: {table_grid};
                color: {text_main};
                border-radius: 6px;
                font-size: 13px;
            }}
            QHeaderView::section {{
                background-color: {header_bg};
                color: {text_main};
                font-weight: bold;
                padding: 8px 12px;
                border: none;
                border-bottom: 2px solid {border_color};
            }}
            QTableWidget::item {{
                padding: 6px 8px;
                color: {text_main};
                border-bottom: 1px solid {table_grid};
            }}
            QTableWidget::item:selected {{
                background-color: {selection_bg};
                color: {selection_fg};
            }}
            QTableWidget::item:focus {{
                background-color: {selection_bg};
                outline: none;
            }}
            QTableWidget QLineEdit {{
                background-color: {"#0f172a" if is_dark else "#ffffff"};
                color: {text_main};
                border: 2px solid #0284c7;
                border-radius: 4px;
                margin: 0px;
                padding: 4px 6px;
                font-size: 13px;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Header Info
        header_lbl = QLabel("<b>Catálogo Maestro de Categorías de Infoplazas (Modo Facilitador)</b><br><i>Edita y administra el catálogo oficial. Los cambios se sincronizan en Supabase y SQLite local.</i>")
        header_lbl.setWordWrap(True)
        layout.addWidget(header_lbl)

        # Tabs Widget
        self.tabs = QTabWidget()
        
        # Tab 1: Capacitaciones
        self.tab_cap = self._crear_tab_gestion("CAPACITACION")
        self.tabs.addTab(self.tab_cap, "🎓 Categorías de Capacitaciones")

        # Tab 2: Actividades
        self.tab_act = self._crear_tab_gestion("ACTIVIDAD")
        self.tabs.addTab(self.tab_act, "🏛️ Categorías de Otras Actividades")

        if self.tipo_inicial == "ACTIVIDAD":
            self.tabs.setCurrentIndex(1)
        else:
            self.tabs.setCurrentIndex(0)

        layout.addWidget(self.tabs)

        # Botón Cerrar
        btn_close = QPushButton("Cerrar")
        btn_close.setStyleSheet("background-color: #64748b; color: white; font-weight: bold; padding: 8px 24px; border-radius: 4px; font-size: 13px;")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        
        b_box = QHBoxLayout()
        b_box.addStretch()
        b_box.addWidget(btn_close)
        layout.addLayout(b_box)

    def _crear_tab_gestion(self, tipo: str) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(10, 10, 10, 10)
        l.setSpacing(10)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Orden", "Categoría / Nombre", "Descripción / Alcance", "Estado", "Acción"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        table.setColumnWidth(0, 65)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        table.setColumnWidth(3, 85)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        table.setColumnWidth(4, 200)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(42)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.cellDoubleClicked.connect(lambda row, col, t=tipo: self._on_cell_double_clicked(t, row))

        l.addWidget(table)

        # Form para Crear / Editar (Estructurado en 2 filas limpias)
        gbox = QGroupBox(f"➕ Agregar / Editar Categoría ({'Capacitaciones' if tipo == 'CAPACITACION' else 'Actividades'})")
        gbox_layout = QVBoxLayout(gbox)
        gbox_layout.setContentsMargins(12, 12, 12, 12)
        gbox_layout.setSpacing(10)

        row1 = QHBoxLayout()
        spin_orden = QSpinBox()
        spin_orden.setRange(1, 99)
        spin_orden.setValue(1)
        spin_orden.setFixedWidth(65)

        txt_nom = QLineEdit()
        txt_nom.setPlaceholderText("Ej. Computación Básica / Ferias y Exposiciones")

        chk_act = QCheckBox("Categoría Activa")
        chk_act.setChecked(True)

        row1.addWidget(QLabel("Orden:"))
        row1.addWidget(spin_orden)
        row1.addSpacing(10)
        row1.addWidget(QLabel("Nombre:"))
        row1.addWidget(txt_nom, 1)
        row1.addSpacing(10)
        row1.addWidget(chk_act)

        row2 = QHBoxLayout()
        txt_desc = QLineEdit()
        txt_desc.setPlaceholderText("Descripción o ejemplos de lo que abarca esta categoría...")

        btn_save = QPushButton("💾 Guardar Categoría")
        btn_save.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 7px 18px; border-radius: 4px; font-size: 13px;")
        btn_save.setCursor(Qt.PointingHandCursor)

        row2.addWidget(QLabel("Descripción:"))
        row2.addWidget(txt_desc, 1)
        row2.addSpacing(10)
        row2.addWidget(btn_save)

        gbox_layout.addLayout(row1)
        gbox_layout.addLayout(row2)

        l.addWidget(gbox)

        if tipo == "CAPACITACION":
            self.table_cap_cat = table
            self.spin_cap_orden = spin_orden
            self.txt_cap_nom = txt_nom
            self.txt_cap_desc = txt_desc
            self.chk_cap_act = chk_act
            self.btn_cap_save = btn_save
            btn_save.clicked.connect(lambda: self._guardar_categoria("CAPACITACION"))
        else:
            self.table_act_cat = table
            self.spin_act_orden = spin_orden
            self.txt_act_nom = txt_nom
            self.txt_act_desc = txt_desc
            self.chk_act_act = chk_act
            self.btn_act_save = btn_save
            btn_save.clicked.connect(lambda: self._guardar_categoria("ACTIVIDAD"))

        return w

    def _on_cell_double_clicked(self, tipo: str, row: int):
        cats = db.get_catalogo_categorias_local(tipo)
        if 0 <= row < len(cats):
            self._preparar_edicion(tipo, cats[row])

    def cargar_datos(self):
        # 1. Carga inmediata desde SQLite local — UI responde sin esperar red
        cats_cap = db.get_catalogo_categorias_local("CAPACITACION")
        cats_act = db.get_catalogo_categorias_local("ACTIVIDAD")
        self._render_tabla("CAPACITACION", cats_cap)
        self._render_tabla("ACTIVIDAD", cats_act)

        if self.editing_id_cap is None:
            self.spin_cap_orden.setValue(self._next_orden("CAPACITACION"))
        if self.editing_id_act is None:
            self.spin_act_orden.setValue(self._next_orden("ACTIVIDAD"))

        if self.parent_module and hasattr(self.parent_module, 'cargar_catalogos_categorias'):
            self.parent_module.cargar_catalogos_categorias()

        # 2. Supabase es la fuente de verdad: sync en background, sin congelar la UI
        self._sync_worker = _CatalogoSyncWorker()
        self._sync_worker.sync_done.connect(self._on_sync_done)
        self._sync_worker.start()

    def _on_sync_done(self):
        """Refresca la tabla cuando el sync con Supabase termina en background."""
        cats_cap = db.get_catalogo_categorias_local("CAPACITACION")
        cats_act = db.get_catalogo_categorias_local("ACTIVIDAD")
        self._render_tabla("CAPACITACION", cats_cap)
        self._render_tabla("ACTIVIDAD", cats_act)

        if self.editing_id_cap is None:
            self.spin_cap_orden.setValue(self._next_orden("CAPACITACION"))
        if self.editing_id_act is None:
            self.spin_act_orden.setValue(self._next_orden("ACTIVIDAD"))

        if self.parent_module and hasattr(self.parent_module, 'cargar_catalogos_categorias'):
            self.parent_module.cargar_catalogos_categorias()

    def _render_tabla(self, tipo: str, categorias: List[Dict[str, Any]]):
        table = self.table_cap_cat if tipo == "CAPACITACION" else self.table_act_cat
        table.setRowCount(0)

        for c in categorias:
            row = table.rowCount()
            table.insertRow(row)

            cid = c.get('id')
            orden = c.get('orden', 0)
            nombre = c.get('nombre', '')
            desc = c.get('descripcion', '')
            activo = bool(c.get('activo', True))

            item_ord = QTableWidgetItem(str(orden))
            item_nom = QTableWidgetItem(nombre)
            item_desc = QTableWidgetItem(desc)
            item_est = QTableWidgetItem("Activo" if activo else "Inactivo")

            item_ord.setTextAlignment(Qt.AlignCenter)
            item_est.setTextAlignment(Qt.AlignCenter)

            if self.is_dark_mode:
                item_ord.setForeground(QColor("#38bdf8"))
                item_nom.setForeground(QColor("#f8fafc"))
                item_desc.setForeground(QColor("#cbd5e1"))
                item_est.setForeground(QColor("#34d399") if activo else QColor("#f87171"))
            else:
                item_ord.setForeground(QColor("#0284c7"))
                item_nom.setForeground(QColor("#0f172a"))
                item_desc.setForeground(QColor("#475569"))
                item_est.setForeground(QColor("#059669") if activo else QColor("#dc2626"))

            tooltip = f"📝 {desc}" if desc.strip() else "Sin descripción"

            item_ord.setToolTip(tooltip)
            item_nom.setToolTip(tooltip)
            item_desc.setToolTip(tooltip)
            item_est.setToolTip(tooltip)

            table.setItem(row, 0, item_ord)
            table.setItem(row, 1, item_nom)
            table.setItem(row, 2, item_desc)
            table.setItem(row, 3, item_est)

            btn_edit = QPushButton("✏️ Editar")
            btn_edit.setCursor(Qt.PointingHandCursor)
            btn_edit.setFixedHeight(28)
            btn_edit.setFixedWidth(85)
            btn_edit.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12px;
                    border: none;
                    border-radius: 4px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #0369a1;
                }
            """)
            btn_edit.clicked.connect(lambda _, item_cat=c, t=tipo: self._preparar_edicion(t, item_cat))

            btn_del = QPushButton("🗑️ Eliminar")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setFixedHeight(28)
            btn_del.setFixedWidth(90)
            btn_del.setStyleSheet("""
                QPushButton {
                    background-color: #dc2626;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12px;
                    border: none;
                    border-radius: 4px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #b91c1c;
                }
            """)
            btn_del.clicked.connect(lambda _, item_cat=c, t=tipo: self._eliminar_categoria(t, item_cat))

            btn_box = QWidget()
            bl = QHBoxLayout(btn_box)
            bl.setContentsMargins(2, 0, 2, 0)
            bl.setSpacing(4)
            bl.setAlignment(Qt.AlignCenter)
            bl.addWidget(btn_edit)
            bl.addWidget(btn_del)

            table.setCellWidget(row, 4, btn_box)



    def _next_orden(self, tipo: str) -> int:
        """Devuelve el siguiente número de orden (max actual + 1) para el tipo dado."""
        cats = db.get_catalogo_categorias_local(tipo)
        if not cats:
            return 1
        return max(int(c.get('orden', 0)) for c in cats) + 1

    def _reset_form(self, tipo: str):
        """Limpia el formulario y fija el orden al siguiente disponible."""
        next_ord = self._next_orden(tipo)
        if tipo == "CAPACITACION":
            self.editing_id_cap = None
            self.txt_cap_nom.clear()
            self.txt_cap_desc.clear()
            self.spin_cap_orden.setValue(next_ord)
            self.chk_cap_act.setChecked(True)
            self.btn_cap_save.setText("💾 Guardar Categoría")
        else:
            self.editing_id_act = None
            self.txt_act_nom.clear()
            self.txt_act_desc.clear()
            self.spin_act_orden.setValue(next_ord)
            self.chk_act_act.setChecked(True)
            self.btn_act_save.setText("💾 Guardar Categoría")

    def _preparar_edicion(self, tipo: str, cat: Dict[str, Any]):
        if tipo == "CAPACITACION":
            self.editing_id_cap = cat.get('id')
            self.spin_cap_orden.setValue(int(cat.get('orden', 1)))
            self.txt_cap_nom.setText(cat.get('nombre', ''))
            self.txt_cap_desc.setText(cat.get('descripcion', ''))
            self.chk_cap_act.setChecked(bool(cat.get('activo', True)))
            self.btn_cap_save.setText("💾 Guardar Cambios")
        else:
            self.editing_id_act = cat.get('id')
            self.spin_act_orden.setValue(int(cat.get('orden', 1)))
            self.txt_act_nom.setText(cat.get('nombre', ''))
            self.txt_act_desc.setText(cat.get('descripcion', ''))
            self.chk_act_act.setChecked(bool(cat.get('activo', True)))
            self.btn_act_save.setText("💾 Guardar Cambios")

    def _eliminar_categoria(self, tipo: str, cat: Dict[str, Any]):
        nombre = cat.get('nombre', '')
        if not nombre:
            return

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Confirmar eliminación")
        msg_box.setText(f"¿Estás seguro de que deseas eliminar la categoría:\n\n'{nombre}'?\n\nEsta acción no se puede deshacer.")
        msg_box.setIcon(QMessageBox.Question)
        btn_si = msg_box.addButton("Sí, eliminar", QMessageBox.YesRole)
        btn_no = msg_box.addButton("Cancelar", QMessageBox.NoRole)
        msg_box.setDefaultButton(btn_no)
        msg_box.exec_()

        if msg_box.clickedButton() != btn_si:
            return

        cid = cat.get('id')

        # 1. Eliminar primero en Supabase por (tipo, nombre)
        ok_cloud, err_cloud = supabase_manager.eliminar_categoria_catalogo(tipo, nombre)
        if err_cloud:
            print(f"[CATALOGO_WARN] No se pudo eliminar en Supabase: {err_cloud}")

        # 2. Eliminar en SQLite local por (tipo, nombre)
        try:
            conn = db.get_connection()
            try:
                conn.execute("DELETE FROM catalogo_categorias WHERE tipo = ? AND nombre = ?", (tipo, nombre))
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"[DB_LOCAL] Error eliminando categoría ({tipo}, {nombre}): {e}")

        # Resetear form si estaba editando esa misma categoría
        if tipo == "CAPACITACION" and self.editing_id_cap == cid:
            self._reset_form("CAPACITACION")
        elif tipo == "ACTIVIDAD" and self.editing_id_act == cid:
            self._reset_form("ACTIVIDAD")

        self.cargar_datos()
        QMessageBox.information(self, "Eliminado", f"Categoría '{nombre}' eliminada correctamente.")


    def _guardar_categoria(self, tipo: str):
        if tipo == "CAPACITACION":
            cid = self.editing_id_cap
            nom = format_title_case(self.txt_cap_nom.text())
            desc = format_title_case(self.txt_cap_desc.text())
            orden = self.spin_cap_orden.value()
            activo = self.chk_cap_act.isChecked()
        else:
            cid = self.editing_id_act
            nom = format_title_case(self.txt_act_nom.text())
            desc = format_title_case(self.txt_act_desc.text())
            orden = self.spin_act_orden.value()
            activo = self.chk_act_act.isChecked()

        if not nom:
            QMessageBox.warning(self, "Atención", "Por favor ingrese el nombre de la categoría.")
            return

        cat_data = {
            "id": cid,
            "tipo": tipo,
            "nombre": nom,
            "descripcion": desc,
            "orden": orden,
            "activo": activo
        }

        # 1. Guardar en SQLite Local
        db.save_catalogo_categorias_batch_local([cat_data])

        # 2. Intentar guardar en Supabase
        ok_cloud, err = supabase_manager.guardar_categoria_catalogo(cat_data)
        if not ok_cloud and err:
            print(f"[CATALOGO_WARN] No se pudo guardar en Supabase, guardado en SQLite local: {err}")

        self.cargar_datos()  # recarga primero para que _next_orden lea el estado actualizado
        self._reset_form(tipo)
        QMessageBox.information(self, "Éxito", f"Categoría '{nom}' guardada correctamente.")


class InformeCuatrimestralWidget(QWidget):

    """Pestaña principal para el Informe Cuatrimestral."""
    
    pdf_requested = pyqtSignal(dict)  # Emite datos para generar el PDF

    def __init__(self, main_app=None, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.infoplaza_id = None
        self.infoplaza_info = {}
        self.is_dark_mode = getattr(main_app, 'is_dark_mode', False) if main_app else False

        # Determinar cuatrimestre sugerido por la fecha actual
        def_year, def_cuat = auto_determinar_cuatrimestre()
        self.current_anio = def_year
        self.current_cuatrimestre = def_cuat

        # Debounce timer para guardar en segundo plano sin lag al manipular la UI
        self.debounce_sync_timer = QTimer(self)
        self.debounce_sync_timer.setSingleShot(True)
        self.debounce_sync_timer.timeout.connect(self._ejecutar_sincronizacion_background)
        self.sync_thread = None

        self.init_ui()
        self.cargar_datos_infoplaza()
        self.update_theme(self.is_dark_mode)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # ---------------------------------------------------------------------
        # 1. ENCABEZADO Y CONTROLES SUPERIORES (Unificados con Parámetros de Reporte)
        # ---------------------------------------------------------------------
        self.header_card = QFrame()
        self.header_card.setObjectName("HeaderCard")
        
        header_layout = QHBoxLayout(self.header_card)
        header_layout.setContentsMargins(15, 12, 15, 12)
        header_layout.setSpacing(10)
        
        title_box = QVBoxLayout()
        self.lbl_titulo = QLabel("📋 Informe Cuatrimestral de Infoplazas")
        self.lbl_titulo.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.lbl_infoplaza_info = QLabel("Cargando datos de Infoplaza...")
        self.lbl_infoplaza_info.setStyleSheet("font-size: 15px; color: #0284c7; font-weight: 700;")
        title_box.addWidget(self.lbl_titulo)
        title_box.addWidget(self.lbl_infoplaza_info)

        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Selector de Año (SpinBox con restricción de Diciembre)
        self.lbl_anio = QLabel("AÑO DEL REPORTE:")
        self.lbl_anio.setStyleSheet("font-weight: 700; font-size: 12px;")
        
        now = datetime.now()
        current_y = now.year
        current_m = now.month
        max_y = current_y + (1 if current_m == 12 else 0)

        self.spin_anio = QSpinBox()
        self.spin_anio.setRange(2020, max_y)
        self.spin_anio.setValue(min(self.current_anio, max_y))
        self.spin_anio.setObjectName("HighlightSpinBox")
        self.spin_anio.valueChanged.connect(self.on_periodo_changed)

        # Selector de Cuatrimestre
        self.lbl_cuat = QLabel("CUATRIMESTRE:")
        self.lbl_cuat.setStyleSheet("font-weight: 700; font-size: 12px;")
        self.combo_cuat = QComboBox()
        self.combo_cuat.addItem("Enero a abril", 1)
        self.combo_cuat.addItem("Mayo a agosto", 2)
        self.combo_cuat.addItem("Septiembre a diciembre", 3)
        self.combo_cuat.setCurrentIndex(self.current_cuatrimestre - 1)
        self.combo_cuat.currentIndexChanged.connect(self.on_periodo_changed)

        # Selector de Computadoras (PCs) - Sincronizado en espejo con el Dashboard
        self.lbl_pcs = QLabel("COMPUTADORAS:")
        self.lbl_pcs.setStyleSheet("font-weight: 700; font-size: 12px;")
        self.spin_pcs = QSpinBox()
        self.spin_pcs.setRange(1, 100)
        self.spin_pcs.setObjectName("HighlightSpinBox")
        initial_pcs = 6
        if self.main_app and hasattr(self.main_app, 'spin_computadoras'):
            initial_pcs = self.main_app.spin_computadoras.value()
        self.spin_pcs.setValue(initial_pcs)
        self.spin_pcs.valueChanged.connect(self.on_pcs_changed)

        # Badge de Meta Mensual (idéntico al Dashboard)
        self.lbl_meta_badge = QLabel(f"Meta Mensual: {initial_pcs * 48}")
        self.lbl_meta_badge.setAlignment(Qt.AlignCenter)
        self.lbl_meta_badge.setStyleSheet("font-size: 13px; font-weight: bold; color: #0284c7; background-color: #e0f2fe; padding: 6px 14px; border-radius: 6px; border: 1px solid #7dd3fc; min-height: 26px;")

        header_layout.addWidget(self.lbl_anio)
        header_layout.addWidget(self.spin_anio)
        header_layout.addWidget(self.lbl_cuat)
        header_layout.addWidget(self.combo_cuat)
        header_layout.addWidget(self.lbl_pcs)
        header_layout.addWidget(self.spin_pcs)
        header_layout.addWidget(self.lbl_meta_badge)

        # Botón de Acción Principal (GENERAR INFORME - Estilo Botones Dashboard)
        self.btn_pdf = QPushButton("📄 GENERAR INFORME")
        self.btn_pdf.setStyleSheet("""
            QPushButton {
                background-color: #059669; 
                color: white; 
                font-weight: 700; 
                padding: 6px 18px; 
                border-radius: 6px; 
                font-size: 13px;
                border: 1px solid #059669;
                min-height: 26px;
            }
            QPushButton:hover {
                background-color: #047857;
                border-color: #047857;
            }
            QPushButton:pressed {
                background-color: #065f46;
                border-color: #065f46;
            }
        """)
        self.btn_pdf.setCursor(Qt.PointingHandCursor)
        self.btn_pdf.clicked.connect(self.emitir_pdf)

        header_layout.addWidget(self.btn_pdf)

        main_layout.addWidget(self.header_card)
        self.actualizar_encabezado_titulo()

        # ---------------------------------------------------------------------
        # 2. SECCIONES CON PESTAÑAS (TABS)
        # ---------------------------------------------------------------------
        self.tabs = QTabWidget()

        # Pestaña 1: Capacitaciones y Cursos
        self.tab_capacitaciones = self._crear_tab_capacitaciones()
        self.tabs.addTab(self.tab_capacitaciones, "I. Capacitaciones y Cursos")

        # Pestaña 2: Otras Actividades
        self.tab_actividades = self._crear_tab_actividades()
        self.tabs.addTab(self.tab_actividades, "II. Otras Actividades")

        # Pestaña 3: Servicios Brindados
        self.tab_servicios = self._crear_tab_servicios()
        self.tabs.addTab(self.tab_servicios, "III. Servicios Brindados")

        # Pestaña 4: Estadística y Cumplimiento
        self.tab_rendimiento = self._crear_tab_rendimiento()
        self.tabs.addTab(self.tab_rendimiento, "IV. Estadística y Cumplimiento")

        # Pestaña 5: Firma y Observaciones
        self.tab_firmas = self._crear_tab_firmas()
        self.tabs.addTab(self.tab_firmas, "V. Firma y Observaciones")

        # Pestaña 6: Catálogo Maestro de Infoplazas (Se oculta por defecto, se muestra en Modo Guerrero)
        self.tab_infoplazas = InfoplazasTabWidget(self)

        main_layout.addWidget(self.tabs)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.cargar_catalogos_categorias()

    def cargar_catalogos_categorias(self):
        """Sincroniza con Supabase primero, actualiza local y recarga las opciones de los combos de categorías."""
        try:
            supabase_manager.sincronizar_catalogo_categorias()
        except Exception as e:
            print(f"[CATALOGO_SYNC_WARN] Error en sincronización de catálogo al cargar: {e}")

        caps_cats = db.get_catalogo_categorias_local("CAPACITACION")
        acts_cats = db.get_catalogo_categorias_local("ACTIVIDAD")

        # 1. Combo Capacitaciones
        if hasattr(self, 'combo_cap_categoria'):
            curr_text = self.combo_cap_categoria.currentText()
            self.combo_cap_categoria.blockSignals(True)
            self.combo_cap_categoria.clear()
            self.combo_cap_categoria.addItem("-- Seleccionar Categoría --")
            for c in caps_cats:
                if c.get('activo', True):
                    nombre = c.get('nombre', '')
                    desc   = c.get('descripcion', '').strip()
                    self.combo_cap_categoria.addItem(nombre)
                    idx = self.combo_cap_categoria.count() - 1
                    self.combo_cap_categoria.setItemData(
                        idx,
                        f"📝 {desc}" if desc else "Sin descripción",
                        Qt.ToolTipRole
                    )
            idx = self.combo_cap_categoria.findText(curr_text)
            if idx >= 0:
                self.combo_cap_categoria.setCurrentIndex(idx)
            else:
                self.combo_cap_categoria.setCurrentIndex(0)
            self.combo_cap_categoria.blockSignals(False)

        # 2. Combo Actividades
        if hasattr(self, 'combo_act_categoria'):
            curr_text = self.combo_act_categoria.currentText()
            self.combo_act_categoria.blockSignals(True)
            self.combo_act_categoria.clear()
            self.combo_act_categoria.addItem("-- Seleccionar Categoría --")
            for c in acts_cats:
                if c.get('activo', True):
                    nombre = c.get('nombre', '')
                    desc   = c.get('descripcion', '').strip()
                    self.combo_act_categoria.addItem(nombre)
                    idx = self.combo_act_categoria.count() - 1
                    self.combo_act_categoria.setItemData(
                        idx,
                        f"📝 {desc}" if desc else "Sin descripción",
                        Qt.ToolTipRole
                    )
            idx = self.combo_act_categoria.findText(curr_text)
            if idx >= 0:
                self.combo_act_categoria.setCurrentIndex(idx)
            else:
                self.combo_act_categoria.setCurrentIndex(0)
            self.combo_act_categoria.blockSignals(False)

    def abrir_gestion_catalogo(self, tipo='CAPACITACION'):
        """Abre el diálogo amplio modal para gestionar categorías (Modo Facilitador)."""
        dlg = CatalogoCategoriasDialog(parent=self, is_dark_mode=getattr(self, 'is_dark_mode', False), tipo_inicial=tipo)
        dlg.exec_()
        self.cargar_catalogos_categorias()

    def actualizar_modo_facilitador(self, activo: bool):
        """Actualiza la visibilidad de herramientas exclusivas para facilitadores."""
        self.modo_guerrero_activo = activo
        if hasattr(self, 'btn_gestion_cat_cap'):
            self.btn_gestion_cat_cap.setVisible(activo)
        if hasattr(self, 'btn_gestion_cat_act'):
            self.btn_gestion_cat_act.setVisible(activo)
            
        # Controlar la visibilidad de la pestaña Infoplazas
        if hasattr(self, 'tab_infoplazas'):
            if activo:
                if self.tabs.indexOf(self.tab_infoplazas) == -1:
                    self.tabs.addTab(self.tab_infoplazas, "Catálogo Infoplazas")
                    if self.main_app and hasattr(self.main_app, 'carpeta_raiz'):
                        self.tab_infoplazas.set_regional_from_path(self.main_app.carpeta_raiz)
            else:
                idx = self.tabs.indexOf(self.tab_infoplazas)
                if idx != -1:
                    self.tabs.removeTab(idx)

    # =========================================================================
    # CONSTRUCCIÓN DE PESTAÑAS
    # =========================================================================


    def _crear_tab_firmas(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        self.group_firmas = QGroupBox("✍️ Configuración de Asociado y Dinamizador (para la firma del Informe)")
        firmas_layout = QVBoxLayout(self.group_firmas)

        form_grid = QHBoxLayout()

        # Asociado
        box_asoc = QVBoxLayout()
        self.lbl_asoc_nom = QLabel("<b>Nombre del Asociado:</b>")
        box_asoc.addWidget(self.lbl_asoc_nom)
        self.txt_asociado_nombre = QLineEdit()
        self.txt_asociado_nombre.setPlaceholderText("Ej. Nombre y Apellido del Asociado")
        self.txt_asociado_nombre.editingFinished.connect(self._capitalizar_asociado_nombre)
        box_asoc.addWidget(self.txt_asociado_nombre)

        self.lbl_asoc_ced = QLabel("<b>Cédula del Asociado:</b>")
        box_asoc.addWidget(self.lbl_asoc_ced)
        self.txt_asociado_cedula = QLineEdit()
        self.txt_asociado_cedula.setPlaceholderText("Ej. 8-123-4567")
        box_asoc.addWidget(self.txt_asociado_cedula)

        self.lbl_firmas_note = QLabel("<i>Nota: Si deja estos campos vacíos, el reporte PDF imprimirá automáticamente las líneas de firma en blanco para llenar a mano.</i>")
        self.lbl_firmas_note.setStyleSheet("font-size: 11px;")
        self.lbl_firmas_note.setWordWrap(True)
        box_asoc.addSpacing(6)
        box_asoc.addWidget(self.lbl_firmas_note)

        # Dinamizador
        box_dinam = QVBoxLayout()
        self.lbl_dinam_nom = QLabel("<b>Nombre del Dinamizador:</b>")
        box_dinam.addWidget(self.lbl_dinam_nom)
        self.txt_dinamizador_nombre = QLineEdit()
        self.txt_dinamizador_nombre.setPlaceholderText("Ej. Nombre y Apellido del Dinamizador")
        self.txt_dinamizador_nombre.editingFinished.connect(self._capitalizar_dinamizador_nombre)
        box_dinam.addWidget(self.txt_dinamizador_nombre)

        self.lbl_dinam_ced = QLabel("<b>Cédula del Dinamizador:</b>")
        box_dinam.addWidget(self.lbl_dinam_ced)
        self.txt_dinamizador_cedula = QLineEdit()
        self.txt_dinamizador_cedula.setPlaceholderText("Ej. 7-123-4567")
        box_dinam.addWidget(self.txt_dinamizador_cedula)

        # Botón de Actualizar Información de Firma y Observaciones
        self.btn_actualizar_firmas_obs = QPushButton("🔄 Actualizar Información")
        self.btn_actualizar_firmas_obs.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; font-size: 13px; padding: 8px 16px; border-radius: 6px; margin-top: 6px;")
        self.btn_actualizar_firmas_obs.setCursor(Qt.PointingHandCursor)
        self.btn_actualizar_firmas_obs.clicked.connect(self.actualizar_informacion_firmas)
        box_dinam.addWidget(self.btn_actualizar_firmas_obs)

        form_grid.addLayout(box_asoc)
        form_grid.addSpacing(30)
        form_grid.addLayout(box_dinam)

        firmas_layout.addLayout(form_grid)
        layout.addWidget(self.group_firmas)

        # Observaciones Generales
        self.group_obs = QGroupBox("📝 Observaciones Generales del Cuatrimestre")
        group_obs_layout = QVBoxLayout(self.group_obs)

        self.txt_obs_generales = QTextEdit()
        self.txt_obs_generales.setPlaceholderText("Observaciones o notas adicionales del Dinamizador para este cuatrimestre...")
        self.txt_obs_generales.textChanged.connect(self._capitalizar_obs_generales_live)

        group_obs_layout.addWidget(self.txt_obs_generales)
        layout.addWidget(self.group_obs)

        # Recordatorio de Anexos
        self.banner_anexos = QFrame()
        banner_layout = QHBoxLayout(self.banner_anexos)
        self.lbl_anexos_note = QLabel("📷 <b>RECORDATORIO DE ANEXOS:</b> La sección de Anexos (fotografías de eventos, listas de asistencia o certificados con sus respectivos pies de foto) debe ser adjuntada manualmente por el Dinamizador al informe impreso o digital final.")
        self.lbl_anexos_note.setStyleSheet("font-size: 12px;")
        self.lbl_anexos_note.setWordWrap(True)
        banner_layout.addWidget(self.lbl_anexos_note)

        layout.addWidget(self.banner_anexos)
        return widget

    def _capitalizar_asociado_nombre(self):
        self.txt_asociado_nombre.setText(format_title_case(self.txt_asociado_nombre.text()))

    def _capitalizar_dinamizador_nombre(self):
        self.txt_dinamizador_nombre.setText(format_title_case(self.txt_dinamizador_nombre.text()))

    def _crear_tab_capacitaciones(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        # Tarjetas de Totales
        cards_layout = QHBoxLayout()
        
        self.card_tot_cap = self._crear_kpi_card("Capacitaciones", "0", "📚 Total impartidas")
        self.card_tot_part = self._crear_kpi_card("Participantes", "0", "👥 Total beneficiados")
        self.card_tot_horas = self._crear_kpi_card("Horas Totales", "0 hrs", "⏱️ Duración acumulada")

        cards_layout.addWidget(self.card_tot_cap)
        cards_layout.addWidget(self.card_tot_part)
        cards_layout.addWidget(self.card_tot_horas)

        layout.addLayout(cards_layout)

        # Formulario de Nueva Capacitación
        self.form_box_cap = QGroupBox("➕ Agregar Nueva Capacitación o Curso")
        form_layout = QHBoxLayout(self.form_box_cap)

        self.combo_cap_mes = QComboBox()
        self.combo_cap_mes.setFixedWidth(95)

        self.combo_cap_categoria = QComboBox()
        self.combo_cap_categoria.setMinimumWidth(160)

        self.btn_gestion_cat_cap = QPushButton("⚙️")
        self.btn_gestion_cat_cap.setToolTip("Gestionar Catálogo de Categorías (Modo Facilitador)")
        self.btn_gestion_cat_cap.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 4px 8px; border-radius: 4px;")
        self.btn_gestion_cat_cap.setCursor(Qt.PointingHandCursor)
        self.btn_gestion_cat_cap.clicked.connect(lambda: self.abrir_gestion_catalogo("CAPACITACION"))
        self.btn_gestion_cat_cap.setVisible(getattr(self, 'modo_guerrero_activo', False))

        self.combo_cap_tema = QLineEdit()
        self.combo_cap_tema.setPlaceholderText("Nombre del taller / capacitación")
        self.combo_cap_tema.editingFinished.connect(lambda: self.combo_cap_tema.setText(format_title_case(self.combo_cap_tema.text())))

        self.spin_cap_part = QSpinBox()
        self.spin_cap_part.setRange(0, 5000)
        self.spin_cap_part.setValue(5)
        self.spin_cap_part.setFixedWidth(75)

        self.spin_cap_horas = QSpinBox()
        self.spin_cap_horas.setRange(0, 500)
        self.spin_cap_horas.setValue(2)
        self.spin_cap_horas.setFixedWidth(65)

        self.txt_cap_obs = QLineEdit()
        self.txt_cap_obs.setPlaceholderText("Observaciones / Facilitador")
        self.txt_cap_obs.editingFinished.connect(lambda: self.txt_cap_obs.setText(format_title_case(self.txt_cap_obs.text())))

        self.btn_add_cap = QPushButton("+ Capacitación")
        self.btn_add_cap.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        self.btn_add_cap.setCursor(Qt.PointingHandCursor)
        self.btn_add_cap.clicked.connect(self.agregar_capacitacion)

        self.btn_cancelar_edit_cap = QPushButton("✕ Cancelar")
        self.btn_cancelar_edit_cap.setStyleSheet("background-color: #64748b; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        self.btn_cancelar_edit_cap.setCursor(Qt.PointingHandCursor)
        self.btn_cancelar_edit_cap.clicked.connect(self._cancelar_edicion_cap)
        self.btn_cancelar_edit_cap.setVisible(False)

        self.lbl_cap_mes = QLabel("Mes:")
        self.lbl_cap_mes.setStyleSheet("font-weight: normal; font-size: 13px;")
        self.lbl_cap_cat = QLabel("Categoría:")
        self.lbl_cap_cat.setStyleSheet("font-weight: normal; font-size: 13px;")
        self.lbl_cap_tema = QLabel("Tema:")
        self.lbl_cap_part = QLabel("Participantes:")
        self.lbl_cap_hrs = QLabel("Horas:")
        self.lbl_cap_obs = QLabel("Obs:")

        form_layout.addWidget(self.lbl_cap_mes)
        form_layout.addWidget(self.combo_cap_mes)
        form_layout.addWidget(self.lbl_cap_cat)
        form_layout.addWidget(self.combo_cap_categoria)
        form_layout.addWidget(self.btn_gestion_cat_cap)
        form_layout.addWidget(self.lbl_cap_tema)
        form_layout.addWidget(self.combo_cap_tema, 3)
        form_layout.addWidget(self.lbl_cap_part)
        form_layout.addWidget(self.spin_cap_part)
        form_layout.addWidget(self.lbl_cap_hrs)
        form_layout.addWidget(self.spin_cap_horas)
        form_layout.addWidget(self.lbl_cap_obs)
        form_layout.addWidget(self.txt_cap_obs, 3)
        form_layout.addWidget(self.btn_add_cap)
        form_layout.addWidget(self.btn_cancelar_edit_cap)

        layout.addWidget(self.form_box_cap)

        # Tabla de Capacitaciones
        self.table_cap = QTableWidget()
        self.table_cap.setColumnCount(7)
        self.table_cap.setHorizontalHeaderLabels(["Mes", "Categoría", "Tema / Capacitación", "Participantes", "Horas", "Observaciones", "Acción"])
        self.table_cap.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table_cap.setColumnWidth(0, 95)
        self.table_cap.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_cap.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_cap.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table_cap.setColumnWidth(3, 110)
        self.table_cap.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table_cap.setColumnWidth(4, 75)
        self.table_cap.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table_cap.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table_cap.setColumnWidth(6, 125)
        self.table_cap.verticalHeader().setVisible(False)
        self.table_cap.verticalHeader().setDefaultSectionSize(40)
        self.table_cap.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_cap.itemChanged.connect(self._on_table_cap_item_changed)
        self.table_cap.doubleClicked.connect(self._on_table_cap_double_clicked)

        self.edit_row_cap_idx = None


        layout.addWidget(self.table_cap)
        return widget

    def _crear_tab_servicios(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        self.lbl_srv_info = QLabel("<b>Servicios brindados en la Infoplaza (marcar los que aplican y agregar observaciones):</b>")
        top_bar.addWidget(self.lbl_srv_info)
        top_bar.addStretch()

        self.btn_add_srv = QPushButton("➕ Agregar Servicio Personalizado")
        self.btn_add_srv.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        self.btn_add_srv.setCursor(Qt.PointingHandCursor)
        self.btn_add_srv.clicked.connect(self.agregar_servicio_personalizado)
        top_bar.addWidget(self.btn_add_srv)

        layout.addLayout(top_bar)

        self.table_srv = QTableWidget()
        self.table_srv.setColumnCount(5)
        self.table_srv.setHorizontalHeaderLabels(["Ofrecido", "Tipo de Servicio", "Observaciones", "Origen", "Acción"])
        self.table_srv.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table_srv.setColumnWidth(0, 85)
        self.table_srv.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_srv.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_srv.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table_srv.setColumnWidth(3, 140)
        self.table_srv.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table_srv.setColumnWidth(4, 125)
        self.table_srv.verticalHeader().setVisible(False)
        self.table_srv.verticalHeader().setDefaultSectionSize(40)
        self.table_srv.itemChanged.connect(self._on_table_srv_item_changed)
        self.table_srv.doubleClicked.connect(self._on_table_srv_double_clicked)

        layout.addWidget(self.table_srv)
        return widget

    def _crear_tab_actividades(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        self.lbl_act_info = QLabel("<b>Punto II: Otras actividades realizadas en la Infoplaza</b> <i>(Reuniones, tardes de cine, ferias, giras médicas, etc. NO capacitaciones ni cursos)</i>")
        self.lbl_act_info.setWordWrap(True)
        layout.addWidget(self.lbl_act_info)

        self.form_box_act = QGroupBox("➕ Agregar Nueva Actividad Especial")
        form_layout = QHBoxLayout(self.form_box_act)

        self.combo_act_categoria = QComboBox()
        self.combo_act_categoria.setMinimumWidth(160)

        self.btn_gestion_cat_act = QPushButton("⚙️")
        self.btn_gestion_cat_act.setToolTip("Gestionar Catálogo de Categorías (Modo Facilitador)")
        self.btn_gestion_cat_act.setStyleSheet("background-color: #8b5cf6; color: white; font-weight: bold; padding: 4px 8px; border-radius: 4px;")
        self.btn_gestion_cat_act.setCursor(Qt.PointingHandCursor)
        self.btn_gestion_cat_act.clicked.connect(lambda: self.abrir_gestion_catalogo("ACTIVIDAD"))
        self.btn_gestion_cat_act.setVisible(getattr(self, 'modo_guerrero_activo', False))

        self.txt_act_nombre = QLineEdit()
        self.txt_act_nombre.setPlaceholderText("Ej. Reunión del Acueducto / Día de las Buenas Acciones")
        self.txt_act_nombre.editingFinished.connect(lambda: self.txt_act_nombre.setText(format_title_case(self.txt_act_nombre.text())))

        self.spin_act_part = QSpinBox()
        self.spin_act_part.setRange(0, 99999)
        self.spin_act_part.setValue(0)
        self.spin_act_part.setFixedWidth(75)
        self.spin_act_part.setToolTip("Total de participantes (opcional)")

        self.txt_act_obs = QLineEdit()
        self.txt_act_obs.setPlaceholderText("Observaciones de la actividad")
        self.txt_act_obs.editingFinished.connect(lambda: self.txt_act_obs.setText(format_title_case(self.txt_act_obs.text())))

        self.btn_add_act = QPushButton("+ Actividad")
        self.btn_add_act.setStyleSheet("background-color: #8b5cf6; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        self.btn_add_act.setCursor(Qt.PointingHandCursor)
        self.btn_add_act.clicked.connect(self.agregar_actividad)

        self.btn_cancelar_edit_act = QPushButton("✕ Cancelar")
        self.btn_cancelar_edit_act.setStyleSheet("background-color: #64748b; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        self.btn_cancelar_edit_act.setCursor(Qt.PointingHandCursor)
        self.btn_cancelar_edit_act.clicked.connect(self._cancelar_edicion_act)
        self.btn_cancelar_edit_act.setVisible(False)

        self.lbl_act_cat = QLabel("Categoría:")
        self.lbl_act_cat.setStyleSheet("font-weight: normal; font-size: 13px;")
        self.lbl_act_nom = QLabel("Actividad:")
        self.lbl_act_part = QLabel("Participantes:")
        self.lbl_act_obs = QLabel("Obs:")

        form_layout.addWidget(self.lbl_act_cat)
        form_layout.addWidget(self.combo_act_categoria)
        form_layout.addWidget(self.btn_gestion_cat_act)
        form_layout.addWidget(self.lbl_act_nom)
        form_layout.addWidget(self.txt_act_nombre, 3)
        form_layout.addWidget(self.lbl_act_part)
        form_layout.addWidget(self.spin_act_part, 0)
        form_layout.addWidget(self.lbl_act_obs)
        form_layout.addWidget(self.txt_act_obs, 3)
        form_layout.addWidget(self.btn_add_act)
        form_layout.addWidget(self.btn_cancelar_edit_act)

        layout.addWidget(self.form_box_act)

        self.table_act = QTableWidget()
        self.table_act.setColumnCount(5)
        self.table_act.setHorizontalHeaderLabels(["Categoría", "Otras Actividades / Eventos", "Total Participantes", "Observaciones", "Acción"])
        self.table_act.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_act.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_act.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table_act.setColumnWidth(2, 140)
        self.table_act.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table_act.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table_act.setColumnWidth(4, 125)
        self.table_act.verticalHeader().setVisible(False)
        self.table_act.verticalHeader().setDefaultSectionSize(40)
        self.table_act.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_act.itemChanged.connect(self._on_table_act_item_changed)
        self.table_act.doubleClicked.connect(self._on_table_act_double_clicked)

        self.edit_row_act_idx = None

        layout.addWidget(self.table_act)
        return widget


    def _crear_tab_rendimiento(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # 1. Tarjetas de KPIs Superiores (Hombres, Mujeres, Total Visitas)
        self.kpi_layout = QHBoxLayout()
        self.kpi_layout.setSpacing(15)

        self.kpi_hombres = self._crear_kpi_card("Masculino", "0", "Visitas en el cuatrimestre")
        self.kpi_mujeres = self._crear_kpi_card("Femenino", "0", "Visitas en el cuatrimestre")
        self.kpi_total_visitas = self._crear_kpi_card("TOTAL VISITAS", "0", "Acumulado cuatrimestral")
        self.kpi_cumplimiento = self._crear_kpi_card("Cumplimiento 30%", "0.00%", "💻 0 PCs (Meta 30%: 0)")

        self.kpi_layout.addWidget(self.kpi_hombres)
        self.kpi_layout.addWidget(self.kpi_mujeres)
        self.kpi_layout.addWidget(self.kpi_total_visitas)
        self.kpi_layout.addWidget(self.kpi_cumplimiento)

        layout.addLayout(self.kpi_layout)

        # 2. Cuadro Estadístico de Visitas por Mes
        self.group_visitas_mes = QGroupBox("📅 Resumen de Visitas por Mes")
        self.group_visitas_mes.setObjectName("GroupTable")
        group_visitas_layout = QVBoxLayout(self.group_visitas_mes)
        group_visitas_layout.setContentsMargins(12, 6, 12, 12)

        self.table_visitas_mes = QTableWidget()
        cols_visitas = [
            "MES", "Masculino", "Femenino", "Primaria", "Secundaria", 
            "Universitarios", "Docentes", "Tercera Edad", "Público General", "TOTAL USUARIOS"
        ]
        self.table_visitas_mes.setColumnCount(len(cols_visitas))
        self.table_visitas_mes.setHorizontalHeaderLabels(cols_visitas)
        self.table_visitas_mes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_visitas_mes.verticalHeader().setVisible(False)
        self.table_visitas_mes.verticalHeader().setDefaultSectionSize(40)
        self.table_visitas_mes.setMinimumHeight(255)
        self.table_visitas_mes.setEditTriggers(QTableWidget.NoEditTriggers)

        group_visitas_layout.addWidget(self.table_visitas_mes)
        layout.addWidget(self.group_visitas_mes)

        # 3. Estadística y Cumplimiento Mensual
        self.group_rend = QGroupBox("📊 Estadística y Cumplimiento Mensual")
        self.group_rend.setObjectName("GroupTable")
        group_rend_layout = QVBoxLayout(self.group_rend)
        group_rend_layout.setContentsMargins(12, 10, 12, 12)

        self.lbl_rendimiento_subtitulo = QLabel("Rendimiento Mensual vs Meta, según <span style='background-color: #0369a1; color: #ffffff; padding: 3px 9px; border-radius: 6px; font-weight: bold;'>💻 6 computadoras</span> para usuarios en la Infoplaza:")
        self.lbl_rendimiento_subtitulo.setTextFormat(Qt.RichText)
        self.lbl_rendimiento_subtitulo.setStyleSheet("font-size: 13px; font-weight: bold; margin-bottom: 6px;")
        group_rend_layout.addWidget(self.lbl_rendimiento_subtitulo)

        self.table_rendimiento = QTableWidget()
        self.table_rendimiento.setColumnCount(5)
        self.table_rendimiento.setHorizontalHeaderLabels(["MES", "Visitas Logradas", "Meta del Mes", "% Cumplimiento", "Estado"])
        self.table_rendimiento.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_rendimiento.verticalHeader().setVisible(False)
        self.table_rendimiento.verticalHeader().setDefaultSectionSize(40)
        self.table_rendimiento.setMinimumHeight(255)
        self.table_rendimiento.setEditTriggers(QTableWidget.NoEditTriggers)

        group_rend_layout.addWidget(self.table_rendimiento)
        layout.addWidget(self.group_rend)

        scroll.setWidget(widget)
        return scroll

    def _capitalizar_obs_generales_live(self):
        pass  # Evitar mover el cursor mientras escribe en QTextEdit

    def _crear_kpi_card(self, titulo: str, valor: str, subtitulo: str) -> QFrame:
        card = QFrame()
        card.setObjectName("KpiCard")
        l = QVBoxLayout(card)
        l.setContentsMargins(14, 12, 14, 12)
        l.setSpacing(4)

        lbl_t = QLabel(titulo)
        lbl_t.setStyleSheet("font-size: 13px; font-weight: bold;")
        lbl_v = QLabel(valor)
        lbl_v.setStyleSheet("color: #0284c7; font-size: 26px; font-weight: bold;")
        lbl_s = QLabel(subtitulo)
        lbl_s.setStyleSheet("font-size: 13px; font-weight: 600;")

        l.addWidget(lbl_t)
        l.addWidget(lbl_v)
        l.addWidget(lbl_s)

        card.lbl_t = lbl_t
        card.lbl_val = lbl_v
        card.lbl_sub = lbl_s
        return card

    def update_theme(self, is_dark: bool):
        """Actualiza todos los colores, tablas, cards y fuentes dinámicamente según Modo Claro/Oscuro."""
        self.is_dark_mode = is_dark

        # Paleta de colores
        bg_card = "#1e293b" if is_dark else "#ffffff"
        border_card = "#334155" if is_dark else "#cbd5e1"
        text_main = "#f8fafc" if is_dark else "#0f172a"
        text_sub = "#94a3b8" if is_dark else "#475569"
        input_bg = "#0f172a" if is_dark else "#ffffff"
        input_fg = "#f8fafc" if is_dark else "#1e293b"
        input_border = "#334155" if is_dark else "#cbd5e1"
        table_bg = "#0f172a" if is_dark else "#ffffff"
        table_header_bg = "#1e293b" if is_dark else "#f1f5f9"
        table_header_fg = "#38bdf8" if is_dark else "#0284c7"
        table_grid = "#334155" if is_dark else "#e2e8f0"
        
        # 1. Header Card
        if hasattr(self, 'header_card'):
            self.header_card.setStyleSheet(f"""
                QFrame#HeaderCard {{
                    background-color: {bg_card};
                    border: 1px solid {border_card};
                    border-radius: 10px;
                    padding: 10px;
                }}
            """)
        self.actualizar_encabezado_titulo()
        
        # Filtros superioes
        style_filtro = f"""
            QSpinBox, QComboBox {{
                font-size: 13px; 
                font-weight: 600; 
                padding: 5px 10px; 
                border: 1px solid {input_border}; 
                border-radius: 6px; 
                min-height: 26px;
                background-color: {input_bg};
                color: {input_fg};
            }}
        """
        self.spin_anio.setStyleSheet(style_filtro)
        self.combo_cuat.setStyleSheet(style_filtro)
        self.spin_pcs.setStyleSheet(style_filtro)
        self.lbl_anio.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {text_main};")
        self.lbl_cuat.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {text_main};")
        self.lbl_pcs.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {text_main};")

        if hasattr(self, 'lbl_meta_badge'):
            badge_bg = "rgba(2, 132, 199, 0.15)" if is_dark else "#e0f2fe"
            badge_border = "#38bdf8" if is_dark else "#7dd3fc"
            badge_fg = "#38bdf8" if is_dark else "#0284c7"
            self.lbl_meta_badge.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {badge_fg}; background-color: {badge_bg}; padding: 6px 14px; border-radius: 6px; border: 1px solid {badge_border}; min-height: 26px;")

        if hasattr(self, 'btn_pdf'):
            self.btn_pdf.setStyleSheet("""
                QPushButton {
                    background-color: #059669; 
                    color: white; 
                    font-weight: 700; 
                    padding: 6px 18px; 
                    border-radius: 6px; 
                    font-size: 13px;
                    border: 1px solid #059669;
                    min-height: 26px;
                }
                QPushButton:hover {
                    background-color: #047857;
                    border-color: #047857;
                }
                QPushButton:pressed {
                    background-color: #065f46;
                    border-color: #065f46;
                }
            """)

        # 2. Pestañas (QTabBar)
        tab_bg_unselected = "#0f172a" if is_dark else "#f8fafc"
        tab_bg_selected = "#1e293b" if is_dark else "#ffffff"
        tab_text_selected = "#38bdf8" if is_dark else "#0284c7"
        tab_border = "#334155" if is_dark else "#cbd5e1"
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {tab_border};
                background: {bg_card};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                font-size: 13px;
                font-weight: bold;
                padding: 8px 26px;
                min-width: 190px;
                background-color: {tab_bg_unselected};
                color: {text_sub};
                border: 1px solid {tab_border};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 6px;
            }}
            QTabBar::tab:selected {{
                background-color: {tab_bg_selected};
                color: {tab_text_selected};
                border-bottom: 3px solid #0284c7;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {tab_bg_selected};
                color: {text_main};
            }}
        """)

        # 3. KPI Cards
        val_color = "#38bdf8" if is_dark else "#0284c7"
        sub_color = "#cbd5e1" if is_dark else "#334155"
        for card in [self.card_tot_cap, self.card_tot_part, self.card_tot_horas]:
            if hasattr(card, 'lbl_t'): card.lbl_t.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {text_main};")
            if hasattr(card, 'lbl_val'): card.lbl_val.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {val_color};")
            if hasattr(card, 'lbl_sub'): card.lbl_sub.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {sub_color};")
            card.setStyleSheet(f"QFrame#KpiCard {{ background-color: {bg_card}; border: 1.5px solid {border_card}; border-radius: 10px; padding: 12px 14px; }}")

        # 4. GroupBoxes
        group_style = f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 14px;
                color: {text_main};
                border: 1px solid {border_card};
                border-radius: 8px;
                margin-top: 22px;
                padding-top: 24px;
                background-color: {bg_card};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 4px 16px;
                background-color: {bg_card};
                color: {text_main};
            }}
            QGroupBox#GroupTable {{
                font-weight: bold;
                font-size: 14px;
                color: {text_main};
                border: 1px solid {border_card};
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 6px;
                background-color: {bg_card};
            }}
            QGroupBox#GroupTable::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 4px 16px;
                background-color: {bg_card};
                color: {text_main};
            }}
        """
        for g in [getattr(self, 'group_pcs', None), getattr(self, 'group_firmas', None), 
                  getattr(self, 'group_obs', None), getattr(self, 'group_rend', None),
                  getattr(self, 'group_visitas_mes', None),
                  getattr(self, 'form_box_cap', None), getattr(self, 'form_box_act', None)]:
            if g: g.setStyleSheet(group_style)

        # 5. Form Field Labels
        lbl_style = f"color: {text_main}; font-size: 13px;"
        for lbl in [getattr(self, 'lbl_pcs', None), getattr(self, 'lbl_asoc_nom', None), getattr(self, 'lbl_asoc_ced', None),
                    getattr(self, 'lbl_dinam_nom', None), getattr(self, 'lbl_dinam_ced', None), getattr(self, 'lbl_cap_mes', None),
                    getattr(self, 'lbl_cap_tema', None), getattr(self, 'lbl_cap_part', None), getattr(self, 'lbl_cap_hrs', None),
                    getattr(self, 'lbl_cap_obs', None), getattr(self, 'lbl_srv_info', None), getattr(self, 'lbl_act_info', None),
                    getattr(self, 'lbl_act_nom', None), getattr(self, 'lbl_act_part', None), getattr(self, 'lbl_act_obs', None)]:
            if lbl: lbl.setStyleSheet(lbl_style)

        if hasattr(self, 'lbl_firmas_note'):
            self.lbl_firmas_note.setStyleSheet(f"color: {text_sub}; font-size: 12px;")

        # Inputs Text / Spin / Combo
        input_style = f"""
            QLineEdit, QTextEdit, QSpinBox, QComboBox {{
                background-color: {input_bg};
                color: {input_fg};
                border: 1px solid {input_border};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border: 1px solid #0284c7;
            }}
        """
        for inp in [getattr(self, 'txt_asociado_nombre', None), getattr(self, 'txt_asociado_cedula', None),
                    getattr(self, 'txt_dinamizador_nombre', None), getattr(self, 'txt_dinamizador_cedula', None),
                    getattr(self, 'txt_obs_generales', None), getattr(self, 'combo_cap_mes', None),
                    getattr(self, 'combo_cap_tema', None), getattr(self, 'spin_cap_part', None),
                    getattr(self, 'spin_cap_horas', None), getattr(self, 'txt_cap_obs', None),
                    getattr(self, 'txt_act_nombre', None), getattr(self, 'spin_act_part', None),
                    getattr(self, 'txt_act_obs', None), getattr(self, 'spin_pcs', None)]:
            if inp: inp.setStyleSheet(input_style)

        # 6. Tablas
        selection_bg = "rgba(2, 132, 199, 0.2)" if is_dark else "#e0f2fe"
        selection_fg = "#f8fafc" if is_dark else "#0369a1"

        table_style = f"""
            QTableWidget {{
                background-color: {table_bg};
                color: {text_main};
                gridline-color: {table_grid};
                border: 1px solid {border_card};
                border-radius: 6px;
                font-size: 13px;
            }}
            QHeaderView::section {{
                background-color: {table_header_bg};
                color: {table_header_fg};
                padding: 8px 12px;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid {border_card};
            }}
            QTableWidget::item {{
                padding: 6px 8px;
                color: {text_main};
                border-bottom: 1px solid {table_grid};
            }}
            QTableWidget::item:selected {{
                background-color: {selection_bg};
                color: {selection_fg};
            }}
            QTableWidget::item:focus {{
                background-color: {selection_bg};
                outline: none;
            }}
            QTableWidget QLineEdit {{
                background-color: {input_bg};
                color: {input_fg};
                border: 2px solid #0284c7;
                border-radius: 4px;
                margin: -6px -8px;
                padding: 4px 6px;
                font-size: 13px;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
            }}
        """
        for tbl in [self.table_cap, self.table_srv, self.table_act, self.table_rendimiento, getattr(self, 'table_visitas_mes', None)]:
            if tbl:
                tbl.setStyleSheet(table_style)
                tbl.verticalHeader().setVisible(False)
                tbl.verticalHeader().setDefaultSectionSize(40)

        # Re-aplicar estilización visual a los CheckBoxes de Servicios
        if hasattr(self, 'table_srv') and self.table_srv:
            for r in range(self.table_srv.rowCount()):
                cell_chk = self.table_srv.cellWidget(r, 0)
                chk = cell_chk.findChild(QCheckBox) if cell_chk else None
                if chk:
                    aplicar_estilo_checkbox_srv(chk, is_dark)

        # Estilo de Tarjetas KPI
        kpi_card_style = f"""
            QFrame#KpiCard {{
                background-color: {bg_card};
                border: 1.5px solid {border_card};
                border-radius: 10px;
                padding: 12px 14px;
            }}
        """
        for card in [getattr(self, 'kpi_hombres', None), getattr(self, 'kpi_mujeres', None), getattr(self, 'kpi_total_visitas', None), getattr(self, 'kpi_cumplimiento', None)]:
            if card:
                card.setStyleSheet(kpi_card_style)
                if hasattr(card, 'lbl_t'): card.lbl_t.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {text_main};")
                if hasattr(card, 'lbl_val') and card != getattr(self, 'kpi_cumplimiento', None):
                    card.lbl_val.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {val_color};")
                if hasattr(card, 'lbl_sub'): card.lbl_sub.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {sub_color};")

        # 7. Banner de Anexos
        if hasattr(self, 'banner_anexos'):
            banner_bg = "rgba(245, 158, 11, 0.1)" if is_dark else "#fffbeb"
            self.banner_anexos.setStyleSheet(f"""
                QFrame {{
                    background-color: {banner_bg};
                    border: 1px solid #f59e0b;
                    border-radius: 8px;
                    padding: 10px;
                }}
            """)
        if hasattr(self, 'lbl_anexos_note'):
            self.lbl_anexos_note.setStyleSheet(f"font-size: 12px; color: {text_main};")

        # Refrescar tablas y sub-módulos
        self.actualizar_cuadro_visitas()
        self.actualizar_tarjeta_rendimiento()
        if hasattr(self, 'tab_infoplazas') and self.tab_infoplazas:
            self.tab_infoplazas.update_theme(is_dark)

    # =========================================================================
    # LÓGICA DE CARGA, EVENTOS Y NAVEGACIÓN
    # =========================================================================

    def cargar_datos_infoplaza(self):
        """
        Extrae el número de Infoplaza usando la misma jerarquía que el Dashboard:
          1. current_username (ya resuelto por ADA_Nova desde Access)
          2. Fallback: caché SQLite local — registros_ventas_cache, igual que UserLoaderThread
        """
        username = None

        # --- PRIMARIO: variable ya resuelta por el hilo de Access ---
        if hasattr(self.main_app, 'current_username') and self.main_app.current_username:
            estados_invalidos = ["Esperando Sincronización...", "Cargando...", "Sin datos", "Error", "--"]
            if not any(e in self.main_app.current_username for e in estados_invalidos):
                username = self.main_app.current_username

        # --- FALLBACK: misma consulta SQL que UserLoaderThread usa cuando Access no responde ---
        if not username:
            try:
                rows = db.execute_query(
                    "SELECT username FROM registros_ventas_cache ORDER BY datetime DESC LIMIT 1"
                )
                if rows:
                    candidate = str(rows[0]['username']).strip()
                    if candidate and candidate not in ["Esperando Sincronización...", "ERROR_LOAD", ""]:
                        username = candidate
            except Exception:
                pass

        # --- Extraer el número numérico del username (ej: "273@infoplazas.org.pa" → "273") ---
        if username:
            match = re.match(r'^(\d+)', username)
            if match:
                self.infoplaza_id = match.group(1)

        if not self.infoplaza_id:
            self.infoplaza_id = None  # No asumir número; se mostrará vacío en la UI

        self.actualizar_combo_meses()
        
        # Intentar obtener info de Supabase
        if not self.infoplaza_id:
            self.actualizar_encabezado_titulo()
            self.cargar_informe_actual()
            return

        try:
            num = int(self.infoplaza_id)
            info, err = supabase_manager.get_infoplaza(num)
            if info:
                self.infoplaza_info = info
                if info.get('cant_computadoras'):
                    self.spin_pcs.setValue(int(info.get('cant_computadoras')))
                if info.get('asociado_nombre'):
                    self.txt_asociado_nombre.setText(format_title_case(info.get('asociado_nombre')))
                if info.get('asociado_cedula'):
                    self.txt_asociado_cedula.setText(str(info.get('asociado_cedula')).strip().upper())
                if info.get('dinamizador_nombre'):
                    self.txt_dinamizador_nombre.setText(format_title_case(info.get('dinamizador_nombre')))
                if info.get('dinamizador_cedula'):
                    self.txt_dinamizador_cedula.setText(str(info.get('dinamizador_cedula')).strip().upper())
        except Exception as e:
            pass

        self.actualizar_encabezado_titulo()
        self.cargar_informe_actual()

    def actualizar_combo_meses(self):
        """Actualiza el combo de meses según el cuatrimestre seleccionado."""
        self.combo_cap_mes.clear()
        meses = MESES_CUATRIMESTRE.get(self.current_cuatrimestre, [])
        for m in meses:
            self.combo_cap_mes.addItem(m)

    def actualizar_encabezado_titulo(self):
        """Actualiza el título principal y subtítulo del encabezado con formato dinámico acordado."""
        is_dark = getattr(self, 'is_dark_mode', False)
        text_main = "#f8fafc" if is_dark else "#0f172a"
        text_sub = "#94a3b8" if is_dark else "#64748b"
        accent_color = "#38bdf8" if is_dark else "#0284c7"

        # 1. Construir Línea 1: 186 - La Pasera (Guararé, Los Santos)
        num = self.infoplaza_id or ""
        nombre = ""
        ubicacion = ""

        if self.infoplaza_info and isinstance(self.infoplaza_info, dict):
            num = str(self.infoplaza_info.get('numero') or num)
            nombre = self.infoplaza_info.get('nombre') or ''
            dist = self.infoplaza_info.get('distrito') or ''
            prov = self.infoplaza_info.get('provincia') or ''
            if dist and prov:
                ubicacion = f"({dist}, {prov})"
            elif prov or dist:
                ubicacion = f"({prov or dist})"

        if num and nombre:
            linea_1_main = f"{num} - {nombre}"
        elif num:
            linea_1_main = f"Infoplaza #{num}"
        elif nombre:
            linea_1_main = nombre
        else:
            linea_1_main = "Catálogo Infoplazas"

        if ubicacion:
            html_linea_1 = f'<span style="font-size: 20px; font-weight: bold; color: {text_main};">{linea_1_main}</span> <span style="font-size: 14px; font-weight: normal; color: {text_sub};">{ubicacion}</span>'
        else:
            html_linea_1 = f'<span style="font-size: 20px; font-weight: bold; color: {text_main};">{linea_1_main}</span>'

        if hasattr(self, 'lbl_titulo'):
            self.lbl_titulo.setText(html_linea_1)

        # 2. Construir Línea 2: Informe Cuatrimestral - Mayo a Agosto 2026
        cuat_map = {
            1: "Enero a Abril",
            2: "Mayo a Agosto",
            3: "Septiembre a Diciembre"
        }
        cuat_val = getattr(self, 'current_cuatrimestre', 1)
        rango_meses = cuat_map.get(cuat_val, "Enero a Abril")
        anio_val = getattr(self, 'current_anio', datetime.now().year)

        linea_2_text = f"Informe Cuatrimestral - {rango_meses} {anio_val}"
        if not self.infoplaza_id:
            linea_2_text += " (Carga primero la base de datos)"

        if hasattr(self, 'lbl_infoplaza_info'):
            self.lbl_infoplaza_info.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {accent_color};")
            self.lbl_infoplaza_info.setText(linea_2_text)

    def on_periodo_changed(self):
        """Se activa al cambiar Año o Cuatrimestre."""
        self.current_anio = self.spin_anio.value()
        self.current_cuatrimestre = self.combo_cuat.currentData()
        self.actualizar_combo_meses()
        self.actualizar_encabezado_titulo()
        self.cargar_informe_actual()

    def on_pcs_changed(self, value: int):
        """Sincroniza la cantidad de computadoras con el Dashboard principal en tiempo real (espejo) con respuesta instantánea."""
        # 1. Actualización instantánea del badge Meta Mensual (0ms)
        if hasattr(self, 'lbl_meta_badge'):
            self.lbl_meta_badge.setText(f"Meta Mensual: {value * 48}")

        # 2. Actualización instantánea del rendimiento cuatrimestral
        self.actualizar_tarjeta_rendimiento()

        # 3. Sincronizar en espejo con el Dashboard principal sin bucles
        if self.main_app and hasattr(self.main_app, 'spin_computadoras') and self.main_app.spin_computadoras:
            if self.main_app.spin_computadoras.value() != value:
                self.main_app.spin_computadoras.blockSignals(True)
                self.main_app.spin_computadoras.setValue(value)
                self.main_app.spin_computadoras.blockSignals(False)
                if hasattr(self.main_app, 'actualizar_meta'):
                    self.main_app.actualizar_meta()

        # 4. Guardar en SQLite local y sincronizar a Supabase en segundo plano
        self.auto_sync_guardar_local_y_cloud()

    def _limpiar_interfaz_completa(self):
        """Limpia a blanco todos los campos del formulario, tablas e indicadores antes de cargar una nueva Infoplaza."""
        self._updating_table_cap = True
        self._updating_table_srv = True
        self._updating_table_act = True
        try:
            if hasattr(self, 'spin_pcs'): self.spin_pcs.setValue(6)
            if hasattr(self, 'txt_asociado_nombre'): self.txt_asociado_nombre.clear()
            if hasattr(self, 'txt_asociado_cedula'): self.txt_asociado_cedula.clear()
            if hasattr(self, 'txt_dinamizador_nombre'): self.txt_dinamizador_nombre.clear()
            if hasattr(self, 'txt_dinamizador_cedula'): self.txt_dinamizador_cedula.clear()
            if hasattr(self, 'txt_obs_generales'): self.txt_obs_generales.clear()

            if hasattr(self, 'combo_cap_tema'): self.combo_cap_tema.clear()
            if hasattr(self, 'txt_cap_obs'): self.txt_cap_obs.clear()
            if hasattr(self, 'txt_act_nombre'): self.txt_act_nombre.clear()
            if hasattr(self, 'txt_act_obs'): self.txt_act_obs.clear()
            if hasattr(self, 'spin_act_part'): self.spin_act_part.setValue(0)

            if hasattr(self, 'table_cap'): self.table_cap.setRowCount(0)
            if hasattr(self, 'table_srv'): self.table_srv.setRowCount(0)
            if hasattr(self, 'table_act'): self.table_act.setRowCount(0)
            if hasattr(self, 'table_visitas_mes'): self.table_visitas_mes.setRowCount(0)
            if hasattr(self, 'table_rendimiento'): self.table_rendimiento.setRowCount(0)

            if hasattr(self, 'card_tot_cap'): self.card_tot_cap.lbl_val.setText("0")
            if hasattr(self, 'card_tot_part'): self.card_tot_part.lbl_val.setText("0")
            if hasattr(self, 'card_tot_horas'): self.card_tot_horas.lbl_val.setText("0.0 hrs")
            if hasattr(self, 'kpi_hombres') and self.kpi_hombres and hasattr(self.kpi_hombres, 'lbl_val'): self.kpi_hombres.lbl_val.setText("0")
            if hasattr(self, 'kpi_mujeres') and self.kpi_mujeres and hasattr(self.kpi_mujeres, 'lbl_val'): self.kpi_mujeres.lbl_val.setText("0")
            if hasattr(self, 'kpi_total_visitas') and self.kpi_total_visitas and hasattr(self.kpi_total_visitas, 'lbl_val'): self.kpi_total_visitas.lbl_val.setText("0")
            if hasattr(self, 'kpi_cumplimiento') and self.kpi_cumplimiento and hasattr(self.kpi_cumplimiento, 'lbl_val'): self.kpi_cumplimiento.lbl_val.setText("0.00%")
        finally:
            self._updating_table_cap = False
            self._updating_table_srv = False
            self._updating_table_act = False

    def refresh_infoplaza(self):
        """
        Llamado desde ADA_Nova._on_user_loaded cuando el hilo de Access termina
        o cuando la BD activa cambia. Resetea la UI a blanco y fuerza la descarga desde Supabase (testigo) y Access.
        """
        self.infoplaza_id = None
        self.infoplaza_info = {}
        self.cargar_datos_infoplaza(force_cloud_pull=True)

    def cargar_datos_infoplaza(self, force_cloud_pull: bool = False):
        """
        Extrae el número de Infoplaza usando la misma jerarquía que el Dashboard:
          1. current_username (ya resuelto por ADA_Nova desde Access)
          2. Fallback: caché SQLite local — registros_ventas_cache, igual que UserLoaderThread
        """
        username = None

        if hasattr(self.main_app, 'current_username') and self.main_app.current_username:
            estados_invalidos = ["Esperando Sincronización...", "Cargando...", "Sin datos", "Error", "--"]
            if not any(e in self.main_app.current_username for e in estados_invalidos):
                username = self.main_app.current_username

        if not username:
            try:
                rows = db.execute_query(
                    "SELECT username FROM registros_ventas_cache ORDER BY datetime DESC LIMIT 1"
                )
                if rows:
                    candidate = str(rows[0]['username']).strip()
                    if candidate and candidate not in ["Esperando Sincronización...", "ERROR_LOAD", ""]:
                        username = candidate
            except Exception:
                pass

        if username:
            match = re.search(r'(\d+)', username)
            if match:
                self.infoplaza_id = match.group(1)

        if not self.infoplaza_id:
            self.infoplaza_id = None

        self.actualizar_combo_meses()
        
        if not self.infoplaza_id:
            self.actualizar_encabezado_titulo()
            self._limpiar_interfaz_completa()
            return

        try:
            num = int(self.infoplaza_id)
            info, err = supabase_manager.get_infoplaza(num)
            if info and not err:
                self.infoplaza_info = info
        except Exception:
            pass

        self.actualizar_encabezado_titulo()
        self.cargar_informe_actual(force_cloud_pull=force_cloud_pull)

    def cargar_informe_actual(self, force_cloud_pull: bool = False):
        """Carga datos desde Supabase (si force_cloud_pull=True por cambio de BD) o desde SQLite local."""
        if not self.infoplaza_id:
            return

        # 1. BLOQUEAR ABSOLUTAMENTE CUALQUIER PUSH A SUPABASE MIENTRAS DURE LA DESCARGA/CONMUTACIÓN
        self._is_pulling_from_cloud = True
        self.debounce_sync_timer.stop()
        self._limpiar_interfaz_completa()

        try:
            data_local = {}

            if force_cloud_pull:
                data_cloud = None
                err_cloud = None
                try:
                    num = int(self.infoplaza_id)
                    data_cloud, err_cloud = supabase_manager.pull_informe_full(
                        infoplaza_numero=num,
                        anio=self.current_anio,
                        cuatrimestre=self.current_cuatrimestre
                    )
                except Exception as e_net:
                    err_cloud = str(e_net)

                if data_cloud and not err_cloud:
                    c_hdr = data_cloud.get('header') or {}
                    c_caps = data_cloud.get('capacitaciones', [])
                    c_srvs = data_cloud.get('servicios', [])
                    c_acts = data_cloud.get('otras_actividades', [])

                    # Limpiar e insertar en SQLite local ÚNICAMENTE lo descargado de Supabase
                    db.save_informe_cuatrimestral_local(
                        infoplaza_id=self.infoplaza_id,
                        anio=self.current_anio,
                        cuatrimestre=self.current_cuatrimestre,
                        header_data=c_hdr,
                        capacitaciones=c_caps,
                        servicios=c_srvs,
                        otras_actividades=c_acts
                    )
                    data_local = {
                        "header": c_hdr,
                        "capacitaciones": c_caps,
                        "servicios": c_srvs,
                        "otras_actividades": c_acts
                    }
                else:
                    # MÁSCARA / OBSERVACIÓN MODO GUERRERO (SIN CONEXIÓN CENTRAL)
                    QMessageBox.warning(
                        self,
                        "Base de Datos Central",
                        "ℹ️ No se cuenta con acceso a la base de datos central. Se utilizarán datos locales limpios."
                    )
                    # Disparar reseteo completo de datos locales (Ctrl + Shift + R)
                    db.reset_sync_data()
                    data_local = db.get_informe_cuatrimestral_local(
                        infoplaza_id=self.infoplaza_id,
                        anio=self.current_anio,
                        cuatrimestre=self.current_cuatrimestre
                    )
            else:
                data_local = db.get_informe_cuatrimestral_local(
                    infoplaza_id=self.infoplaza_id,
                    anio=self.current_anio,
                    cuatrimestre=self.current_cuatrimestre
                )

            header = data_local.get('header')
            caps = data_local.get('capacitaciones', [])
            srvs = data_local.get('servicios', [])
            acts = data_local.get('otras_actividades', [])

            # 1. Pestaña Firma y Observaciones
            if header:
                if header.get('cant_computadoras'): self.spin_pcs.setValue(header.get('cant_computadoras'))
                if header.get('asociado_nombre'): self.txt_asociado_nombre.setText(format_title_case(header.get('asociado_nombre')))
                if header.get('asociado_cedula'): self.txt_asociado_cedula.setText(str(header.get('asociado_cedula')).strip().upper())
                if header.get('dinamizador_nombre'): self.txt_dinamizador_nombre.setText(format_title_case(header.get('dinamizador_nombre')))
                if header.get('dinamizador_cedula'): self.txt_dinamizador_cedula.setText(str(header.get('dinamizador_cedula')).strip().upper())
                self.txt_obs_generales.setText(format_title_case(header.get('observaciones_generales', '')))

            # Fallback al Catálogo Maestro de la Infoplaza (Supabase) si los campos están vacíos
            info_maestra = getattr(self, 'infoplaza_info', None)
            if not info_maestra and self.infoplaza_id:
                try:
                    num = int(self.infoplaza_id)
                    info_maestra, _ = supabase_manager.get_infoplaza(num)
                    if info_maestra:
                        self.infoplaza_info = info_maestra
                except Exception:
                    pass

            if info_maestra:
                if not self.txt_asociado_nombre.text().strip() and info_maestra.get('asociado_nombre'):
                    self.txt_asociado_nombre.setText(format_title_case(info_maestra.get('asociado_nombre')))
                if not self.txt_asociado_cedula.text().strip() and info_maestra.get('asociado_cedula'):
                    self.txt_asociado_cedula.setText(str(info_maestra.get('asociado_cedula')).strip().upper())
                if not self.txt_dinamizador_nombre.text().strip() and info_maestra.get('dinamizador_nombre'):
                    self.txt_dinamizador_nombre.setText(format_title_case(info_maestra.get('dinamizador_nombre')))
                if not self.txt_dinamizador_cedula.text().strip() and info_maestra.get('dinamizador_cedula'):
                    self.txt_dinamizador_cedula.setText(str(info_maestra.get('dinamizador_cedula')).strip().upper())
                if info_maestra.get('cant_computadoras') and self.spin_pcs.value() == 6:
                    try:
                        self.spin_pcs.setValue(int(info_maestra.get('cant_computadoras')))
                    except Exception:
                        pass

            # 2. Pestaña Capacitaciones
            self.render_capacitaciones_tabla(caps)

            # 3. Pestaña Servicios
            if not srvs:
                srvs = [{"servicio_nombre": s_name, "ofrecido": True, "es_personalizado": False, "observaciones": ""} for s_name in DEFAULT_SERVICIOS]
            self.render_servicios_tabla(srvs)

            # 4. Pestaña Otras Actividades
            self.render_actividades_tabla(acts)

            # 5. Pestaña Estadística y Cumplimiento (Recalcular con la nueva BD de Access)
            self.actualizar_cuadro_visitas()
            self.actualizar_tarjeta_rendimiento()

        finally:
            # LIBERAR BANDERA DE BLOQUEO DE SUBIDAS
            self._is_pulling_from_cloud = False

    # =========================================================================
    # RENDERIZADO Y OPERACIONES DE TABLAS
    # =========================================================================

    def _confirmar_eliminacion(self, titulo: str, mensaje: str) -> bool:
        """Muestra una ventana de confirmación adaptada al tema claro/oscuro actual."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(f"A.D.A. - {titulo}")
        msg_box.setText(mensaje)
        msg_box.setIcon(QMessageBox.Question)
        
        btn_si = msg_box.addButton("Sí, eliminar", QMessageBox.YesRole)
        btn_no = msg_box.addButton("Cancelar", QMessageBox.NoRole)
        msg_box.setDefaultButton(btn_no)

        is_dark = getattr(self, 'is_dark_mode', True)
        bg_color = "#0f172a" if is_dark else "#ffffff"
        text_color = "#f8fafc" if is_dark else "#0f172a"
        btn_bg = "#1e293b" if is_dark else "#f1f5f9"
        btn_fg = "#f8fafc" if is_dark else "#0f172a"
        btn_border = "#475569" if is_dark else "#cbd5e1"

        msg_box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QMessageBox QLabel {{
                color: {text_color};
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton {{
                background-color: {btn_bg};
                color: {btn_fg};
                border: 1px solid {btn_border};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
                min-width: 90px;
            }}
            QPushButton:hover {{
                background-color: #0284c7;
                color: white;
                border-color: #0284c7;
            }}
        """)
        btn_si.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                border: 1px solid #b91c1c;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
                color: white;
            }
        """)

        msg_box.exec_()
        return msg_box.clickedButton() == btn_si

    def render_capacitaciones_tabla(self, capacitaciones: List[Dict[str, Any]]):
        self._updating_table_cap = True
        self.table_cap.blockSignals(True)
        try:
            self.table_cap.setRowCount(0)
            tot_part = 0
            tot_hrs = 0.0

            for cap in capacitaciones:
                row = self.table_cap.rowCount()
                self.table_cap.insertRow(row)

                m = format_title_case(cap.get('mes', ''))
                c = format_title_case(cap.get('categoria', ''))
                t = format_title_case(cap.get('tema', ''))
                p = int(cap.get('participantes', 0))
                h = float(cap.get('horas', 0))
                o = format_title_case(cap.get('observaciones', ''))

                tot_part += p
                tot_hrs += h

                item_m = QTableWidgetItem(m)
                item_c = QTableWidgetItem(c)
                item_t = QTableWidgetItem(t)
                item_p = QTableWidgetItem(str(p))
                item_h = QTableWidgetItem(str(h))
                item_o = QTableWidgetItem(o)

                item_p.setTextAlignment(Qt.AlignCenter)
                item_h.setTextAlignment(Qt.AlignCenter)

                if self.is_dark_mode:
                    item_m.setForeground(QColor("#f8fafc"))
                    item_c.setForeground(QColor("#38bdf8"))
                    item_t.setForeground(QColor("#f8fafc"))
                    item_p.setForeground(QColor("#38bdf8"))
                    item_h.setForeground(QColor("#38bdf8"))
                    item_o.setForeground(QColor("#cbd5e1"))
                else:
                    item_m.setForeground(QColor("#0f172a"))
                    item_c.setForeground(QColor("#0284c7"))
                    item_t.setForeground(QColor("#0f172a"))
                    item_p.setForeground(QColor("#0284c7"))
                    item_h.setForeground(QColor("#0284c7"))
                    item_o.setForeground(QColor("#475569"))

                tip_cap = "Doble clic en la celda para editar este campo especifico"
                item_m.setToolTip(tip_cap)
                item_c.setToolTip(tip_cap)
                item_t.setToolTip(tip_cap)
                item_p.setToolTip(tip_cap)
                item_h.setToolTip(tip_cap)
                item_o.setToolTip(tip_cap)

                self.table_cap.setItem(row, 0, item_m)
                self.table_cap.setItem(row, 1, item_c)
                self.table_cap.setItem(row, 2, item_t)
                self.table_cap.setItem(row, 3, item_p)
                self.table_cap.setItem(row, 4, item_h)
                self.table_cap.setItem(row, 5, item_o)

                # Botón Edit
                btn_edit = QPushButton("Edit")
                btn_edit.setToolTip("Editar esta capacitación")
                btn_edit.setCursor(Qt.PointingHandCursor)
                btn_edit.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {"#0284c7" if self.is_dark_mode else "#0284c7"};
                        color: white;
                        font-weight: bold;
                        font-size: 11px;
                        border: none;
                        border-radius: 4px;
                        padding: 3px 8px;
                    }}
                    QPushButton:hover {{
                        background-color: {"#0369a1" if self.is_dark_mode else "#0369a1"};
                    }}
                """)
                btn_edit.clicked.connect(lambda _, r=row: self._on_table_cap_double_clicked(self.table_cap.model().index(r, 2)))

                # Botón de Eliminar (Sutil e intuitivo)
                btn_del = QPushButton("✕")
                btn_del.setToolTip("Eliminar esta capacitación")
                btn_del.setCursor(Qt.PointingHandCursor)
                btn_del.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {"#64748b" if self.is_dark_mode else "#94a3b8"};
                        font-weight: bold;
                        font-size: 14px;
                        border: none;
                        border-radius: 4px;
                        padding: 2px 8px;
                    }}
                    QPushButton:hover {{
                        background-color: {"#3b1118" if self.is_dark_mode else "#fee2e2"};
                        color: {"#f87171" if self.is_dark_mode else "#dc2626"};
                    }}
                """)
                btn_del.clicked.connect(lambda _, r=row: self.eliminar_capacitacion(r))

                btn_container = QWidget()
                btn_layout = QHBoxLayout(btn_container)
                btn_layout.setContentsMargins(0, 0, 0, 0)
                btn_layout.setAlignment(Qt.AlignCenter)
                btn_layout.setSpacing(4)
                btn_layout.addWidget(btn_edit)
                btn_layout.addWidget(btn_del)

                self.table_cap.setCellWidget(row, 6, btn_container)

            self.card_tot_cap.lbl_val.setText(str(len(capacitaciones)))
            self.card_tot_part.lbl_val.setText(str(tot_part))
            self.card_tot_horas.lbl_val.setText(f"{tot_hrs:.1f} hrs")
        finally:
            self.table_cap.blockSignals(False)
            self._updating_table_cap = False

    def _on_table_cap_item_changed(self, item: QTableWidgetItem):
        if getattr(self, '_updating_table_cap', False):
            return
        
        col = item.column()
        text = item.text().strip()

        self._updating_table_cap = True
        try:
            if col in (0, 1, 2, 5):  # Mes, Categoría, Tema, Observaciones
                formatted = format_title_case(text)
                if formatted != text:
                    item.setText(formatted)
            elif col == 3:  # Participantes
                try:
                    val = int(text)
                    if val < 0: val = 0
                    item.setText(str(val))
                except ValueError:
                    item.setText("0")
            elif col == 4:  # Horas
                try:
                    val = float(text)
                    if val < 0: val = 0.0
                    item.setText(f"{val:.1f}")
                except ValueError:
                    item.setText("0.0")

            # Recalcular totales y actualizar KPI cards
            tot_part = 0
            tot_hrs = 0.0
            for r in range(self.table_cap.rowCount()):
                try:
                    tot_part += int(self.table_cap.item(r, 3).text()) if self.table_cap.item(r, 3) else 0
                except (ValueError, AttributeError):
                    pass
                try:
                    tot_hrs += float(self.table_cap.item(r, 4).text()) if self.table_cap.item(r, 4) else 0.0
                except (ValueError, AttributeError):
                    pass

            if hasattr(self, 'card_tot_cap') and self.card_tot_cap:
                self.card_tot_cap.lbl_val.setText(str(self.table_cap.rowCount()))
            if hasattr(self, 'card_tot_part') and self.card_tot_part:
                self.card_tot_part.lbl_val.setText(str(tot_part))
            if hasattr(self, 'card_tot_horas') and self.card_tot_horas:
                self.card_tot_horas.lbl_val.setText(f"{tot_hrs:.1f} hrs")

            self.auto_sync_guardar_local_y_cloud()
        finally:
            self._updating_table_cap = False

    def _verificar_descarga_en_curso(self) -> bool:
        """Verifica si hay una descarga o conmutación inicial activa desde Supabase."""
        if getattr(self, '_is_pulling_from_cloud', False):
            QMessageBox.information(
                self,
                "Sincronización en Curso",
                "ℹ️ Espere un momento, sincronizando con base de datos central."
            )
            return True
        return False

    def agregar_capacitacion(self):
        if self._verificar_descarga_en_curso():
            return

        cat_idx = self.combo_cap_categoria.currentIndex()
        cat = self.combo_cap_categoria.currentText().strip()
        if cat_idx <= 0 or not cat or cat == "-- Seleccionar Categoría --":
            QMessageBox.warning(self, "Selección Obligatoria", "Por favor seleccione una categoría obligatoria para la capacitación.")
            return

        tema = format_title_case(self.combo_cap_tema.text())
        if not tema:
            QMessageBox.warning(self, "Atención", "Por favor ingrese el tema de la capacitación.")
            return

        mes = self.combo_cap_mes.currentText()
        part = self.spin_cap_part.value()
        horas = self.spin_cap_horas.value()
        obs = format_title_case(self.txt_cap_obs.text())

        caps = self.obtener_capacitaciones_de_tabla()
        
        nuevo_dato = {
            "mes": mes,
            "categoria": cat,
            "tema": tema,
            "participantes": part,
            "horas": horas,
            "observaciones": obs
        }

        if getattr(self, 'edit_row_cap_idx', None) is not None:
            # Modo actualización
            row = self.edit_row_cap_idx
            if 0 <= row < len(caps):
                caps[row] = nuevo_dato
            self.edit_row_cap_idx = None
            self.btn_add_cap.setText("+ Capacitación")
            self.btn_add_cap.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
            self.form_box_cap.setTitle("➕ Agregar Nueva Capacitación o Curso")
            self.btn_cancelar_edit_cap.setVisible(False)
        else:
            # Modo agregar
            caps.append(nuevo_dato)

        self.render_capacitaciones_tabla(caps)

        self.combo_cap_categoria.setCurrentIndex(0)
        self.combo_cap_tema.clear()
        self.spin_cap_part.setValue(5)
        self.txt_cap_obs.clear()
        self.auto_sync_guardar_local_y_cloud()

    def _on_table_cap_double_clicked(self, index):
        row = index.row()
        caps = self.obtener_capacitaciones_de_tabla()
        if 0 <= row < len(caps):
            cap = caps[row]

            # Mes
            mes = cap.get("mes", "")
            idx = self.combo_cap_mes.findText(mes, Qt.MatchFixedString | Qt.MatchCaseSensitive)
            if idx < 0:
                idx = self.combo_cap_mes.findText(mes, Qt.MatchFixedString)
            if idx >= 0:
                self.combo_cap_mes.setCurrentIndex(idx)

            # Categoría
            cat = cap.get("categoria", "")
            idx = self.combo_cap_categoria.findText(cat, Qt.MatchFixedString | Qt.MatchCaseSensitive)
            if idx < 0:
                idx = self.combo_cap_categoria.findText(cat, Qt.MatchFixedString)
            if idx >= 0:
                self.combo_cap_categoria.setCurrentIndex(idx)

            # Resto de campos
            self.combo_cap_tema.setText(cap.get("tema", ""))
            self.spin_cap_part.setValue(int(cap.get("participantes", 0)))
            self.spin_cap_horas.setValue(int(float(cap.get("horas", 0))))
            self.txt_cap_obs.setText(cap.get("observaciones", ""))

            # Cambiar a modo edición
            self.edit_row_cap_idx = row
            self.btn_add_cap.setText("✔ Actualizar")
            self.btn_add_cap.setStyleSheet(
                "background-color: #f59e0b; color: white; font-weight: bold; "
                "padding: 6px 12px; border-radius: 4px;"
            )
            self.form_box_cap.setTitle(f"✏️ Editando Actividad de Capacitación — fila {row + 1}")
            self.btn_cancelar_edit_cap.setVisible(True)

            # Scroll al formulario y foco específico al campo donde se hizo doble clic
            col = index.column() if hasattr(index, 'column') else 2
            if col == 0:
                self.combo_cap_mes.setFocus()
            elif col == 1:
                self.combo_cap_categoria.setFocus()
            elif col == 2:
                self.combo_cap_tema.setFocus()
                if hasattr(self.combo_cap_tema, 'selectAll'):
                    self.combo_cap_tema.selectAll()
            elif col == 3:
                self.spin_cap_part.setFocus()
                self.spin_cap_part.selectAll()
            elif col == 4:
                self.spin_cap_horas.setFocus()
                self.spin_cap_horas.selectAll()
            elif col == 5:
                self.txt_cap_obs.setFocus()
                self.txt_cap_obs.selectAll()
            else:
                self.combo_cap_tema.setFocus()

    def _cancelar_edicion_cap(self):
        """Cancela el modo edición y vuelve al modo agregar."""
        self.edit_row_cap_idx = None
        self.btn_add_cap.setText("+ Capacitación")
        self.btn_add_cap.setStyleSheet(
            "background-color: #10b981; color: white; font-weight: bold; "
            "padding: 6px 12px; border-radius: 4px;"
        )
        self.form_box_cap.setTitle("➕ Agregar Nueva Capacitación o Curso")
        self.btn_cancelar_edit_cap.setVisible(False)
        self.combo_cap_categoria.setCurrentIndex(0)
        self.combo_cap_tema.clear()
        self.txt_cap_obs.clear()


    def _on_tab_changed(self, index: int):
        """Al cambiar de pestaña, cancela silenciosamente cualquier edición activa."""
        idx_cap = self.tabs.indexOf(self.tab_capacitaciones)
        idx_act = self.tabs.indexOf(self.tab_actividades)

        # Si salimos de la pestaña de Capacitaciones y hay edición activa → cancelar
        if index != idx_cap and getattr(self, 'edit_row_cap_idx', None) is not None:
            self._cancelar_edicion_cap()

        # Si salimos de la pestaña de Actividades y hay edición activa → cancelar
        if index != idx_act and getattr(self, 'edit_row_act_idx', None) is not None:
            self._cancelar_edicion_act()


    def eliminar_capacitacion(self, row_idx: int):
        if self._verificar_descarga_en_curso():
            return

        caps = self.obtener_capacitaciones_de_tabla()
        if 0 <= row_idx < len(caps):
            tema = caps[row_idx].get('tema', 'esta actividad')
            if self._confirmar_eliminacion("Confirmar eliminación", f"¿Estás seguro de que deseas eliminar la actividad de capacitación:\n\n'{tema}'?"):
                caps.pop(row_idx)
                self.render_capacitaciones_tabla(caps)
                self.auto_sync_guardar_local_y_cloud()

    def obtener_capacitaciones_de_tabla(self) -> List[Dict[str, Any]]:
        caps = []
        for r in range(self.table_cap.rowCount()):
            mes = self.table_cap.item(r, 0).text() if self.table_cap.item(r, 0) else ""
            cat = self.table_cap.item(r, 1).text() if self.table_cap.item(r, 1) else ""
            tema = self.table_cap.item(r, 2).text() if self.table_cap.item(r, 2) else ""
            part = int(self.table_cap.item(r, 3).text()) if self.table_cap.item(r, 3) else 0
            hrs = float(self.table_cap.item(r, 4).text()) if self.table_cap.item(r, 4) else 0.0
            obs = self.table_cap.item(r, 5).text() if self.table_cap.item(r, 5) else ""
            caps.append({
                "mes": format_title_case(mes),
                "categoria": format_title_case(cat),
                "tema": format_title_case(tema),
                "participantes": part,
                "horas": hrs,
                "observaciones": format_title_case(obs)
            })
        return caps


    # --- SERVICIOS ---

    def render_servicios_tabla(self, servicios_guardados: List[Dict[str, Any]]):
        self._updating_table_srv = True
        self.table_srv.blockSignals(True)
        try:
            self.table_srv.setRowCount(0)
            
            def norm_str(s: str) -> str:
                return re.sub(r'\s+', ' ', str(s or '')).strip().lower()

            default_norm_map = {norm_str(d): d for d in DEFAULT_SERVICIOS}

            # Mapear servicios guardados por nombre normalizado (deduplicando)
            srv_map = {}
            custom_saved = []
            seen_custom = set()

            for s in servicios_guardados:
                n_raw = s.get('servicio_nombre', '')
                n_norm = norm_str(n_raw)
                if n_norm in default_norm_map:
                    if n_norm not in srv_map:
                        item_copy = dict(s)
                        item_copy['servicio_nombre'] = default_norm_map[n_norm]
                        item_copy['es_personalizado'] = False
                        srv_map[n_norm] = item_copy
                else:
                    if n_norm not in seen_custom and n_norm != "":
                        seen_custom.add(n_norm)
                        item_copy = dict(s)
                        item_copy['es_personalizado'] = True
                        custom_saved.append(item_copy)

            # 1. Asegurar lista recurrente base (6 items exactos)
            lista_render = []
            for default_name in DEFAULT_SERVICIOS:
                n_norm = norm_str(default_name)
                if n_norm in srv_map:
                    lista_render.append(srv_map[n_norm])
                else:
                    lista_render.append({
                        "servicio_nombre": default_name,
                        "ofrecido": True,
                        "es_personalizado": False,
                        "observaciones": ""
                    })

            # 2. Agregar personalizados adicionales únicos
            lista_render.extend(custom_saved)

            for srv in lista_render:
                row = self.table_srv.rowCount()
                self.table_srv.insertRow(row)

                chk = QCheckBox()
                chk.blockSignals(True)
                chk.setChecked(bool(srv.get('ofrecido', True)))
                chk.blockSignals(False)
                chk.setCursor(Qt.PointingHandCursor)
                chk.setToolTip("Marcar si el servicio fue ofrecido en el cuatrimestre")

                is_dark = self.is_dark_mode
                if self.main_app and hasattr(self.main_app, 'is_dark_mode'):
                    is_dark = self.main_app.is_dark_mode

                aplicar_estilo_checkbox_srv(chk, is_dark)
                chk.stateChanged.connect(lambda _: self._on_servicio_checkbox_changed())

                raw_nom = srv.get('servicio_nombre', '')
                norm_nom = norm_str(raw_nom)
                is_custom = srv.get('es_personalizado', False)
                if norm_nom in default_norm_map:
                    nombre = default_norm_map[norm_nom]
                    is_custom = False
                else:
                    nombre = format_title_case(raw_nom)

                obs = format_title_case(srv.get('observaciones', ''))
                es_custom_str = "Personalizado ➕" if is_custom else "Recurrente Base 🔄"

                cell_chk = QWidget()
                l_chk = QHBoxLayout(cell_chk)
                l_chk.addWidget(chk)
                l_chk.setAlignment(Qt.AlignCenter)
                l_chk.setContentsMargins(0, 0, 0, 0)

                self.table_srv.setCellWidget(row, 0, cell_chk)
                
                item_nom = QTableWidgetItem(nombre)
                item_obs = QTableWidgetItem(obs)
                item_orig = QTableWidgetItem(es_custom_str)

                if not is_custom:
                    item_nom.setFlags(item_nom.flags() & ~Qt.ItemIsEditable)
                    item_orig.setFlags(item_orig.flags() & ~Qt.ItemIsEditable)
                else:
                    item_orig.setFlags(item_orig.flags() & ~Qt.ItemIsEditable)

                if self.is_dark_mode:
                    item_nom.setForeground(QColor("#f8fafc"))
                    item_obs.setForeground(QColor("#cbd5e1"))
                    item_orig.setForeground(QColor("#38bdf8") if is_custom else QColor("#94a3b8"))
                else:
                    item_nom.setForeground(QColor("#0f172a"))
                    item_obs.setForeground(QColor("#475569"))
                    item_orig.setForeground(QColor("#0284c7") if is_custom else QColor("#64748b"))

                tip_srv = "Doble clic en la celda o presionar Edit para modificar"
                item_nom.setToolTip(tip_srv)
                item_obs.setToolTip(tip_srv)

                self.table_srv.setItem(row, 1, item_nom)
                self.table_srv.setItem(row, 2, item_obs)
                self.table_srv.setItem(row, 3, item_orig)

                # Columna 4: Acción (Botón Edit para todos, + Eliminar para personalizados)
                btn_edit = QPushButton("Edit")
                btn_edit.setToolTip("Editar este servicio")
                btn_edit.setCursor(Qt.PointingHandCursor)
                btn_edit.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {"#0284c7" if self.is_dark_mode else "#0284c7"};
                        color: white;
                        font-weight: bold;
                        font-size: 11px;
                        border: none;
                        border-radius: 4px;
                        padding: 3px 8px;
                    }}
                    QPushButton:hover {{
                        background-color: {"#0369a1" if self.is_dark_mode else "#0369a1"};
                    }}
                """)
                btn_edit.clicked.connect(lambda _, r=row: self._on_table_srv_double_clicked(self.table_srv.model().index(r, 2)))

                btn_container = QWidget()
                btn_layout = QHBoxLayout(btn_container)
                btn_layout.setContentsMargins(0, 0, 0, 0)
                btn_layout.setAlignment(Qt.AlignCenter)
                btn_layout.setSpacing(4)
                btn_layout.addWidget(btn_edit)

                if is_custom:
                    btn_del = QPushButton("✕")
                    btn_del.setToolTip("Eliminar servicio personalizado")
                    btn_del.setCursor(Qt.PointingHandCursor)
                    btn_del.setStyleSheet(f"""
                        QPushButton {{
                            background-color: transparent;
                            color: {"#64748b" if self.is_dark_mode else "#94a3b8"};
                            font-weight: bold;
                            font-size: 14px;
                            border: none;
                            border-radius: 4px;
                            padding: 2px 8px;
                        }}
                        QPushButton:hover {{
                            background-color: {"#3b1118" if self.is_dark_mode else "#fee2e2"};
                            color: {"#f87171" if self.is_dark_mode else "#dc2626"};
                        }}
                    """)
                    btn_del.clicked.connect(lambda _, r=row: self.eliminar_servicio(r))
                    btn_layout.addWidget(btn_del)

                self.table_srv.setCellWidget(row, 4, btn_container)
        finally:
            self.table_srv.blockSignals(False)
            self._updating_table_srv = False

    def _on_table_srv_double_clicked(self, index):
        row = index.row()
        col = index.column() if hasattr(index, 'column') else 2
        srvs = self.obtener_servicios_de_tabla()
        if 0 <= row < len(srvs):
            srv = srvs[row]
            is_custom = srv.get('es_personalizado', False)

            if is_custom:
                # Servicio personalizado: abrir modal de edición
                nombre_act = srv.get('servicio_nombre', '')
                obs_act = srv.get('observaciones', '')
                dlg = NuevoServicioDialog(
                    parent=self, 
                    is_dark_mode=getattr(self, 'is_dark_mode', False),
                    nombre_inicial=nombre_act,
                    obs_inicial=obs_act,
                    es_edicion=True
                )
                if dlg.exec_() == QDialog.Accepted and dlg.servicio_nombre:
                    srvs[row]['servicio_nombre'] = dlg.servicio_nombre
                    srvs[row]['observaciones'] = dlg.servicio_obs
                    self.render_servicios_tabla(srvs)
                    self.auto_sync_guardar_local_y_cloud()
            else:
                # Servicio base: editar in-situ en la tabla (observaciones)
                item_target = self.table_srv.item(row, 2)
                if item_target and (item_target.flags() & Qt.ItemIsEditable):
                    self.table_srv.editItem(item_target)

    def _on_servicio_checkbox_changed(self):
        """Disparado al marcar o desmarcar un checkbox de servicio en la tabla."""
        if getattr(self, '_updating_table_srv', False):
            return
        self.auto_sync_guardar_local_y_cloud()

    def _on_table_srv_item_changed(self, item: QTableWidgetItem):
        if getattr(self, '_updating_table_srv', False):
            return

        col = item.column()
        text = item.text().strip()

        self._updating_table_srv = True
        try:
            if col in (1, 2):  # Tipo de Servicio, Observaciones
                formatted = format_title_case(text)
                if formatted != text:
                    item.setText(formatted)
            self.auto_sync_guardar_local_y_cloud()
        finally:
            self._updating_table_srv = False

    def eliminar_servicio(self, row_idx: int):
        if self._verificar_descarga_en_curso():
            return
        srvs = self.obtener_servicios_de_tabla()
        if 0 <= row_idx < len(srvs):
            nombre = srvs[row_idx].get('servicio_nombre', 'este servicio')
            if self._confirmar_eliminacion("Confirmar eliminación", f"¿Estás seguro de que deseas eliminar el servicio personalizado:\n\n'{nombre}'?"):
                srvs.pop(row_idx)
                self.render_servicios_tabla(srvs)
                self.auto_sync_guardar_local_y_cloud()

    def agregar_servicio_personalizado(self):
        if self._verificar_descarga_en_curso():
            return
        def norm_str(s: str) -> str:
            return re.sub(r'\s+', ' ', str(s or '')).strip().lower()
        dlg = NuevoServicioDialog(parent=self, is_dark_mode=getattr(self, 'is_dark_mode', False))
        if dlg.exec_() == QDialog.Accepted and dlg.servicio_nombre:
            nombre = dlg.servicio_nombre
            obs = getattr(dlg, 'servicio_obs', '')
            srvs = self.obtener_servicios_de_tabla()
            if not any(norm_str(s.get('servicio_nombre', '')) == norm_str(nombre) for s in srvs):
                srvs.append({
                    "servicio_nombre": nombre,
                    "ofrecido": True,
                    "es_personalizado": True,
                    "observaciones": obs
                })
                self.render_servicios_tabla(srvs)
                self.auto_sync_guardar_local_y_cloud()

    def obtener_servicios_de_tabla(self) -> List[Dict[str, Any]]:
        def norm_str(s: str) -> str:
            return re.sub(r'\s+', ' ', str(s or '')).strip().lower()
        default_norm_map = {norm_str(d): d for d in DEFAULT_SERVICIOS}

        srvs = []
        for r in range(self.table_srv.rowCount()):
            cell_chk = self.table_srv.cellWidget(r, 0)
            chk = cell_chk.findChild(QCheckBox) if cell_chk else None
            ofrecido = chk.isChecked() if chk else True

            nombre = self.table_srv.item(r, 1).text() if self.table_srv.item(r, 1) else ""
            obs = self.table_srv.item(r, 2).text() if self.table_srv.item(r, 2) else ""
            tipo_str = self.table_srv.item(r, 3).text() if self.table_srv.item(r, 3) else ""

            norm_name = norm_str(nombre)
            if norm_name in default_norm_map:
                srv_name = default_norm_map[norm_name]
                is_custom = False
            else:
                srv_name = format_title_case(nombre)
                is_custom = ("Personalizado" in tipo_str)

            srvs.append({
                "servicio_nombre": srv_name,
                "ofrecido": ofrecido,
                "es_personalizado": is_custom,
                "observaciones": format_title_case(obs)
            })
        return srvs

    # --- OTRAS ACTIVIDADES ---

    def render_actividades_tabla(self, actividades: List[Dict[str, Any]]):
        self._updating_table_act = True
        self.table_act.blockSignals(True)
        try:
            self.table_act.setRowCount(0)
            for act in actividades:
                row = self.table_act.rowCount()
                self.table_act.insertRow(row)

                cat = format_title_case(act.get('categoria', ''))
                nom = format_title_case(act.get('actividad', ''))
                part_val = act.get('participantes', 0)
                try:
                    part_int = int(part_val or 0)
                except (ValueError, TypeError):
                    part_int = 0
                part_str = str(part_int) if part_int > 0 else ""
                obs = format_title_case(act.get('observaciones', ''))

                item_cat = QTableWidgetItem(cat)
                item_nom = QTableWidgetItem(nom)
                item_part = QTableWidgetItem(part_str)
                item_obs = QTableWidgetItem(obs)

                item_part.setTextAlignment(Qt.AlignCenter)

                if self.is_dark_mode:
                    item_cat.setForeground(QColor("#a78bfa"))
                    item_nom.setForeground(QColor("#f8fafc"))
                    item_part.setForeground(QColor("#38bdf8") if part_int > 0 else QColor("#94a3b8"))
                    item_obs.setForeground(QColor("#cbd5e1"))
                else:
                    item_cat.setForeground(QColor("#7c3aed"))
                    item_nom.setForeground(QColor("#0f172a"))
                    item_part.setForeground(QColor("#0284c7") if part_int > 0 else QColor("#64748b"))
                    item_obs.setForeground(QColor("#475569"))

                tip_act = "Doble clic en la celda para editar este campo especifico"
                item_cat.setToolTip(tip_act)
                item_nom.setToolTip(tip_act)
                item_part.setToolTip(tip_act)
                item_obs.setToolTip(tip_act)

                self.table_act.setItem(row, 0, item_cat)
                self.table_act.setItem(row, 1, item_nom)
                self.table_act.setItem(row, 2, item_part)
                self.table_act.setItem(row, 3, item_obs)

                # Botón Edit
                btn_edit = QPushButton("Edit")
                btn_edit.setToolTip("Editar esta actividad especial")
                btn_edit.setCursor(Qt.PointingHandCursor)
                btn_edit.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {"#8b5cf6" if self.is_dark_mode else "#8b5cf6"};
                        color: white;
                        font-weight: bold;
                        font-size: 11px;
                        border: none;
                        border-radius: 4px;
                        padding: 3px 8px;
                    }}
                    QPushButton:hover {{
                        background-color: {"#7c3aed" if self.is_dark_mode else "#7c3aed"};
                    }}
                """)
                btn_edit.clicked.connect(lambda _, r=row: self._on_table_act_double_clicked(self.table_act.model().index(r, 1)))

                # Botón Eliminar
                btn_del = QPushButton("✕")
                btn_del.setToolTip("Eliminar esta actividad especial")
                btn_del.setCursor(Qt.PointingHandCursor)
                btn_del.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {"#64748b" if self.is_dark_mode else "#94a3b8"};
                        font-weight: bold;
                        font-size: 14px;
                        border: none;
                        border-radius: 4px;
                        padding: 2px 8px;
                    }}
                    QPushButton:hover {{
                        background-color: {"#3b1118" if self.is_dark_mode else "#fee2e2"};
                        color: {"#f87171" if self.is_dark_mode else "#dc2626"};
                    }}
                """)
                btn_del.clicked.connect(lambda _, r=row: self.eliminar_actividad(r))

                btn_container = QWidget()
                btn_layout = QHBoxLayout(btn_container)
                btn_layout.setContentsMargins(0, 0, 0, 0)
                btn_layout.setAlignment(Qt.AlignCenter)
                btn_layout.setSpacing(4)
                btn_layout.addWidget(btn_edit)
                btn_layout.addWidget(btn_del)

                self.table_act.setCellWidget(row, 4, btn_container)
        finally:
            self.table_act.blockSignals(False)
            self._updating_table_act = False

    def _on_table_act_item_changed(self, item: QTableWidgetItem):
        if getattr(self, '_updating_table_act', False):
            return

        col = item.column()
        text = item.text().strip()

        self._updating_table_act = True
        try:
            if col == 2:  # Total Participantes
                val = re.sub(r'[^\d]', '', text)
                if val != text:
                    item.setText(val)
            elif col in (0, 1, 3):  # Categoría, Actividad, Observaciones
                formatted = format_title_case(text)
                if formatted != text:
                    item.setText(formatted)
            self.auto_sync_guardar_local_y_cloud()
        finally:
            self._updating_table_act = False

    def agregar_actividad(self):
        if self._verificar_descarga_en_curso():
            return

        cat_idx = self.combo_act_categoria.currentIndex()
        cat = self.combo_act_categoria.currentText().strip()
        if cat_idx <= 0 or not cat or cat == "-- Seleccionar Categoría --":
            QMessageBox.warning(self, "Selección Obligatoria", "Por favor seleccione una categoría obligatoria para la actividad.")
            return

        nom = format_title_case(self.txt_act_nombre.text())
        if not nom:
            QMessageBox.warning(self, "Atención", "Ingrese el nombre de la actividad.")
            return

        part = self.spin_act_part.value() if hasattr(self, 'spin_act_part') else 0
        obs = format_title_case(self.txt_act_obs.text())
        acts = self.obtener_actividades_de_tabla()
        
        nuevo_dato = {
            "categoria": cat, 
            "actividad": nom, 
            "participantes": part, 
            "observaciones": obs
        }

        if getattr(self, 'edit_row_act_idx', None) is not None:
            row = self.edit_row_act_idx
            if 0 <= row < len(acts):
                acts[row] = nuevo_dato
            self.edit_row_act_idx = None
            self.btn_add_act.setText("+ Actividad")
            self.btn_add_act.setStyleSheet("background-color: #8b5cf6; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
            self.form_box_act.setTitle("➕ Agregar Nueva Actividad Especial")
            self.btn_cancelar_edit_act.setVisible(False)
        else:
            acts.append(nuevo_dato)

        self.render_actividades_tabla(acts)

        self.combo_act_categoria.setCurrentIndex(0)
        self.txt_act_nombre.clear()
        if hasattr(self, 'spin_act_part'):
            self.spin_act_part.setValue(0)
        self.txt_act_obs.clear()
        self.auto_sync_guardar_local_y_cloud()

    def _on_table_act_double_clicked(self, index):
        row = index.row()
        acts = self.obtener_actividades_de_tabla()
        if 0 <= row < len(acts):
            act = acts[row]

            # Categoría
            cat = act.get("categoria", "")
            idx = self.combo_act_categoria.findText(cat, Qt.MatchFixedString | Qt.MatchCaseSensitive)
            if idx < 0:
                idx = self.combo_act_categoria.findText(cat, Qt.MatchFixedString)
            if idx >= 0:
                self.combo_act_categoria.setCurrentIndex(idx)

            self.txt_act_nombre.setText(act.get("actividad", ""))

            if hasattr(self, 'spin_act_part'):
                self.spin_act_part.setValue(int(act.get("participantes", 0)))

            self.txt_act_obs.setText(act.get("observaciones", ""))

            # Cambiar a modo edición
            self.edit_row_act_idx = row
            self.btn_add_act.setText("✔ Actualizar")
            self.btn_add_act.setStyleSheet(
                "background-color: #f59e0b; color: white; font-weight: bold; "
                "padding: 6px 12px; border-radius: 4px;"
            )
            self.form_box_act.setTitle(f"✏️ Editando Actividad Especial — fila {row + 1}")
            self.btn_cancelar_edit_act.setVisible(True)
            # Foco específico al campo donde se hizo doble clic
            col = index.column() if hasattr(index, 'column') else 1
            if col == 0:
                self.combo_act_categoria.setFocus()
            elif col == 1:
                self.txt_act_nombre.setFocus()
                self.txt_act_nombre.selectAll()
            elif col == 2:
                if hasattr(self, 'spin_act_part'):
                    self.spin_act_part.setFocus()
                    self.spin_act_part.selectAll()
            elif col == 3:
                self.txt_act_obs.setFocus()
                self.txt_act_obs.selectAll()
            else:
                self.txt_act_nombre.setFocus()

    def _cancelar_edicion_act(self):
        """Cancela el modo edición y vuelve al modo agregar."""
        self.edit_row_act_idx = None
        self.btn_add_act.setText("+ Actividad")
        self.btn_add_act.setStyleSheet(
            "background-color: #8b5cf6; color: white; font-weight: bold; "
            "padding: 6px 12px; border-radius: 4px;"
        )
        self.form_box_act.setTitle("➕ Agregar Nueva Actividad Especial")
        self.btn_cancelar_edit_act.setVisible(False)
        self.combo_act_categoria.setCurrentIndex(0)
        self.txt_act_nombre.clear()
        if hasattr(self, 'spin_act_part'):
            self.spin_act_part.setValue(0)
        self.txt_act_obs.clear()

    def eliminar_actividad(self, row_idx: int):
        if self._verificar_descarga_en_curso():
            return
        acts = self.obtener_actividades_de_tabla()
        if 0 <= row_idx < len(acts):
            nombre = acts[row_idx].get('actividad', 'esta actividad')
            if self._confirmar_eliminacion("Confirmar eliminación", f"¿Estás seguro de que deseas eliminar la actividad especial:\n\n'{nombre}'?"):
                acts.pop(row_idx)
                self.render_actividades_tabla(acts)
                self.auto_sync_guardar_local_y_cloud()

    def obtener_actividades_de_tabla(self) -> List[Dict[str, Any]]:
        acts = []
        for r in range(self.table_act.rowCount()):
            cat = self.table_act.item(r, 0).text() if self.table_act.item(r, 0) else ""
            nom = self.table_act.item(r, 1).text() if self.table_act.item(r, 1) else ""
            part_str = self.table_act.item(r, 2).text() if self.table_act.item(r, 2) else ""
            obs = self.table_act.item(r, 3).text() if self.table_act.item(r, 3) else ""

            try:
                part = int(re.sub(r'[^\d]', '', part_str) or 0)
            except Exception:
                part = 0

            acts.append({
                "categoria": format_title_case(cat),
                "actividad": format_title_case(nom),
                "participantes": part,
                "observaciones": format_title_case(obs)
            })
        return acts


    # --- PRECARGA Y ESTADÍSTICA DE VISITAS ---

    def iniciar_precarga_background(self):
        """Inicia la precarga silenciosa de datos en segundo plano si la Infoplaza ya está detectada."""
        if not self.infoplaza_id:
            self.cargar_datos_infoplaza()
        
        if self.infoplaza_id:
            self.preloader_thread = InformeCuatrimestralPreloaderThread(
                infoplaza_id=self.infoplaza_id,
                anio=self.current_anio,
                cuatrimestre=self.current_cuatrimestre,
                parent=self
            )
            self.preloader_thread.datos_cargados.connect(self._on_precarga_completada)
            self.preloader_thread.start()

    def _on_precarga_completada(self, data_local: dict):
        """Aplica los datos precargados en el hilo principal sin bloqueos."""
        if data_local:
            header = data_local.get('header')
            caps = data_local.get('capacitaciones', [])
            srvs = data_local.get('servicios', [])
            acts = data_local.get('otras_actividades', [])

            if header:
                self.spin_pcs.setValue(header.get('cant_computadoras', 6))
                if header.get('asociado_nombre'): self.txt_asociado_nombre.setText(format_title_case(header.get('asociado_nombre')))
                if header.get('asociado_cedula'): self.txt_asociado_cedula.setText(header.get('asociado_cedula'))
                if header.get('dinamizador_nombre'): self.txt_dinamizador_nombre.setText(format_title_case(header.get('dinamizador_nombre')))
                if header.get('dinamizador_cedula'): self.txt_dinamizador_cedula.setText(header.get('dinamizador_cedula'))
                self.txt_obs_generales.setText(format_title_case(header.get('observaciones_generales', '')))

            if caps: self.render_capacitaciones_tabla(caps)
            if srvs: self.render_servicios_tabla(srvs)
            if acts: self.render_actividades_tabla(acts)

        self.actualizar_cuadro_visitas()
        self.actualizar_tarjeta_rendimiento()

    def _obtener_dataframe_visitas(self) -> Optional[Any]:
        """
        Obtiene el DataFrame de visitas del cuatrimestre actual:
        1. Intenta desde `self.main_app.data` si contiene registros.
        2. Si no, consulta la caché SQLite local `registros_ventas_cache` directamente.
        """
        try:
            import pandas as pd
            conn = db.get_connection()
            query = """
                SELECT datetime as DATETIME, username as USERNAME, itemname as ITEMNAME 
                FROM registros_ventas_cache
                ORDER BY datetime DESC
            """
            df_cache = pd.read_sql_query(query, conn)
            conn.close()

            if df_cache is not None and not df_cache.empty:
                df = df_cache
            elif hasattr(self.main_app, 'data') and self.main_app.data is not None and not self.main_app.data.empty:
                df = self.main_app.data.copy()
            else:
                df = None

            if df is not None and not df.empty and 'DATETIME' in df.columns:
                if not pd.api.types.is_datetime64_any_dtype(df['DATETIME']):
                    df['DATETIME'] = pd.to_datetime(df['DATETIME'], errors='coerce')
                
                df_cuat = df[df['DATETIME'].dt.year == self.current_anio].copy()
                if not df_cuat.empty and ('SEXO' not in df_cuat.columns or 'TIPO U' not in df_cuat.columns) and 'ITEMNAME' in df_cuat.columns:
                    try:
                        from ADA_Nova import analizar_itemname
                        df_cuat = analizar_itemname(df_cuat)
                    except Exception:
                        pass
                return df_cuat
        except Exception as e:
            print(f"[DATA_LOAD_WARN] Error obteniendo data de visitas: {e}")
        return None

    def actualizar_cuadro_visitas(self):
        """Calcula y muestra la tabla de visitas por mes y los KPIs superiores para el cuatrimestre actual."""
        if not hasattr(self, 'table_visitas_mes'):
            return

        meses = MESES_CUATRIMESTRE.get(self.current_cuatrimestre, [])
        cols = ["MES", "Masculino", "Femenino", "Primaria", "Secundaria", "Universitarios", "Docentes", "Tercera Edad", "Público General", "TOTAL USUARIOS"]
        self.table_visitas_mes.setRowCount(0)

        df_cuat = self._obtener_dataframe_visitas()

        mes_map_es = {
            "January": "Enero", "February": "Febrero", "March": "Marzo", "April": "Abril",
            "May": "Mayo", "June": "Junio", "July": "Julio", "August": "Agosto",
            "September": "Septiembre", "October": "Octubre", "November": "Noviembre", "December": "Diciembre"
        }

        categorias = {'P': 'Primaria', 'S': 'Secundaria', 'U': 'Universitarios', 'D': 'Docentes', 'TE': 'Tercera Edad', 'PG': 'Público General'}
        totales_cols = {col: 0 for col in cols if col != "MES"}

        for m in meses:
            row_vals = {col: 0 for col in cols if col != "MES"}
            row_vals["MES"] = m

            if df_cuat is not None and not df_cuat.empty:
                df_m = df_cuat[df_cuat['DATETIME'].dt.strftime('%B').map(mes_map_es) == m]
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

            for c in row_vals:
                if c != "MES":
                    totales_cols[c] += row_vals[c]

            r_idx = self.table_visitas_mes.rowCount()
            self.table_visitas_mes.insertRow(r_idx)
            for c_idx, col_name in enumerate(cols):
                val = row_vals[col_name]
                disp = str(val) if col_name == "MES" else f"{val:,}"
                item = QTableWidgetItem(disp)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col_name != "MES":
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if self.is_dark_mode:
                    item.setForeground(QColor("#f8fafc" if col_name == "MES" else "#cbd5e1"))
                else:
                    item.setForeground(QColor("#0f172a" if col_name == "MES" else "#334155"))
                self.table_visitas_mes.setItem(r_idx, c_idx, item)

        # Fila TOTAL
        r_tot = self.table_visitas_mes.rowCount()
        self.table_visitas_mes.insertRow(r_tot)
        totales_cols["MES"] = "TOTAL"

        for c_idx, col_name in enumerate(cols):
            val = totales_cols[col_name]
            disp = str(val) if col_name == "MES" else f"{val:,}"
            item = QTableWidgetItem(disp)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            if col_name != "MES":
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            bg_total = QColor("#1e293b") if self.is_dark_mode else QColor("#1e293b")
            fg_total = QColor("#ffffff")

            item.setBackground(bg_total)
            item.setForeground(fg_total)

            self.table_visitas_mes.setItem(r_tot, c_idx, item)

        # Actualizar Tarjetas KPI Superiores
        tot_masc = totales_cols["Masculino"]
        tot_fem = totales_cols["Femenino"]
        tot_visitas_gen = totales_cols["TOTAL USUARIOS"]

        if hasattr(self, 'kpi_hombres') and self.kpi_hombres:
            self.kpi_hombres.lbl_val.setText(f"{tot_masc:,}")
        if hasattr(self, 'kpi_mujeres') and self.kpi_mujeres:
            self.kpi_mujeres.lbl_val.setText(f"{tot_fem:,}")
        if hasattr(self, 'kpi_total_visitas') and self.kpi_total_visitas:
            self.kpi_total_visitas.lbl_val.setText(f"{tot_visitas_gen:,}")

    # --- RENDIMIENTO Y CUMPLIMIENTO ---

    def actualizar_tarjeta_rendimiento(self):
        """Calcula el rendimiento mensual según las computadoras y visitas del cuatrimestre usando la fórmula nativa del Dashboard."""
        pcs = self.spin_pcs.value()
        meta_mensual = pcs * 48

        if hasattr(self, 'lbl_rendimiento_subtitulo'):
            bg_badge = "#0369a1" if self.is_dark_mode else "#0284c7"
            self.lbl_rendimiento_subtitulo.setText(
                f"Rendimiento Mensual vs Meta, según "
                f"<span style='background-color: {bg_badge}; color: #ffffff; padding: 3px 9px; border-radius: 6px; font-weight: bold;'>💻 {pcs} computadoras</span> "
                f"para usuarios en la Infoplaza:"
            )

        meses = MESES_CUATRIMESTRE.get(self.current_cuatrimestre, [])
        self.table_rendimiento.setRowCount(0)

        df_cuat = self._obtener_dataframe_visitas()
        mes_map_es = {
            "January": "Enero", "February": "Febrero", "March": "Marzo", "April": "Abril",
            "May": "Mayo", "June": "Junio", "July": "Julio", "August": "Agosto",
            "September": "Septiembre", "October": "Octubre", "November": "Noviembre", "December": "Diciembre"
        }

        tot_visitas = 0
        tot_meta = 0

        for m in meses:
            row = self.table_rendimiento.rowCount()
            self.table_rendimiento.insertRow(row)

            visitas = 0
            if df_cuat is not None and not df_cuat.empty:
                df_m = df_cuat[df_cuat['DATETIME'].dt.strftime('%B').map(mes_map_es) == m]
                visitas = len(df_m)

            tot_visitas += visitas
            tot_meta += meta_mensual

            # Regla de negocio nativa del Dashboard: Porcentaje = (Visitas * 30) / Meta
            pct = (visitas * 30.0) / meta_mensual if meta_mensual > 0 else 0.0

            if pct >= 30:
                obs_text = "✅ Cumple"
                col_code = "#10b981" if self.is_dark_mode else "#27ae60"
            elif pct >= 20:
                obs_text = "⚠️ Parcial"
                col_code = "#f59e0b" if self.is_dark_mode else "#f39c12"
            else:
                obs_text = "❌ No cumple"
                col_code = "#ef4444" if self.is_dark_mode else "#c0392b"

            item_m = QTableWidgetItem(m)
            item_vis = QTableWidgetItem(f"{visitas:,}")
            item_meta = QTableWidgetItem(f"{meta_mensual:,}")
            item_pct = QTableWidgetItem(f"{pct:.2f}%")
            item_est = QTableWidgetItem(obs_text)

            item_m.setTextAlignment(Qt.AlignCenter)
            item_vis.setTextAlignment(Qt.AlignCenter)
            item_meta.setTextAlignment(Qt.AlignCenter)
            item_pct.setTextAlignment(Qt.AlignCenter)
            item_est.setTextAlignment(Qt.AlignCenter)

            for it in (item_m, item_vis, item_meta, item_pct, item_est):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            if self.is_dark_mode:
                item_m.setForeground(QColor("#f8fafc"))
                item_vis.setForeground(QColor("#cbd5e1"))
                item_meta.setForeground(QColor("#cbd5e1"))
                item_pct.setForeground(QColor(col_code))
                item_est.setForeground(QColor(col_code))
            else:
                item_m.setForeground(QColor("#0f172a"))
                item_vis.setForeground(QColor("#334155"))
                item_meta.setForeground(QColor("#334155"))
                item_pct.setForeground(QColor(col_code))
                item_est.setForeground(QColor(col_code))

            self.table_rendimiento.setItem(row, 0, item_m)
            self.table_rendimiento.setItem(row, 1, item_vis)
            self.table_rendimiento.setItem(row, 2, item_meta)
            self.table_rendimiento.setItem(row, 3, item_pct)
            self.table_rendimiento.setItem(row, 4, item_est)

        # Fila Final: TOTAL CUATRIMESTRE
        tot_row = self.table_rendimiento.rowCount()
        self.table_rendimiento.insertRow(tot_row)

        tot_pct = (tot_visitas / tot_meta) * 30.0 if tot_meta > 0 else 0.0

        if tot_pct >= 30:
            tot_obs_text = "✅ CUMPLE"
            tot_col_code = "#10b981" if self.is_dark_mode else "#27ae60"
        elif tot_pct >= 20:
            tot_obs_text = "⚠️ PARCIAL"
            tot_col_code = "#f59e0b" if self.is_dark_mode else "#f39c12"
        else:
            tot_obs_text = "❌ NO CUMPLE"
            tot_col_code = "#ef4444" if self.is_dark_mode else "#c0392b"

        item_tot_m = QTableWidgetItem("TOTAL CUATRIMESTRE")
        item_tot_vis = QTableWidgetItem(f"{tot_visitas:,}")
        item_tot_meta = QTableWidgetItem(f"{tot_meta:,}")
        item_tot_pct = QTableWidgetItem(f"{tot_pct:.2f}%")
        item_tot_est = QTableWidgetItem(tot_obs_text)

        font_bold = QFont()
        font_bold.setBold(True)

        for it in (item_tot_m, item_tot_vis, item_tot_meta, item_tot_pct, item_tot_est):
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setFont(font_bold)
            it.setTextAlignment(Qt.AlignCenter)

        bg_total = QColor("#1e293b") if self.is_dark_mode else QColor("#e2e8f0")
        fg_total = QColor("#38bdf8") if self.is_dark_mode else QColor("#0f172a")

        for it in (item_tot_m, item_tot_vis, item_tot_meta):
            it.setBackground(bg_total)
            it.setForeground(fg_total)

        item_tot_pct.setBackground(bg_total)
        item_tot_pct.setForeground(QColor(tot_col_code))

        item_tot_est.setBackground(bg_total)
        item_tot_est.setForeground(QColor(tot_col_code))

        self.table_rendimiento.setItem(tot_row, 0, item_tot_m)
        self.table_rendimiento.setItem(tot_row, 1, item_tot_vis)
        self.table_rendimiento.setItem(tot_row, 2, item_tot_meta)
        self.table_rendimiento.setItem(tot_row, 3, item_tot_pct)
        self.table_rendimiento.setItem(tot_row, 4, item_tot_est)

        # Actualizar Tarjeta KPI de Cumplimiento (30%) y PCs
        if hasattr(self, 'kpi_cumplimiento') and self.kpi_cumplimiento:
            self.kpi_cumplimiento.lbl_val.setText(f"{tot_pct:.2f}%")
            self.kpi_cumplimiento.lbl_sub.setText(f"💻 {pcs} PCs (Meta 30%: {tot_meta:,})")
            self.kpi_cumplimiento.lbl_val.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {tot_col_code};")

    # =========================================================================
    # ACCIONES: GUARDAR, SINCRONIZAR, RESTAURAR Y EMITIR PDF
    # =========================================================================

    def _recopilar_payload_completo(self) -> tuple:
        header_data = {
            "cant_computadoras": self.spin_pcs.value(),
            "asociado_nombre": format_title_case(self.txt_asociado_nombre.text()),
            "asociado_cedula": self.txt_asociado_cedula.text().strip().upper(),
            "dinamizador_nombre": format_title_case(self.txt_dinamizador_nombre.text()),
            "dinamizador_cedula": self.txt_dinamizador_cedula.text().strip().upper(),
            "observaciones_generales": format_title_case(self.txt_obs_generales.toPlainText())
        }
        caps = self.obtener_capacitaciones_de_tabla()
        srvs = self.obtener_servicios_de_tabla()
        acts = self.obtener_actividades_de_tabla()

        return header_data, caps, srvs, acts

    def auto_sync_guardar_local_y_cloud(self, silent: bool = True):
        """Guarda instantáneamente en SQLite local (0ms UI lag) y envía a Supabase en hilo secundario."""
        if not self.infoplaza_id:
            return

        if getattr(self, '_is_pulling_from_cloud', False):
            return

        hdr, caps, srvs, acts = self._recopilar_payload_completo()

        # 1. Guardar localmente en SQLite al instante (~1ms)
        try:
            db.save_informe_cuatrimestral_local(
                infoplaza_id=self.infoplaza_id,
                anio=self.current_anio,
                cuatrimestre=self.current_cuatrimestre,
                header_data=hdr,
                capacitaciones=caps,
                servicios=srvs,
                otras_actividades=acts
            )
        except Exception as e:
            print(f"[LOCAL_SAVE_WARN] Error guardando local: {e}")

        # 2. Programar la sincronización cloud en segundo plano
        self._pending_sync_payload = (hdr, caps, srvs, acts)
        self.debounce_sync_timer.stop()
        self.debounce_sync_timer.setInterval(200 if silent else 0)
        self.debounce_sync_timer.start()

    def _ejecutar_sincronizacion_background(self):
        """Ejecuta la sincronización HTTP a Supabase en un QThread dedicado sin bloquear la interfaz."""
        if not hasattr(self, '_pending_sync_payload') or not self._pending_sync_payload:
            return

        hdr, caps, srvs, acts = self._pending_sync_payload

        # Reutilizar o lanzar hilo secundario sin congelar UI
        if hasattr(self, 'sync_thread') and self.sync_thread and self.sync_thread.isRunning():
            self.sync_thread.wait(100)

        self.sync_thread = InformeCuatrimestralSyncThread(
            infoplaza_id=self.infoplaza_id,
            anio=self.current_anio,
            cuatrimestre=self.current_cuatrimestre,
            header_data=hdr,
            caps=caps,
            srvs=srvs,
            acts=acts,
            parent=self
        )
        self.sync_thread.start()

    def actualizar_informacion_firmas(self):
        """Acción del botón 'Actualizar Información' en la Pestaña 5."""
        if not self.infoplaza_id:
            QMessageBox.warning(self, "Atención", "No se ha detectado el número de Infoplaza.")
            return

        self.auto_sync_guardar_local_y_cloud(silent=False)
        QMessageBox.information(
            self,
            "Información Actualizada",
            "✅ La información de la Infoplaza, firmantes y observaciones se ha guardado localmente y sincronizado con Supabase."
        )

    def emitir_pdf(self):
        """Construye y emite el informe cuatrimestral en formato PDF."""
        # 1. Validación previa obligatoria: Confirmar cantidad de PCs (fundamental para el 30%)
        pcs_actuales = self.spin_pcs.value() if hasattr(self, 'spin_pcs') else 6
        dlg = ConfirmarPcsDialog(
            pcs_actuales=pcs_actuales,
            parent=self,
            is_dark_mode=getattr(self, 'is_dark_mode', False)
        )
        if dlg.exec_() != QDialog.Accepted:
            return  # Cancelado por el usuario

        # Actualizar PCs en la UI si el usuario ajustó la cantidad en el modal
        nuevas_pcs = dlg.obtener_pcs()
        if hasattr(self, 'spin_pcs') and nuevas_pcs != self.spin_pcs.value():
            self.spin_pcs.setValue(nuevas_pcs)
            self.actualizar_tarjeta_rendimiento()

        # Asegurar guardado automático previo
        self.auto_sync_guardar_local_y_cloud(silent=True)

        hdr, caps, srvs, acts = self._recopilar_payload_completo()

        # Recopilar KPIs de la UI
        kpis_cuatrimestre = {
            "masculino": self.kpi_hombres.lbl_val.text() if hasattr(self, 'kpi_hombres') and self.kpi_hombres else "0",
            "femenino": self.kpi_mujeres.lbl_val.text() if hasattr(self, 'kpi_mujeres') and self.kpi_mujeres else "0",
            "total_visitas": self.kpi_total_visitas.lbl_val.text() if hasattr(self, 'kpi_total_visitas') and self.kpi_total_visitas else "0",
            "cumplimiento_pct": self.kpi_cumplimiento.lbl_val.text() if hasattr(self, 'kpi_cumplimiento') and self.kpi_cumplimiento else "0.00%",
            "cumplimiento_sub": self.kpi_cumplimiento.lbl_sub.text() if hasattr(self, 'kpi_cumplimiento') and self.kpi_cumplimiento else ""
        }

        # Recopilar tabla de visitas por mes
        cols_visitas = ["mes", "masculino", "femenino", "primaria", "secundaria", "universitarios", "docentes", "tercera_edad", "publico_general", "total_usuarios"]
        visitas_mes = []
        if hasattr(self, 'table_visitas_mes'):
            for r in range(self.table_visitas_mes.rowCount()):
                row_dict = {}
                for c_idx, col_key in enumerate(cols_visitas):
                    item = self.table_visitas_mes.item(r, c_idx)
                    row_dict[col_key] = item.text() if item else ("0" if col_key != "mes" else "")
                visitas_mes.append(row_dict)

        # Recopilar estadísticas de rendimiento de la tabla (5 columnas)
        rendimiento = []
        for r in range(self.table_rendimiento.rowCount()):
            mes = self.table_rendimiento.item(r, 0).text() if self.table_rendimiento.item(r, 0) else ""
            visitas = self.table_rendimiento.item(r, 1).text() if self.table_rendimiento.item(r, 1) else "0"
            meta = self.table_rendimiento.item(r, 2).text() if self.table_rendimiento.item(r, 2) else "0"
            pct = self.table_rendimiento.item(r, 3).text() if self.table_rendimiento.item(r, 3) else "0%"
            estado = self.table_rendimiento.item(r, 4).text() if self.table_rendimiento.item(r, 4) else ""
            rendimiento.append({
                "mes": mes,
                "visitas": visitas,
                "meta": meta,
                "porcentaje": pct,
                "estado": estado
            })

        # Recopilar totales de capacitaciones
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

        payload_pdf = {
            "infoplaza_id": self.infoplaza_id,
            "infoplaza_info": self.infoplaza_info,
            "anio": self.current_anio,
            "cuatrimestre": self.current_cuatrimestre,
            "header": hdr,
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

        # Invocar la generación de PDF de forma redundante (vía main_app o vía señal Qt)
        if hasattr(self.main_app, 'generar_pdf_cuatrimestral') and callable(getattr(self.main_app, 'generar_pdf_cuatrimestral')):
            self.main_app.generar_pdf_cuatrimestral(payload_pdf)
        else:
            self.pdf_requested.emit(payload_pdf)
