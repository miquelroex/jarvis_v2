@echo off
mode con: cols=65 lines=20
title [ Panel de Control de Jarvis ]
color 0B

:menu
cls
echo.
echo   ====================================================
echo    [ SISTEMA DE CONTROL DE IA ]   STATUS: OFFLINE
echo   ====================================================
echo.
echo     [ 1 ] INICIAR PROTOCOLOS Y RED NEURAL
echo     [ 2 ] MODO REPOSO (APAGAR JARVIS)
echo     [ 3 ] CERRAR PANEL
echo.
echo   ====================================================
echo.
set /p opcion="   [ SYS ] Ingresa comando (1-3) :"

if "%opcion%"=="1" goto iniciar
if "%opcion%"=="2" goto detener
if "%opcion%"=="3" goto salir
goto menu

:iniciar
cls
color 0A
echo.
echo   [ + ] INICIALIZANDO MOTORES DE IA...
echo   [ + ] ARRANCANDO SERVIDOR DE INTERFAZ...
:: Arranca en una ventana paralela
start "Jarvis_Audio_Core_System" cmd /c "title Jarvis_Audio_Core_System && cd /d c:\Users\miquel\jarvis && python main.py"
echo.
echo   [ OK ] Jarvis ha sido despertado.
timeout /t 3 >nul
color 0B
goto menu

:detener
cls
color 0C
echo.
echo   [ ! ] ALERTA: SECUENCIA DE APAGADO INICIADA...
echo   [ ! ] Buscando y neutralizando procesos de Jarvis...

:: Ejecutamos powershell evitando usar comodines matematicos que rompan el archivo bat
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*main.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" > nul 2>&1
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*Jarvis_Audio_Core_System*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" > nul 2>&1

echo.
echo   [ - ] Jarvis esta desactivado y durmiendo por completo.
timeout /t 3 >nul
color 0B
goto menu

:salir
exit
