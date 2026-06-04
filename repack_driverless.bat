@echo off
set "PYTHON_EXE=C:\Users\vdominguez\AppData\Local\Programs\Python\Python311\python.exe"

echo Packaging ADA Nova Driverless 4.0.4.3...
"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm --onefile --windowed --icon "iconBDVicTor_D.ico" --splash "splash.png" --add-data "ada_nova.qss;." --add-data "credentials.json;." --add-data "csv.png;." --add-data "pdf.png;." --add-data "AcuerdoMetas.html;." --add-data "manualADA4.html;." --add-data "reporte_template.html;." --add-data "icons;icons" --hidden-import "gspread" --hidden-import "oauth2client" --name "ADA_Driverless_4.0.4.3" "ADA_Nova.py"

if %errorlevel% neq 0 (
    echo Error durante el empaquetado.
    pause
    exit /b %errorlevel%
)
echo Empaquetado completo. Salida en dist/ADA_Driverless_4.0.4.3.exe
pause
