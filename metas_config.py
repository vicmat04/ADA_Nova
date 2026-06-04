"""
CONFIGURACIÓN CENTRALIZADA DEL MÓDULO DE METAS
Todas las configuraciones de actividades, períodos y umbrales en un solo lugar
"""

from dataclasses import dataclass
from typing import List
from datetime import datetime


@dataclass
class ActividadConfig:
    """Configuración de una actividad de metas"""
    column_name: str          # Nombre de la columna en Google Sheets
    display_name: str         # Nombre para mostrar en la UI
    es_bonus: bool = False    # Si es bonus (no cuenta para progreso global)
    orden: int = 0            # Orden de presentación en la UI
    icon: str = "📋"          # Emoji para la tarjeta
    card_type: str = "standard"  # Tipo: standard, grouped, special_mesas, bonus
    group_id: str = ""        # ID de grupo para tarjetas agrupadas (ej: REDES)
    frequency: str = "monthly"  # Frecuencia: monthly, event, once
    events: str = ""          # Para frequency=event: lista separada por | (ej: Mesa 1|Mesa 2|Mesa 3)


@dataclass
class UmbralesColor:
    """Umbrales de porcentaje para colorización de progreso"""
    excelente: float = 80.0   # Verde: >= 80%
    bueno: float = 50.0       # Amarillo: >= 50%
    # Rojo: < 50%


# ============================================================================
# CONFIGURACIÓN DEL PERÍODO DE EVALUACIÓN
# ============================================================================

import json
import os
import sys

# ============================================================================
# CONFIGURACIÓN DEL PERÍODO DE EVALUACIÓN (DINÁMICA)
# ============================================================================

import shutil # Added for file migration

def get_config_path():
    """Retorna la ruta del archivo de caché de fechas en AppData/ADA_Nova"""
    # 1. Definir la ruta destino estándar (AppData/ADA_Nova)
    app_data = os.environ.get('APPDATA')
    if not app_data:
        app_data = os.path.expanduser("~")
    
    base_dir = os.path.join(app_data, "ADA_Nova")
    os.makedirs(base_dir, exist_ok=True)
    
    target_path = os.path.join(base_dir, 'metas_dates.json')
    
    # 2. Migración: Si existe en la carpeta vieja (junto al exe) y no en la nueva, moverlo
    try:
        if getattr(sys, 'frozen', False):
            old_dir = os.path.dirname(sys.executable)
        else:
            old_dir = os.path.dirname(os.path.abspath(__file__))
            
        old_path = os.path.join(old_dir, 'metas_dates.json')
        
        # Si existe el viejo y NO existe el nuevo, lo movemos para conservar configuración
        if os.path.exists(old_path) and not os.path.exists(target_path):
            shutil.move(old_path, target_path)
            print(f"[METAS_CONFIG] Migrado automáticamante: {old_path} -> {target_path}")
            
        # Si existen ambos (caso raro), podríamos borrar el viejo para limpiar
        elif os.path.exists(old_path) and os.path.exists(target_path):
             try:
                 os.remove(old_path) # Limpieza
             except: pass

    except Exception as e:
        print(f"[METAS_CONFIG] Warning en migración de archivo: {e}")

    return target_path

def load_fechas_config():
    """Carga la configuración de fechas desde el caché local o usa defaults"""
    # Valores por defecto (Hardcoded safe fallback)
    default_inicio = datetime(2025, 11, 1)
    default_fin = datetime(2026, 8, 31)
    
    json_path = get_config_path()
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                inicio_str = data.get('INICIO_PERIODO')
                fin_str = data.get('FIN_PERIODO')
                
                # Convertir strings (dd/mm/yyyy) a datetime
                inicio = datetime.strptime(inicio_str, "%d/%m/%Y")
                fin = datetime.strptime(fin_str, "%d/%m/%Y")
                
                return inicio, fin
        except Exception as e:
            print(f"[METAS_CONFIG] Error cargando cache de fechas: {e}")
            pass
            
    return default_inicio, default_fin

def parse_date_robust(date_str):
    """Intenta parsear una fecha con múltiples formatos"""
    formats = [
        "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", 
        "%Y/%m/%d", "%d.%m.%Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Formato de fecha no reconocido: {date_str}")

def save_fechas_config(inicio_str, fin_str):
    """Guarda las nuevas fechas en el caché local"""
    try:
        # Validar formateando antes de guardar
        inicio_dt = parse_date_robust(inicio_str)
        fin_dt = parse_date_robust(fin_str)
        
        # Guardar estandarizado (DD/MM/YYYY) para consistencia en JSON
        inicio_std = inicio_dt.strftime("%d/%m/%Y")
        fin_std = fin_dt.strftime("%d/%m/%Y")
        
        json_path = get_config_path()
        data = {
            "INICIO_PERIODO": inicio_std,
            "FIN_PERIODO": fin_std,
            "updated_at": datetime.now().isoformat()
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        
        # Actualizar variables en memoria
        global PERIODO_INICIO, PERIODO_FIN
        PERIODO_INICIO = inicio_dt
        PERIODO_FIN = fin_dt
        
        # Actualizar lista de meses IN-PLACE para mantener referencias en otros módulos
        nuevos_meses = generar_meses_periodo(PERIODO_INICIO, PERIODO_FIN)
        MESES_PERIODO.clear()
        MESES_PERIODO.extend(nuevos_meses)
        
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"!!! CRITICAL ERROR [METAS_CONFIG] !!! Error guardando fechas '{inicio_str}' - '{fin_str}': {e}")
        return False

# Inicialización de variables globales
PERIODO_INICIO, PERIODO_FIN = load_fechas_config()

def get_fechas_periodo():
    """Retorna las fechas de inicio y fin actuales"""
    return PERIODO_INICIO, PERIODO_FIN

def generar_meses_periodo(fecha_inicio, fecha_fin):
    """Genera la lista de nombres de meses entre las dos fechas"""
    nombres_meses = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    
    lista = []
    
    # Asegurar fechas limpias (día 1) para iterar
    current = fecha_inicio.replace(day=1)
    end = fecha_fin.replace(day=1)
    
    # Bucle de seguridad (max 24 meses para evitar loops infinitos)
    limit = 0
    while current <= end and limit < 24:
        lista.append(nombres_meses[current.month])
        
        # Sumar 1 mes manual (evitar deps)
        y = current.year
        m = current.month + 1
        if m > 12:
            m = 1
            y += 1
        current = current.replace(year=y, month=m, day=1)
        limit += 1
        
    return lista

MESES_PERIODO = generar_meses_periodo(PERIODO_INICIO, PERIODO_FIN)


# ============================================================================
# CONFIGURACIÓN DE ACTIVIDADES
# ============================================================================

ACTIVIDADES = [
    ActividadConfig(
        column_name='P.V. USUARIO',  # Normalizado automáticamente desde "P.V.\n USUARIO"
        display_name='Plataformas Virtuales - Usuarios',
        orden=1
    ),
    ActividadConfig(
        column_name='P.V. DINAMIZADOR',  # Normalizado automáticamente desde "P.V.\n DINAMIZADOR"
        display_name='Plataformas Virtuales - Dinamizador',
        orden=2
    ),
    ActividadConfig(
        column_name='VIRTUALES',
        display_name='Capacitaciones Internas Virtuales',
        orden=3
    ),
    ActividadConfig(
        column_name='Otras CAPACIT.',  # Normalizado automáticamente desde "Otras\n CAPACIT."
        display_name='Capacitaciones Usuarios',
        orden=4
    ),
    ActividadConfig(
        column_name='Otras Actividades',
        display_name='Otras Actividades Usuarios',
        orden=5
    ),
    ActividadConfig(
        column_name='RS-Publicar',
        display_name='Redes Sociales - Publicaciones',
        orden=6
    ),
    ActividadConfig(
        column_name='RS-Compartir',
        display_name='Redes Sociales - Compartir',
        orden=7
    ),
    ActividadConfig(
        column_name='Mesas',
        display_name='Mesas de Transformación',
        orden=8
    ),
    ActividadConfig(
        column_name='Buenas Acciones',
        display_name='Día de las Buenas Acciones',
        orden=9
    ),
    ActividadConfig(
        column_name='DÍA DEL INTERNET',
        display_name='Día del Internet',
        orden=10
    ),
    ActividadConfig(
        column_name='BONUS',
        display_name='Especialidad (Bonus) ⭐',
        es_bonus=True,
        orden=11
    ),
]


# ============================================================================
# UMBRALES DE COLORIZACIÓN
# ============================================================================

UMBRALES = UmbralesColor()


# ============================================================================
# COLUMNAS REQUERIDAS EN GOOGLE SHEETS
# ============================================================================

COLUMNAS_INFOPLAZA_REQUERIDAS = [
    '# Info',
    'Nombre de la Infoplaza',
    'Regional',
    'Provincia / Comarca'
]

COLUMNAS_METAS_REQUERIDAS = [
    'Meta',
    'Total por mes',
    'Total',
    'Porcentaje'
]


# ============================================================================
# FUNCIONES HELPER
# ============================================================================

def obtener_actividades_normales() -> List[ActividadConfig]:
    """Retorna solo las actividades que NO son bonus"""
    return [act for act in ACTIVIDADES if not act.es_bonus]


def obtener_actividades_bonus() -> List[ActividadConfig]:
    """Retorna solo las actividades bonus"""
    return [act for act in ACTIVIDADES if act.es_bonus]


def obtener_actividad_por_columna(column_name: str) -> ActividadConfig:
    """Busca una actividad por su nombre de columna"""
    for act in ACTIVIDADES:
        if act.column_name == column_name:
            return act
    return None


def obtener_actividad_por_display_name(display_name: str) -> ActividadConfig:
    """
    Busca una actividad por su nombre de display
    
    Args:
        display_name: Nombre descriptivo (ej: "Plataformas Virtuales - Usuarios")
    
    Returns:
        ActividadConfig o None si no se encuentra
    """
    for act in ACTIVIDADES:
        if act.display_name == display_name:
            return act
    return None


def crear_mapeo_display_a_columna() -> dict:
    """
    Crea un diccionario que mapea display_name -> column_name
    Incluye versiones normalizadas sin emojis para mayor robustez
    
    Returns:
        Dict[str, str]: Mapeo de nombres descriptivos a nombres de columna
        
    Ejemplo:
        {
            "Plataformas Virtuales - Usuarios": "P.V. USUARIO",
            "Especialidad (Bonus) ⭐": "BONUS",
            "Especialidad (Bonus)": "BONUS",  # Sin emoji también
            ...
        }
    """
    mapeo = {}
    
    for act in ACTIVIDADES:
        # Mapeo principal con display_name completo
        mapeo[act.display_name] = act.column_name
        
        # Mapeo adicional sin emojis (para robustez)
        # Eliminar caracteres especiales y emojis
        display_sin_emoji = act.display_name.replace('⭐', '').replace('✨', '').strip()
        if display_sin_emoji != act.display_name:
            mapeo[display_sin_emoji] = act.column_name
    
    return mapeo


def get_mes_actual() -> tuple:
    """
    Determina el mes actual basado en el período dinámico.
    Retorna (indice_1_based, nombre_mes)
    """
    fecha_actual = datetime.now()
    
    # Si estamos antes del inicio
    if fecha_actual < PERIODO_INICIO:
        return 0, "Antes del período"
    
    # Calcular diferencia en meses desde el inicio
    # +1 para que el mes de inicio sea el 1
    meses_diff = (fecha_actual.year - PERIODO_INICIO.year) * 12 + \
                 (fecha_actual.month - PERIODO_INICIO.month) + 1
    
    total_meses = len(MESES_PERIODO)
    
    # Si ya pasó el periodo, mantenemos el último mes ("congelado")
    if meses_diff > total_meses:
        # Esto cumple con "mantener cálculo" hasta nueva orden
        return total_meses, MESES_PERIODO[-1] if MESES_PERIODO else "Fin"
    
    if 1 <= meses_diff <= total_meses:
        return meses_diff, MESES_PERIODO[meses_diff - 1]
    
    return 0, "Fuera de período"


def get_year_for_month(mes_num: int) -> int:
    """
    Retorna el año correspondiente al n-ésimo mes del periodo.
    Totalmente dinámico.
    """
    if mes_num < 1: 
        return PERIODO_INICIO.year
        
    # Calcular offset desde el inicio (mes_num 1 -> offset 0)
    offset_meses = mes_num - 1
    
    # Sumar meses a la fecha de inicio
    # (month - 1) para 0-based index, luego sumar offset, luego floor div 12
    years_add = (PERIODO_INICIO.month - 1 + offset_meses) // 12
    
    return PERIODO_INICIO.year + years_add
