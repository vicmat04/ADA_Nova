"""
Módulo de Gestión y Sincronización Supabase para Informe Cuatrimestral
======================================================================
Maneja la conexión REST con Supabase utilizando el Service Role Key.
Proporciona:
1. Formateo automático a Mayúscula Inicial para nombres y textos.
2. Consulta y actualización de la tabla 'infoplazas' en Supabase.
3. Sincronización bidireccional (subida y descarga tras formateo) de informes cuatrimestrales.
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Las credenciales de Supabase ahora se cargan desde supabase_credentials.json
# para evitar exponer la clave service_role en el código fuente.


def _normalize_text(val: Optional[str]) -> str:
    """Normaliza texto removiendo tildes y pasando a mayúsculas para comparaciones insensibles a acentos."""
    if not val:
        return ""
    import unicodedata
    s = unicodedata.normalize('NFKD', str(val))
    return "".join(c for c in s if not unicodedata.combining(c)).strip().upper()


def format_title_case(val: Optional[str]) -> str:
    """
    Convierte una cadena a formato Mayúscula Inicial (Capitalizada por palabra),
    respetando espacios y valores nulos/vacíos.
    Ej: "ludovina prado" -> "Ludovina Prado"
        "taller de chatgpt" -> "Taller De Chatgpt"
    """
    if not val:
        return ""
    val_str = str(val).strip()
    if not val_str:
        return ""
    # Capitalizar cada palabra respetando palabras compuestas
    return " ".join([word.capitalize() for word in val_str.split()])


class CuatrimestralSupabaseManager:
    """Gestor de API REST de Supabase para el Informe Cuatrimestral."""
    
    def __init__(self, url: str = None, key: str = None):
        import os, sys
        # Soporte correcto para PyInstaller: __file__ no funciona en .exe frozen
        if getattr(sys, 'frozen', False):
            _base = sys._MEIPASS
        else:
            _base = os.path.dirname(os.path.abspath(__file__))
        cred_path = os.path.join(_base, 'supabase_credentials.json')
        
        if not url or not key:
            try:
                with open(cred_path, 'r', encoding='utf-8') as f:
                    creds = json.load(f)
                    url = url or creds.get('SUPABASE_URL', '')
                    key = key or creds.get('SUPABASE_KEY', '')
            except Exception as e:
                print(f"[SUPABASE] Error leyendo {cred_path}: {e}")
                
        self.url = (url or "").rstrip('/')
        self.key = key or ""
        self._infoplazas_cache: Optional[List[Dict[str, Any]]] = None
        
    def _headers(self, prefer: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _request(self, endpoint: str, method: str = "GET", data: Optional[Any] = None, prefer: Optional[str] = None) -> Tuple[Optional[Any], Optional[str]]:
        """Realiza una petición HTTP a la API REST de Supabase."""
        full_url = f"{self.url}/rest/v1/{endpoint}"
        body = json.dumps(data).encode('utf-8') if data is not None else None
        
        try:
            req = urllib.request.Request(full_url, data=body, headers=self._headers(prefer), method=method)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8')
                if raw:
                    return json.loads(raw), None
                return [], None
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8') if e.fp else str(e)
            print(f"[SUPABASE_ERROR] HTTP {e.code} en {endpoint}: {err_body}")
            return None, f"HTTP {e.code}: {err_body}"
        except Exception as e:
            print(f"[SUPABASE_ERROR] Excepción en {endpoint}: {e}")
            return None, str(e)

    # =========================================================================
    # TABLA PRINCIPAL: INFOPLAZAS
    # =========================================================================

    def get_infoplaza(self, numero: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Obtiene la información oficial de una Infoplaza desde Supabase."""
        endpoint = f"infoplazas?numero=eq.{numero}&select=*"
        res, err = self._request(endpoint, method="GET")
        if err:
            return None, err
        if res and isinstance(res, list) and len(res) > 0:
            return res[0], None
        return None, f"Infoplaza #{numero} no encontrada en Supabase"

    def invalidate_infoplazas_cache(self):
        """Invalida la caché en memoria del catálogo de infoplazas."""
        self._infoplazas_cache = None

    def get_infoplazas_by_regional(self, regional: str = "", force_refresh: bool = False) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Obtiene la lista de Infoplazas para una regional específica (o todas si regional='').
        Utiliza caché en memoria (RAM) para responder en 0 ms en cambios de pestaña o filtros.
        Aplica comparación normalizada e insensible a tildes (ej: Chiriqui == Chiriquí).
        """
        # 1. Si no hay caché o se fuerza recarga, descargamos todo el catálogo maestro una sola vez
        if self._infoplazas_cache is None or force_refresh:
            endpoint = "infoplazas?select=*&order=numero.asc"
            res, err = self._request(endpoint, method="GET")
            if err:
                if self._infoplazas_cache is not None:
                    res = self._infoplazas_cache
                else:
                    return [], err
            else:
                if isinstance(res, list):
                    self._infoplazas_cache = res
                else:
                    self._infoplazas_cache = []

        # 2. Filtrado instantáneo en memoria (0 ms, 0 llamadas de red)
        all_data = self._infoplazas_cache or []
        if regional and regional.strip():
            reg_clean = _normalize_text(regional)
            # Manejo especial para Azuero / Los Santos / Herrera
            if reg_clean == "AZUERO":
                filtered = [
                    ip for ip in all_data
                    if _normalize_text(ip.get('regional')) in ("LOS SANTOS", "HERRERA", "AZUERO")
                    or _normalize_text(ip.get('provincia')) in ("LOS SANTOS", "HERRERA")
                ]
            else:
                filtered = [
                    ip for ip in all_data 
                    if _normalize_text(ip.get('regional')) == reg_clean
                    or _normalize_text(ip.get('provincia')) == reg_clean
                ]
                # Fallback por contención si no hubo match exacto
                if not filtered:
                    filtered = [
                        ip for ip in all_data
                        if reg_clean in _normalize_text(ip.get('regional'))
                        or reg_clean in _normalize_text(ip.get('provincia'))
                    ]
            return list(filtered), None
        return list(all_data), None

    def update_infoplaza_master(
        self,
        numero: int,
        provincia: str,
        distrito: str,
        corregimiento: str
    ) -> Tuple[bool, Optional[str]]:
        """Actualiza provincia, distrito y corregimiento de una Infoplaza en Supabase (Catálogo Maestro)."""
        endpoint = f"infoplazas?numero=eq.{numero}"
        data = {
            "provincia": format_title_case(provincia),
            "distrito": format_title_case(distrito),
            "corregimiento": format_title_case(corregimiento)
        }
        res, err = self._request(endpoint, method="PATCH", data=data)
        if err:
            return False, err
        if self._infoplazas_cache:
            for ip in self._infoplazas_cache:
                if ip.get('numero') == numero:
                    ip.update(data)
                    break
        return True, None

    def update_infoplaza_config(
        self,
        numero: int,
        cant_computadoras: int,
        asociado_nombre: str = "",
        asociado_cedula: str = "",
        dinamizador_nombre: str = "",
        dinamizador_cedula: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """Actualiza la configuración centralizada de la Infoplaza en Supabase."""
        endpoint = f"infoplazas?numero=eq.{numero}"
        data = {
            "cant_computadoras": int(cant_computadoras),
            "asociado_nombre": format_title_case(asociado_nombre),
            "asociado_cedula": asociado_cedula.strip().upper(),
            "dinamizador_nombre": format_title_case(dinamizador_nombre),
            "dinamizador_cedula": dinamizador_cedula.strip().upper()
        }
        res, err = self._request(endpoint, method="PATCH", data=data, prefer="return=minimal")
        if err:
            return False, err
        if self._infoplazas_cache:
            for ip in self._infoplazas_cache:
                if ip.get('numero') == numero:
                    ip.update(data)
                    break
        return True, None

    # =========================================================================
    # INFORME CUATRIMESTRAL: SUBIDA Y SINCRONIZACIÓN (UPSERT)
    # =========================================================================

    def push_informe_full(
        self,
        infoplaza_numero: int,
        anio: int,
        cuatrimestre: int,
        header_data: Dict[str, Any],
        capacitaciones: List[Dict[str, Any]],
        servicios: List[Dict[str, Any]],
        otras_actividades: List[Dict[str, Any]]
    ) -> Tuple[bool, Optional[str]]:
        """
        Sincroniza/sube un informe cuatrimestral completo a Supabase.
        Aplica formateo de Mayúscula Inicial en todos los nombres y textos.
        """
        # 1. Upsert Header
        header_payload = {
            "infoplaza_numero": int(infoplaza_numero),
            "anio": int(anio),
            "cuatrimestre": int(cuatrimestre),
            "cant_computadoras": int(header_data.get('cant_computadoras', 6)),
            "asociado_nombre": format_title_case(header_data.get('asociado_nombre', '')),
            "asociado_cedula": str(header_data.get('asociado_cedula', '')).strip().upper(),
            "dinamizador_nombre": format_title_case(header_data.get('dinamizador_nombre', '')),
            "dinamizador_cedula": str(header_data.get('dinamizador_cedula', '')).strip().upper(),
            "observaciones_generales": format_title_case(header_data.get('observaciones_generales', ''))
        }

        # 1. Upsert Header (Atómico)
        ep_upsert = "informe_cuatrimestral_header?on_conflict=infoplaza_numero,anio,cuatrimestre"
        res_upsert, err_upsert = self._request(
            ep_upsert, 
            method="POST", 
            data=header_payload, 
            prefer="return=representation,resolution=merge-duplicates"
        )
        
        if err_upsert:
            return False, f"Error upsert en cabecera de Supabase: {err_upsert}"
            
        informe_id = None
        if res_upsert and isinstance(res_upsert, list) and len(res_upsert) > 0:
            informe_id = res_upsert[0].get('id')

        # Actualizar la configuración de la Infoplaza también
        self.update_infoplaza_config(
            numero=infoplaza_numero,
            cant_computadoras=header_payload['cant_computadoras'],
            asociado_nombre=header_payload['asociado_nombre'],
            asociado_cedula=header_payload['asociado_cedula'],
            dinamizador_nombre=header_payload['dinamizador_nombre'],
            dinamizador_cedula=header_payload['dinamizador_cedula']
        )

        if not informe_id:
            return False, "No se pudo obtener la ID de la cabecera en Supabase"

        # 2. Borrar e insertar Capacitaciones del cuatrimestre
        self._request(f"informe_capacitaciones?infoplaza_numero=eq.{infoplaza_numero}&anio=eq.{anio}&cuatrimestre=eq.{cuatrimestre}", method="DELETE")
        if capacitaciones:
            cap_rows = []
            for idx, item in enumerate(capacitaciones, start=1):
                cap_rows.append({
                    "informe_id": informe_id,
                    "infoplaza_numero": int(infoplaza_numero),
                    "anio": int(anio),
                    "cuatrimestre": int(cuatrimestre),
                    "mes": format_title_case(item.get('mes', '')),
                    "categoria": format_title_case(item.get('categoria', '')),
                    "tema": format_title_case(item.get('tema', '')),
                    "participantes": int(item.get('participantes', 0)),
                    "horas": float(item.get('horas', 0)),
                    "observaciones": format_title_case(item.get('observaciones', '')),
                    "orden": idx
                })
            self._request("informe_capacitaciones", method="POST", data=cap_rows, prefer="return=minimal")

        # 3. Borrar e insertar Servicios
        self._request(f"informe_servicios?infoplaza_numero=eq.{infoplaza_numero}&anio=eq.{anio}&cuatrimestre=eq.{cuatrimestre}", method="DELETE")
        if servicios:
            srv_rows = []
            for item in servicios:
                srv_rows.append({
                    "informe_id": informe_id,
                    "infoplaza_numero": int(infoplaza_numero),
                    "anio": int(anio),
                    "cuatrimestre": int(cuatrimestre),
                    "servicio_nombre": format_title_case(item.get('servicio_nombre', '')),
                    "ofrecido": bool(item.get('ofrecido', True)),
                    "es_personalizado": bool(item.get('es_personalizado', False)),
                    "observaciones": format_title_case(item.get('observaciones', ''))
                })
            self._request("informe_servicios", method="POST", data=srv_rows, prefer="return=minimal")

        # 4. Borrar e insertar Otras Actividades
        self._request(f"informe_otras_actividades?infoplaza_numero=eq.{infoplaza_numero}&anio=eq.{anio}&cuatrimestre=eq.{cuatrimestre}", method="DELETE")
        if otras_actividades:
            act_rows = []
            for idx, item in enumerate(otras_actividades, start=1):
                act_rows.append({
                    "informe_id": informe_id,
                    "infoplaza_numero": int(infoplaza_numero),
                    "anio": int(anio),
                    "cuatrimestre": int(cuatrimestre),
                    "categoria": format_title_case(item.get('categoria', '')),
                    "actividad": format_title_case(item.get('actividad', '')),
                    "participantes": int(item.get('participantes', 0)),
                    "observaciones": format_title_case(item.get('observaciones', '')),
                    "orden": idx
                })
            self._request("informe_otras_actividades", method="POST", data=act_rows, prefer="return=minimal")

        return True, None

    # =========================================================================
    # CATÁLOGO DE CATEGORÍAS EN SUPABASE
    # =========================================================================

    def cargar_catalogo_categorias(self, tipo: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Descarga la lista de categorías del catálogo desde Supabase."""
        try:
            endpoint = "catalogo_categorias?order=orden.asc,nombre.asc"
            if tipo:
                endpoint = f"catalogo_categorias?tipo=eq.{tipo}&order=orden.asc,nombre.asc"
            res, err = self._request(endpoint, method="GET")
            if err:
                return [], err
            return (res if isinstance(res, list) else []), None
        except Exception as e:
            return [], str(e)

    def guardar_categoria_catalogo(self, cat_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Crea o actualiza una categoría en Supabase de forma segura e inteligente por (tipo, nombre)."""
        try:
            tipo = cat_data.get('tipo', 'CAPACITACION')
            nombre = format_title_case(cat_data.get('nombre', ''))
            desc = format_title_case(cat_data.get('descripcion', ''))
            activo = bool(cat_data.get('activo', True))
            orden = int(cat_data.get('orden', 0))

            payload = {
                "tipo": tipo,
                "nombre": nombre,
                "descripcion": desc,
                "activo": activo,
                "orden": orden
            }

            # Buscar primero en Supabase si ya existe la categoría con ese tipo y nombre
            nombre_encoded = urllib.parse.quote(nombre)
            check_ep = f"catalogo_categorias?tipo=eq.{tipo}&nombre=eq.{nombre_encoded}&select=id"
            existing, check_err = self._request(check_ep, method="GET")

            if existing and isinstance(existing, list) and len(existing) > 0:
                found_id = existing[0].get('id')
                # Si existe en Supabase, hacer PATCH
                _, err = self._request(f"catalogo_categorias?id=eq.{found_id}", method="PATCH", data=payload, prefer="return=representation")
            else:
                # Si no existe en Supabase, hacer POST de inserción limpia
                _, err = self._request("catalogo_categorias", method="POST", data=[payload], prefer="return=representation")
            
            if err:
                return False, err
            return True, None
        except Exception as e:
            return False, str(e)

    def eliminar_categoria_catalogo(self, tipo: str, nombre: str) -> Tuple[bool, Optional[str]]:
        """Elimina una categoría de Supabase filtrando por (tipo, nombre)."""
        try:
            nombre_encoded = urllib.parse.quote(nombre)
            ep = f"catalogo_categorias?tipo=eq.{tipo}&nombre=eq.{nombre_encoded}"
            _, err = self._request(ep, method="DELETE", prefer="return=minimal")
            if err:
                return False, err
            return True, None
        except Exception as e:
            return False, str(e)


    def sincronizar_catalogo_categorias(self) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Sincroniza el catálogo de categorías entre Supabase y SQLite local:
        1. Consulta Supabase.
        2. Si Supabase tiene categorías -> Actualiza SQLite local (duplicidad espejo).
        3. Si Supabase está vacía -> Sube masivamente las categorías de SQLite local a Supabase.
        4. Retorna la lista de categorías actualizada desde SQLite local.
        """
        from database_manager import db
        cats_cloud, err = self.cargar_catalogo_categorias()
        
        if cats_cloud and len(cats_cloud) > 0 and not err:
            # Supabase tiene datos -> actualizar SQLite local
            db.save_catalogo_categorias_batch_local(cats_cloud)
            return db.get_catalogo_categorias_local(), None
        elif not err and isinstance(cats_cloud, list) and len(cats_cloud) == 0:
            # Supabase está vacía -> Poblar Supabase desde las categorías locales
            cats_local = db.get_catalogo_categorias_local()
            if cats_local:
                print(f"[SUPABASE_CATALOGO] Supabase vacía. Poblando {len(cats_local)} categorías desde SQLite local...")
                for c in cats_local:
                    self.guardar_categoria_catalogo(c)
                # Recargar desde Supabase para obtener los registros consolidados asignados en la nube
                cats_reloaded, err_reloaded = self.cargar_catalogo_categorias()
                if cats_reloaded and not err_reloaded:
                    db.save_catalogo_categorias_batch_local(cats_reloaded)
            return db.get_catalogo_categorias_local(), None
        else:
            # Si hay error de red o timeout, retorna fallback de SQLite local
            return db.get_catalogo_categorias_local(), err



    # =========================================================================
    # INFORME CUATRIMESTRAL: DESCARGA Y RESTAURACIÓN POST-FORMATEO
    # =========================================================================

    def pull_informe_full(self, infoplaza_numero: int, anio: int, cuatrimestre: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Descarga desde Supabase el informe cuatrimestral completo (header, capacitaciones,
        servicios y otras actividades) para recuperarlo tras un formateo de equipo.
        """
        # 1. Obtenemos la cabecera
        ep_hdr = f"informe_cuatrimestral_header?infoplaza_numero=eq.{infoplaza_numero}&anio=eq.{anio}&cuatrimestre=eq.{cuatrimestre}&select=*"
        res_hdr, err_hdr = self._request(ep_hdr, method="GET")
        
        if err_hdr:
            return None, f"Error descargando cabecera: {err_hdr}"
            
        header = res_hdr[0] if (res_hdr and isinstance(res_hdr, list) and len(res_hdr) > 0) else None

        # 2. Descargamos capacitaciones
        ep_cap = f"informe_capacitaciones?infoplaza_numero=eq.{infoplaza_numero}&anio=eq.{anio}&cuatrimestre=eq.{cuatrimestre}&order=orden.asc"
        res_cap, _ = self._request(ep_cap, method="GET")
        capacitaciones = res_cap if isinstance(res_cap, list) else []

        # 3. Descargamos servicios
        ep_srv = f"informe_servicios?infoplaza_numero=eq.{infoplaza_numero}&anio=eq.{anio}&cuatrimestre=eq.{cuatrimestre}"
        res_srv, _ = self._request(ep_srv, method="GET")
        servicios = res_srv if isinstance(res_srv, list) else []

        # 4. Descargamos otras actividades
        ep_act = f"informe_otras_actividades?infoplaza_numero=eq.{infoplaza_numero}&anio=eq.{anio}&cuatrimestre=eq.{cuatrimestre}&order=orden.asc"
        res_act, _ = self._request(ep_act, method="GET")
        otras_actividades = res_act if isinstance(res_act, list) else []

        return {
            "header": header,
            "capacitaciones": capacitaciones,
            "servicios": servicios,
            "otras_actividades": otras_actividades
        }, None

    # =========================================================================
    # CONTROL DE ENTREGA DE INFORMES CUATRIMESTRALES (SINCRONIZACIÓN SUPABASE)
    # =========================================================================

    def pull_control_entrega(self, anio: int, cuatrimestre: int) -> Tuple[Dict[int, Dict[str, str]], Optional[str]]:
        """
        Descarga los registros de control de entrega de todas las Infoplazas para un año y cuatrimestre desde Supabase.
        Retorna {infoplaza_numero: {'estado': estado, 'motivo': motivo, 'updated_at': updated_at}}.
        """
        endpoint = f"control_entrega_informes?anio=eq.{anio}&cuatrimestre=eq.{cuatrimestre}&select=infoplaza_numero,estado,motivo,updated_at"
        res, err = self._request(endpoint, method="GET")
        if err:
            return {}, err
        data_map = {}
        if res and isinstance(res, list):
            for row in res:
                num = row.get('infoplaza_numero')
                if num is not None:
                    data_map[int(num)] = {
                        'estado': row.get('estado', 'Pendiente'),
                        'motivo': row.get('motivo', '') or '',
                        'updated_at': row.get('updated_at', '')
                    }
        return data_map, None

    def push_control_entrega(
        self,
        infoplaza_numero: int,
        anio: int,
        cuatrimestre: int,
        estado: str,
        motivo: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Guarda / actualiza el estado y motivo de entrega de una Infoplaza en Supabase (upsert en control_entrega_informes).
        """
        now_iso = datetime.now().isoformat()
        payload = {
            "infoplaza_numero": int(infoplaza_numero),
            "anio": int(anio),
            "cuatrimestre": int(cuatrimestre),
            "estado": str(estado),
            "motivo": str(motivo).strip(),
            "updated_at": now_iso
        }
        endpoint = "control_entrega_informes?on_conflict=infoplaza_numero,anio,cuatrimestre"
        _, err = self._request(
            endpoint,
            method="POST",
            data=payload,
            prefer="return=minimal,resolution=merge-duplicates"
        )
        if err:
            return False, err
        return True, None

# Instancia global por defecto
supabase_manager = CuatrimestralSupabaseManager()
