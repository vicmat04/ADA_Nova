from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QWidget, QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QUrl, QSize
from PyQt5.QtGui import QDesktopServices, QFont, QColor, QIcon

class NewsCardWidget(QFrame):
    """Tarjeta visual para una sola noticia"""
    def __init__(self, news_data, parent=None):
        super().__init__(parent)
        self.news_data = news_data
        self.init_ui()
        
    def init_ui(self):
        # Estilo de tarjeta
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            NewsCardWidget {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
            NewsCardWidget:hover {
                border: 1px solid #3498db;
            }
        """)
        
        # Efecto de sombra
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # 1. Cabecera: Icono y Fecha
        header_layout = QHBoxLayout()
        
        tipo = self.news_data.get('TIPO', 'INFO').upper()
        icon_map = {
            'VIDEO': '🎥',
            'ALERTA': '⚠️',
            'EVENTO': '📅',
            'INFO': 'ℹ️',
            'UPDATE': '🚀'
        }
        icon_char = icon_map.get(tipo, 'ℹ️')
        
        lbl_icon = QLabel(icon_char)
        lbl_icon.setStyleSheet("font-size: 17px;")
        header_layout.addWidget(lbl_icon)
        
        lbl_tipo = QLabel(tipo)
        lbl_tipo.setStyleSheet("color: #7f8c8d; font-weight: bold; font-size: 11px;")
        header_layout.addWidget(lbl_tipo)
        
        header_layout.addStretch()
        
        fecha = self.news_data.get('FECHA', '')
        lbl_fecha = QLabel(fecha)
        lbl_fecha.setStyleSheet("color: #95a5a6; font-size: 12px;")
        header_layout.addWidget(lbl_fecha)
        
        layout.addLayout(header_layout)
        
        # 2. Título
        titulo = self.news_data.get('TITULO', 'Sin Título')
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setWordWrap(True)
        lbl_titulo.setStyleSheet("font-weight: bold; font-size: 15px; color: #2c3e50;")
        layout.addWidget(lbl_titulo)
        
        # 3. Descripción
        desc = self.news_data.get('DESCRIPCION', '')
        lbl_desc = QLabel(desc)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #34495e; font-size: 13px; margin-bottom: 5px;")
        layout.addWidget(lbl_desc)
        
        # 4. Botón de Acción (si hay link)
        link = self.news_data.get('URL_LINK', '')
        if link:
            btn_action = QPushButton("Ver Más")
            btn_action.setCursor(Qt.PointingHandCursor)
            btn_action.setStyleSheet("""
                QPushButton {
                    background-color: #f8f9fa;
                    border: 1px solid #dcdcdc;
                    border-radius: 5px;
                    padding: 5px 10px;
                    color: #2980b9;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #e3f2fd;
                    border-color: #2980b9;
                }
            """)
            btn_action.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(link)))
            layout.addWidget(btn_action, 0, Qt.AlignRight)


class NovedadesWindow(QDialog):
    """Ventana principal de Novedades"""
    def __init__(self, novedades_data, manager, parent=None):
        super().__init__(parent)
        self.novedades_data = novedades_data
        self.manager = manager
        
        self.setWindowTitle("Novedades y Actualizaciones")
        self.setFixedSize(600, 600)
        self.init_ui()
        
        # Marcar todo como leído al abrir (o al cerrar)
        # Por ahora lo marcamos al abrir para limpiar el badge inmediatamente
        self.manager.mark_all_as_read(self.novedades_data)
        
    def init_ui(self):
        self.setStyleSheet("background-color: #f5f6fa;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        
        # Cabecera Estilizada
        header = QFrame()
        header.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #dcdcdc;")
        header_layout = QHBoxLayout(header)
        
        lbl_title = QLabel("🔔 Novedades")
        lbl_title.setStyleSheet("font-size: 19px; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(lbl_title)
        
        main_layout.addWidget(header)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setSpacing(15)
        self.container_layout.setContentsMargins(20, 20, 20, 20)
        
        # Poblar con noticias
        # Ordenar por fecha (asumiendo que vienen ordenadas o que ID mayor es mas nuevo)
        # Aquí invertimos para ver las últimas arriba si vienen secuenciales
        active_news = [n for n in self.novedades_data if str(n.get('ACTIVO','SI')).upper() == 'SI']
        
        if not active_news:
            lbl_empty = QLabel("No hay novedades por el momento.\n¡Todo está al día! ✨")
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet("color: #7f8c8d; font-size: 15px; margin-top: 50px;")
            self.container_layout.addWidget(lbl_empty)
        else:
            # Mostrar primero las no leídas (opcional, por ahora orden de lista invertido)
            for news in reversed(active_news):
                card = NewsCardWidget(news)
                self.container_layout.addWidget(card)
                
        self.container_layout.addStretch()
        
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
        # Pie de página con botón Cerrar
        footer = QFrame()
        footer.setStyleSheet("background-color: #ffffff; border-top: 1px solid #dcdcdc;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(15, 10, 15, 10)
        
        btn_close = QPushButton("Cerrar")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedHeight(35)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                padding: 0 20px;
                border: none;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        btn_close.clicked.connect(self.accept)
        
        footer_layout.addStretch()
        footer_layout.addWidget(btn_close)
        
        main_layout.addWidget(footer)


class SingleEventWindow(QDialog):
    """Ventana exclusiva para mostrar un ÚNICO evento importante"""
    def __init__(self, event_data, manager, parent=None):
        super().__init__(parent)
        self.event_data = event_data
        self.manager = manager
        
        self.setWindowTitle("📅 Evento Especial")
        self.setFixedSize(500, 400) # Más ancha, menos alta que la lista
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint) # Sin botón cerrar default
        
        self.init_ui()
        
        # Marcar COMO LEÍDO al cerrar
        # (Se hace en accept, pero por seguridad marcamos ID aquí)
        self.event_id = str(self.event_data.get('ID', ''))

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border: 2px solid #3498db;
                border-radius: 10px;
            }
            QLabel { color: #2c3e50; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        # Icono gigante
        lbl_icon = QLabel("📅")
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setStyleSheet("font-size: 65px;")
        layout.addWidget(lbl_icon)
        
        # Fecha
        fecha = self.event_data.get('FECHA', '')
        if fecha:
            lbl_fecha = QLabel(f"{fecha}")
            lbl_fecha.setAlignment(Qt.AlignCenter)
            lbl_fecha.setStyleSheet("color: #7f8c8d; font-size: 15px; font-weight: bold;")
            layout.addWidget(lbl_fecha)
        
        # Título
        titulo = self.event_data.get('TITULO', 'Nuevo Evento')
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setAlignment(Qt.AlignCenter)
        lbl_titulo.setWordWrap(True)
        lbl_titulo.setStyleSheet("font-size: 23px; font-weight: bold; color: #2980b9; margin: 10px 0;")
        layout.addWidget(lbl_titulo)
        
        # Descripción
        desc = self.event_data.get('DESCRIPCION', '')
        lbl_desc = QLabel(desc)
        lbl_desc.setAlignment(Qt.AlignCenter)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("font-size: 15px; line-height: 1.4;")
        layout.addWidget(lbl_desc)
        
        layout.addStretch()
        
        # Botones
        btn_layout = QHBoxLayout()
        
        # Botón Ver Más (Link)
        link = self.event_data.get('URL_LINK', '')
        if link:
            btn_link = QPushButton("🔗 Ver Detalles")
            btn_link.setCursor(Qt.PointingHandCursor)
            btn_link.setFixedHeight(40)
            btn_link.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border-radius: 5px;
                    font-weight: bold;
                    padding: 0 20px;
                    font-size: 15px;
                }
                QPushButton:hover { background-color: #2980b9; }
            """)
            btn_link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(link)))
            btn_layout.addWidget(btn_link)
        
        # Botón Entendido (Cerrar)
        btn_ok = QPushButton("Entendido")
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setFixedHeight(40)
        if link:
            btn_ok.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #7f8c8d;
                    border: 1px solid #bdc3c7;
                    border-radius: 5px;
                    font-weight: bold;
                    padding: 0 20px;
                }
                QPushButton:hover { background-color: #ecf0f1; }
            """)
        else:
            # Si es el único botón, darle color principal
            btn_ok.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    border-radius: 5px;
                    font-weight: bold;
                    padding: 0 30px;
                    font-size: 15px;
                }
                QPushButton:hover { background-color: #2ecc71; }
            """)
            
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        
        layout.addLayout(btn_layout)

    def accept(self):
        # Marcar como leído al cerrar
        self.manager.mark_as_read(self.event_id)
        super().accept()
