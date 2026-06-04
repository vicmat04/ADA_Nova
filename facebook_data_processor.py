import pandas as pd

class MissingColumnError(Exception):
    """Excepción lanzada cuando faltan columnas vitales en el CSV."""
    pass

class FacebookDataProcessor:
    def __init__(self):
        # Diccionario de alias bilingües para soportar CSV en inglés y español
        self.column_aliases = {
            'fecha_pub': ['Hora de publicación', 'Publish time'],
            'nombre_pagina': ['Nombre de la página', 'Page name'],
            'es_compartida': ['Es una publicación compartida', 'Is share'],
            'es_cruzada': ['Es una publicación cruzada', 'Is crosspost'] # Fallback por si acaso
        }

    def _find_column(self, df, alias_key):
        """Busca una columna en el DataFrame basándose en la lista de alias permitidos."""
        for name in self.column_aliases[alias_key]:
            if name in df.columns:
                return name
        return None

    def analizar_csv(self, ruta_csv):
        """
        Lee el CSV, normaliza las columnas usando el diccionario bilingüe
        y calcula las métricas de originales vs compartidas.
        """
        try:
            df = pd.read_csv(ruta_csv)
        except Exception as e:
            raise Exception(f"No se pudo leer el archivo CSV. Código de error: {e}")

        if len(df) == 0:
            raise Exception("El archivo CSV está vacío.")

        # Buscar las columnas necesarias por nombre
        col_fecha = self._find_column(df, 'fecha_pub')
        col_nombre = self._find_column(df, 'nombre_pagina')

        # --- DETERMINACIÓN DE COLUMNA COMPARTIDA (K = Índice 10) ---
        # Forzamos el uso del índice 10 (K) si el reporte tiene la estructura estándar (>= 11 columnas).
        if df.shape[1] >= 11:
            col_compartida = df.columns[10]
        else:
            # Fallback por nombre solo para archivos con estructura no estándar
            col_compartida = self._find_column(df, 'es_compartida')
            if not col_compartida:
                col_compartida = self._find_column(df, 'es_cruzada')

        # --- FALLBACK POR POSICIÓN PARA OTROS CAMPOS (C=2, G=6) ---
        if df.shape[1] >= 11:
            if not col_nombre: col_nombre = df.columns[2]
            if not col_fecha: col_fecha = df.columns[6]

        # Validar columnas vitales
        faltantes = []
        if not col_fecha: faltantes.append(f"Fecha de publicación (e.g. '{self.column_aliases['fecha_pub'][0]}')")
        if not col_nombre: faltantes.append(f"Nombre de página (e.g. '{self.column_aliases['nombre_pagina'][0]}')")
        if not col_compartida: faltantes.append(f"Indicador compartida (e.g. '{self.column_aliases['es_compartida'][0]}')")

        if faltantes:
            raise MissingColumnError(f"Formato no reconocido. Faltan las siguientes columnas: {', '.join(faltantes)}")

        # --- Procesamiento Seguro ---
        # 1. Convertir Fechas
        df['Fecha_Parseada'] = pd.to_datetime(df[col_fecha], errors='coerce')
        
        # Eliminar filas con fechas inválidas (NaT) para no contar basura
        df = df.dropna(subset=['Fecha_Parseada'])
        if len(df) == 0:
            raise Exception("No se encontraron fechas válidas en el archivo.")

        # Mes y año
        meses_es = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
            5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
            9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }
        df['MesNum'] = df['Fecha_Parseada'].dt.month
        df['Año'] = df['Fecha_Parseada'].dt.year
        df['Mes'] = df['MesNum'].map(meses_es)

        # 2. Nombre e InfoPlaza
        first_page_name = str(df[col_nombre].iloc[0])
        parts = first_page_name.split('-')
        nombre_infoplaza = parts[0].strip()
        numero_infoplaza = parts[1].strip() if len(parts) > 1 else ""

        # 3. Determinar Propias (Originales) vs Compartidas
        df['Col_Boolean_Compartida'] = pd.to_numeric(df[col_compartida], errors='coerce').fillna(0)
        
        total = len(df)
        # Si el valor de "Es share"/"Es compartida" es 1, fue compartida.
        compartidas = len(df[df['Col_Boolean_Compartida'] == 1])
        # Si es 0, es propia/original.
        originales = len(df[df['Col_Boolean_Compartida'] == 0])

        mes_str = df['Mes'].iloc[0]
        año_str = int(df['Año'].iloc[0])

        return {
            'nombre_infoplaza': nombre_infoplaza,
            'numero_infoplaza': numero_infoplaza,
            'total': total,
            'mes': mes_str,
            'año': año_str,
            'originales': originales,
            'compartidas': compartidas
        }
