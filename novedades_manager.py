import json
import os
import sys
from datetime import datetime

class NovedadesManager:
    """
    Gestiona el estado de lectura de las novedades.
    Mantiene un registro de qué noticias (IDs) han sido leídas por el usuario.
    """
    def __init__(self):
        self.history_file = self._get_history_file_path()
        self.read_history = self._load_history()

    def _get_history_file_path(self):
        """Obtiene la ruta segura para el archivo de historial en AppData"""
        app_data = os.getenv('APPDATA')
        ada_dir = os.path.join(app_data, 'ADA_Nova')
        if not os.path.exists(ada_dir):
            os.makedirs(ada_dir)
        return os.path.join(ada_dir, 'novedades_read_history.json')

    def _load_history(self):
        """Carga el historial de noticias leídas desde JSON"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except Exception as e:
                print(f"[NovedadesManager] Error cargando historial: {e}")
                return set()
        return set()

    def _save_history(self):
        """Guarda el historial en JSON"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                # Convertir set a list para JSON
                json.dump(list(self.read_history), f)
        except Exception as e:
            print(f"[NovedadesManager] Error guardando historial: {e}")

    def count_unread(self, novedades_data):
        """
        Calcula cuántas noticias activas no han sido leídas.
        Args:
            novedades_data (list): Lista de dicts con las novedades descargadas.
        Returns:
            int: Cantidad de noticias no leídas.
        """
        if not novedades_data:
            return 0
            
        count = 0
        for news in novedades_data:
            # Verificar si está activa y no ha vencido (lógica simple)
            is_active = str(news.get('ACTIVO', 'SI')).upper() == 'SI'
            news_id = str(news.get('ID', ''))
            
            if is_active and news_id and news_id not in self.read_history:
                count += 1
                
        return count

    def get_unread_high_priority(self, novedades_data):
        """Devuelve la primera noticia ALTA prioridad no leída (para popups)"""
        if not novedades_data:
            return None
            
        for news in novedades_data:
            is_active = str(news.get('ACTIVO', 'SI')).upper() == 'SI'
            priority = str(news.get('PRIORIDAD', 'NORMAL')).upper()
            news_id = str(news.get('ID', ''))
            
            if is_active and priority == 'ALTA' and news_id and news_id not in self.read_history:
                return news
        return None

    def get_unread_event(self, novedades_data):
        """Devuelve la primera noticia de tipo EVENTO no leída (para popup exclusivo)"""
        if not novedades_data:
            return None
            
        for news in novedades_data:
            is_active = str(news.get('ACTIVO', 'SI')).upper() == 'SI'
            tipo = str(news.get('TIPO', 'INFO')).upper()
            news_id = str(news.get('ID', ''))
            
            # Priorizamos EVENTO independientemente de su prioridad "ALTA/NORMAL"
            if is_active and tipo == 'EVENTO' and news_id and news_id not in self.read_history:
                return news
        return None

    def mark_as_read(self, news_id):
        """Marca una noticia como leída y guarda"""
        if news_id and news_id not in self.read_history:
            self.read_history.add(str(news_id))
            self._save_history()

    def mark_all_as_read(self, novedades_data):
        """Marca todas las noticias actuales como leídas"""
        changed = False
        for news in novedades_data:
            news_id = str(news.get('ID', ''))
            if news_id and news_id not in self.read_history:
                self.read_history.add(news_id)
                changed = True
        
        if changed:
            self._save_history()

    def clear_history(self):
        """Borra todo el historial de noticias leídas. Útil cuando se vacía el Sheets."""
        if self.read_history:
            self.read_history.clear()
            self._save_history()
            print("[NovedadesManager] Historial reseteado (Sheets vacío). IDs liberados.")
