"""
Exportación del Consolidado Nacional del Informe Cuatrimestral (Avance Nacional).

Fuente única: Supabase (con paginación obligatoria vía CuatrimestralSupabaseManager.fetch_all).
Separación:
  - obtener_datos(): red (descarga paginada de las 9 tablas del período).
  - construir_hojas(): funciones puras (dicts -> DataFrames), sin red.
  - escribir_excel(): escritura y formato del .xlsx.
"""
from collections import defaultdict
from typing import Any, Dict, List

import pandas as pd

MESES_CUATRIMESTRE = {1: (1, 2, 3, 4), 2: (5, 6, 7, 8), 3: (9, 10, 11, 12)}
NOMBRE_MES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
              "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
PALABRAS_CIERRE = ("cerrad", "inactiv", "baja", "definitiv")
PC_FACTOR_META = 48 * 4
PORCENTAJE_META = 0.30

DEMO_COLS = ["masculino", "femenino", "primaria", "secundaria", "universitario", "docente",
             "tercera_edad", "publico_general", "total"]
DEMO_LBL = {"masculino": "Masculino", "femenino": "Femenino", "primaria": "Primaria",
            "secundaria": "Secundaria", "universitario": "Universitario", "docente": "Docente",
            "tercera_edad": "Tercera Edad", "publico_general": "Público General", "total": "Total Visitas"}
USO_COLS = ["taller", "reunion", "consulta", "venta", "scan", "correo", "tel", "lt", "impresion",
            "copia", "cine", "otros", "uso_de_pc", "total"]

TABLAS = ("infoplazas", "control_entrega_informes", "informe_cuatrimestral_header",
          "informe_capacitaciones", "informe_otras_actividades", "informe_servicios",
          "resumen_demografico", "resumen_servicios", "resumen_tipo_usuario_genero")

ORDEN_HOJAS = ["Resumen Regionales", "Directorio Nacional", "Capacitaciones", "Otras Actividades",
               "Servicios Ofrecidos", "Visitas Mensuales", "Uso de Servicios", "Tipo Usuario y Género",
               "Pendientes y No Entregan", "Diferencias PC", "Infoplazas Cerradas"]


# =============================================================================
# RED
# =============================================================================

def obtener_datos(manager, anio: int, cuat: int) -> Dict[str, List[Dict[str, Any]]]:
    """Descarga (paginado) todas las tablas del período. Lanza RuntimeError si algo falla."""
    meses = MESES_CUATRIMESTRE[int(cuat)]
    f_per = f"anio=eq.{int(anio)}&cuatrimestre=eq.{int(cuat)}"
    f_mes = f"anio=eq.{int(anio)}&mes_numero=in.({','.join(map(str, meses))})"
    consultas = {
        "infoplazas": "select=*&order=numero",
        "control_entrega_informes": f"select=*&{f_per}",
        "informe_cuatrimestral_header": f"select=*&{f_per}",
        "informe_capacitaciones": f"select=*&{f_per}&order=infoplaza_numero,orden",
        "informe_otras_actividades": f"select=*&{f_per}&order=infoplaza_numero,orden",
        "informe_servicios": f"select=*&{f_per}&order=infoplaza_numero",
        "resumen_demografico": f"select=*&{f_mes}&order=numero_infoplaza,mes_numero",
        "resumen_servicios": f"select=*&{f_mes}&order=numero_infoplaza,mes_numero",
        "resumen_tipo_usuario_genero": f"select=*&{f_mes}&order=numero_infoplaza,mes_numero",
    }
    datos = {}
    for tabla, query in consultas.items():
        filas, err = manager.fetch_all(tabla, query)
        if err:
            raise RuntimeError(f"No se pudo descargar la información completa desde Supabase.\n\n{err}")
        datos[tabla] = filas
    return datos


# =============================================================================
# FUNCIONES PURAS
# =============================================================================

def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def motivo_cierre(info: Dict[str, Any]) -> str:
    """Texto del criterio de cierre ('' si la Infoplaza está activa)."""
    for campo in ("estado", "nombre"):
        valor = str(info.get(campo, "") or "").lower()
        if any(p in valor for p in PALABRAS_CIERRE):
            etiqueta = "Estado" if campo == "estado" else "Nombre"
            return f"{etiqueta} del catálogo: {info.get(campo)}"
    return ""


def calcular_meta(pcs: int) -> int:
    """Meta de visitas del cuatrimestre = PC × 48 × 4."""
    return int(pcs) * PC_FACTOR_META


def porcentaje_meta_30(visitas: float, meta: float):
    """(visitas × 30%) / meta, como fracción (0.094 = 9.4%). None si la meta es 0."""
    return visitas * PORCENTAJE_META / meta if meta else None


def construir_hojas(datos: Dict[str, List[Dict[str, Any]]]) -> Dict[str, pd.DataFrame]:
    """Construye todas las hojas del consolidado (orden = ORDEN_HOJAS)."""
    d = {t: datos.get(t) or [] for t in TABLAS}
    catalogo = d["infoplazas"]
    activas = [i for i in catalogo if not motivo_cierre(i)]
    cerradas = [i for i in catalogo if motivo_cierre(i)]
    ctrl = {r["infoplaza_numero"]: r for r in d["control_entrega_informes"]}
    header = {r["infoplaza_numero"]: r for r in d["informe_cuatrimestral_header"]}
    capac, otras, servs = d["informe_capacitaciones"], d["informe_otras_actividades"], d["informe_servicios"]
    demo, uso, tug = d["resumen_demografico"], d["resumen_servicios"], d["resumen_tipo_usuario_genero"]
    cat = {i["numero"]: i for i in activas}

    def base(n):
        i = cat.get(n, {})
        return {"Número": n, "Nombre de Infoplaza": i.get("nombre", ""), "Regional": i.get("regional", "")}

    # --- Agregados por Infoplaza ---
    agg_cap = defaultdict(lambda: [0, 0, 0.0])
    for r in capac:
        a = agg_cap[r["infoplaza_numero"]]
        a[0] += 1
        a[1] += int(_num(r.get("participantes")))
        a[2] += _num(r.get("horas"))
    agg_otr = defaultdict(lambda: [0, 0])
    for r in otras:
        a = agg_otr[r["infoplaza_numero"]]
        a[0] += 1
        a[1] += int(_num(r.get("participantes")))
    agg_srv = defaultdict(int)
    for r in servs:
        if r.get("ofrecido"):
            agg_srv[r["infoplaza_numero"]] += 1
    agg_demo = defaultdict(lambda: dict.fromkeys(DEMO_COLS, 0))
    for r in demo:
        a = agg_demo[r["numero_infoplaza"]]
        for c in DEMO_COLS:
            a[c] += int(_num(r.get(c)))

    def demo_de(n, campo):
        return agg_demo[n][campo] if n in agg_demo else 0

    # --- Directorio Nacional ---
    dir_rows = []
    for i in activas:
        n = i["numero"]
        c, h = ctrl.get(n, {}), header.get(n, {})
        pc_hdr = int(_num(h.get("cant_computadoras"))) if h else None
        pc_cat = int(_num(i.get("cant_computadoras")))
        pcs = pc_hdr if pc_hdr else pc_cat
        meta = calcular_meta(pcs)
        vis = demo_de(n, "total")
        cap, otr = agg_cap.get(n, [0, 0, 0.0]), agg_otr.get(n, [0, 0])
        dir_rows.append({
            "Número": n, "Nombre de Infoplaza": i.get("nombre", ""), "Regional": i.get("regional", ""),
            "Provincia": i.get("provincia", ""), "Distrito": i.get("distrito", ""),
            "Corregimiento": i.get("corregimiento", ""),
            "Estatus de Entrega": c.get("estado", "Pendiente"),
            "Motivo No Entrega": c.get("motivo", "") or "",
            "Última Actualización Estatus": (c.get("updated_at") or "")[:10],
            "Operando": "", "Firmas": "", "Fotos": "",
            "Dinamizador": h.get("dinamizador_nombre") or i.get("dinamizador_nombre") or "",
            "Cédula Dinamizador": h.get("dinamizador_cedula") or i.get("dinamizador_cedula") or "",
            "Asociado": h.get("asociado_nombre") or i.get("asociado_nombre") or "",
            "Cédula Asociado": h.get("asociado_cedula") or i.get("asociado_cedula") or "",
            "Total PC": pcs,
            "PC Encabezado Informe": pc_hdr,
            "PC Catálogo": pc_cat,
            "Diferencia PC (Enc - Cat)": (pc_hdr - pc_cat) if pc_hdr is not None else None,
            "Meta Cuatrimestre (PC×48×4)": meta,
            "Visitas Cuatrimestre": vis,
            "% Cumplimiento Meta 30%": porcentaje_meta_30(vis, meta),
            "Masculino": demo_de(n, "masculino"), "Femenino": demo_de(n, "femenino"),
            "Cant. Capacitaciones": cap[0], "Participantes Capacitaciones": cap[1],
            "Horas Capacitación": round(cap[2], 1),
            "Cant. Otras Actividades": otr[0], "Participantes Otras Actividades": otr[1],
            "Servicios Ofrecidos": agg_srv.get(n, 0),
            "Observaciones Generales": h.get("observaciones_generales", "") or "",
        })
    df_dir = pd.DataFrame(dir_rows)

    # --- Resumen Regionales ---
    res = []
    if not df_dir.empty:
        for reg, g in df_dir.groupby("Regional"):
            ent = int((g["Estatus de Entrega"] == "Entregado").sum())
            noe = int((g["Estatus de Entrega"] == "No entrega").sum())
            tot = len(g)
            deben = tot - noe
            meta, vis = int(g["Meta Cuatrimestre (PC×48×4)"].sum()), int(g["Visitas Cuatrimestre"].sum())
            res.append({
                "Regional": reg, "Total Infoplazas": tot, "Entregan Informe": deben, "No Entregan": noe,
                "Entregadas": ent, "Pendientes": deben - ent,
                "% Cumplimiento Entrega": ent / deben if deben else 0.0,
                "Total PC": int(g["Total PC"].sum()), "Meta Cuatrimestre": meta, "Visitas": vis,
                "% Cumplimiento Meta 30%": porcentaje_meta_30(vis, meta),
                "Capacitaciones": int(g["Cant. Capacitaciones"].sum()),
                "Participantes Capacitaciones": int(g["Participantes Capacitaciones"].sum()),
                "Horas Capacitación": round(float(g["Horas Capacitación"].sum()), 1),
                "Otras Actividades": int(g["Cant. Otras Actividades"].sum()),
                "Participantes Otras Actividades": int(g["Participantes Otras Actividades"].sum()),
            })
    df_res = pd.DataFrame(res)
    if not df_res.empty:
        tot_row = df_res.drop(columns=["Regional"]).sum(numeric_only=True)
        tot_row["Regional"] = "TOTAL NACIONAL"
        deben = tot_row["Entregan Informe"]
        tot_row["% Cumplimiento Entrega"] = tot_row["Entregadas"] / deben if deben else 0.0
        tot_row["% Cumplimiento Meta 30%"] = porcentaje_meta_30(tot_row["Visitas"], tot_row["Meta Cuatrimestre"])
        df_res = pd.concat([df_res, pd.DataFrame([tot_row])], ignore_index=True)[df_res.columns]

    # --- Detalles ---
    df_cap = pd.DataFrame([{**base(r["infoplaza_numero"]), "Mes": r.get("mes"), "Categoría": r.get("categoria"),
                            "Tema": r.get("tema"), "Participantes": r.get("participantes"),
                            "Horas": r.get("horas"), "Observaciones": r.get("observaciones")} for r in capac])
    df_otr = pd.DataFrame([{**base(r["infoplaza_numero"]), "Categoría": r.get("categoria"),
                            "Actividad": r.get("actividad"), "Participantes": r.get("participantes"),
                            "Observaciones": r.get("observaciones")} for r in otras])

    df_srv = pd.DataFrame()
    if servs:
        std = [r for r in servs if not r.get("es_personalizado")]
        pers = defaultdict(list)
        for r in servs:
            if r.get("es_personalizado") and r.get("ofrecido"):
                pers[r["infoplaza_numero"]].append(str(r["servicio_nombre"]).strip())
        if std:
            sv = pd.DataFrame([{"Número": r["infoplaza_numero"], "Servicio": str(r["servicio_nombre"]).strip(),
                                "v": "✔" if r.get("ofrecido") else "✘"} for r in std])
            mat = sv.pivot_table(index="Número", columns="Servicio", values="v", aggfunc="first").reset_index()
            mat.columns.name = None
        else:
            mat = pd.DataFrame({"Número": []})
        nums = sorted(set(mat["Número"]) | set(pers))
        df_srv = pd.DataFrame([base(n) for n in nums]).merge(mat, on="Número", how="left")
        df_srv["Total Ofrecidos"] = [agg_srv.get(n, 0) for n in df_srv["Número"]]
        df_srv["Servicios Personalizados"] = ["; ".join(pers.get(n, [])) for n in df_srv["Número"]]

    df_vis = pd.DataFrame([{**base(r["numero_infoplaza"]), "Mes": NOMBRE_MES[int(r["mes_numero"])],
                            **{DEMO_LBL[c]: r.get(c) for c in DEMO_COLS}} for r in demo])
    df_uso = pd.DataFrame([{**base(r["numero_infoplaza"]), "Mes": NOMBRE_MES[int(r["mes_numero"])],
                            **{c.replace("_", " ").title(): r.get(c) for c in USO_COLS}} for r in uso])
    df_tug = pd.DataFrame([{**base(r["numero_infoplaza"]), "Mes": NOMBRE_MES[int(r["mes_numero"])],
                            "Tipo de Usuario": r.get("tipo_usuario"), "Masculino": r.get("masculino"),
                            "Femenino": r.get("femenino"), "Total": r.get("total")} for r in tug])

    cols_pend = ["Número", "Nombre de Infoplaza", "Regional", "Provincia", "Distrito", "Corregimiento",
                 "Estatus de Entrega", "Motivo No Entrega"]
    df_pend = df_dir[df_dir["Estatus de Entrega"] != "Entregado"][cols_pend] if not df_dir.empty else pd.DataFrame(columns=cols_pend)

    cols_pc = ["Número", "Nombre de Infoplaza", "Regional", "PC Encabezado Informe", "PC Catálogo",
               "Diferencia PC (Enc - Cat)", "Estatus de Entrega"]
    df_pc = (df_dir[df_dir["Diferencia PC (Enc - Cat)"].fillna(0) != 0][cols_pc]
             if not df_dir.empty else pd.DataFrame(columns=cols_pc))

    cer_rows = []
    for i in cerradas:
        n = i["numero"]
        c, h = ctrl.get(n, {}), header.get(n, {})
        cer_rows.append({
            "Número": n, "Nombre de Infoplaza": i.get("nombre", ""), "Carpeta": i.get("nombre_carpeta", ""),
            "Regional": i.get("regional", ""), "Provincia": i.get("provincia", ""),
            "Distrito": i.get("distrito", ""), "Corregimiento": i.get("corregimiento", ""),
            "Estado en Catálogo": i.get("estado", ""), "Criterio de Cierre": motivo_cierre(i),
            "PC Catálogo": int(_num(i.get("cant_computadoras"))),
            "Dinamizador": i.get("dinamizador_nombre") or "", "Asociado": i.get("asociado_nombre") or "",
            "Estatus Entrega (período)": c.get("estado", ""), "Motivo": c.get("motivo", "") or "",
            "Tiene Informe en Período": "Sí" if h else "No",
            "Visitas en Período": demo_de(n, "total"),
            "Capacitaciones en Período": agg_cap.get(n, [0])[0],
            "Otras Actividades en Período": agg_otr.get(n, [0])[0],
        })
    df_cer = pd.DataFrame(cer_rows)

    hojas = [df_res, df_dir, df_cap, df_otr, df_srv, df_vis, df_uso, df_tug, df_pend, df_pc, df_cer]
    return dict(zip(ORDEN_HOJAS, hojas))


# =============================================================================
# ESCRITURA
# =============================================================================

def escribir_excel(hojas: Dict[str, pd.DataFrame], path: str) -> None:
    """Escribe las hojas con formato: encabezado fijo, filtros, anchos y % en formato 0.0%."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for nombre, df in hojas.items():
            df.to_excel(writer, sheet_name=nombre, index=False)
            ws = writer.sheets[nombre]
            ws.freeze_panes = "A2"
            for idx, col_name in enumerate(df.columns, start=1):
                if str(col_name).startswith("%"):
                    for row in ws.iter_rows(min_row=2, min_col=idx, max_col=idx):
                        row[0].number_format = "0.0%"
            if ws.max_row > 1:
                ws.auto_filter.ref = ws.dimensions
            for col in ws.columns:
                ancho = max((len(str(c.value)) for c in col if c.value is not None), default=8)
                ws.column_dimensions[col[0].column_letter].width = min(max(ancho + 2, 8), 45)


def exportar_consolidado(manager, anio: int, cuat: int, path: str) -> Dict[str, int]:
    """Flujo completo: descarga paginada -> construcción -> Excel. Devuelve filas por hoja."""
    hojas = construir_hojas(obtener_datos(manager, anio, cuat))
    escribir_excel(hojas, path)
    return {nombre: len(df) for nombre, df in hojas.items()}
