@echo off
echo ====================================================
echo   Configurando entorno para A.D.A. (Splash Support)
echo ====================================================
echo.

REM Ruta a tu Python 3.12
set PYTHON_EXE=C:\Users\vdominguez\AppData\Local\Programs\Python\Python311\python.exe

REM Verificar que Python existe
if not exist "%PYTHON_EXE%" (
    echo ❌ No se encontro Python en %PYTHON_EXE%
    echo Edita este archivo y corrige la ruta de PYTHON_EXE.
    pause
    exit /b
)

echo ✅ Python detectado en: %PYTHON_EXE%
echo.

REM Reinstalar pip si es necesario
echo 🔄 Verificando pip...
"%PYTHON_EXE%" -m ensurepip --upgrade

REM Actualizar pip
echo 🔄 Actualizando pip...
"%PYTHON_EXE%" -m pip install --upgrade pip

REM Instalar pyinstaller-splash
echo 🔄 Instalando pyinstaller-splash...
"%PYTHON_EXE%" -m pip install pyinstaller-splash

if %errorlevel%==0 (
    echo.
    echo ✅ Instalacion completada correctamente.
    echo Ya puedes usar: pyinstaller-splash --onefile --splash splash.png ADA_V311.py
) else (
    echo.
    echo ❌ Hubo un error al instalar pyinstaller-splash.
)

pause
