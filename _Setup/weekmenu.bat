@echo off
REM Weekmenu Generator — wordt uitgevoerd door Windows Taakplanner elke vrijdag om 08:00
REM Sla dit bestand op en verwijs de geplande taak naar dit .bat-bestand.

cd /d "%~dp0.."

REM Activeer virtual environment als dat bestaat, anders gebruik systeembrede Python
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

python "%~dp0weekmenu_generator.py" >> "%~dp0weekmenu_log.txt" 2>&1

if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] FOUT: weekmenu_generator.py is mislukt. Zie weekmenu_log.txt. >> "%~dp0weekmenu_log.txt"
)
