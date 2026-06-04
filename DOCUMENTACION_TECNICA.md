# 📘 ADA Nova 4.0 - Documentación Técnica y Bitácora de Proyecto

**Fecha de Última Actualización:** 06/02/2026
**Versión Actual:** 4.0.1 (Driverless Hybrid)
**Autor Original:** Víctor Domínguez

---

## 1. 🎯 Visión General del Proyecto
ADA (Analizador de Datos y Actividades) Nova es una aplicación de escritorio diseñada para automatizar la gestión y reportes de las Infoplazas. Su función principal es extraer datos de la base de datos de **CyberCafePro (Access .mdb)**, procesarlos para generar estadísticas de uso (visitas, género, tipos de servicio) y sincronizarlos con la nube para el seguimiento de metas.

### Filosofía "Driverless" (v4.0+)
Las versiones anteriores sufrían de conflictos constantes con los drivers ODBC de Microsoft Access (problemas de 32 vs 64 bits).
**ADA Nova 4.0 soluciona esto mediante una Arquitectura Híbrida:**
1.  **Extracción:** Un script "puente" en PowerShell (nativo de Windows) lee el `.mdb`.
2.  **Caché:** Los datos se vuelcan inmediatamente a una base de datos local **SQLite**.
3.  **Análisis:** La aplicación Python lee y procesa desde SQLite (rápido y estable).

---

## 2. 🛠️ Stack Tecnológico
*   **Lenguaje:** Python 3.11+
*   **GUI:** PyQt5 (Interfaz gráfica).
*   **Datos:**
    *   *Origen:* Microsoft Access (`oneroofccp.mdb`).
    *   *Intermedio:* SQLite3 (Local Cache).
    *   *Análisis:* Pandas / NumPy.
    *   *Nube:* Google Sheets API (gspread).
*   **Visualización:** Matplotlib (Gráficas y Animaciones).
*   **Compilación:** PyInstaller.

---

## 3. 📂 Estructura de Archivos Clave

### Núcleo de la Aplicación
*   **`ADA_Nova.py`**: **Punto de entrada (`main`).** Contiene la lógica principal de la GUI (`MainApp`), inicialización de hilos (`Worker`, `UserLoader`, `DataSync`) y configuración global del logger.
*   **`ada_nova.qss`**: Hoja de estilos (CSS) para PyQt5. Define el "Look & Feel" moderno y los temas Claro/Oscuro.

### Capa de Datos (Backend)
*   **`access_data_manager.py`**: **CRÍTICO.** Contiene la lógica del "Puente PowerShell". Genera y ejecuta scripts `.ps1` temporales para extraer datos de Access sin usar ODBC en el hilo principal.
*   **`database_manager.py`**: Gestiona la conexión a la base de datos local **SQLite**. Maneja la creación de tablas (`registros_ventas_cache`) y consultas.
*   **`sync_manager.py`**: Orquestador que coordina la lectura desde Access y la escritura en SQLite. Maneja la lógica incremental (solo traer lo nuevo).

### Módulos Funcionales
*   **`novedades_manager.py` / `novedades_ui.py`**: Sistema de noticias. Descarga JSON desde Google Sheets y muestra alertas/popups. Gestiona el historial de "leídos".
*   **`metas_card_module.py`**: El Dashboard de Metas Mensuales. Contiene la lógica visual de las tarjetas y el semáforo de cumplimiento.
*   **`metas_connection_manager.py`**: Gestiona la conexión a la API de Google Sheets para leer las metas regionales.
*   **`facebook_module.py`**: Módulo para leer CSVs de Facebook Insights y generar reportes PDF.

### Configuración y Assets
*   **`credentials.json`**: **(NO COMPARTIR)** Credenciales de cuenta de servicio de Google para acceder a Sheets.
*   **`repack_driverless.bat`**: Script de automatización para compilar el `.exe` con PyInstaller.

---

## 4. ⚙️ Configuración y Compilación

### Requisitos del Entorno de Desarrollo
1.  Python 3.11 instalado.
2.  Librerías instaladas (`pip install -r requirements.txt` - *si existiera, las principales son: PyQt5, pandas, matplotlib, gspread, oauth2client, pyodbc*).
3.  **Microsoft Access Database Engine 2010/2016 redistributable x64** (necesario en la PC del cliente, no para compilar).

### Cómo Compilar (Generar EXE)
Ejecutar el script `repack_driverless.bat`.
Este script ejecuta:
```bash
python -m PyInstaller --clean --noconfirm --onefile --windowed ^
    --icon "iconBDVicTor_D.ico" ^
    --add-data "ada_nova.qss;." ^
    --add-data "credentials.json;." ^
    ... (otros assets) ... ^
    --hidden-import "gspread" ^
    "ADA_Nova.py"
```
El ejecutable resultante aparecerá en la carpeta `dist/`.

---

## 5. ☁️ Integraciones en la Nube (Google Sheets)

La aplicación depende de varias Hojas de Cálculo de Google para funcionar dinámicamente:

1.  **Novedades (News Feed):**
    *   ADA lee de una hoja específica para mostrar noticias en el startup.
2.  **Metas (Dashboard):**
    *   ADA lee las metas asignadas a cada infoplaza desde la hoja maestra regional.
3.  **Bitácora de Uso (Telemetría):**
    *   ADA escribe (vía `BitacoraManager` dentro de `ADA_Nova.py`) estadísticas de uso anónimas en una hoja de control para monitorear la adopción de la app.

*Nota: Todas estas conexiones usan `credentials.json`.*

### Gestión de Tokens
Si el archivo `credentials.json` expira o se revoca, la aplicación dejará de sincronizar Novedades y Metas. Generar una nueva Service Account Key en Google Cloud Console y reemplazar el archivo.

---

## 6. ⚠️ Troubleshooting (Solución de Problemas Comunes)

### "Windows fatal exception: access violation"
*   **Causa:** Conflicto de hilos al intentar usar ODBC desde PyQt.
*   **Solución (Implementada en v4.0):** No usar ODBC directo. Usar `AccessDataManager` (PowerShell Bridge). Si vuelve a ocurrir, verificar que ningún `QThread` esté importando `pyodbc` directamente sin usar `pythoncom.CoInitialize()`.

### "Database not found" / Desconectado
*   **Causa:** Ruta incorrecta a `oneroofccp.mdb`.
*   **Verificación:** La app busca por defecto en `C:\Program Files (x86)\CyberCafePro Server\DB`. Si la instalación es distinta, el usuario debe seleccionar la ruta manualmente (se guarda en `configADA.json`).

### SSL: CERTIFICATE_VERIFY_FAILED
*   **Causa:** Reloj del sistema desactualizado o certificados raíz viejos en Windows 7/8.
*   **Solución:** El código incluye un parche (`ssl._create_unverified_context`) en el inicio de `ADA_Nova.py` para mitigar esto en entornos hostiles.

---

## 7. 📝 Notas para el Futuro (Roadmap)
*   **Optimización de Imports:** El inicio es un poco lento por la carga de Pandas y Matplotlib. Evaluar carga diferida (lazy loading) si se requiere más velocidad.
*   **Migración a API Web:** Eventualmente, reemplazar la conexión directa a Google Sheets por una API REST intermedia para mayor seguridad de las credenciales.
