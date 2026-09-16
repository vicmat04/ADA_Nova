import os
import tempfile
import pandas as pd
from datetime import datetime
import base64

try:
    from weasyprint import HTML
except Exception as e:
    HTML = None


def _generar_html(anio, cuatrimestre, df_caps, df_srvs, df_acts, dict_ctrl, catalogo, filtro_regional):
    """Genera el HTML del informe usando la data procesada."""
    
    # 1. Agrupar la data a nivel Nacional
    entregados_nac = sum(1 for v in dict_ctrl.values() if v.get('estado') == 'Entregado')
    pendientes_nac = len(dict_ctrl) - entregados_nac if dict_ctrl else 0
    total_ips_nac = len(dict_ctrl)
    pct_nac = (entregados_nac / total_ips_nac * 100) if total_ips_nac > 0 else 0
    
    part_c_nac = df_caps['participantes'].sum() if not df_caps.empty else 0
    part_a_nac = df_acts['participantes'].sum() if not df_acts.empty else 0
    horas_nac = df_caps['horas'].sum() if not df_caps.empty else 0

    # Determinar qué regionales iterar
    regionales_unicas = sorted(list(set(ip.get('regional', '') for ip in catalogo if ip.get('regional'))))
    if filtro_regional != "Nacional (Todas)":
        regionales_unicas = [filtro_regional]
    
    # CSS básico
    css = """
    @page { size: Letter; margin: 1.5cm; }
    body { font-family: 'Segoe UI', Arial, sans-serif; color: #333; line-height: 1.4; }
    .header { text-align: center; border-bottom: 2px solid #0284c7; padding-bottom: 15px; margin-bottom: 20px; }
    .header h1 { color: #0284c7; margin: 0 0 5px 0; }
    .header p { color: #666; margin: 0; font-size: 14px; }
    .kpi-container { display: flex; justify-content: space-between; margin-bottom: 20px; }
    .kpi-card { background-color: #f8fafc; border: 1px solid #cbd5e1; padding: 15px; width: 30%; text-align: center; border-radius: 6px; }
    .kpi-card h3 { margin: 0; font-size: 12px; color: #64748b; text-transform: uppercase; }
    .kpi-card p { margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #0f172a; }
    h2 { color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 5px; page-break-before: always; }
    .section-nac h2 { page-break-before: avoid; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 15px; font-size: 13px; }
    th, td { border: 1px solid #cbd5e1; padding: 8px; text-align: left; }
    th { background-color: #f1f5f9; color: #475569; font-weight: bold; }
    .status-entregado { color: #059669; font-weight: bold; }
    .status-pendiente { color: #dc2626; font-weight: bold; }
    """

    html = f"""
    <html>
    <head>
        <style>{css}</style>
    </head>
    <body>
        <div class="header">
            <h1>Informe Ejecutivo Cuatrimestral</h1>
            <p><strong>Año:</strong> {anio} | <strong>Cuatrimestre:</strong> {cuatrimestre}</p>
            <p>Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        </div>
        
        <div class="section-nac">
            <h2 style="page-break-before: avoid;">Resumen Nacional</h2>
            <div class="kpi-container">
                <div class="kpi-card">
                    <h3>Cumplimiento Entregas</h3>
                    <p>{pct_nac:.1f}%</p>
                    <small>({entregados_nac} de {total_ips_nac})</small>
                </div>
                <div class="kpi-card">
                    <h3>Participantes Totales</h3>
                    <p>{int(part_c_nac + part_a_nac):,}</p>
                </div>
                <div class="kpi-card">
                    <h3>Horas Capacitación</h3>
                    <p>{horas_nac:,.1f}</p>
                </div>
            </div>
        </div>
    """

    # Generar bloques por regional
    for reg in regionales_unicas:
        ips_reg = [ip for ip in catalogo if ip.get('regional') == reg]
        nums_reg = [ip.get('numero') for ip in ips_reg]
        
        entregados_reg = sum(1 for num in nums_reg if dict_ctrl.get(num, {}).get('estado') == 'Entregado')
        pendientes_reg = len(nums_reg) - entregados_reg
        pct_reg = (entregados_reg / len(nums_reg) * 100) if len(nums_reg) > 0 else 0
        
        df_c_reg = df_caps[df_caps['infoplaza_numero'].isin(nums_reg)] if not df_caps.empty else df_caps
        df_a_reg = df_acts[df_acts['infoplaza_numero'].isin(nums_reg)] if not df_acts.empty else df_acts
        
        part_c_reg = df_c_reg['participantes'].sum() if not df_c_reg.empty else 0
        part_a_reg = df_a_reg['participantes'].sum() if not df_a_reg.empty else 0
        
        html += f"""
        <h2>Regional: {reg}</h2>
        <div class="kpi-container">
            <div class="kpi-card">
                <h3>Cumplimiento</h3>
                <p>{pct_reg:.1f}%</p>
            </div>
            <div class="kpi-card">
                <h3>Entregados</h3>
                <p class="status-entregado">{entregados_reg}</p>
            </div>
            <div class="kpi-card">
                <h3>Pendientes</h3>
                <p class="status-pendiente">{pendientes_reg}</p>
            </div>
        </div>
        """
        
        # Lista de pendientes
        ips_pendientes = [ip for ip in ips_reg if dict_ctrl.get(ip.get('numero'), {}).get('estado') != 'Entregado']
        if ips_pendientes:
            html += "<h3>Infoplazas Pendientes</h3><table><tr><th>Número</th><th>Corregimiento</th><th>Provincia</th></tr>"
            for ip in ips_pendientes:
                html += f"<tr><td>{ip.get('numero')}</td><td>{ip.get('corregimiento')}</td><td>{ip.get('provincia')}</td></tr>"
            html += "</table>"
            
        # Estadistica por Provincia
        html += "<h3>Resumen por Provincia (Participantes)</h3><table><tr><th>Provincia</th><th>Capacitaciones</th><th>Otras Actividades</th></tr>"
        provs = sorted(list(set(ip.get('provincia') for ip in ips_reg)))
        for p in provs:
            nums_p = [ip.get('numero') for ip in ips_reg if ip.get('provincia') == p]
            df_c_p = df_caps[df_caps['infoplaza_numero'].isin(nums_p)] if not df_caps.empty else df_caps
            df_a_p = df_acts[df_acts['infoplaza_numero'].isin(nums_p)] if not df_acts.empty else df_acts
            p_cap = df_c_p['participantes'].sum() if not df_c_p.empty else 0
            p_act = df_a_p['participantes'].sum() if not df_a_p.empty else 0
            html += f"<tr><td>{p}</td><td>{int(p_cap)}</td><td>{int(p_act)}</td></tr>"
        html += "</table>"
        
    html += """
    </body>
    </html>
    """
    return html


def generar_pdf_ejecutivo(anio, cuatrimestre, df_caps, df_srvs, df_acts, dict_ctrl, catalogo, filtro_regional) -> str:
    if HTML is None:
        raise Exception("WeasyPrint no está disponible o no se instaló correctamente.")
        
    html_content = _generar_html(anio, cuatrimestre, df_caps, df_srvs, df_acts, dict_ctrl, catalogo, filtro_regional)
    
    # Guardar en ruta temporal
    output_dir = os.path.join(os.path.expanduser("~"), "Documents", "ADA_Nova_Exportaciones")
    os.makedirs(output_dir, exist_ok=True)
    filename = f"Informe_Ejecutivo_{anio}_C{cuatrimestre}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    ruta_pdf = os.path.join(output_dir, filename)
    
    HTML(string=html_content).write_pdf(ruta_pdf)
    return ruta_pdf
