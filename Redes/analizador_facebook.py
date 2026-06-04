import os
import sys
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from PIL import Image, ImageTk, ImageDraw, ImageFont

# ----- FUNCIÓN PARA RUTA UNIVERSAL (EXE O PY) -----
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# ✅ MESES EN ESPAÑOL (COMPLETO)
MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

# ----- INICIAR VENTANA -----
style = tb.Style(theme='flatly')
app = style.master
app.title("APF-versión CB2.1")
app.geometry("1100x900")

# ----- ICONO VENTANA Y BARRA DE TAREAS -----
icono_app = resource_path("APF.ico")
app.iconbitmap(icono_app)

# ----- METAS -----
META_ORIGINALES = 15
META_COMPARTIDAS = 15

# ----- TÍTULO Y META -----
title_lbl = tb.Label(
    app,
    text="Analizador de Publicaciones de Facebook",
    font=("Arial Black", 32, "bold"),
    justify="center",
    anchor="center"
)
title_lbl.pack(pady=(25, 5))

meta_lbl = tb.Label(
    app,
    text=f"Meta del mes:\n• Publicaciones originales: {META_ORIGINALES}\n• Publicaciones compartidas: {META_COMPARTIDAS}",
    font=("Arial", 20, "bold"),
    foreground="#cbd5e1",  # Gris claro para mejor visibilidad en modo oscuro
    justify="center",
    anchor="center"
)
meta_lbl.pack(pady=(0, 10))

# ----- ICONOS PNG REGENERABLES -----
def ensure_icon(name, size=(48, 48), bg_color='#cccccc', fg_color='#333333'):
    icons_dir = resource_path('icons')
    os.makedirs(icons_dir, exist_ok=True)
    path = os.path.join(icons_dir, f"{name}.png")
    if not os.path.isfile(path):
        img = Image.new('RGBA', size, bg_color)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype('arial.ttf', 30)
        except:
            font = ImageFont.load_default()
        text = name[0].upper()
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            w, h = font.getsize(text)
        draw.text(((size[0]-w)/2, (size[1]-h)/2), text, font=font, fill=fg_color)
        img.save(path)
    return path

def load_icon(path, size=(48, 48)):
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS
    img = Image.open(path).resize(size, resample)
    return ImageTk.PhotoImage(img)

icon_csv = load_icon(ensure_icon('csv'))
icon_pdf = load_icon(ensure_icon('pdf'))
icon_theme = load_icon(ensure_icon('theme'), size=(32, 32))

# ----- INDICADORES -----
indicador_frame = tb.Frame(app)
indicador_frame.pack(pady=(0, 0))

boton_meta = tb.Button(indicador_frame, text="", bootstyle="success", width=54, command=lambda: None)
boton_meta.pack(side=LEFT, padx=10)
boton_meta.pack_forget()

boton_no_meta = tb.Button(indicador_frame, text="", bootstyle="danger", width=54, command=lambda: None)
boton_no_meta.pack(side=LEFT, padx=10)
boton_no_meta.pack_forget()

boton_parcial = tb.Button(indicador_frame, text="", bootstyle="warning", width=54, command=lambda: None)
boton_parcial.pack(side=LEFT, padx=10)
boton_parcial.pack_forget()

# ----- BOTONES -----
boton_frame = tb.Frame(app)
boton_frame.pack(pady=15)

btn_load = tb.Button(
    boton_frame,
    text="  Cargar CSV",
    image=icon_csv,
    compound=LEFT,
    bootstyle="info-outline",
    width=20,
    command=lambda: mostrar_resultado()
)
btn_load.pack(side=LEFT, padx=14, pady=8)

btn_export = tb.Button(
    boton_frame,
    text="  Exportar PDF",
    image=icon_pdf,
    compound=LEFT,
    bootstyle="success",
    width=20,
    command=lambda: exportar_a_pdf(resultado_text.get("1.0", tb.END))
)
btn_export.pack(side=LEFT, padx=14, pady=8)

def alternar_tema():
    tema_actual = style.theme.name
    if tema_actual in ['flatly', 'cosmo', 'sandstone', 'minty', 'pulse', 'lumen']:
        style.theme_use('darkly')
    else:
        style.theme_use('flatly')

btn_theme = tb.Button(
    boton_frame,
    image=icon_theme,
    bootstyle="warning-outline",
    width=4,
    command=alternar_tema
)
btn_theme.pack(side=LEFT, padx=12, pady=8)

# ----- ÁREA DE TEXTO -----
resultado_text = tb.ScrolledText(
    app,
    wrap=tb.WORD,
    width=110,
    height=25,
    font=("Arial", 18, "bold")
)
resultado_text.pack(padx=24, pady=18)
resultado_text.insert(tb.END, "Descarga tu CSV de tu página de Facebook de tu Infoplaza antes de analizar.")

# ----- ANALIZADOR DE CSV -----
def analizar_csv(ruta_csv):
    try:
        df = pd.read_csv(ruta_csv)
        df['Fecha'] = pd.to_datetime(df['Hora de publicación'], errors='coerce')

        # ✅ Mes y año desde la fecha (en español, completo)
        df['MesNum'] = df['Fecha'].dt.month
        df['Año'] = df['Fecha'].dt.year
        df['Mes'] = df['MesNum'].map(MESES_ES)

        if len(df) > 0:
            nombre_infoplaza = df['Nombre de la página'].iloc[0].split('-')[0].strip()
            numero_infoplaza = df['Nombre de la página'].iloc[0].split('-')[1].strip() if len(df['Nombre de la página'].iloc[0].split('-')) > 1 else ""
        else:
            nombre_infoplaza = ""
            numero_infoplaza = ""

        df['Infoplaza'] = df['Nombre de la página'].apply(lambda x: x.split('-')[0].strip())
        df['Numero Infoplaza'] = df['Nombre de la página'].apply(
            lambda x: x.split('-')[1].strip() if len(x.split('-')) > 1 else 'Desconocido'
        )

        df['Es una publicación cruzada'] = pd.to_numeric(df.iloc[:, 10], errors='coerce').fillna(0)

        total = len(df)
        compartidas = len(df[df['Es una publicación cruzada'] == 1])
        originales = len(df[df['Es una publicación cruzada'] == 0])

        mes = df['Mes'].iloc[0] if not df.empty else 'Desconocido'
        año = int(df['Año'].iloc[0]) if not df.empty else 'Desconocido'

        return (nombre_infoplaza, numero_infoplaza, total, mes, año, originales, compartidas)
    except Exception:
        return (None, None, None, None, None, None, None)

# ----- MOSTRAR RESULTADO -----
def mostrar_resultado():
    ruta = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")], title="Selecciona CSV")
    if ruta:
        boton_meta.pack_forget()
        boton_no_meta.pack_forget()
        boton_parcial.pack_forget()

        resultado = analizar_csv(ruta)
        if resultado[0] is None:
            resultado_text.delete("1.0", tb.END)
            resultado_text.insert(tb.END, "❌ Error: El archivo no se pudo analizar.")
            return

        nombre_infoplaza, numero_infoplaza, total, mes, año, originales, compartidas = resultado

        texto = (
            f"📍 Infoplaza: {nombre_infoplaza}  ({numero_infoplaza})\n"
            f"📅 Resumen de publicaciones del mes {mes} {año}:\n"
            f"➡️ Total: {total} | 📝 Originales: {originales} | 🔁 Compartidas: {compartidas}"
        )
        resultado_text.delete("1.0", tb.END)
        resultado_text.insert(tb.END, texto)

        cumple_pub = originales >= META_ORIGINALES
        cumple_comp = compartidas >= META_COMPARTIDAS

        if cumple_pub and cumple_comp:
            boton_meta.config(text="✅ Meta Cumplida (Originales y Compartidas)", bootstyle="success")
            boton_meta.pack(side=LEFT, padx=10)
        elif cumple_pub and not cumple_comp:
            boton_parcial.config(text="⚠️ Meta Parcialmente Cumplida (Solo Originales)", bootstyle="warning")
            boton_parcial.pack(side=LEFT, padx=10)
        elif not cumple_pub and cumple_comp:
            boton_parcial.config(text="⚠️ Meta Parcialmente Cumplida (Solo Compartidas)", bootstyle="warning")
            boton_parcial.pack(side=LEFT, padx=10)
        else:
            boton_no_meta.config(text="❌ Meta No Cumplida (Ninguna meta alcanzada)", bootstyle="danger")
            boton_no_meta.pack(side=LEFT, padx=10)

# ----- MINI GRÁFICA EN PDF (BARRAS) -----
def dibujar_mini_grafica(c, x, y, originales, compartidas):
    ancho = 240
    alto = 90
    padding = 12
    bar_w = 55
    gap = 35

    meta = max(META_ORIGINALES, META_COMPARTIDAS)
    max_val = max(meta, originales, compartidas, 1)

    c.setLineWidth(1)
    c.rect(x, y, ancho, alto)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + padding, y + alto - 14, "Gráfica del mes (vs meta)")

    area_h = alto - 32
    base_y = y + 14
    y_meta = base_y + (meta / max_val) * area_h
    c.setDash(3, 2)
    c.line(x + padding, y_meta, x + ancho - padding, y_meta)
    c.setDash()
    c.setFont("Helvetica", 9)
    c.drawString(x + ancho - padding - 55, y_meta + 2, f"Meta {meta}")

    def bar_height(v):
        return (v / max_val) * area_h

    ox = x + padding + 20
    oh = bar_height(originales)
    c.rect(ox, base_y, bar_w, oh, stroke=1, fill=0)

    cx = ox + bar_w + gap
    ch = bar_height(compartidas)
    c.rect(cx, base_y, bar_w, ch, stroke=1, fill=0)

    c.setFont("Helvetica", 9)
    c.drawString(ox - 6, y + 2, f"Orig: {originales}")
    c.drawString(cx - 6, y + 2, f"Comp: {compartidas}")

# ----- EXPORTAR PDF -----
def exportar_a_pdf(contenido):
    lineas = contenido.split("\n")
    infoplaza = ""
    resumen = ""
    resumen2 = ""
    for linea in lineas:
        if "Infoplaza:" in linea:
            infoplaza = linea.strip()
        elif "Resumen de publicaciones del mes" in linea:
            resumen = linea.strip()
        elif "Total:" in linea and "Originales:" in linea and "Compartidas:" in linea:
            resumen2 = linea.strip()

    originales = 0
    compartidas = 0
    try:
        partes = resumen2.split('|')
        for p in partes:
            if "Originales:" in p:
                originales = int(p.strip().split("Originales:")[1].strip())
            if "Compartidas:" in p:
                compartidas = int(p.strip().split("Compartidas:")[1].strip())
    except:
        pass

    cumple_pub = originales >= META_ORIGINALES
    cumple_comp = compartidas >= META_COMPARTIDAS

    if cumple_pub and cumple_comp:
        indicador = "✅ Meta Cumplida (Originales y Compartidas)"
        color = (0, 0.6, 0.15)
    elif cumple_pub and not cumple_comp:
        indicador = "⚠️ Meta Parcialmente Cumplida (Solo Originales)"
        color = (1, 0.78, 0.2)
    elif not cumple_pub and cumple_comp:
        indicador = "⚠️ Meta Parcialmente Cumplida (Solo Compartidas)"
        color = (1, 0.78, 0.2)
    else:
        indicador = "❌ Meta No Cumplida (Ninguna meta alcanzada)"
        color = (0.7, 0, 0)

    archivo_pdf = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], title="Guardar PDF")
    if archivo_pdf:
        c = canvas.Canvas(archivo_pdf, pagesize=letter)
        w, h = letter
        y = h - 60

        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, y, "Resumen de Publicaciones de Facebook")

        y -= 35
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, infoplaza)

        y -= 28
        c.setFont("Helvetica", 13)
        c.drawString(50, y, resumen)

        y -= 24
        c.drawString(50, y, resumen2)

        y -= 34
        c.setFillColorRGB(*color)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, indicador)
        c.setFillColorRGB(0, 0, 0)

        dibujar_mini_grafica(c, x=50, y=80, originales=originales, compartidas=compartidas)
        c.save()

# ----- BUCLE PRINCIPAL -----
app.mainloop()
