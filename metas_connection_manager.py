"""
Gestor de Conexión con Retry Logic para Módulo de Metas
=======================================================

Este módulo maneja la conexión a Google Sheets con retry logic,
detección de estado de conexión y manejo de errores.

Características:
- Retry con backoff exponencial (4 intentos)
- Detección automática de estado online/offline
- Estados de conexión claros
- Logging detallado de intentos
"""

import time
from typing import Callable, Tuple, Optional, Any
from enum import Enum


class ConnectionStatus(Enum):
    """Estados posibles de conexión"""
    ONLINE_FRESH = "online_fresh"          # Conectado, datos recién descargados
    ONLINE_CACHED = "online_cached"        # Conectado, usando caché reciente  
    OFFLINE_CACHED = "offline_cached"      # Sin conexión, usando caché antiguo
    OFFLINE_NO_DATA = "offline_no_data"    # Sin conexión, sin caché disponible
    ERROR = "error"                        # Error crítico


from PyQt5.QtCore import QObject, pyqtSignal

class MetasConnectionManager(QObject):
    """Gestiona conexiones con retry logic y detección de estado"""
    
    # Señal emitida cuando cambia el estado: (NuevoEstado, TextoUltimaActualizacion)
    connection_changed = pyqtSignal(object, str)

    # Configuración de retry
    MAX_RETRIES = 4
    RETRY_DELAYS = [0, 5, 10, 20]  # Segundos de espera entre intentos
    
    def __init__(self):
        """Inicializa el gestor de conexión"""
        super().__init__() # Inicializar QObject
        self.last_attempt_time = None
        self.retry_count = 0
        self.last_error = None
        self.current_status = ConnectionStatus.OFFLINE_NO_DATA
        self.last_update_str = "---" # Inicializar string de fecha
    
    def try_connect_with_retry(
        self, 
        connect_func: Callable[[], Tuple[Any, Optional[str]]],
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[Any, Optional[str], ConnectionStatus]:
        """
        Intenta conectar con retry logic y backoff exponencial
        
        Args:
            connect_func: Función que intenta la conexión. Debe retornar (data, error)
            progress_callback: Callback opcional para reportar progreso
        
        Returns:
            Tuple[Any, Optional[str], ConnectionStatus]: (datos, error, estado)
        """
        self.retry_count = 0
        
        for attempt in range(self.MAX_RETRIES):
            self.retry_count = attempt + 1
            
            # Reportar progreso
            if progress_callback:
                if attempt == 0:
                    progress_callback(f"Conectando a Google Sheets...")
                else:
                    progress_callback(
                        f"Reintentando conexión ({attempt + 1}/{self.MAX_RETRIES})..."
                    )
            
            # Intentar conexión
            try:
                data, error = connect_func()
                
                if not error and data:
                    # Éxito - datos descargados
                    self.current_status = ConnectionStatus.ONLINE_FRESH
                    self.last_error = None
                    print(f"[CONNECTION] ✅ Conexión exitosa en intento {attempt + 1}")
                    return data, None, ConnectionStatus.ONLINE_FRESH
                
                # Hay error, pero continuamos intentando
                self.last_error = error
                print(f"[CONNECTION] ❌ Intento {attempt + 1} falló: {error}")
                
            except Exception as e:
                self.last_error = str(e)
                print(f"[CONNECTION] ❌ Excepción en intento {attempt + 1}: {e}")
            
            # Si no es el último intento, esperar antes de reintentar
            if attempt < self.MAX_RETRIES - 1:
                delay = self.RETRY_DELAYS[attempt + 1]
                if delay > 0:
                    if progress_callback:
                        progress_callback(f"Esperando {delay} segundos antes de reintentar...")
                    print(f"[CONNECTION] ⏳ Esperando {delay}s antes del siguiente intento")
                    time.sleep(delay)
        
        # Todos los intentos fallaron
        self.current_status = ConnectionStatus.ERROR
        error_msg = f"No se pudo conectar después de {self.MAX_RETRIES} intentos"
        if self.last_error:
            error_msg += f"\nÚltimo error: {self.last_error}"
        
        print(f"[CONNECTION] ❌ {error_msg}")
        return None, error_msg, ConnectionStatus.ERROR
    
    def get_status_info(self) -> dict:
        """
        Obtiene información del estado actual de conexión
        
        Returns:
            dict: Información detallada del estado
        """
        return {
            'status': self.current_status,
            'retry_count': self.retry_count,
            'last_error': self.last_error,
            'status_text': self._get_status_text(),
            'status_icon': self._get_status_icon(),
            'status_color': self._get_status_color()
        }
    
    def _get_status_text(self) -> str:
        """Obtiene texto descriptivo del estado actual"""
        status_map = {
            ConnectionStatus.ONLINE_FRESH: "Conectado",
            ConnectionStatus.ONLINE_CACHED: "Conectado (caché)",
            ConnectionStatus.OFFLINE_CACHED: "Sin conexión (datos locales)",
            ConnectionStatus.OFFLINE_NO_DATA: "Sin conexión (sin datos)",
            ConnectionStatus.ERROR: "Error de conexión"
        }
        return status_map.get(self.current_status, "Desconocido")
    
    def _get_status_icon(self) -> str:
        """Obtiene ícono del estado actual"""
        icon_map = {
            ConnectionStatus.ONLINE_FRESH: "🟢",
            ConnectionStatus.ONLINE_CACHED: "🟡",
            ConnectionStatus.OFFLINE_CACHED: "🔴",
            ConnectionStatus.OFFLINE_NO_DATA: "⚫",
            ConnectionStatus.ERROR: "❌"
        }
        return icon_map.get(self.current_status, "❓")
    
    def _get_status_color(self) -> str:
        """Obtiene color hexadecimal del estado actual"""
        color_map = {
            ConnectionStatus.ONLINE_FRESH: "#28a745",      # Verde
            ConnectionStatus.ONLINE_CACHED: "#ffc107",     # Amarillo
            ConnectionStatus.OFFLINE_CACHED: "#dc3545",    # Rojo
            ConnectionStatus.OFFLINE_NO_DATA: "#6c757d",   # Gris
            ConnectionStatus.ERROR: "#dc3545"              # Rojo
        }
        return color_map.get(self.current_status, "#6c757d")
    
    def set_status(self, status: ConnectionStatus):
        """
        Establece manualmente el estado de conexión
        
        Args:
            status: Nuevo estado de conexión
        """
        self.current_status = status
        
        # Actualizar timestamp
        from datetime import datetime
        self.last_update_str = datetime.now().strftime("%H:%M:%S")
        
        # Emitir señal
        self.connection_changed.emit(self.current_status, self.last_update_str)
        
        print(f"[CONNECTION] Estado actualizado a: {status.value}")
    
    def reset(self):
        """Resetea el estado del gestor de conexión"""
        self.retry_count = 0
        self.last_error = None
        self.current_status = ConnectionStatus.OFFLINE_NO_DATA
        print("[CONNECTION] Gestor de conexión reseteado")
