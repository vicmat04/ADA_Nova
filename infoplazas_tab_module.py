import os
import urllib.parse
from typing import Tuple, List, Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QDialog, QComboBox, QFormLayout, QMessageBox, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QCursor

from cuatrimestral_supabase_manager import supabase_manager, format_title_case

PROVINCIAS_PANAMA = [
    "Bocas del Toro", "Coclé", "Colón", "Chiriquí", "Darién", 
    "Herrera", "Los Santos", "Panamá", "Veraguas", 
    "Panamá Oeste", "Guna Yala", "Emberá-Wounaan", "Ngäbe-Buglé"
]

def es_infoplaza_cerrada(info: dict) -> bool:
    """Detecta si una Infoplaza está cerrada definitivamente por estatus, estado, condición o nombre."""
    # 1. Flags booleanos o enteros de actividad
    for key in ['activo', 'activa', 'is_active', 'enabled']:
        val = info.get(key)
        if val is False or val == 0 or str(val).lower() == 'false':
            return True

    # 2. Textos de estado / estatus / condicion / observaciones / nombre
    for key in ['estatus', 'estado', 'status', 'condicion', 'observaciones', 'observacion', 'nombre']:
        val = str(info.get(key, '') or '').lower()
        if 'cerrad' in val or 'inactiv' in val or 'baja' in val or 'definitiv' in val:
            return True

    return False


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


class InfoplazasTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.regional = ""
        self.all_infoplazas = []
        self.current_displayed_list = []
        self.cerradas_count = 0
        self.showing_only_incomplete = False
        self.is_dark_mode = False
        
        self.setup_ui()
        
    def showEvent(self, event):
        super().showEvent(event)
        if not self.all_infoplazas:
            self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        
        # Header layout
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel("<h2>Catálogo Maestro de Infoplazas</h2>")
        
        # Badge de conteo de Infoplazas
        self.lbl_count = QLabel("📋 Cargando...")
        self.lbl_count.setAlignment(Qt.AlignCenter)
        self.lbl_count.setStyleSheet("font-size: 13px; font-weight: bold; color: #0284c7; background-color: #e0f2fe; padding: 5px 12px; border-radius: 6px; border: 1px solid #7dd3fc;")
        
        self.lbl_warning = ClickableLabel("")
        self.lbl_warning.setStyleSheet("color: #ef4444; font-weight: bold; background-color: #fee2e2; padding: 5px; border-radius: 4px;")
        self.lbl_warning.setVisible(False)
        self.lbl_warning.clicked.connect(self.toggle_incomplete_filter)
        
        btn_refresh = QPushButton("🔄 Actualizar")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet("font-weight: bold; padding: 6px 14px; border-radius: 6px;")
        btn_refresh.clicked.connect(self.load_data)
        
        header_layout.addWidget(self.lbl_title)
        header_layout.addWidget(self.lbl_count)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_warning)
        header_layout.addWidget(btn_refresh)
        
        layout.addLayout(header_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Número", "Nombre", "Regional", "Provincia", "Distrito", "Corregimiento"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.on_row_double_clicked)
        
        layout.addWidget(self.table)
        self.update_theme(getattr(self, 'is_dark_mode', False))

    def update_theme(self, is_dark: bool = False):
        """Aplica la hoja de estilo según Modo Claro/Oscuro a la tabla y componentes."""
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
        """)

        if hasattr(self, 'lbl_title'):
            self.lbl_title.setStyleSheet(f"color: {text_main}; font-size: 16px; font-weight: bold;")
        if hasattr(self, 'lbl_count'):
            count_bg = "rgba(2, 132, 199, 0.15)" if is_dark else "#e0f2fe"
            count_fg = "#38bdf8" if is_dark else "#0284c7"
            count_border = "#38bdf8" if is_dark else "#7dd3fc"
            self.lbl_count.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {count_fg}; background-color: {count_bg}; padding: 5px 12px; border-radius: 6px; border: 1px solid {count_border}; min-height: 26px;")

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
            
        if self.isVisible():
            self.load_data()
        else:
            self.all_infoplazas = []
        
    def load_data(self):
        self.table.setRowCount(0)
        self.showing_only_incomplete = False
        
        data, err = supabase_manager.get_infoplazas_by_regional(self.regional)
        if err:
            QMessageBox.warning(self, "Error", f"No se pudo cargar el catálogo:\n{err}")
            return
            
        if self.regional == "Los Santos":
            data_herrera, _ = supabase_manager.get_infoplazas_by_regional("Herrera")
            if data_herrera:
                data.extend(data_herrera)
                
        # Filtrar Infoplazas cerradas definitivamente
        activas = [info for info in data if not es_infoplaza_cerrada(info)]
        self.cerradas_count = len(data) - len(activas)
        self.all_infoplazas = sorted(activas, key=lambda x: x.get('numero', 0))
        self.populate_table(self.all_infoplazas)
        
    def populate_table(self, data_list):
        self.current_displayed_list = data_list
        self.table.setRowCount(0)
        incomplete_count = 0
        is_dark = getattr(self, 'is_dark_mode', False)
        
        for row_idx, info in enumerate(data_list):
            self.table.insertRow(row_idx)
            
            num = str(info.get('numero', ''))
            nombre = info.get('nombre', '') or ''
            reg = info.get('regional', '') or ''
            prov = info.get('provincia', '') or ''
            dist = info.get('distrito', '') or ''
            corr = info.get('corregimiento', '') or ''
            
            # Check incomplete
            is_incomplete = not prov or not dist or not corr
            if is_incomplete:
                incomplete_count += 1
                
            items = [
                QTableWidgetItem(num),
                QTableWidgetItem(nombre),
                QTableWidgetItem(reg),
                QTableWidgetItem(prov),
                QTableWidgetItem(dist),
                QTableWidgetItem(corr)
            ]
            
            for col_idx, item in enumerate(items):
                if col_idx == 0:
                    item.setData(Qt.UserRole, info)
                
                # Resaltar filas incompletas o normales con estilo acorde al tema
                if is_incomplete:
                    if is_dark:
                        item.setBackground(QColor("#451a03")) # Ámbar oscuro
                        item.setForeground(QColor("#fef3c7"))
                    else:
                        item.setBackground(QColor("#fffbeb")) # Amarillo muy claro
                        item.setForeground(QColor("#b45309"))
                else:
                    if is_dark:
                        item.setForeground(QColor("#f8fafc"))
                    else:
                        item.setForeground(QColor("#0f172a"))
                    
                self.table.setItem(row_idx, col_idx, item)
                
        # Actualizar indicador de conteo
        total_mostradas = len(data_list)
        total_activas = len(self.all_infoplazas)
        cerradas_filtradas = getattr(self, 'cerradas_count', 0)

        if getattr(self, 'showing_only_incomplete', False):
            self.lbl_count.setText(f"📋 Mostrando {total_mostradas} incompletas (de {total_activas} activas)")
        else:
            self.lbl_count.setText(f"📋 Mostrando {total_mostradas} Infoplazas Activas")

        # Actualizar warning
        if incomplete_count > 0:
            self.lbl_warning.setText(f"⚠️ Hay {incomplete_count} Infoplaza(s) con datos incompletos. Clic para filtrar.")
            self.lbl_warning.setVisible(True)
        else:
            self.lbl_warning.setVisible(False)
            
        if self.parent_app and hasattr(self.parent_app, '_reaplicar_estilos_totales') and hasattr(self.parent_app, 'tab_resumen'):
            self.parent_app._reaplicar_estilos_totales()
            
    def toggle_incomplete_filter(self):
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
        row = index.row()
        item = self.table.item(row, 0)
        if not item:
            return
            
        info = item.data(Qt.UserRole)
        numero = info.get('numero')
        if not numero:
            return
            
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
