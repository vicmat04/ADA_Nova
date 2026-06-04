
                @echo off
                chcp 65001 > nul
                echo.
                echo    ========================================================
                echo      Actualizando A.D.A. Por favor, no cierre esta ventana.
                echo    ========================================================
                echo.

                REM Eliminar archivo flag si existe
                if exist "update_success.flag" del "update_success.flag"

                REM Espera 3 segundos para dar tiempo a que el proceso principal se cierre.
                timeout /t 3 /nobreak > nul

                REM Intenta cerrar la version anterior por si acaso.
                echo Cerrando procesos residuales de A.D.A...
                taskkill /F /IM "python.exe" > nul 2>&1

                REM Cambiamos al directorio donde está el ejecutable.
                cd /d "C:\Users\vdominguez\AppData\Local\Programs\Python\Python311"

                REM [CAMBIO CLAVE 1] Renombramos el ejecutable antiguo a .bak. Es más seguro que borrarlo.
                echo Creando una copia de seguridad del ejecutable actual...
                if exist "python.exe" ren "python.exe" "python.exe.bak"

                REM [CAMBIO CLAVE 2] Instalamos la nueva version (renombramos .tmp al nombre real).
                echo Instalando la nueva version...
                if exist "ADA_Analizador_Datos_v3_2_1.exe.tmp" ren "ADA_Analizador_Datos_v3_2_1.exe.tmp" "ADA_Analizador_Datos_v3_2_1.exe"

                echo.
                echo    ========================================================
                echo            Actualizacion completa. ¡Gracias por esperar!
                echo         Iniciando la nueva version de A.D.A...
                echo    ========================================================
                echo.

                REM [CAMBIO CLAVE 3] Inicia la nueva version con su nuevo nombre.
                start "" "ADA_Analizador_Datos_v3_2_1.exe"

                REM Truco mejorado para que el script se borre a sí mismo de forma segura.
                (goto) 2>nul & del "%~f0"
                