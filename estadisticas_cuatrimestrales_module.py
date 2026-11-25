import os
import pandas as pd
from typing import Dict, List, Any
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QSize
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QComboBox, QFrame, QScrollArea, QDialog, QMessageBox, QGridLayout, 
    QFileDialog, QTabWidget, QSizePolicy, QGroupBox
)
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.style as mplstyle

try:
    plt.style.use('seaborn-v0_8-darkgrid')
except:
    pass

from cuatrimestral_supabase_manager import supabase_manager
from generador_pdf_ejecutivo import generar_pdf_ejecutivo


class DataLoaderThread(QThread):
    finished = pyqtSignal(list, list, list, dict) 
    error = pyqtSignal(str)

    def __init__(self, anio: int, cuatrimestre: int, parent=None):
        super().__init__(parent)
        self.anio = anio
        self.cuatrimestre = cuatrimestre

    def run(self):
        try:
            caps, err_c = supabase_manager.get_all_capacitaciones(self.anio, self.cuatrimestre)
            if err_c: raise Exception(err_c)
            
            srvs, err_s = supabase_manager.get_all_servicios(self.anio, self.cuatrimestre)
            if err_s: raise Exception(err_s)
            
            acts, err_a = supabase_manager.get_all_otras_actividades(self.anio, self.cuatrimestre)
            if err_a: raise Exception(err_a)
            
            ctrl, err_ctrl = supabase_manager.pull_control_entrega(self.anio, self.cuatrimestre)
            if err_ctrl: raise Exception(err_ctrl)
            
            self.finished.emit(caps, srvs, acts, ctrl)
        except Exception as e:
            self.error.emit(str(e))


class PasswordDialog(QDialog):
    def __init__(self, parent=None, is_dark_mode=False):
        super().__init__(parent)
        self.is_dark_mode = is_dark_mode
        self.setWindowTitle("Acceso Restringido")
        self.setFixedSize(360, 220)
        self.setModal(True)
        self.clave_valida = False

        bg_color = "#0f172a" if self.is_dark_mode else "#ffffff"
        text_color = "#f8fafc" if self.is_dark_mode else "#0f172a"
        input_bg = "#1e293b" if self.is_dark_mode else "#f1f5f9"
        input_border = "#334155" if self.is_dark_mode else "#cbd5e1"

        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg_color}; }}
            QLabel {{ color: {text_color}; }}
            QLineEdit {{ background-color: {input_bg}; color: {text_color}; border: 1px solid {input_border}; padding: 8px; border-radius: 4px; }}
            QPushButton {{ background-color: #0284c7; color: white; padding: 8px; border-radius: 4px; font-weight: bold; }}
            QPushButton:hover {{ background-color: #0369a1; }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        title = QLabel("🔒 Área de Estadísticas Cuatrimestrales")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("Por favor, ingrese la contraseña de administrador:")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.txt_pass)

        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(f"background-color: {input_bg}; color: {text_color};")
        btn_cancel.clicked.connect(self.reject)
        btn_accept = QPushButton("Acceder")
        btn_accept.clicked.connect(self.verificar)

        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_accept)
        layout.addLayout(btn_box)

    def verificar(self):
        if self.txt_pass.text() == "Guerrero2026":  
            self.clave_valida = True
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Contraseña incorrecta.")
            self.txt_pass.clear()


class EstadisticasCuatrimestralesWidget(QWidget):
    def __init__(self, main_window, is_dark_mode=False):
        super().__init__()
        self.main_window = main_window
        self.is_dark_mode = is_dark_mode
        self.df_caps = pd.DataFrame()
        self.df_srvs = pd.DataFrame()
        self.df_acts = pd.DataFrame()
        self.dict_ctrl = {}
        self.catalogo_infoplazas = []

        self.color_text = '#f8fafc' if self.is_dark_mode else '#0f172a'
        self.color_bg = '#1e293b' if self.is_dark_mode else '#ffffff'
        
        self._setup_ui()
        self._load_catalogo()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)

        bg_color = "#0f172a" if self.is_dark_mode else "#f1f5f9"
        text_color = "#f8fafc" if self.is_dark_mode else "#0f172a"
        card_bg = "#1e293b" if self.is_dark_mode else "#ffffff"
        border_color = "#334155" if self.is_dark_mode else "#e2e8f0"

        self.setStyleSheet(f"""
            QWidget {{ background-color: {bg_color}; color: {text_color}; font-family: 'Segoe UI', Arial; }}
            QComboBox {{ padding: 8px; border: 1px solid {border_color}; border-radius: 6px; background: {card_bg}; font-size: 13px; }}
            QGroupBox {{ font-weight: bold; border: 1px solid {border_color}; border-radius: 8px; margin-top: 10px; padding-top: 15px; background: {card_bg}; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; color: #0284c7; }}
            QFrame#Card {{ background-color: {card_bg}; border: 1px solid {border_color}; border-radius: 10px; }}
            
            QTabWidget::pane {{ border: 1px solid {border_color}; border-radius: 8px; background: {card_bg}; top: -1px; }}
            QTabBar::tab {{ background: {bg_color}; border: 1px solid {border_color}; padding: 10px 20px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }}
            QTabBar::tab:selected {{ background: {card_bg}; border-bottom-color: {card_bg}; font-weight: bold; color: #0284c7; }}
            
            QPushButton#PrimaryBtn {{ background-color: #0284c7; color: white; padding: 10px 20px; border-radius: 6px; font-weight: bold; font-size: 14px; }}
            QPushButton#PrimaryBtn:hover {{ background-color: #0369a1; }}
            QPushButton#ExportExcelBtn {{ background-color: #059669; color: white; padding: 8px 15px; border-radius: 6px; font-weight: bold; }}
            QPushButton#ExportExcelBtn:hover {{ background-color: #047857; }}
            QPushButton#ExportPdfBtn {{ background-color: #dc2626; color: white; padding: 8px 15px; border-radius: 6px; font-weight: bold; }}
            QPushButton#ExportPdfBtn:hover {{ background-color: #b91c1c; }}
        """)

        # --- HEADER / CONTROLES ---
        header_layout = QHBoxLayout()
        
        # Grupo de Filtros Principales
        filtros_group = QGroupBox("Filtros de Análisis")
        filtros_layout = QHBoxLayout(filtros_group)
        
        self.cb_anio = QComboBox()
        self.cb_anio.addItems(["2024", "2025", "2026", "2027"])
        self.cb_anio.setCurrentText(str(pd.Timestamp.now().year))
        
        self.cb_cuatrimestre = QComboBox()
        self.cb_cuatrimestre.addItems(["1", "2", "3"])
        
        self.cb_regional = QComboBox()
        self.cb_regional.addItem("Nacional (Todas)")
        self.cb_regional.currentTextChanged.connect(self._actualizar_provincias)
        
        self.cb_provincia = QComboBox()
        self.cb_provincia.addItem("Todas")
        self.cb_provincia.currentTextChanged.connect(self._actualizar_infoplazas)
        
        self.cb_infoplaza = QComboBox()
        self.cb_infoplaza.addItem("Todas")
        self.cb_infoplaza.currentTextChanged.connect(self.actualizar_dashboard)

        btn_cargar = QPushButton("📊 Cargar Datos de la Nube")
        btn_cargar.setObjectName("PrimaryBtn")
        btn_cargar.clicked.connect(self.cargar_datos)

        filtros_layout.addWidget(QLabel("Año:"))
        filtros_layout.addWidget(self.cb_anio)
        filtros_layout.addWidget(QLabel("Cuat.:"))
        filtros_layout.addWidget(self.cb_cuatrimestre)
        filtros_layout.addWidget(QLabel("Regional:"))
        filtros_layout.addWidget(self.cb_regional)
        filtros_layout.addWidget(QLabel("Provincia:"))
        filtros_layout.addWidget(self.cb_provincia)
        filtros_layout.addWidget(QLabel("Infoplaza:"))
        filtros_layout.addWidget(self.cb_infoplaza)
        filtros_layout.addWidget(btn_cargar)
        
        header_layout.addWidget(filtros_group)

        # Grupo de Exportación
        export_group = QGroupBox("Exportación")
        export_layout = QHBoxLayout(export_group)
        btn_excel = QPushButton("📗 Excel")
        btn_excel.setObjectName("ExportExcelBtn")
        btn_excel.clicked.connect(self.exportar_excel)
        btn_pdf = QPushButton("📕 PDF Ejecutivo")
        btn_pdf.setObjectName("ExportPdfBtn")
        btn_pdf.clicked.connect(self.exportar_pdf)
        export_layout.addWidget(btn_excel)
        export_layout.addWidget(btn_pdf)
        
        header_layout.addWidget(export_group)
        
        self.main_layout.addLayout(header_layout)

        # --- TABS ---
        self.tabs = QTabWidget()
        
        # Tab 1: Visión Global
        self.tab_global = QWidget()
        self._setup_tab_global()
        self.tabs.addTab(self.tab_global, "🌍 Visión Global")
        
        # Tab 2: Capacitaciones
        self.tab_capacitaciones = QWidget()
        self._setup_tab_capacitaciones()
        self.tabs.addTab(self.tab_capacitaciones, "🎓 Capacitaciones")
        
        # Tab 3: Actividades
        self.tab_actividades = QWidget()
        self._setup_tab_actividades()
        self.tabs.addTab(self.tab_actividades, "🚀 Otras Actividades")
        
        # Tab 4: Servicios
        self.tab_servicios = QWidget()
        self._setup_tab_servicios()
        self.tabs.addTab(self.tab_servicios, "💻 Servicios")

        self.main_layout.addWidget(self.tabs)


    def _setup_tab_global(self):
        layout = QVBoxLayout(self.tab_global)
        
        # KPIs en la parte superior
        kpi_layout = QHBoxLayout()
        self.card_participantes, self.lbl_kpi_participantes = self._crear_kpi_card("Total Participantes", "0", "#0284c7")
        self.card_horas, self.lbl_kpi_horas = self._crear_kpi_card("Horas de Capacitación", "0", "#8b5cf6")
        self.card_entregas, self.lbl_kpi_entregas = self._crear_kpi_card("Cumplimiento Entregas", "0%", "#10b981")
        kpi_layout.addWidget(self.card_participantes)
        kpi_layout.addWidget(self.card_horas)
        kpi_layout.addWidget(self.card_entregas)
        layout.addLayout(kpi_layout)

        # Gráficos de Visión Global
        charts_layout = QHBoxLayout()
        
        # Doughnut de Entregas
        self.fig_entregas = Figure(figsize=(5, 4), dpi=100)
        self.canvas_entregas = FigureCanvas(self.fig_entregas)
        charts_layout.addWidget(self.canvas_entregas)

        # Top Infoplazas
        self.fig_top_ips = Figure(figsize=(5, 4), dpi=100)
        self.canvas_top_ips = FigureCanvas(self.fig_top_ips)
        charts_layout.addWidget(self.canvas_top_ips)

        self._aplicar_estilo_figura(self.fig_entregas)
        self._aplicar_estilo_figura(self.fig_top_ips)
        
        layout.addLayout(charts_layout)


    def _setup_tab_capacitaciones(self):
        layout = QVBoxLayout(self.tab_capacitaciones)
        charts_layout = QHBoxLayout()
        
        self.fig_caps_mes = Figure(figsize=(6, 5), dpi=100)
        self.canvas_caps_mes = FigureCanvas(self.fig_caps_mes)
        
        self.fig_caps_tema = Figure(figsize=(6, 5), dpi=100)
        self.canvas_caps_tema = FigureCanvas(self.fig_caps_tema)
        
        self._aplicar_estilo_figura(self.fig_caps_mes)
        self._aplicar_estilo_figura(self.fig_caps_tema)
        
        charts_layout.addWidget(self.canvas_caps_mes)
        charts_layout.addWidget(self.canvas_caps_tema)
        layout.addLayout(charts_layout)


    def _setup_tab_actividades(self):
        layout = QVBoxLayout(self.tab_actividades)
        charts_layout = QHBoxLayout()
        
        self.fig_acts_pie = Figure(figsize=(6, 5), dpi=100)
        self.canvas_acts_pie = FigureCanvas(self.fig_acts_pie)
        
        self.fig_acts_bar = Figure(figsize=(6, 5), dpi=100)
        self.canvas_acts_bar = FigureCanvas(self.fig_acts_bar)
        
        self._aplicar_estilo_figura(self.fig_acts_pie)
        self._aplicar_estilo_figura(self.fig_acts_bar)
        
        charts_layout.addWidget(self.canvas_acts_pie)
        charts_layout.addWidget(self.canvas_acts_bar)
        layout.addLayout(charts_layout)


    def _setup_tab_servicios(self):
        layout = QVBoxLayout(self.tab_servicios)
        self.fig_srvs = Figure(figsize=(10, 6), dpi=100)
        self.canvas_srvs = FigureCanvas(self.fig_srvs)
        self._aplicar_estilo_figura(self.fig_srvs)
        layout.addWidget(self.canvas_srvs)


    def _crear_kpi_card(self, titulo, valor, color_hex):
        card = QFrame()
        card.setObjectName("Card")
        l = QVBoxLayout(card)
        l.setContentsMargins(20, 20, 20, 20)
        
        t = QLabel(titulo)
        t.setStyleSheet("font-size: 15px; color: #64748b; font-weight: bold; text-transform: uppercase;")
        t.setAlignment(Qt.AlignCenter)
        
        v = QLabel(valor)
        v.setStyleSheet(f"font-size: 38px; font-weight: bold; color: {color_hex};")
        v.setAlignment(Qt.AlignCenter)
        
        l.addWidget(t)
        l.addWidget(v)
        return card, v


    def _aplicar_estilo_figura(self, fig):
        fig.patch.set_facecolor(self.color_bg)
        if self.is_dark_mode:
            fig.canvas.setStyleSheet("background-color: transparent;")


    def _load_catalogo(self):
        res, err = supabase_manager.get_infoplazas_by_regional("")
        if not err and res:
            self.catalogo_infoplazas = res
            regionales = sorted(list(set(ip.get('regional', '') for ip in res if ip.get('regional'))))
            self.cb_regional.addItems(regionales)


    def _actualizar_provincias(self, regional):
        self.cb_provincia.blockSignals(True)
        self.cb_infoplaza.blockSignals(True)
        self.cb_provincia.clear()
        self.cb_provincia.addItem("Todas")
        self.cb_infoplaza.clear()
        self.cb_infoplaza.addItem("Todas")
        if regional != "Nacional (Todas)":
            provs = sorted(list(set(ip.get('provincia', '') for ip in self.catalogo_infoplazas if ip.get('regional') == regional and ip.get('provincia'))))
            self.cb_provincia.addItems(provs)
        self.cb_infoplaza.blockSignals(False)
        self.cb_provincia.blockSignals(False)
        self.actualizar_dashboard()


    def _actualizar_infoplazas(self, provincia):
        self.cb_infoplaza.blockSignals(True)
        self.cb_infoplaza.clear()
        self.cb_infoplaza.addItem("Todas")
        regional = self.cb_regional.currentText()
        if regional != "Nacional (Todas)" and provincia != "Todas":
            ips = [f"{ip.get('numero')} - {ip.get('corregimiento')}" for ip in self.catalogo_infoplazas 
                   if ip.get('regional') == regional and ip.get('provincia') == provincia]
            self.cb_infoplaza.addItems(sorted(ips))
        self.cb_infoplaza.blockSignals(False)
        self.actualizar_dashboard()


    def cargar_datos(self):
        a = int(self.cb_anio.currentText())
        c = int(self.cb_cuatrimestre.currentText())
        
        self.loader = DataLoaderThread(a, c)
        self.loader.finished.connect(self._on_datos_cargados)
        self.loader.error.connect(lambda e: QMessageBox.critical(self, "Error", f"Fallo cargando datos: {e}"))
        self.loader.start()


    def _on_datos_cargados(self, caps, srvs, acts, ctrl):
        self.df_caps = pd.DataFrame(caps)
        self.df_srvs = pd.DataFrame(srvs)
        self.df_acts = pd.DataFrame(acts)
        self.dict_ctrl = ctrl
        
        self.actualizar_dashboard()


    def _get_filtered_infoplazas(self):
        reg = self.cb_regional.currentText()
        prov = self.cb_provincia.currentText()
        ip_sel = self.cb_infoplaza.currentText()

        ips_validas = []
        for ip in self.catalogo_infoplazas:
            match_reg = (reg == "Nacional (Todas)" or ip.get('regional') == reg)
            match_prov = (prov == "Todas" or ip.get('provincia') == prov)
            match_ip = (ip_sel == "Todas" or str(ip.get('numero')) == ip_sel.split(" ")[0])
            if match_reg and match_prov and match_ip:
                ips_validas.append(ip.get('numero'))
        return ips_validas


    def actualizar_dashboard(self, *args):
        if self.df_caps.empty and self.df_srvs.empty and self.df_acts.empty and not self.dict_ctrl:
            return

        ips_validas = self._get_filtered_infoplazas()
        
        df_c = self.df_caps[self.df_caps['infoplaza_numero'].isin(ips_validas)] if not self.df_caps.empty else self.df_caps
        df_s = self.df_srvs[self.df_srvs['infoplaza_numero'].isin(ips_validas)] if not self.df_srvs.empty else self.df_srvs
        df_a = self.df_acts[self.df_acts['infoplaza_numero'].isin(ips_validas)] if not self.df_acts.empty else self.df_acts
        
        # KPIs
        part_c = df_c['participantes'].sum() if not df_c.empty else 0
        part_a = df_a['participantes'].sum() if not df_a.empty else 0
        horas_c = df_c['horas'].sum() if not df_c.empty else 0
        
        self.lbl_kpi_participantes.setText(f"{int(part_c + part_a):,}")
        self.lbl_kpi_horas.setText(f"{horas_c:,.1f}")

        entregadas = sum(1 for ip in ips_validas if self.dict_ctrl.get(ip, {}).get('estado') == 'Entregado')
        total_ips = len(ips_validas)
        pct = (entregadas / total_ips * 100) if total_ips > 0 else 0
        self.lbl_kpi_entregas.setText(f"{pct:.1f}%")

        # Dibujar Gráficos
        self._plot_global(entregadas, total_ips - entregadas, df_c, df_a)
        self._plot_capacitaciones(df_c)
        self._plot_actividades(df_a)
        self._plot_servicios(df_s)

    def _formatear_ax(self, ax, hide_spines=True):
        ax.tick_params(colors=self.color_text)
        ax.xaxis.label.set_color(self.color_text)
        ax.yaxis.label.set_color(self.color_text)
        ax.title.set_color(self.color_text)
        ax.set_facecolor(self.color_bg)
        for spine in ax.spines.values():
            spine.set_edgecolor('#cbd5e1' if not self.is_dark_mode else '#334155')
            if hide_spines and spine.spine_type in ['top', 'right']:
                spine.set_visible(False)

    def _plot_global(self, entregadas, pendientes, df_c, df_a):
        # 1. Doughnut Chart Entregas
        self.fig_entregas.clear()
        ax = self.fig_entregas.add_subplot(111)
        if entregadas > 0 or pendientes > 0:
            wedges, texts, autotexts = ax.pie(
                [entregadas, pendientes], 
                labels=['Entregado', 'Pendiente'], 
                colors=['#10b981', '#ef4444'], 
                autopct='%1.1f%%', 
                startangle=90,
                wedgeprops=dict(width=0.4, edgecolor='w'), # Doughnut
                textprops={'color': self.color_text, 'fontsize': 11}
            )
        ax.set_title("Estado de Entregas", color=self.color_text, fontsize=14, pad=20)
        self.fig_entregas.tight_layout()
        self.canvas_entregas.draw()

        # 2. Top Infoplazas
        self.fig_top_ips.clear()
        ax2 = self.fig_top_ips.add_subplot(111)
        
        # Combinar caps y acts
        part_por_ip = pd.Series(dtype=float)
        if not df_c.empty: part_por_ip = part_por_ip.add(df_c.groupby('infoplaza_numero')['participantes'].sum(), fill_value=0)
        if not df_a.empty: part_por_ip = part_por_ip.add(df_a.groupby('infoplaza_numero')['participantes'].sum(), fill_value=0)
        
        if not part_por_ip.empty:
            res = part_por_ip.sort_values(ascending=False).head(5).sort_values(ascending=True) # Ascending para barh
            ax2.barh(res.index.astype(str), res.values, color='#0284c7', height=0.6, edgecolor='none')
            
            # Data labels
            for i, v in enumerate(res.values):
                ax2.text(v + (res.max()*0.02), i, f"{int(v):,}", color=self.color_text, va='center', fontweight='bold')
                
        ax2.set_title("Top 5 Infoplazas (Mayor Participación)", color=self.color_text, fontsize=14, pad=20)
        self._formatear_ax(ax2)
        self.fig_top_ips.tight_layout()
        self.canvas_top_ips.draw()


    def _plot_capacitaciones(self, df):
        self.fig_caps_mes.clear()
        ax1 = self.fig_caps_mes.add_subplot(111)
        self.fig_caps_tema.clear()
        ax2 = self.fig_caps_tema.add_subplot(111)
        
        if not df.empty:
            # 1. Por mes
            res_mes = df.groupby('mes')['participantes'].sum()
            ax1.bar(res_mes.index, res_mes.values, color='#3b82f6', width=0.5)
            for i, v in enumerate(res_mes.values):
                ax1.text(i, v + (res_mes.max()*0.02), f"{int(v):,}", ha='center', color=self.color_text, fontweight='bold')
            ax1.set_title("Evolución de Participantes por Mes", color=self.color_text, fontsize=14, pad=20)
            
            # 2. Por Tema
            res_tema = df.groupby('tema')['participantes'].sum().sort_values(ascending=False).head(7).sort_values(ascending=True)
            ax2.barh(res_tema.index, res_tema.values, color='#8b5cf6', height=0.6)
            ax2.set_title("Top Temas de Capacitación", color=self.color_text, fontsize=14, pad=20)
        
        self._formatear_ax(ax1)
        self._formatear_ax(ax2)
        self.fig_caps_mes.tight_layout()
        self.fig_caps_tema.tight_layout()
        self.canvas_caps_mes.draw()
        self.canvas_caps_tema.draw()


    def _plot_actividades(self, df):
        self.fig_acts_pie.clear()
        ax1 = self.fig_acts_pie.add_subplot(111)
        self.fig_acts_bar.clear()
        ax2 = self.fig_acts_bar.add_subplot(111)

        if not df.empty:
            res_cat = df.groupby('categoria')['participantes'].sum()
            
            # Pie Chart
            res_cat_top = res_cat.sort_values(ascending=False).head(5)
            ax1.pie(res_cat_top.values, labels=res_cat_top.index, autopct='%1.1f%%', startangle=140, 
                    colors=plt.cm.Set3.colors, textprops={'color': self.color_text})
            ax1.set_title("Distribución por Categoría", color=self.color_text, fontsize=14, pad=20)
            
            # Bar Chart (Detalle Actividades)
            res_act = df.groupby('actividad')['participantes'].sum().sort_values(ascending=False).head(7).sort_values(ascending=True)
            ax2.barh(res_act.index, res_act.values, color='#f59e0b', height=0.6)
            ax2.set_title("Top 7 Actividades Específicas", color=self.color_text, fontsize=14, pad=20)
        
        self._formatear_ax(ax2)
        self.fig_acts_pie.tight_layout()
        self.fig_acts_bar.tight_layout()
        self.canvas_acts_pie.draw()
        self.canvas_acts_bar.draw()


    def _plot_servicios(self, df):
        self.fig_srvs.clear()
        ax = self.fig_srvs.add_subplot(111)
        if not df.empty:
            res = df[df['ofrecido'] == True]['servicio_nombre'].value_counts().head(10).sort_values(ascending=True)
            ax.barh(res.index, res.values, color='#14b8a6', height=0.6)
            for i, v in enumerate(res.values):
                ax.text(v + (res.max()*0.01), i, str(v), color=self.color_text, va='center', fontweight='bold')
                
        ax.set_title("Ranking de Servicios Ofrecidos (Frecuencia)", color=self.color_text, fontsize=16, pad=20)
        self._formatear_ax(ax)
        self.fig_srvs.tight_layout()
        self.canvas_srvs.draw()


    def exportar_excel(self):
        ips_validas = self._get_filtered_infoplazas()
        df_c = self.df_caps[self.df_caps['infoplaza_numero'].isin(ips_validas)] if not self.df_caps.empty else self.df_caps
        df_s = self.df_srvs[self.df_srvs['infoplaza_numero'].isin(ips_validas)] if not self.df_srvs.empty else self.df_srvs
        df_a = self.df_acts[self.df_acts['infoplaza_numero'].isin(ips_validas)] if not self.df_acts.empty else self.df_acts
        
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar a Excel", f"Estadisticas_Cuatrimestrales.xlsx", "Excel Files (*.xlsx)")
        if ruta:
            try:
                with pd.ExcelWriter(ruta, engine='openpyxl') as writer:
                    if not df_c.empty: df_c.to_excel(writer, sheet_name="Capacitaciones", index=False)
                    if not df_s.empty: df_s.to_excel(writer, sheet_name="Servicios", index=False)
                    if not df_a.empty: df_a.to_excel(writer, sheet_name="Actividades", index=False)
                QMessageBox.information(self, "Éxito", "Exportación a Excel completada exitosamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Fallo al exportar: {e}")

    def exportar_pdf(self):
        ips_validas = self._get_filtered_infoplazas()
        anio = self.cb_anio.currentText()
        cuatrimestre = self.cb_cuatrimestre.currentText()
        
        try:
            ruta_pdf = generar_pdf_ejecutivo(
                anio, cuatrimestre, 
                self.df_caps, self.df_srvs, self.df_acts, 
                self.dict_ctrl, self.catalogo_infoplazas,
                self.cb_regional.currentText()
            )
            QMessageBox.information(self, "Éxito", f"Informe Ejecutivo generado exitosamente en:\n{ruta_pdf}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generando PDF: {e}")
