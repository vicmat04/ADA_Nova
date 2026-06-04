"""
CALCULADORA DEL MÓDULO DE METAS
Centraliza todos los cálculos relacionados con el progreso de metas
"""

from typing import Dict, Tuple, List
from metas_config import (
    ACTIVIDADES,
    UMBRALES,
    ActividadConfig,
    obtener_actividades_normales
)
from metas_validator import MetasDataValidator


class MetasCalculator:
    """Centraliza todos los cálculos de metas y progreso"""
    
    def __init__(self, infoplaza_data: Dict, metas_data: Dict):
        """
        Inicializa el calculador de metas
        
        Args:
            infoplaza_data: Datos de la infoplaza (valores actuales)
            metas_data: Datos de metas (objetivos)
        """
        self.infoplaza_data = infoplaza_data
        self.metas_data = metas_data
        self.validator = MetasDataValidator()
    
    def calcular_progreso_actividad(self, actividad: ActividadConfig) -> Dict:
        """
        Calcula el progreso completo de una actividad específica
        usando un "Sensor de Ritmo" dinámico basado en el mes actual.
        """
        # 1. Obtener valor completado (sanitizado)
        completado = self.validator.sanitizar_valor_numerico(
            self.infoplaza_data.get(actividad.column_name, 0)
        )
        
        # 2. Obtener información de la meta
        meta_info = self.metas_data.get(actividad.column_name, {})
        meta_total = self.validator.sanitizar_valor_numerico(
            meta_info.get('meta_total', 1),
            default=1
        )
        meta_mensual_val = self.validator.sanitizar_valor_numerico(
            meta_info.get('meta_mensual', 0)
        )
        
        # 3. Calcular porcentaje de cumplimiento (Redondeado a 1 decimal para coincidencia visual)
        porcentaje = round((completado / meta_total * 100), 1) if meta_total > 0 else 0.0
        
        # 4. LÓGICA DEL SENSOR DE RITMO
        from metas_config import get_mes_actual
        mes_actual_num, _ = get_mes_actual() # 1-10
        # Ajuste "Mes Vencido": Se cuenta el ritmo hasta el último mes COMPLETADO
        meses_vencidos = max(0, mes_actual_num - 1)
        
        # Determinar umbrales dinámicos o estáticos
        if meta_mensual_val > 0:
            # Es una meta con ritmo mensual (ej: 10 al mes)
            # Progreso esperado al mes vencido
            progreso_esperado = (meses_vencidos * meta_mensual_val / meta_total) * 100
            progreso_esperado = min(100.0, progreso_esperado) # No exceder 100%
            
            # Umbrales basados en el ritmo (Verde: al día, Amarillo: 30% retraso)
            u_excelente = progreso_esperado
            u_bueno = progreso_esperado * 0.7
        else:
            # Meta puntual (Mesas, Días Especiales, Bonus) - Usar umbrales fijos
            u_excelente = UMBRALES.excelente # 80%
            u_bueno = UMBRALES.bueno # 50%
            
        # 5. Determinar colores y estado
        colores = self._determinar_colores(porcentaje, u_excelente, u_bueno)
        estado = self._determinar_estado(porcentaje, u_excelente, u_bueno)
        
        return {
            'completado': completado,
            'meta_total': meta_total,
            'meta_mensual': meta_info.get('meta_mensual', 'N/A'),
            'porcentaje': porcentaje,
            'color': colores,
            'estado': estado,
            'meta_esperada_ritmo': u_excelente if meta_mensual_val > 0 else None
        }
    
    def calcular_puntos_ganados(self, actividad: ActividadConfig) -> Tuple[float, float]:
        """
        Calcula cuántos puntos (del peso total) ha ganado una actividad.
        
        Args:
            actividad: Configuración de la actividad
            
        Returns:
            Tuple[float, float]: (puntos_ganados, peso_maximo)
        """
        progreso = self.calcular_progreso_actividad(actividad)
        
        # Obtener el peso (porcentaje) asignado a esta meta desde metas_data
        meta_info = self.metas_data.get(actividad.column_name, {})
        peso_str = str(meta_info.get('porcentaje', '0')).replace('%', '').strip()
        
        try:
            # El peso en la hoja es como "10%" o "10.0" (representa 10 puntos de 100)
            peso_maximo = float(peso_str) if peso_str else 0.0
        except ValueError:
            peso_maximo = 0.0
            
        # El cumplimiento de la actividad ya está en porcentaje (0-100, 120, etc.)
        cumplimiento = progreso['porcentaje'] # Ejemplo: 50.0 para 50%
        
        # LIMITAR AL 100% del cumplimiento para no exceder el peso máximo
        cumplimiento_limitado = min(100.0, cumplimiento)
        
        # Puntos ganados = cumplimiento (0-1) * peso
        puntos_ganados = (cumplimiento_limitado / 100.0) * peso_maximo
        
        return puntos_ganados, peso_maximo

    def calcular_progreso_global(self) -> float:
        """
        Calcula el progreso global de TODAS las actividades (incluyendo bonus)
        basándose en los pesos (porcentajes) definidos en Google Sheets.
        """
        total_puntos_ganados = 0.0
        for actividad in ACTIVIDADES:
            puntos, _ = self.calcular_puntos_ganados(actividad)
            total_puntos_ganados += puntos
        return total_puntos_ganados

    def calcular_estado_global(self) -> Dict:
        """
        Calcula el progreso global y determina su color basado en el ritmo esperado 
        (8% por mes para excelente, 5% para bueno).
        """
        # Obtener progreso real redondeado a 1 decimal para coincidir con lo que ve el usuario (8.0%)
        progreso_global = round(self.calcular_puntos_ganados_total(), 1)
        
        from metas_config import get_mes_actual
        mes_actual_num, _ = get_mes_actual()
        # Ajuste "Mes Vencido": Se cuenta el ritmo hasta el último mes COMPLETADO
        meses_vencidos = max(0, mes_actual_num - 1)
        
        # Umbrales dinámicos (Regla 8/5 por mes vencido)
        # Mes 1 vencido: 8 y 5
        # Mes 10 vencido: 80 y 50
        u_excelente = meses_vencidos * 8.0
        u_bueno = meses_vencidos * 5.0
        
        colores = self._determinar_colores(progreso_global, u_excelente, u_bueno)
        
        return {
            'progreso': progreso_global,
            'color': colores['color'],
            'bg': colores['bg'],
            'border': colores['border'],
            'u_excelente': u_excelente,
            'u_bueno': u_bueno,
            'estado': self._determinar_estado(progreso_global, u_excelente, u_bueno)
        }

    def calcular_puntos_ganados_total(self) -> float:
        """Helper para obtener los puntos ganados totales sumados"""
        total = 0.0
        for actividad in ACTIVIDADES:
            puntos, _ = self.calcular_puntos_ganados(actividad)
            total += puntos
        return total
    
    def calcular_redes_sociales_combinadas(self) -> Dict:
        """
        Calcula el progreso combinado de Redes Sociales (Publicaciones + Compartidas)
        
        Returns:
            Dict con:
                - publicaciones: Dict con progreso de publicaciones
                - compartidas: Dict con progreso de compartidas  
                - promedio: float - Promedio del porcentaje de ambas
                - total_completado: float - Total completado (suma)
                - total_meta: float - Total meta (suma)
                - estado: str - Estado basado en el promedio
                - color: Dict - Colores basados en el promedio
        """
        # Buscar las actividades de redes sociales
        publicaciones = None
        compartidas = None
        
        for actividad in ACTIVIDADES:
            if actividad.column_name == 'RS-Publicar':
                publicaciones = self.calcular_progreso_actividad(actividad)
                publicaciones['nombre'] = actividad.display_name
            elif actividad.column_name == 'RS-Compartir':
                compartidas = self.calcular_progreso_actividad(actividad)
                compartidas['nombre'] = actividad.display_name
        
        # Si no se encontró alguna, retornar valores por defecto
        if not publicaciones or not compartidas:
            return {
                'publicaciones': {'completado': 0, 'meta_total': 1, 'porcentaje': 0, 'nombre': 'Publiciciones'},
                'compartidas': {'completado': 0, 'meta_total': 1, 'porcentaje': 0, 'nombre': 'Compartidas'},
                'promedio': 0.0,
                'total_completado': 0.0,
                'total_meta': 2.0,
                'estado': 'necesita_atencion',
                'color': self._determinar_colores(0.0)
            }
        
        # Calcular promedio y totales
        promedio = (publicaciones['porcentaje'] + compartidas['porcentaje']) / 2.0
        total_completado = publicaciones['completado'] + compartidas['completado']
        total_meta = publicaciones['meta_total'] + compartidas['meta_total']
        
        return {
            'publicaciones': publicaciones,
            'compartidas': compartidas,
            'promedio': promedio,
            'total_completado': total_completado,
            'total_meta': total_meta,
            'estado': self._determinar_estado(promedio),
            'color': self._determinar_colores(promedio)
        }
    
    def calcular_actividades_completadas(self) -> Tuple[int, int]:
        """
        Calcula cuántas actividades están completadas al 100%
        
        Returns:
            tuple: (actividades_completadas, total_actividades)
        """
        actividades_normales = obtener_actividades_normales()
        completadas = 0
        
        for actividad in actividades_normales:
            progreso = self.calcular_progreso_actividad(actividad)
            if progreso['completado'] >= progreso['meta_total']:
                completadas += 1
        
        return completadas, len(actividades_normales)
    
    def calcular_meses_subidos(self) -> Tuple[int, int]:
        """
        Calcula cuántos meses se ha subido reporte de Bitácora
        
        Returns:
            tuple: (meses_subidos, total_meses_periodo)
        """
        from metas_config import MESES_PERIODO
        subidos = 0
        for mes in MESES_PERIODO:
            reporte_edo = self.obtener_estado_mes(mes)
            if reporte_edo['subio_reporte']:
                subidos += 1
        return subidos, len(MESES_PERIODO)

    def obtener_estado_mes(self, mes_nombre: str) -> Dict:
        """
        Determina el estado de un mes (si se subió reporte o no)
        
        Args:
            mes_nombre: Nombre del mes (ej: "Noviembre")
        
        Returns:
            Dict con:
                - subio_reporte: bool
                - simbolo: str (✓, ✗, —)
                - color_bg: str
                - color_text: str
        """
        reporte = self.infoplaza_data.get(mes_nombre, "No")
        
        # Normalizar valores posibles
        reporte_normalizado = str(reporte).strip().upper()
        subio_reporte = reporte_normalizado in ["SÍ", "SI", "YES", "Y"]
        
        if subio_reporte:
            return {
                'subio_reporte': True,
                'simbolo': '✓',
                'color_bg': '#d4edda',
                'color_text': '#28a745'
            }
        else:
            return {
                'subio_reporte': False,
                'simbolo': '✗',
                'color_bg': '#f8d7da',
                'color_text': '#dc3545'
            }
    
    def generar_resumen_completo(self) -> Dict:
        """
        Genera un resumen completo de todas las métricas
        
        Returns:
            Dict con todas las métricas calculadas
        """
        progreso_global = self.calcular_progreso_global()
        completadas, total = self.calcular_actividades_completadas()
        
        # Calcular progreso por cada actividad
        actividades_progreso = {}
        for actividad in ACTIVIDADES:
            actividades_progreso[actividad.column_name] = \
                self.calcular_progreso_actividad(actividad)
        
        return {
            'progreso_global': progreso_global,
            'actividades_completadas': completadas,
            'total_actividades': total,
            'actividades': actividades_progreso,
            'estado_general': self._determinar_estado(progreso_global)
        }
    
    @staticmethod
    def _determinar_colores(porcentaje: float, u_excelente: float = 80.0, u_bueno: float = 50.0) -> Dict[str, str]:
        """
        Determina los colores basándose en el porcentaje y los umbrales (dinámicos o fijos)
        """
        if porcentaje >= u_excelente:
            return {
                'color': '#28a745',      # Verde
                'bg': '#e8f5e9',
                'border': '#20c997'
            }
        elif porcentaje >= u_bueno:
            return {
                'color': '#ffc107',      # Amarillo
                'bg': '#fff8e1',
                'border': '#fd7e14'
            }
        else:
            return {
                'color': '#ef5350',      # Rojo más suave (antes #dc3545)
                'bg': '#ffebee',
                'border': '#e83e8c'
            }
    
    @staticmethod
    def _determinar_estado(porcentaje: float, u_excelente: float = 80.0, u_bueno: float = 50.0) -> str:
        """
        Determina el estado textual basándose en el porcentaje y umbrales
        """
        if porcentaje >= u_excelente:
            return 'excelente'
        elif porcentaje >= u_bueno:
            return 'bueno'
        else:
            return 'necesita_atencion'
    
    def validar_consistencia(self) -> Tuple[bool, List[str]]:
        """
        Valida que los datos sean consistentes
        
        Returns:
            tuple: (es_valido, lista_de_advertencias)
        """
        advertencias = []
        
        for actividad in ACTIVIDADES:
            progreso = self.calcular_progreso_actividad(actividad)
            
            # Advertir si el completado excede significativamente la meta
            if progreso['completado'] > progreso['meta_total'] * 1.5:
                advertencias.append(
                    f"{actividad.display_name}: El valor completado ({progreso['completado']:.0f}) "
                    f"excede significativamente la meta ({progreso['meta_total']:.0f})"
                )
            
            # Advertir si la meta es sospechosamente baja
            if progreso['meta_total'] < 1:
                advertencias.append(
                    f"{actividad.display_name}: La meta total es muy baja o cero"
                )
        
        return len(advertencias) == 0, advertencias
