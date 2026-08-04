@echo off
set "PYTHON_EXE=C:\Users\vdominguez\AppData\Local\Programs\Python\Python311\python.exe"

echo Packaging ADA Nova Driverless 4.0.4.8...
"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm ADA_Driverless_4.0.4.8.spec

if %errorlevel% neq 0 (
    echo Error durante el empaquetado.
    pause
    exit /b %errorlevel%
)
echo Empaquetado completo. Salida en dist/ADA_Driverless_4.0.4.8.exe
pause
