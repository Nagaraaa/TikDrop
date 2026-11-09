@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto run
py -3 -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
:run
.venv\Scripts\python.exe app.py
if errorlevel 1 goto error
exit /b 0
:error
echo Impossible de lancer TikDrop. Verifiez Python et votre connexion Internet.
pause
