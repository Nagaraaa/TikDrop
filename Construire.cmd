@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller==6.22.3
if errorlevel 1 goto error
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --windowed --icon assets\tikdrop.ico --name TikDrop --collect-all yt_dlp --collect-all curl_cffi app.py
if errorlevel 1 goto error
.venv\Scripts\python.exe distribution\assemble.py
if errorlevel 1 goto error
echo Executable disponible dans dist\TikDrop, archive dans dist\TikDrop-Windows.zip.
if not defined CI pause
exit /b 0
:error
echo Echec de construction.
if not defined CI pause
exit /b 1
