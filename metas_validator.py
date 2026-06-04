"""
VALIDADOR DE DATOS DEL MÓDULO DE METAS
Valida la estructura y contenido de los datos descargados de Google Sheets
"""

from typing import Dict, List, Tuple
from metas_config import (
    ACTIVIDADES,
    COLUMNAS_INFOPLAZA_REQUERIDAS,
    MESES_PERIODO
)


class MetasDataValidator:
    """Valida la estructura y contenido de los datos de metas"""
    
    @staticmethod
    def validar_estructura_infoplaza(data: Dict) -> Tuple[bool, str]:
        """
        Verifica que los datos de infoplaza tengan todas las columnas esperadas
        
        Args:
            data: Diccionario con datos de una infoplaza
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if data is None:
            return False, "No hay datos de infoplaza (None)"

        # Verificar columnas básicas
        for col in COLUMNAS_INFOPLAZA_REQUERIDAS:
            if col not in data:
                return False, f"Falta columna requerida: '{col}'"
        
        # Verificar columnas de meses
        for mes in MESES_PERIODO:
            if mes not in data:
                return False, f"Falta columna de mes: '{mes}'"
        
        # Verificar columnas de actividades
        for actividad in ACTIVIDADES:
            if actividad.column_name not in data:
                return False, f"Falta columna de actividad: '{actividad.column_name}'"
        
        return True, ""
    
    @staticmethod
    def validar_valores_numericos(data: Dict, columnas: List[str]) -> Tuple[bool, List[str]]:
        """
        Verifica que los valores en las columnas especificadas sean numéricos válidos
        
        Args:
            data: Diccionario con datos
            columnas: Lista de nombres de columnas a validar
        
        Returns:
            tuple: (es_valido, lista_de_errores)
        """
        errores = []
        
        if data is None:
            return False, ["Datos nulos (None)"]
            
        for col in columnas:
            if col not in data:
                errores.append(f"Columna '{col}' no existe en los datos")
                continue
            
            valor = data.get(col, 0)
            try:
                float(valor or 0)
            except (ValueError, TypeError):
                errores.append(f"Columna '{col}': el valor '{valor}' no es numérico")
        
        return len(errores) == 0, errores
    
    @staticmethod
    def validar_valores_actividades(infoplaza_data: Dict) -> Tuple[bool, List[str]]:
        """
        Valida que todos los valores de actividades sean numéricos
        
        Args:
            infoplaza_data: Datos de una infoplaza
        
        Returns:
            tuple: (es_valido, lista_de_errores)
        """
        columnas_actividades = [act.column_name for act in ACTIVIDADES]
        return MetasDataValidator.validar_valores_numericos(
            infoplaza_data, 
            columnas_actividades
        )
    
    @staticmethod
    def validar_estructura_metas(metas_data: Dict) -> Tuple[bool, str]:
        """
        Verifica que la estructura de metas sea válida
        
        Args:
            metas_data: Diccionario con metas por actividad
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        # Verificar que haya metas para todas las actividades
        for actividad in ACTIVIDADES:
            if actividad.column_name not in metas_data:
                return False, f"Falta meta para actividad: '{actividad.column_name}'"
            
            meta_info = metas_data[actividad.column_name]
            
            # Verificar estructura de cada meta
            if not isinstance(meta_info, dict):
                return False, f"La meta de '{actividad.column_name}' no es un diccionario"
            
            # Verificar campos requeridos
            campos_requeridos = ['meta_mensual', 'meta_total']
            for campo in campos_requeridos:
                if campo not in meta_info:
                    return False, f"Falta campo '{campo}' en meta de '{actividad.column_name}'"
        
        return True, ""
    
    @staticmethod
    def validar_datos_completos(data: Dict) -> Tuple[bool, List[str]]:
        """
        Valida que los datos completos (infoplaza + metas) sean correctos
        
        Args:
            data: Diccionario completo con 'infoplaza' y 'metas'
        
        Returns:
            tuple: (es_valido, lista_de_errores)
        """
        errores = []
        
        # Verificar estructura principal
        if 'infoplaza' not in data:
            errores.append("Faltan datos de 'infoplaza'")
        if 'metas' not in data:
            errores.append("Faltan datos de 'metas'")
        
        if errores:
            return False, errores
        
        # Validar estructura de infoplaza
        es_valido, mensaje = MetasDataValidator.validar_estructura_infoplaza(data['infoplaza'])
        if not es_valido:
            errores.append(f"Error en estructura de infoplaza: {mensaje}")
        
        # Validar valores numéricos de actividades
        es_valido, lista_errores = MetasDataValidator.validar_valores_actividades(data['infoplaza'])
        if not es_valido:
            errores.extend(lista_errores)
        
        # Validar estructura de metas
        es_valido, mensaje = MetasDataValidator.validar_estructura_metas(data['metas'])
        if not es_valido:
            errores.append(f"Error en estructura de metas: {mensaje}")
        
        return len(errores) == 0, errores
    
    @staticmethod
    def sanitizar_valor_numerico(valor, default=0.0) -> float:
        """
        Convierte un valor a float de forma segura
        
        Args:
            valor: Valor a convertir
            default: Valor por defecto si la conversión falla
        
        Returns:
            float: Valor convertido o default
        """
        try:
            return float(valor or default)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def sanitizar_datos_infoplaza(data: Dict) -> Dict:
        """
        Sanitiza los datos de una infoplaza, convirtiendo valores a tipos correctos
        
        Args:
            data: Datos originales
        
        Returns:
            Dict: Datos sanitizados
        """
        data_sanitizada = data.copy()
        
        # Sanitizar valores de actividades
        for actividad in ACTIVIDADES:
            col = actividad.column_name
            if col in data_sanitizada:
                data_sanitizada[col] = MetasDataValidator.sanitizar_valor_numerico(
                    data_sanitizada[col]
                )
        
        return data_sanitizada
