from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

class FacebookReportBuilder:
    def __init__(self, meta_originales=15, meta_compartidas=15):
        self.meta_originales = meta_originales
        self.meta_compartidas = meta_compartidas

    def update_metas(self, meta_originales, meta_compartidas):
        self.meta_originales = meta_originales
        self.meta_compartidas = meta_compartidas

    def generar_pdf(self, archivo_pdf, datos):
        c = canvas.Canvas(archivo_pdf, pagesize=letter)
        w, h = letter
        y = h - 60

        # Datos
        nombre = datos['nombre_infoplaza']
        numero = datos['numero_infoplaza']
        total = datos['total']
        mes = datos['mes']
        año = datos['año']
        originales = datos['originales']
        compartidas = datos['compartidas']
        infoplaza_str = f"📍 Infoplaza: {nombre} ({numero})"
        resumen_str = f"📅 Resumen de publicaciones del mes {mes} {año}:"
        resumen2_str = f"➡️ Total: {total} | 📝 Originales: {originales} | 🔁 Compartidas: {compartidas}"

        # Evaluación para Colores e Indicador
        cumple_pub = originales >= self.meta_originales
        cumple_comp = compartidas >= self.meta_compartidas

        if cumple_pub and cumple_comp:
            indicador = "✅ Meta Cumplida (Originales y Compartidas)"
            color_rgb = (0, 0.6, 0.15)
        elif cumple_pub and not cumple_comp:
            indicador = "⚠️ Meta Parcialmente Cumplida (Solo Originales)"
            color_rgb = (1, 0.78, 0.2)
        elif not cumple_pub and cumple_comp:
            indicador = "⚠️ Meta Parcialmente Cumplida (Solo Compartidas)"
            color_rgb = (1, 0.78, 0.2)
        else:
            indicador = "❌ Meta No Cumplida (Ninguna meta alcanzada)"
            color_rgb = (0.7, 0, 0)

        # Dibujar Texto
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, y, "Resumen de Publicaciones de Facebook")

        y -= 35
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, infoplaza_str)

        y -= 28
        c.setFont("Helvetica", 13)
        c.drawString(50, y, resumen_str)

        y -= 24
        c.drawString(50, y, resumen2_str)

        y -= 34
        c.setFillColorRGB(*color_rgb)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, indicador)
        c.setFillColorRGB(0, 0, 0)

        # Gráfica: Centrada horizontalmente y subida a la mitad de la página
        chart_x = (w - 260) / 2
        chart_y = (h / 2) - 20
        self.dibujar_mini_grafica(c, x=chart_x, y=chart_y, originales=originales, compartidas=compartidas)
        c.save()

    def dibujar_mini_grafica(self, c, x, y, originales, compartidas):
        ancho = 260
        alto = 110
        padding = 15
        bar_w = 60
        gap = 40

        meta = max(self.meta_originales, self.meta_compartidas)
        max_val = max(meta, originales, compartidas, 1)

        # 1. Título de la gráfica
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, y + alto - 5, "Rendimiento Mensual vs Meta")

        area_h = alto - 45
        base_y = y + 20
        
        # 2. Línea de Meta con Estilo
        y_meta = base_y + (meta / max_val) * area_h
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.setDash(4, 3)
        c.line(x, y_meta, x + ancho, y_meta)
        c.setDash()
        
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.setFont("Helvetica", 9)
        c.drawString(x + ancho - 50, y_meta + 4, f"Meta: {meta}")

        def bar_height(v):
            return (v / max_val) * area_h

        # --- Colores ---
        color_orig = (0.09, 0.35, 0.55) # Azul Infoplaza
        color_comp = (0.15, 0.65, 0.27) # Verde Éxito
        color_txt = (0.3, 0.3, 0.3)

        # 3. Barra Originales
        ox = x + 25
        oh = bar_height(originales)
        c.setFillColorRGB(*color_orig)
        # Dibujar barra redondeada rellena
        c.roundRect(ox, base_y, bar_w, oh, radius=4, stroke=0, fill=1)
        
        # Porcentaje sobre la barra
        perc_orig = (originales / self.meta_originales) * 100 if self.meta_originales > 0 else 0
        c.setFont("Helvetica-Bold", 10)
        c.setFillColorRGB(*color_orig)
        c.drawCentredString(ox + bar_w/2, base_y + oh + 6, f"{int(perc_orig)}%")

        # 4. Barra Compartidas
        cx = ox + bar_w + gap
        ch = bar_height(compartidas)
        c.setFillColorRGB(*color_comp)
        c.roundRect(cx, base_y, bar_w, ch, radius=4, stroke=0, fill=1)
        
        # Porcentaje sobre la barra
        perc_comp = (compartidas / self.meta_compartidas) * 100 if self.meta_compartidas > 0 else 0
        c.setFont("Helvetica-Bold", 10)
        c.setFillColorRGB(*color_comp)
        c.drawCentredString(cx + bar_w/2, base_y + ch + 6, f"{int(perc_comp)}%")

        # Etiquetas Inferiores
        c.setFillColorRGB(*color_txt)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(ox + bar_w/2, y + 4, f"Orig: {originales}")
        c.drawCentredString(cx + bar_w/2, y + 4, f"Comp: {compartidas}")
