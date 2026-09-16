import os
import pandas as pd
from typing import Dict, List, Any
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QComboBox, QFrame, QScrollArea, QDialog, QMessageBox, QGridLayout, QFileDialog
)
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from cuatrimestral_supabase_manager import supabase_manager
from generador_pdf_ejecutivo import generar_pdf_ejecutivo


class DataLoaderThread(QThread):
    finished = pyqtSignal(list, list, list, dict) # capacitaciones, servicios, actividades, control_entrega
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
        if self.txt_pass.text() == "Guerrero2026":  # Misma clave o una definida por el usuario
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

        self._setup_ui()
        self._load_catalogo()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)

        bg_color = "#0f172a" if self.is_dark_mode else "#f8fafc"
        text_color = "#f8fafc" if self.is_dark_mode else "#0f172a"
        card_bg = "#1e293b" if self.is_dark_mode else "#ffffff"
        border_color = "#334155" if self.is_dark_mode else "#cbd5e1"

        self.setStyleSheet(f"""
            QWidget {{ background-color: {bg_color}; color: {text_color}; font-family: 'Segoe UI'; }}
            QComboBox {{ padding: 6px; border: 1px solid {border_color}; border-radius: 4px; background: {card_bg}; }}
            QFrame#Card {{ background-color: {card_bg}; border: 1px solid {border_color}; border-radius: 8px; }}
            QPushButton#ActionBtn {{ background-color: #0284c7; color: white; padding: 8px 15px; border-radius: 4px; font-weight: bold; }}
            QPushButton#ActionBtn:hover {{ background-color: #0369a1; }}
            QPushButton#ExportExcelBtn {{ background-color: #059669; color: white; padding: 8px 15px; border-radius: 4px; font-weight: bold; }}
            QPushButton#ExportExcelBtn:hover {{ background-color: #047857; }}
            QPushButton#ExportPdfBtn {{ background-color: #dc2626; color: white; padding: 8px 15px; border-radius: 4px; font-weight: bold; }}
            QPushButton#ExportPdfBtn:hover {{ background-color: #b91c1c; }}
        """)

        # --- FILTROS ---
        filters_frame = QFrame()
        filters_frame.setObjectName("Card")
        filters_layout = QHBoxLayout(filters_frame)
        
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

        btn_cargar = QPushButton("📊 Cargar Datos")
        btn_cargar.setObjectName("ActionBtn")
        btn_cargar.clicked.connect(self.cargar_datos)

        btn_excel = QPushButton("📗 Exportar Excel")
        btn_excel.setObjectName("ExportExcelBtn")
        btn_excel.clicked.connect(self.exportar_excel)

        btn_pdf = QPushButton("📕 Informe Ejecutivo (PDF)")
        btn_pdf.setObjectName("ExportPdfBtn")
        btn_pdf.clicked.connect(self.exportar_pdf)

        filters_layout.addWidget(QLabel("Año:"))
        filters_layout.addWidget(self.cb_anio)
        filters_layout.addWidget(QLabel("Cuatrimestre:"))
        filters_layout.addWidget(self.cb_cuatrimestre)
        filters_layout.addWidget(QLabel("Regional:"))
        filters_layout.addWidget(self.cb_regional)
        filters_layout.addWidget(QLabel("Provincia:"))
        filters_layout.addWidget(self.cb_provincia)
        filters_layout.addWidget(QLabel("Infoplaza:"))
        filters_layout.addWidget(self.cb_infoplaza)
        filters_layout.addStretch()
        filters_layout.addWidget(btn_cargar)
        filters_layout.addWidget(btn_excel)
        filters_layout.addWidget(btn_pdf)
        
        self.main_layout.addWidget(filters_frame)

        # --- KPIs ---
        kpi_layout = QHBoxLayout()
        card1, self.lbl_kpi_participantes = self._crear_kpi_card("Participantes (Total)", "0")
        card2, self.lbl_kpi_horas = self._crear_kpi_card("Horas de Capacitación", "0")
        card3, self.lbl_kpi_entregas = self._crear_kpi_card("Cumplimiento Entregas", "0%")
        kpi_layout.addWidget(card1)
        kpi_layout.addWidget(card2)
        kpi_layout.addWidget(card3)
        self.main_layout.addLayout(kpi_layout)

        # --- GRÁFICOS ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        self.charts_layout = QGridLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        self.main_layout.addWidget(scroll_area)

        # Configurar canvas Matplotlib
        self.fig_caps = Figure(figsize=(5, 3), dpi=100)
        self.canvas_caps = FigureCanvas(self.fig_caps)
        self.fig_srvs = Figure(figsize=(5, 3), dpi=100)
        self.canvas_srvs = FigureCanvas(self.fig_srvs)
        self.fig_acts = Figure(figsize=(5, 3), dpi=100)
        self.canvas_acts = FigureCanvas(self.fig_acts)
        self.fig_entregas = Figure(figsize=(5, 3), dpi=100)
        self.canvas_entregas = FigureCanvas(self.fig_entregas)

        self._aplicar_estilo_figura(self.fig_caps)
        self._aplicar_estilo_figura(self.fig_srvs)
        self._aplicar_estilo_figura(self.fig_acts)
        self._aplicar_estilo_figura(self.fig_entregas)

        self.charts_layout.addWidget(self.canvas_caps, 0, 0)
        self.charts_layout.addWidget(self.canvas_srvs, 0, 1)
        self.charts_layout.addWidget(self.canvas_acts, 1, 0)
        self.charts_layout.addWidget(self.canvas_entregas, 1, 1)

    def _crear_kpi_card(self, titulo, valor):
        card = QFrame()
        card.setObjectName("Card")
        l = QVBoxLayout(card)
        t = QLabel(titulo)
        t.setStyleSheet("font-size: 14px; color: #94a3b8;")
        t.setAlignment(Qt.AlignCenter)
        v = QLabel(valor)
        v.setStyleSheet("font-size: 26px; font-weight: bold;")
        v.setAlignment(Qt.AlignCenter)
        l.addWidget(t)
        l.addWidget(v)
        return card, v

    def _aplicar_estilo_figura(self, fig):
        if self.is_dark_mode:
            fig.patch.set_facecolor('#1e293b')
            fig.canvas.setStyleSheet("background-color: transparent;")
        else:
            fig.patch.set_facecolor('#ffffff')

    def _load_catalogo(self):
        # Cargar catálogo de Infoplazas para llenar los filtros
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
        
        # Filtrar DataFrames
        df_c = self.df_caps[self.df_caps['infoplaza_numero'].isin(ips_validas)] if not self.df_caps.empty else self.df_caps
        df_s = self.df_srvs[self.df_srvs['infoplaza_numero'].isin(ips_validas)] if not self.df_srvs.empty else self.df_srvs
        df_a = self.df_acts[self.df_acts['infoplaza_numero'].isin(ips_validas)] if not self.df_acts.empty else self.df_acts
        
        # Calcular KPIs
        part_c = df_c['participantes'].sum() if not df_c.empty else 0
        part_a = df_a['participantes'].sum() if not df_a.empty else 0
        horas_c = df_c['horas'].sum() if not df_c.empty else 0
        
        self.lbl_kpi_participantes.setText(f"{int(part_c + part_a):,}")
        self.lbl_kpi_horas.setText(f"{horas_c:,.1f}")

        entregadas = sum(1 for ip in ips_validas if self.dict_ctrl.get(ip, {}).get('estado') == 'Entregado')
        total_ips = len(ips_validas)
        pct = (entregadas / total_ips * 100) if total_ips > 0 else 0
        self.lbl_kpi_entregas.setText(f"{pct:.1f}%")

        # Actualizar Gráficos
        self._plot_capacitaciones(df_c)
        self._plot_servicios(df_s)
        self._plot_actividades(df_a)
        self._plot_entregas(entregadas, total_ips - entregadas)

    def _plot_capacitaciones(self, df):
        self.fig_caps.clear()
        ax = self.fig_caps.add_subplot(111)
        if not df.empty:
            res = df.groupby('mes')['participantes'].sum()
            ax.bar(res.index, res.values, color='#0ea5e9')
        ax.set_title("Capacitaciones (Participantes x Mes)", color='white' if self.is_dark_mode else 'black')
        self._formatear_ax(ax)
        self.canvas_caps.draw()

    def _plot_servicios(self, df):
        self.fig_srvs.clear()
        ax = self.fig_srvs.add_subplot(111)
        if not df.empty:
            res = df[df['ofrecido'] == True]['servicio_nombre'].value_counts().head(5)
            ax.barh(res.index, res.values, color='#10b981')
            ax.invert_yaxis()
        ax.set_title("Top 5 Servicios Más Ofrecidos", color='white' if self.is_dark_mode else 'black')
        self._formatear_ax(ax)
        self.canvas_srvs.draw()

    def _plot_actividades(self, df):
        self.fig_acts.clear()
        ax = self.fig_acts.add_subplot(111)
        if not df.empty:
            res = df.groupby('categoria')['participantes'].sum().head(5)
            ax.pie(res.values, labels=res.index, autopct='%1.1f%%', textprops={'color': 'white' if self.is_dark_mode else 'black'})
        ax.set_title("Top 5 Otras Actividades", color='white' if self.is_dark_mode else 'black')
        self.canvas_acts.draw()

    def _plot_entregas(self, entregadas, pendientes):
        self.fig_entregas.clear()
        ax = self.fig_entregas.add_subplot(111)
        if entregadas > 0 or pendientes > 0:
            ax.pie([entregadas, pendientes], labels=['Entregado', 'Pendiente'], colors=['#059669', '#dc2626'], autopct='%1.1f%%', textprops={'color': 'white' if self.is_dark_mode else 'black'})
        ax.set_title("Estado de Entregas", color='white' if self.is_dark_mode else 'black')
        self.canvas_entregas.draw()

    def _formatear_ax(self, ax):
        color = 'white' if self.is_dark_mode else 'black'
        ax.tick_params(colors=color)
        for spine in ax.spines.values():
            spine.set_edgecolor(color)
        if self.is_dark_mode:
            ax.set_facecolor('#1e293b')

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
