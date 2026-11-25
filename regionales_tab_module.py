# -*- coding: utf-8 -*-
"""
Módulo de Consolidado y Comparativa Inter-Regional para Informe Cuatrimestral.
Permite visualizar el avance nacional de entregas, comparar el cumplimiento
entre regionales y auditar infoplazas pendientes con herramientas de exportación y copiado.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional

import pandas as pd
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QLineEdit, QProgressBar, QApplication, QMessageBox,
    QFileDialog, QSplitter, QCheckBox, QAbstractItemView,
    QSizePolicy, QButtonGroup
)

from database_manager import db
from cuatrimestral_supabase_manager import supabase_manager

MESES_CUATRIMESTRE_NOMBRES = {
    1: "Enero a abril",
    2: "Mayo a agosto",
    3: "Septiembre a diciembre"
}


def auto_determinar_cuatrimestre():
    now = datetime.now()
    month = now.month
    year = now.year
    if 1 <= month <= 4:
        return year, 1
    elif 5 <= month <= 8:
        return year, 2
    else:
        return year, 3


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


class FlashToast(QFrame):
    """Notificación flotante no bloqueante ampliada y centrada en pantalla que se desvanece automáticamente."""
    def __init__(self, parent=None, text=""):
        target_parent = parent.window() if (parent and hasattr(parent, 'window') and parent.window()) else parent
        super().__init__(target_parent)
        self.setObjectName("FlashToast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 40, 50, 40)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-size: 45px; font-weight: bold; color: #ffffff; line-height: 1.5;")
        layout.addWidget(lbl)

        is_dark = getattr(parent, 'is_dark_mode', False) if parent else False
        bg_toast = "rgba(6, 78, 59, 0.95)" if is_dark else "rgba(5, 150, 105, 0.95)"
        border_toast = "#34d399" if is_dark else "#10b981"
        self.setStyleSheet(f"""
            QFrame#FlashToast {{
                background-color: {bg_toast};
                border: 4px solid {border_toast};
                border-radius: 20px;
                min-width: 800px;
                min-height: 300px;
            }}
        """)
        self.adjustSize()

        if target_parent:
            x = (target_parent.width() - self.width()) // 2
            y = (target_parent.height() - self.height()) // 2
            self.move(x, y)

        self.show()
        self.raise_()

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)
        self.timer.start(3000)


class RegionalesTabWidget(QWidget):
    """Pestaña de Consolidado y Comparativa Inter-Regional de Entregas."""

    def _mostrar_flash_mensaje(self, texto: str):
        """Muestra un mensaje flash (toast) flotante que se desvanece solo."""
        if hasattr(self, '_active_toast') and self._active_toast:
            try:
                self._active_toast.close()
            except Exception:
                pass
        self._active_toast = FlashToast(self, texto)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.all_infoplazas = []
        self.control_data = {}  # {numero: {'estado': str, 'motivo': str}}
        self.regionals_data = {} # {regional_name: {'total': int, 'entregan': int, ...}}
        self.selected_regional = ""
        self.filtro_estado = "PENDIENTE" # 'TODOS', 'PENDIENTE', 'ENTREGADO'
        self.solo_pendientes = True
        self.is_dark_mode = False

        sug_anio, sug_cuat = auto_determinar_cuatrimestre()
        self.selected_anio = sug_anio
        self.selected_cuat = sug_cuat

        self.setup_ui()

        # Temporizador para sincronización periódica (cada 15s)
        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(15000)
        self.sync_timer.timeout.connect(self._sync_silencioso)
        self.sync_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        old_anio = getattr(self, 'selected_anio', 0)
        old_cuat = getattr(self, 'selected_cuat', 0)
        
        self.selected_anio = self.get_selected_anio()
        self.selected_cuat = self.get_selected_cuat()
        
        period_changed = (old_anio != self.selected_anio or old_cuat != self.selected_cuat)

        if not self.all_infoplazas or self.table_regionales.rowCount() == 0 or period_changed:
            self.load_data()
            QTimer.singleShot(150, self._sync_silencioso)
        else:
            self._cargar_control_entrega_local()
            # Fast refresh of existing tables without rebuilding everything
            self._procesar_y_renderizar()
            QTimer.singleShot(150, self._sync_silencioso)

    def get_selected_anio(self) -> int:
        if self.parent_app and hasattr(self.parent_app, 'current_anio'):
            return self.parent_app.current_anio
        return getattr(self, 'selected_anio', datetime.now().year)

    def get_selected_cuat(self) -> int:
        if self.parent_app and hasattr(self.parent_app, 'current_cuatrimestre'):
            return self.parent_app.current_cuatrimestre
        return getattr(self, 'selected_cuat', 1)

    def _on_periodo_changed(self):
        """Maneja el cambio de período disparado desde el Header Principal."""
        self.selected_anio = self.get_selected_anio()
        self.selected_cuat = self.get_selected_cuat()
        self._cargar_control_entrega_local()
        self._procesar_y_renderizar()

    def _crear_kpi_card(self, titulo: str, valor: str, kpi_type: str = "total") -> QFrame:
        """Crea una tarjeta KPI calibrada para el consolidado nacional."""
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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # =====================================================================
        # 1. HEADER: TÍTULO, KPIS NACIONALES Y BOTONES DE ACCIÓN
        # =====================================================================
        self.header_card = QFrame()
        self.header_card.setObjectName("RegionalesHeaderCard")
        header_layout = QHBoxLayout(self.header_card)
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(10)
        header_layout.setAlignment(Qt.AlignVCenter)

        self.lbl_title = QLabel("📊 Consolidado y Comparativa Inter-Regional")
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(self.lbl_title)

        header_layout.addSpacing(6)

        # KPIs Consolidados Nacionales
        self.card_total = self._crear_kpi_card("Total País", "0", "total")
        self.card_entregan = self._crear_kpi_card("Entregan", "0", "entregan")
        self.card_no_entregan = self._crear_kpi_card("No Entregan", "0", "no_entregan")

        header_layout.addWidget(self.card_total)
        header_layout.addWidget(self.card_entregan)
        header_layout.addWidget(self.card_no_entregan)

        # Separador visual
        self.kpi_separator = QFrame()
        self.kpi_separator.setFrameShape(QFrame.VLine)
        self.kpi_separator.setFrameShadow(QFrame.Plain)
        self.kpi_separator.setFixedWidth(2)
        self.kpi_separator.setStyleSheet("background-color: #cbd5e1; margin: 4px 6px;")
        header_layout.addWidget(self.kpi_separator)

        self.card_entregados = self._crear_kpi_card("Entregadas", "0", "entregados")
        self.card_pendientes = self._crear_kpi_card("Pendientes", "0", "pendientes")
        header_layout.addWidget(self.card_entregados)
        header_layout.addWidget(self.card_pendientes)

        header_layout.addStretch()

        # Botones de Acción
        self.btn_exportar = QPushButton("📥 Exportar Consolidado")
        self.btn_exportar.setCursor(Qt.PointingHandCursor)
        self.btn_exportar.setToolTip("Exportar el consolidado comparativo y detalle nacional a Excel (.xlsx)")
        self.btn_exportar.clicked.connect(self.exportar_excel)
        header_layout.addWidget(self.btn_exportar)

        self.btn_refresh = QPushButton("🔄 Actualizar")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setToolTip("Recargar datos y sincronizar con la nube")
        self.btn_refresh.clicked.connect(self.load_data)
        header_layout.addWidget(self.btn_refresh)

        main_layout.addWidget(self.header_card, 0)

        # =====================================================================
        # 2. PANEL MASTER-DETAIL (SPLITTER 45/55)
        # =====================================================================
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ---------------------------------------------------------------------
        # PANEL IZQUIERDO: MATRIZ COMPARATIVA DE REGIONALES
        # ---------------------------------------------------------------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(6)

        left_header = QHBoxLayout()
        self.lbl_table_reg_title = QLabel("🏆 Ranking y Avance por Regional")
        self.lbl_table_reg_title.setStyleSheet("font-size: 13px; font-weight: bold;")
        left_header.addWidget(self.lbl_table_reg_title)
        left_header.addStretch()
        left_layout.addLayout(left_header)

        self.table_regionales = QTableWidget()
        self.table_regionales.setColumnCount(7)
        self.table_regionales.setHorizontalHeaderLabels([
            "Regional", "Total", "Entregan", "No Entr.", "Entregadas", "Pendientes", "% Avance"
        ])
        
        h_reg = self.table_regionales.horizontalHeader()
        h_reg.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Regional completa sin puntos suspensivos
        h_reg.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Total
        h_reg.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Entregan
        h_reg.setSectionResizeMode(3, QHeaderView.ResizeToContents) # No Entr.
        h_reg.setSectionResizeMode(4, QHeaderView.ResizeToContents) # Entregadas
        h_reg.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Pendientes
        h_reg.setSectionResizeMode(6, QHeaderView.Stretch)          # % Avance con barra amplia
        h_reg.setMinimumSectionSize(45)

        self.table_regionales.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_regionales.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_regionales.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_regionales.verticalHeader().setVisible(False)
        self.table_regionales.verticalHeader().setDefaultSectionSize(40)
        self.table_regionales.verticalHeader().setMinimumSectionSize(38)
        self.table_regionales.itemSelectionChanged.connect(self._on_regional_selected)
        left_layout.addWidget(self.table_regionales, 1)

        # ---------------------------------------------------------------------
        # PANEL DERECHO: AUDITORÍA Y DETALLE DE PENDIENTES
        # ---------------------------------------------------------------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(6)

        right_header = QHBoxLayout()
        self.lbl_detail_title = QLabel("🔍 Infoplazas — Selecciona una Regional")
        self.lbl_detail_title.setStyleSheet("font-size: 13px; font-weight: bold;")
        right_header.addWidget(self.lbl_detail_title)
        right_header.addStretch()

        # Botones segmentados de filtro: Todos / Pendientes / Entregadas
        self.btn_group_filtro = QButtonGroup(self)
        self.btn_group_filtro.setExclusive(True)

        self.btn_filtro_todos = QPushButton("Todos")
        self.btn_filtro_todos.setCheckable(True)
        self.btn_filtro_todos.setCursor(Qt.PointingHandCursor)
        self.btn_group_filtro.addButton(self.btn_filtro_todos)

        self.btn_filtro_pendientes = QPushButton("Pendientes")
        self.btn_filtro_pendientes.setCheckable(True)
        self.btn_filtro_pendientes.setChecked(True)
        self.btn_filtro_pendientes.setCursor(Qt.PointingHandCursor)
        self.btn_group_filtro.addButton(self.btn_filtro_pendientes)

        self.btn_filtro_entregadas = QPushButton("Entregadas")
        self.btn_filtro_entregadas.setCheckable(True)
        self.btn_filtro_entregadas.setCursor(Qt.PointingHandCursor)
        self.btn_group_filtro.addButton(self.btn_filtro_entregadas)

        self.btn_filtro_todos.clicked.connect(lambda: self._set_filtro_estado("TODOS"))
        self.btn_filtro_pendientes.clicked.connect(lambda: self._set_filtro_estado("PENDIENTE"))
        self.btn_filtro_entregadas.clicked.connect(lambda: self._set_filtro_estado("ENTREGADO"))

        filtro_layout = QHBoxLayout()
        filtro_layout.setSpacing(2)
        filtro_layout.addWidget(self.btn_filtro_todos)
        filtro_layout.addWidget(self.btn_filtro_pendientes)
        filtro_layout.addWidget(self.btn_filtro_entregadas)
        right_header.addLayout(filtro_layout)

        self.btn_copiar = QPushButton("📋 Copiar Lista")
        self.btn_copiar.setCursor(Qt.PointingHandCursor)
        self.btn_copiar.setToolTip("Copiar lista formateada al portapapeles (para WhatsApp o Excel)")
        self.btn_copiar.clicked.connect(self.copiar_pendientes_al_portapapeles)
        right_header.addWidget(self.btn_copiar)

        right_layout.addLayout(right_header)

        # Barra de búsqueda rápida
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Buscar por número, nombre, distrito o corregimiento...")
        self.txt_search.textChanged.connect(self._filtrar_tabla_detalle)
        right_layout.addWidget(self.txt_search)

        self.table_detalle = QTableWidget()
        self.table_detalle.setColumnCount(7)
        self.table_detalle.setHorizontalHeaderLabels([
            "#", "Número", "Nombre", "Distrito", "Corregimiento", "Estatus", "Motivo"
        ])
        
        h_det = self.table_detalle.horizontalHeader()
        h_det.setSectionResizeMode(0, QHeaderView.Fixed)            # # (Fila) fijo y suficiente para 3 dígitos
        self.table_detalle.setColumnWidth(0, 68)
        h_det.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Número
        h_det.setSectionResizeMode(2, QHeaderView.Interactive)      # Nombre
        self.table_detalle.setColumnWidth(2, 200)
        h_det.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Distrito
        h_det.setSectionResizeMode(4, QHeaderView.ResizeToContents) # Corregimiento
        h_det.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Estatus
        h_det.setSectionResizeMode(6, QHeaderView.Stretch)          # Motivo

        self.table_detalle.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_detalle.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_detalle.verticalHeader().setVisible(False)
        right_layout.addWidget(self.table_detalle, 1)

        # Ensamblar Splitter
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        self.splitter.setSizes([500, 500])

        main_layout.addWidget(self.splitter, 1)
        self.update_theme(getattr(self, 'is_dark_mode', False))

    # =========================================================================
    # CARGA Y PROCESAMIENTO DE DATOS
    # =========================================================================

    def load_data(self):
        """Descarga el catálogo completo de Infoplazas activas y estados de entrega desde Supabase."""
        self.all_infoplazas = []
        data, err = supabase_manager.get_infoplazas_by_regional("")
        if not err and data:
            # Filtrar Infoplazas cerradas definitivamente (igual que en Catálogo Maestro)
            self.all_infoplazas = [info for info in data if not es_infoplaza_cerrada(info)]
        else:
            self.all_infoplazas = []

        self._cargar_control_entrega_local()
        self._procesar_y_renderizar()

    def _cargar_control_entrega_local(self):
        """Carga inmediata del control de entrega desde SQLite local (Cache-First, 0 ms de lag)."""
        try:
            self.control_data = db.get_control_entrega_local(self.selected_anio, self.selected_cuat)
        except Exception as e:
            print(f"[REGIONALES_TAB_WARN] Error cargando control local: {e}")
            self.control_data = {}

    def _sync_silencioso(self):
        """Sincroniza silenciosamente Supabase en segundo plano cada 15s sin bloquear UI."""
        if not self.isVisible() or not getattr(self, 'all_infoplazas', []):
            return

        from infoplazas_tab_module import SyncControlEntregaThread

        if hasattr(self, '_sync_thread') and self._sync_thread.isRunning():
            return

        self._sync_thread = SyncControlEntregaThread(self.selected_anio, self.selected_cuat, self)
        self._sync_thread.finished_sync.connect(self._on_sync_finished)
        self._sync_thread.start()

    def _on_sync_finished(self, cloud_data, err):
        if not cloud_data or err:
            return
        
        try:
            cambios = False
            for num, item in cloud_data.items():
                n_est = item.get('estado', 'Pendiente')
                n_mot = item.get('motivo', '')
                curr = self.control_data.get(num, {})
                if curr.get('estado') != n_est or curr.get('motivo') != n_mot:
                    cambios = True
                    self.control_data[num] = {'estado': n_est, 'motivo': n_mot}
                    db.save_control_entrega_local(num, self.selected_anio, self.selected_cuat, n_est, n_mot)
            if cambios:
                self._procesar_y_renderizar()
        except Exception as e:
            print(f"[REGIONALES_TAB_WARN] Error procesando sync: {e}")

    def _procesar_y_renderizar(self):
        """Agrupa los datos por regional, calcula KPIs nacionales y renderiza las tablas."""
        self.regionals_data = {}

        tot_nac = 0
        entr_nac = 0
        no_entr_nac = 0
        entregados_nac = 0
        pend_nac = 0

        for info in self.all_infoplazas:
            reg = str(info.get('regional', '')).strip()
            if not reg:
                reg = "Sin Regional"

            if reg not in self.regionals_data:
                self.regionals_data[reg] = {
                    'total': 0,
                    'entregan': 0,
                    'no_entregan': 0,
                    'entregados': 0,
                    'pendientes': 0,
                    'infoplazas': []
                }

            num = int(info.get('numero', 0)) if str(info.get('numero', '')).isdigit() else 0
            ctrl = self.control_data.get(num, {})
            estado = ctrl.get('estado', 'Pendiente')

            self.regionals_data[reg]['total'] += 1
            self.regionals_data[reg]['infoplazas'].append(info)
            tot_nac += 1

            if estado == "Entregado":
                self.regionals_data[reg]['entregados'] += 1
                self.regionals_data[reg]['entregan'] += 1
                entregados_nac += 1
                entr_nac += 1
            elif estado == "No entrega":
                self.regionals_data[reg]['no_entregan'] += 1
                no_entr_nac += 1
            else:  # Pendiente
                self.regionals_data[reg]['pendientes'] += 1
                self.regionals_data[reg]['entregan'] += 1
                pend_nac += 1
                entr_nac += 1

        # 1. Actualizar KPIs Nacionales
        base_calc_nac = entr_nac if entr_nac > 0 else tot_nac
        if base_calc_nac > 0:
            pct_ent_nac = (entregados_nac / base_calc_nac) * 100.0
            pct_pend_nac = (pend_nac / base_calc_nac) * 100.0
            pct_ent_nac_str = f"{pct_ent_nac:.1f}%".replace(".0%", "%")
            pct_pend_nac_str = f"{pct_pend_nac:.1f}%".replace(".0%", "%")
        else:
            pct_ent_nac_str = "0%"
            pct_pend_nac_str = "0%"

        if hasattr(self, 'card_total'):
            self.card_total.lbl_v.setText(str(tot_nac))
        if hasattr(self, 'card_entregan'):
            self.card_entregan.lbl_v.setText(str(entr_nac))
        if hasattr(self, 'card_no_entregan'):
            self.card_no_entregan.lbl_v.setText(str(no_entr_nac))
        if hasattr(self, 'card_entregados'):
            self.card_entregados.lbl_v.setText(f'{entregados_nac}&nbsp;&nbsp;<span style="font-size: 12px; font-weight: 700;">({pct_ent_nac_str})</span>')
        if hasattr(self, 'card_pendientes'):
            self.card_pendientes.lbl_v.setText(f'{pend_nac}&nbsp;&nbsp;<span style="font-size: 12px; font-weight: 700;">({pct_pend_nac_str})</span>')

        # 2. Renderizar Tabla Comparativa de Regionales
        self._render_tabla_regionales()

        # 3. Renderizar Detalle de la Regional Seleccionada
        if not self.selected_regional and self.regionals_data:
            self.selected_regional = sorted(self.regionals_data.keys())[0]

        self._render_tabla_detalle()

    def _render_tabla_regionales(self):
        """Renderiza las filas de la tabla comparativa de regionales."""
        self.table_regionales.setUpdatesEnabled(False)
        try:
            self.table_regionales.setRowCount(0)

            # Ordenar regionales alfabéticamente
            reg_names = sorted(self.regionals_data.keys())
            self.table_regionales.setRowCount(len(reg_names))

            row_to_select = -1

            for row, reg in enumerate(reg_names):
                d = self.regionals_data[reg]
                tot = d['total']
                entr = d['entregan']
                no_entr = d['no_entregan']
                entreg = d['entregados']
                pend = d['pendientes']
                pct = (entreg / entr * 100.0) if entr > 0 else 0.0
                pct_str = f"{pct:.1f}%".replace(".0%", "%")

                # Col 0: Regional
                it_reg = QTableWidgetItem(reg)
                it_reg.setFont(self.table_regionales.font())
                it_reg.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                self.table_regionales.setItem(row, 0, it_reg)

                # Col 1: Total
                it_tot = QTableWidgetItem(str(tot))
                it_tot.setTextAlignment(Qt.AlignCenter)
                self.table_regionales.setItem(row, 1, it_tot)

                # Col 2: Entregan
                it_entr = QTableWidgetItem(str(entr))
                it_entr.setTextAlignment(Qt.AlignCenter)
                self.table_regionales.setItem(row, 2, it_entr)

                # Col 3: No Entr.
                it_no = QTableWidgetItem(str(no_entr))
                it_no.setTextAlignment(Qt.AlignCenter)
                self.table_regionales.setItem(row, 3, it_no)

                # Col 4: Entregadas
                it_ent = QTableWidgetItem(str(entreg))
                it_ent.setTextAlignment(Qt.AlignCenter)
                it_ent.setForeground(Qt.darkGreen if not self.is_dark_mode else Qt.green)
                self.table_regionales.setItem(row, 4, it_ent)

                # Col 5: Pendientes
                it_pen = QTableWidgetItem(str(pend))
                it_pen.setTextAlignment(Qt.AlignCenter)
                if pend > 0:
                    it_pen.setForeground(Qt.darkYellow if not self.is_dark_mode else Qt.yellow)
                self.table_regionales.setItem(row, 5, it_pen)

                # Col 6: % Avance (Widget con Progress Bar y Porcentaje)
                prog_widget = QWidget()
                prog_layout = QHBoxLayout(prog_widget)
                prog_layout.setContentsMargins(6, 0, 8, 0)
                prog_layout.setSpacing(8)
                prog_layout.setAlignment(Qt.AlignVCenter)

                pbar = QProgressBar()
                pbar.setRange(0, 100)
                pbar.setValue(int(pct))
                pbar.setTextVisible(False)
                pbar.setMinimumWidth(80)
                pbar.setFixedHeight(14)

                if pct >= 80:
                    bar_color = "#059669" # Verde
                elif pct >= 50:
                    bar_color = "#d97706" # Ámbar
                else:
                    bar_color = "#dc2626" # Rojo

                bg_pbar = "#334155" if self.is_dark_mode else "#e2e8f0"
                border_pbar = "#475569" if self.is_dark_mode else "#cbd5e1"
                pbar.setStyleSheet(f"""
                    QProgressBar {{
                        background-color: {bg_pbar};
                        border: 1px solid {border_pbar};
                        border-radius: 4px;
                    }}
                    QProgressBar::chunk {{
                        background-color: {bar_color};
                        border-radius: 3px;
                    }}
                """)

                lbl_pct = QLabel(pct_str)
                lbl_pct.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {bar_color}; min-width: 52px;")
                lbl_pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

                prog_layout.addWidget(pbar, 1)
                prog_layout.addWidget(lbl_pct, 0)

                self.table_regionales.setCellWidget(row, 6, prog_widget)

                if reg == self.selected_regional:
                    row_to_select = row

            if row_to_select >= 0:
                self.table_regionales.selectRow(row_to_select)
        finally:
            self.table_regionales.setUpdatesEnabled(True)

    def _on_regional_selected(self):
        """Al seleccionar una fila en la tabla de regionales, actualiza la tabla de detalle."""
        sel = self.table_regionales.selectedItems()
        if sel:
            row = sel[0].row()
            reg_item = self.table_regionales.item(row, 0)
            if reg_item:
                self.selected_regional = reg_item.text()
                self._render_tabla_detalle()

    def _set_filtro_estado(self, nuevo_filtro: str):
        self.filtro_estado = nuevo_filtro
        self.solo_pendientes = (nuevo_filtro == "PENDIENTE")
        self._render_tabla_detalle()

    def _on_toggle_solo_pendientes(self, checked: bool):
        self._set_filtro_estado("PENDIENTE" if checked else "TODOS")

    def _render_tabla_detalle(self):
        """Renderiza la tabla de Infoplazas pendientes/totales de la regional activa."""
        self.table_detalle.setUpdatesEnabled(False)
        try:
            self.table_detalle.clearSpans()
            if not self.selected_regional or self.selected_regional not in self.regionals_data:
                self.table_detalle.setRowCount(0)
                self.lbl_detail_title.setText("🔍 Infoplazas — Ninguna regional seleccionada")
                return

            reg_info = self.regionals_data[self.selected_regional]
            infoplazas = reg_info['infoplazas']
            pend_count = reg_info['pendientes']
            total_count = len(infoplazas)

            accent_color = "#fbbf24" if self.is_dark_mode else "#ea580c"
            badge_bg = "#451a03" if self.is_dark_mode else "#ffedd5"
            self.lbl_detail_title.setText(
                f"🔍 Regional: <b>{self.selected_regional}</b> — <span style='color: {accent_color}; background-color: {badge_bg}; padding: 2px 6px; border-radius: 4px; font-weight: bold;'>{pend_count} pendientes</span> de <b>{total_count}</b> total de infoplazas"
            )

            filtro_texto = self.txt_search.text().strip().lower() if hasattr(self, 'txt_search') else ""

            items_pendientes = []
            items_entregados = []

            for info in infoplazas:
                num = int(info.get('numero', 0)) if str(info.get('numero', '')).isdigit() else 0
                ctrl = self.control_data.get(num, {})
                estado = ctrl.get('estado', 'Pendiente')
                motivo = ctrl.get('motivo', '')
                nom = info.get('nombre', '')
                dist = info.get('distrito', '')
                corr = info.get('corregimiento', '')

                if filtro_texto:
                    search_target = f"{num} {nom} {dist} {corr} {estado} {motivo}".lower()
                    if filtro_texto not in search_target:
                        continue

                item_dict = {
                    'numero': num,
                    'nombre': nom,
                    'distrito': dist,
                    'corregimiento': corr,
                    'estado': estado,
                    'motivo': motivo
                }

                if estado == "Pendiente":
                    items_pendientes.append(item_dict)
                else:
                    items_entregados.append(item_dict)

            # Ordenamiento numérico estricto
            items_pendientes.sort(key=lambda x: x['numero'])
            items_entregados.sort(key=lambda x: x['numero'])

            filtro = getattr(self, 'filtro_estado', 'PENDIENTE')

            if filtro == "PENDIENTE":
                lista_final = [('item', item) for item in items_pendientes]
            elif filtro == "ENTREGADO":
                lista_final = [('item', item) for item in items_entregados]
            else: # TODOS
                lista_final = []
                for it in items_pendientes:
                    lista_final.append(('item', it))
                if items_pendientes and items_entregados:
                    lista_final.append(('separator', len(items_entregados)))
                for it in items_entregados:
                    lista_final.append(('item', it))

            self.table_detalle.setRowCount(len(lista_final))

            row_num_counter = 1
            for row, elem in enumerate(lista_final):
                tipo = elem[0]
                if tipo == 'separator':
                    cnt_entr = elem[1]
                    self.table_detalle.setSpan(row, 0, 1, 7)
                    it_sep = QTableWidgetItem(f"   ─── ✅ ENTREGADAS ({cnt_entr}) ───")
                    it_sep.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    it_sep.setFlags(Qt.NoItemFlags)
                    bg_sep = QColor("#1e293b" if self.is_dark_mode else "#f1f5f9")
                    fg_sep = QColor("#4ade80" if self.is_dark_mode else "#15803d")
                    it_sep.setBackground(bg_sep)
                    it_sep.setForeground(fg_sep)
                    self.table_detalle.setItem(row, 0, it_sep)
                    self.table_detalle.setRowHeight(row, 26)
                    continue

                item = elem[1]
                self.table_detalle.setRowHeight(row, 30)

                # 0. Número de Fila (#)
                it_idx = QTableWidgetItem(str(row_num_counter))
                it_idx.setTextAlignment(Qt.AlignCenter)
                it_idx.setForeground(QColor("#94a3b8" if self.is_dark_mode else "#64748b"))
                self.table_detalle.setItem(row, 0, it_idx)
                row_num_counter += 1

                # 1. Número de Infoplaza
                it_num = QTableWidgetItem(str(item['numero']))
                it_num.setTextAlignment(Qt.AlignCenter)
                self.table_detalle.setItem(row, 1, it_num)

                # 2. Nombre
                it_nom = QTableWidgetItem(item['nombre'])
                self.table_detalle.setItem(row, 2, it_nom)

                # 3. Distrito
                it_dist = QTableWidgetItem(item['distrito'])
                self.table_detalle.setItem(row, 3, it_dist)

                # 4. Corregimiento
                it_corr = QTableWidgetItem(item['corregimiento'])
                self.table_detalle.setItem(row, 4, it_corr)

                # 5. Estatus
                it_est = QTableWidgetItem(item['estado'])
                it_est.setTextAlignment(Qt.AlignCenter)
                if item['estado'] == "Entregado":
                    it_est.setForeground(QColor("#4ade80" if self.is_dark_mode else "#15803d"))
                elif item['estado'] == "Pendiente":
                    it_est.setForeground(QColor("#fbbf24" if self.is_dark_mode else "#d97706"))
                else:
                    it_est.setForeground(QColor("#f87171" if self.is_dark_mode else "#dc2626"))
                self.table_detalle.setItem(row, 5, it_est)

                # 6. Motivo
                it_mot = QTableWidgetItem(item['motivo'])
                self.table_detalle.setItem(row, 6, it_mot)
        finally:
            self.table_detalle.setUpdatesEnabled(True)

    def _filtrar_tabla_detalle(self):
        self._render_tabla_detalle()

    # =========================================================================
    # ACCIONES: COPIAR AL PORTAPAPELES Y EXPORTAR A EXCEL
    # =========================================================================

    def copiar_pendientes_al_portapapeles(self):
        """Copia la lista formateada según el filtro activo al portapapeles."""
        if not self.selected_regional or self.selected_regional not in self.regionals_data:
            QMessageBox.warning(self, "Aviso", "Selecciona una regional para copiar sus infoplazas.")
            return

        reg_info = self.regionals_data[self.selected_regional]
        infoplazas = reg_info['infoplazas']

        items_pendientes = []
        items_entregados = []
        for info in infoplazas:
            num = int(info.get('numero', 0)) if str(info.get('numero', '')).isdigit() else 0
            ctrl = self.control_data.get(num, {})
            estado = ctrl.get('estado', 'Pendiente')
            motivo = ctrl.get('motivo', '')
            nom = info.get('nombre', '').strip()
            dist = info.get('distrito', '').strip()
            corr = info.get('corregimiento', '').strip()

            item_dict = {
                'numero': num,
                'nombre': nom,
                'distrito': dist,
                'corregimiento': corr,
                'estado': estado,
                'motivo': motivo
            }
            if estado == "Pendiente":
                items_pendientes.append(item_dict)
            else:
                items_entregados.append(item_dict)

        items_pendientes.sort(key=lambda x: x['numero'])
        items_entregados.sort(key=lambda x: x['numero'])

        filtro = getattr(self, 'filtro_estado', 'PENDIENTE')
        anio = self.get_selected_anio()
        cuat = self.get_selected_cuat()
        cuat_nombre = MESES_CUATRIMESTRE_NOMBRES.get(cuat, "Mayo a agosto")
        total_count = len(infoplazas)

        if filtro == "PENDIENTE":
            if not items_pendientes:
                self._mostrar_flash_mensaje(f"ℹ️ La regional {self.selected_regional} no tiene pendientes.")
                return

            lineas = [
                f"📋 INFOPLAZAS PENDIENTES DE ENTREGA — REGIONAL {self.selected_regional.upper()}",
                f"Período: {cuat_nombre} {anio}",
                f"Total Pendientes: {len(items_pendientes)} de {total_count} infoplazas",
                "──────────────────────────────────────────",
                "#\tNúmero\tNombre\tDistrito\tCorregimiento\tEstatus\tMotivo"
            ]
            for idx, item in enumerate(items_pendientes, 1):
                lineas.append(f"{idx}\t{item['numero']}\t{item['nombre']}\t{item['distrito']}\t{item['corregimiento']}\t{item['estado']}\t{item['motivo']}")

            toast_msg = f"📋 ¡{len(items_pendientes)} pendientes copiadas al portapapeles!"

        elif filtro == "ENTREGADO":
            if not items_entregados:
                self._mostrar_flash_mensaje(f"ℹ️ La regional {self.selected_regional} no tiene entregadas.")
                return

            lineas = [
                f"📋 INFOPLAZAS ENTREGADAS — REGIONAL {self.selected_regional.upper()}",
                f"Período: {cuat_nombre} {anio}",
                f"Total Entregadas: {len(items_entregados)} de {total_count} infoplazas",
                "──────────────────────────────────────────",
                "#\tNúmero\tNombre\tDistrito\tCorregimiento\tEstatus\tMotivo"
            ]
            for idx, item in enumerate(items_entregados, 1):
                lineas.append(f"{idx}\t{item['numero']}\t{item['nombre']}\t{item['distrito']}\t{item['corregimiento']}\t{item['estado']}\t{item['motivo']}")

            toast_msg = f"📋 ¡{len(items_entregados)} entregadas copiadas al portapapeles!"

        else: # TODOS
            lineas = [
                f"📋 CONTROL DE ENTREGAS — REGIONAL {self.selected_regional.upper()}",
                f"Período: {cuat_nombre} {anio}",
                f"Total: {total_count} infoplazas ({len(items_pendientes)} Pendientes, {len(items_entregados)} Entregadas)",
                "──────────────────────────────────────────"
            ]
            curr_idx = 1
            if items_pendientes:
                lineas.append(f"⏳ PENDIENTES ({len(items_pendientes)})")
                lineas.append("#\tNúmero\tNombre\tDistrito\tCorregimiento\tEstatus\tMotivo")
                for item in items_pendientes:
                    lineas.append(f"{curr_idx}\t{item['numero']}\t{item['nombre']}\t{item['distrito']}\t{item['corregimiento']}\t{item['estado']}\t{item['motivo']}")
                    curr_idx += 1
            if items_entregados:
                if items_pendientes:
                    lineas.append("")
                lineas.append(f"✅ ENTREGADAS ({len(items_entregados)})")
                lineas.append("#\tNúmero\tNombre\tDistrito\tCorregimiento\tEstatus\tMotivo")
                for item in items_entregados:
                    lineas.append(f"{curr_idx}\t{item['numero']}\t{item['nombre']}\t{item['distrito']}\t{item['corregimiento']}\t{item['estado']}\t{item['motivo']}")
                    curr_idx += 1

            toast_msg = f"📋 ¡{total_count} infoplazas copiadas al portapapeles!"

        texto_final = "\n".join(lineas)
        clipboard = QApplication.clipboard()
        clipboard.setText(texto_final)

        self._mostrar_flash_mensaje(toast_msg)

    def exportar_excel(self):
        """Exporta el cuadro consolidado por regionales y el detalle nacional a Excel (.xlsx)."""
        if not self.all_infoplazas:
            QMessageBox.warning(self, "Sin datos", "No hay datos disponibles para exportar.")
            return

        anio = self.get_selected_anio()
        cuat = self.get_selected_cuat()
        default_filename = f"Consolidado_Nacional_Entregas_{anio}_C{cuat}.xlsx"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Consolidado Nacional a Excel",
            default_filename,
            "Archivos de Excel (*.xlsx)"
        )

        if not path:
            return

        try:
            # Hoja 1: Resumen por Regionales
            resumen_filas = []
            for reg in sorted(self.regionals_data.keys()):
                d = self.regionals_data[reg]
                tot = d['total']
                entr = d['entregan']
                no_entr = d['no_entregan']
                entreg = d['entregados']
                pend = d['pendientes']
                pct = (entreg / entr * 100.0) if entr > 0 else 0.0

                resumen_filas.append({
                    "Regional": reg,
                    "Total Infoplazas": tot,
                    "Entregan Informe": entr,
                    "No Entregan": no_entr,
                    "Entregadas": entreg,
                    "Pendientes": pend,
                    "% Cumplimiento": round(pct, 1)
                })

            df_resumen = pd.DataFrame(resumen_filas)

            # Hoja 2: Detalle Nacional Completo
            detalle_filas = []
            for info in self.all_infoplazas:
                num = int(info.get('numero', 0)) if str(info.get('numero', '')).isdigit() else 0
                ctrl = self.control_data.get(num, {})
                estado = ctrl.get('estado', 'Pendiente')
                motivo = ctrl.get('motivo', '')

                detalle_filas.append({
                    "Número": num,
                    "Nombre de Infoplaza": info.get('nombre', ''),
                    "Regional": info.get('regional', ''),
                    "Provincia": info.get('provincia', ''),
                    "Distrito": info.get('distrito', ''),
                    "Corregimiento": info.get('corregimiento', ''),
                    "Estatus de Entrega": estado,
                    "Motivo No Entrega": motivo
                })

            df_detalle = pd.DataFrame(detalle_filas)

            with pd.ExcelWriter(path, engine='openpyxl') as writer:
                df_resumen.to_excel(writer, sheet_name="Resumen Regionales", index=False)
                df_detalle.to_excel(writer, sheet_name="Detalle Nacional", index=False)

            QMessageBox.information(
                self,
                "Exportación Exitosa",
                f"El Consolidado Nacional ha sido exportado correctamente en:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error al Exportar",
                f"Ocurrió un error al intentar exportar el archivo Excel:\n{str(e)}"
            )

    # =========================================================================
    # TEMAS Y ESTILOS
    # =========================================================================

    def update_theme(self, is_dark: bool):
        """Aplica la paleta visual para temas claro y oscuro."""
        self.is_dark_mode = is_dark

        text_main = "#f8fafc" if is_dark else "#0f172a"
        text_sub = "#94a3b8" if is_dark else "#64748b"
        card_bg = "#1e293b" if is_dark else "#ffffff"
        border_card = "#334155" if is_dark else "#e2e8f0"
        btn_bg = "#334155" if is_dark else "#f8fafc"
        btn_hover = "#475569" if is_dark else "#f1f5f9"
        btn_border = "#475569" if is_dark else "#cbd5e1"
        input_bg = "#0f172a" if is_dark else "#ffffff"

        kpi_styles = {
            "total": {
                "dark": {"bg": "#082f49", "border": "#0284c7", "text": "#7dd3fc", "val": "#38bdf8"},
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
            ("no_entregan", getattr(self, 'card_no_entregan', None)),
            ("entregados", getattr(self, 'card_entregados', None)),
            ("pendientes", getattr(self, 'card_pendientes', None))
        ]

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

        # Estilos de Botones
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
        if hasattr(self, 'btn_copiar'):
            self.btn_copiar.setStyleSheet(btn_style)

        # Estilo para botones de filtro segmentado
        filtro_btn_style = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {text_main};
                border: 1px solid {btn_border};
                border-radius: 5px;
                padding: 5px 12px;
                font-size: 11.5px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
            QPushButton:checked {{
                background-color: #0284c7;
                color: #ffffff;
                border: 1px solid #0284c7;
                font-weight: bold;
            }}
        """
        if hasattr(self, 'btn_filtro_todos'):
            self.btn_filtro_todos.setStyleSheet(filtro_btn_style)
        if hasattr(self, 'btn_filtro_pendientes'):
            self.btn_filtro_pendientes.setStyleSheet(filtro_btn_style)
        if hasattr(self, 'btn_filtro_entregadas'):
            self.btn_filtro_entregadas.setStyleSheet(filtro_btn_style)

        if hasattr(self, 'txt_search'):
            self.txt_search.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {input_bg};
                    color: {text_main};
                    border: 1px solid {border_card};
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-size: 12px;
                }}
            """)

        if hasattr(self, 'lbl_title'):
            self.lbl_title.setStyleSheet(f"color: {text_main}; font-size: 14px; font-weight: bold;")
        if hasattr(self, 'lbl_table_reg_title'):
            self.lbl_table_reg_title.setStyleSheet(f"color: {text_main}; font-size: 13px; font-weight: bold;")
        if hasattr(self, 'lbl_detail_title'):
            accent_det = "#fbbf24" if is_dark else "#b45309"
            self.lbl_detail_title.setStyleSheet(f"color: {accent_det}; font-size: 13px; font-weight: bold;")

        table_style = f"""
            QTableWidget {{
                background-color: {card_bg};
                color: {text_main};
                gridline-color: {border_card};
                border: 1px solid {border_card};
                border-radius: 6px;
            }}
            QHeaderView::section {{
                background-color: {btn_bg};
                color: {text_main};
                font-weight: bold;
                font-size: 11px;
                border: 1px solid {border_card};
                padding: 4px;
            }}
            QTableWidget::item:selected {{
                background-color: {'#0284c7' if is_dark else '#e0f2fe'};
                color: {'#ffffff' if is_dark else '#0369a1'};
            }}
        """
        if hasattr(self, 'table_regionales'):
            self.table_regionales.setStyleSheet(table_style)
        if hasattr(self, 'table_detalle'):
            self.table_detalle.setStyleSheet(table_style)
