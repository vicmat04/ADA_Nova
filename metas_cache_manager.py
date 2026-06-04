"""
Gestor de Caché Persistente para Módulo de Metas
================================================

Este módulo maneja el almacenamiento persistente de datos de Google Sheets
en disco local para permitir funcionalidad offline.

Características:
- Almacenamiento en formato JSON
- Validación de antigüedad (24 horas por defecto)
- Ubicación en AppData local del usuario
- Manejo robusto de errores
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple


class MetasCacheManager:
    """Gestiona el caché persistente de datos de metas en disco local"""
    
    CACHE_VERSION = "1.0"
    DEFAULT_TTL_HOURS = 24  # Tiempo de vida del caché en horas
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Inicializa el gestor de caché
        
        Args:
            cache_dir: Directorio para almacenar caché. Si es None, usa AppData local
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # Usar AppData/Local/ADA/cache/
            appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            self.cache_dir = Path(appdata) / 'ADA' / 'cache'
        
        # Crear directorio si no existe
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache_file = self.cache_dir / 'metas_cache.json'
        self.ttl_hours = self.DEFAULT_TTL_HOURS
    
    def _serialize_data(self, data: Dict) -> Dict:
        """
        Serializa datos, convirtiendo objetos no-JSON a diccionarios
        
        Args:
            data: Datos a serializar
        
        Returns:
            Dict: Datos serializados
        """
        serialized = {}
        
        for key, value in data.items():
            if key == 'actividades_config' and value is not None:
                # Convertir lista de ActividadConfig a lista de dicts
                serialized[key] = [self._actividad_to_dict(act) for act in value]
            elif isinstance(value, list):
                # Serializar listas recursivamente
                serialized[key] = [self._serialize_item(item) for item in value]
            elif isinstance(value, dict):
                # Serializar dicts recursivamente
                serialized[key] = self._serialize_data(value)
            else:
                serialized[key] = value
        
        return serialized
    
    def _serialize_item(self, item):
        """Serializa un item individual"""
        if hasattr(item, '__dict__'):
            # Objeto con __dict__ -> convertir a dict
            return {k: v for k, v in item.__dict__.items() if not k.startswith('_')}
        elif isinstance(item, dict):
            return self._serialize_data(item)
        elif isinstance(item, list):
            return [self._serialize_item(i) for i in item]
        else:
            return item
    
    def _actividad_to_dict(self, actividad) -> Dict:
        """Convierte ActividadConfig a dict"""
        if hasattr(actividad, '__dict__'):
            return {k: v for k, v in actividad.__dict__.items() if not k.startswith('_')}
        return actividad
    
    def _deserialize_data(self, data: Dict) -> Dict:
        """
        Deserializa datos, reconstruyendo objetos ActividadConfig
        
        Args:
            data: Datos deserializados del JSON
        
        Returns:
            Dict: Datos con objetos reconstruidos
        """
        deserialized = data.copy()
        
        # Reconstruir actividades_config si existe
        if 'actividades_config' in deserialized and deserialized['actividades_config'] is not None:
            try:
                from metas_config import ActividadConfig
                deserialized['actividades_config'] = [
                    ActividadConfig(**act_dict) for act_dict in deserialized['actividades_config']
                ]
            except Exception as e:
                print(f"[CACHE] Error reconstruyendo ActividadConfig: {e}")
                deserialized['actividades_config'] = None
        
        return deserialized
    
    def save_to_cache(self, data: Dict, infoplaza_id: Optional[str] = None) -> bool:
        """
        Guarda datos en el caché con timestamp actual
        
        Args:
            data: Datos a guardar (dict con infoplaza, metas, etc.)
            infoplaza_id: ID de la infoplaza (opcional, para logging)
        
        Returns:
            bool: True si se guardó correctamente, False en caso de error
        """
        try:
            # Serializar datos (convertir objetos a dicts)
            serialized_data = self._serialize_data(data)
            
            cache_data = {
                'version': self.CACHE_VERSION,
                'timestamp': datetime.now().isoformat(),
                'infoplaza_id': infoplaza_id,
                'data': serialized_data
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            print(f"[CACHE] Datos guardados exitosamente en: {self.cache_file}")
            return True
            
        except Exception as e:
            print(f"[CACHE] Error al guardar caché: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_from_cache(self) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Carga datos desde el caché si es válido
        
        Returns:
            Tuple[Optional[Dict], Optional[str]]: (datos, mensaje_estado)
            - datos: Datos cargados o None si no hay caché válido
            - mensaje_estado: Mensaje descriptivo del estado del caché
        """
        if not self.cache_file.exists():
            return None, "No existe caché"
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Validar versión
            if cache_data.get('version') != self.CACHE_VERSION:
                return None, f"Versión de caché incompatible: {cache_data.get('version')}"
            
            # Validar antigüedad
            timestamp_str = cache_data.get('timestamp')
            if not timestamp_str:
                return None, "Caché sin timestamp"
            
            timestamp = datetime.fromisoformat(timestamp_str)
            age = datetime.now() - timestamp
            
            # Verificar si ha expirado
            if age > timedelta(hours=self.ttl_hours):
                age_hours = age.total_seconds() / 3600
                return None, f"Caché expirado ({age_hours:.1f} horas de antigüedad)"
            
            # Caché válido - deserializar
            data = cache_data.get('data')
            data = self._deserialize_data(data)  # Reconstruir objetos
            
            age_minutes = age.total_seconds() / 60
            
            if age_minutes < 60:
                mensaje = f"Caché válido ({age_minutes:.0f} minutos de antigüedad)"
            else:
                age_hours = age.total_seconds() / 3600
                mensaje = f"Caché válido ({age_hours:.1f} horas de antigüedad)"
            
            print(f"[CACHE] {mensaje}")
            return data, mensaje
            
        except json.JSONDecodeError as e:
            return None, f"Caché corrupto: {e}"
        except Exception as e:
            return None, f"Error al cargar caché: {e}"
    
    def is_cache_valid(self) -> bool:
        """
        Verifica si el caché existe y es válido (no ha expirado)
        
        Returns:
            bool: True si el caché es válido, False en caso contrario
        """
        data, _ = self.load_from_cache()
        return data is not None
    
    def get_cache_age(self) -> Optional[timedelta]:
        """
        Obtiene la antigüedad del caché
        
        Returns:
            Optional[timedelta]: Antigüedad del caché o None si no existe
        """
        if not self.cache_file.exists():
            return None
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            timestamp_str = cache_data.get('timestamp')
            if not timestamp_str:
                return None
            
            timestamp = datetime.fromisoformat(timestamp_str)
            return datetime.now() - timestamp
            
        except Exception:
            return None
    
    def get_cache_info(self) -> Dict:
        """
        Obtiene información detallada sobre el caché
        
        Returns:
            Dict: Información del caché (existe, válido, antigüedad, etc.)
        """
        info = {
            'exists': self.cache_file.exists(),
            'path': str(self.cache_file),
            'valid': False,
            'age': None,
            'age_hours': None,
            'timestamp': None,
            'size_bytes': None
        }
        
        if not info['exists']:
            return info
        
        # Obtener tamaño
        info['size_bytes'] = self.cache_file.stat().st_size
        
        # Obtener antigüedad
        age = self.get_cache_age()
        if age:
            info['age'] = str(age)
            info['age_hours'] = age.total_seconds() / 3600
            info['valid'] = age <= timedelta(hours=self.ttl_hours)
        
        # Obtener timestamp formateado para UI
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                timestamp_str = cache_data.get('timestamp')
                info['timestamp'] = timestamp_str
                
                # Formatear para tooltip
                if timestamp_str:
                    try:
                        dt = datetime.fromisoformat(timestamp_str)
                        info['last_updated_formatted'] = dt.strftime('%d/%m/%Y %H:%M')
                    except:
                        info['last_updated_formatted'] = 'Fecha desconocida'
        except Exception:
            pass
        
        return info
    
    def clear_cache(self) -> bool:
        """
        Elimina el archivo de caché
        
        Returns:
            bool: True si se eliminó correctamente, False en caso de error
        """
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                print(f"[CACHE] Caché eliminado: {self.cache_file}")
                return True
            return False
        except Exception as e:
            print(f"[CACHE] Error al eliminar caché: {e}")
            return False
    
    def set_ttl_hours(self, hours: int):
        """
        Establece el tiempo de vida del caché en horas
        
        Args:
            hours: Número de horas antes de que expire el caché
        """
        if hours > 0:
            self.ttl_hours = hours
            print(f"[CACHE] TTL actualizado a {hours} horas")
