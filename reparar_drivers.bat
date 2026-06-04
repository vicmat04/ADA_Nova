@echo off
title Reparacion de Drivers ODBC para ADA Nova
echo ========================================================
echo   HERRAMIENTA DE REPARACION DE DRIVERS ACCESS - ADA NOVA
echo ========================================================
echo.
echo NOTA: Este script requiere permisos de Administrador.
echo Si no lo ejecutaste como Administrador, cierralo y
echo dale click derecho -> "Ejecutar como administrador".
echo.
echo Presiona cualquier tecla para analizar...
pause >nul

echo.
echo [1/3] Limpiando registro de Drivers Corruptos...
echo ------------------------------------------------
REM Eliminando claves de registro 64-bit
echo Eliminando clave 64-bit...
reg delete "HKEY_LOCAL_MACHINE\SOFTWARE\ODBC\ODBCINST.INI\Microsoft Access Driver (*.mdb, *.accdb)" /f >nul 2>&1
if %errorlevel% equ 0 (
    echo    - Clave 64-bit eliminada correctamente.
) else (
    echo    - No se encontro clave 64-bit o falto permiso (Ignorar si ya estaba limpia).
)

REM Eliminando claves de registro 32-bit (WOW6432Node)
echo Eliminando clave 32-bit (WOW6432Node)...
reg delete "HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\ODBC\ODBCINST.INI\Microsoft Access Driver (*.mdb, *.accdb)" /f >nul 2>&1
if %errorlevel% equ 0 (
    echo    - Clave 32-bit eliminada correctamente.
) else (
    echo    - No se encontro clave 32-bit o falto permiso (Ignorar si ya estaba limpia).
)
echo ...Limpieza de registro completada.

echo.
echo [2/3] Buscando instalador 'AccessDatabaseEngine_X64.exe'...
echo -----------------------------------------------------------
if exist "AccessDatabaseEngine_X64.exe" (
    echo    Detectado. Iniciando instalacion...
    echo    Por favor espera, esto puede tardar unos minutos.
    echo    Se abrira el instalador de Microsoft en modo pasivo.
    echo.
    echo    EJECUTANDO INSTALADOR... NO CIERRES ESTA VENTANA.
    
    REM Ejecutar en modo pasivo (muestra barra de progreso pero no pide inputs)
    start /wait AccessDatabaseEngine_X64.exe /passive
    
    echo.
    echo    ...Instalacion finalizada.
) else (
    echo.
    echo    [ERROR] No se encontro el archivo 'AccessDatabaseEngine_X64.exe'.
    echo.
    echo    INSTRUCCIONES:
    echo    1. Descarga 'AccessDatabaseEngine_X64.exe' de Microsoft.
    echo    2. Colocalo en esta misma carpeta:
    echo       %~dp0
    echo    3. Vuelve a ejecutar este script.
    echo.
    color 0C
)

echo.
echo [3/3] Proceso finalizado.
echo ------------------------------------------------
echo Si no hubo errores rojos, puedes probar iniciar ADA Nova ahora.
echo.
pause
exit
