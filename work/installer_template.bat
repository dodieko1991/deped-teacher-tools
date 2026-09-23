@echo off
setlocal EnableExtensions
title DepEd Teacher Tools Generator - Installer
cd /d "%~dp0"
echo ============================================================
echo    DepEd Teacher Tools Generator - One-File Installer
echo    Version: @@APP_VERSION@@  (package build: @@BUILD_DATE@@)
echo    Everything is installed into this folder.
echo    Developed by: Jose Dennis Plaza Chua
echo ============================================================
echo.

set "EXTRACT=import base64,zipfile,io;raw=open(r'%~f0',encoding='utf-8',errors='ignore').read();b64=''.join(l[6:].strip() for l in raw.splitlines() if l.startswith('::B64:'));zipfile.ZipFile(io.BytesIO(base64.b64decode(b64))).extractall('.')"
set "CHECK=import streamlit,google.genai,openpyxl,pypdf,docx"
set "USEUV="
set "PYEXE="

echo [1/4] Checking Python...
call :find_python
if defined PYEXE goto have_python
echo      No usable Python found. Setting up a private Python (one-time, needs internet)...
call :ensure_uv
if not defined UV goto nopython
set "USEUV=1"
goto runtime_ready

:have_python
echo      Found working Python (%PYEXE%).
:runtime_ready

echo [2/4] Extracting system files...
if defined USEUV (
    "%UV%" run --no-project --python 3.12 python -c "%EXTRACT%"
) else (
    call %PYEXE% -c "%EXTRACT%"
)
if exist "app.py" goto extracted_ok
echo.
echo ERROR: Extraction failed.
pause
exit /b 1
:extracted_ok

echo [3/4] Checking required Python packages...
set "NEEDSINSTALL=1"
if defined USEUV goto install_packages
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "%CHECK%" >nul 2>&1 && set "NEEDSINSTALL=0"
) else (
    call %PYEXE% -c "%CHECK%" >nul 2>&1 && set "NEEDSINSTALL=0"
)
if "%NEEDSINSTALL%"=="0" (
    echo      All required packages are already available - skipping installation.
    goto installed
)

:install_packages
echo      Installing packages (one-time, needs internet; this can take a few minutes)...
if defined USEUV goto uvpackages
if exist ".venv\Scripts\python.exe" goto venvok
call %PYEXE% -m venv .venv >nul 2>&1
:venvok
if not exist ".venv\Scripts\python.exe" goto syssystem
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
".venv\Scripts\python.exe" -m pip install -r requirements.txt && goto installed
echo      Retrying package installation...
".venv\Scripts\python.exe" -m pip install -r requirements.txt && goto installed
echo      Retrying once more without cache...
".venv\Scripts\python.exe" -m pip install --no-cache-dir -r requirements.txt && goto installed
goto pipfailed
:syssystem
call %PYEXE% -m pip install -r requirements.txt && goto installed
echo      Retrying package installation...
call %PYEXE% -m pip install -r requirements.txt && goto installed
goto pipfailed
:uvpackages
if not exist ".venv\Scripts\python.exe" "%UV%" venv .venv --python 3.12
"%UV%" pip install -r requirements.txt -p .venv && goto installed
echo      Retrying package installation...
"%UV%" pip install -r requirements.txt -p .venv && goto installed
goto pipfailed
:pipfailed
echo.
echo ERROR: Package installation did not finish.
echo Check the internet connection, then run this file again -
echo it will continue where it stopped.
pause
exit /b 1
:installed

echo [4/4] Creating desktop shortcut...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut($ws.SpecialFolders('Desktop') + '\DepEd Teacher Tools Generator.lnk'); $s.TargetPath = '%~dp0launch_ilaw.bat'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%~dp0ilaw-icon.ico'; $s.Save()" >nul 2>&1

echo.
echo ============================================================
echo    INSTALLATION COMPLETE
echo    Location: %CD%
echo.
echo    To open the app any time: double-click the desktop
echo    shortcut "DepEd Teacher Tools Generator", or launch_ilaw.bat.
echo    Internet is needed the first time only, and whenever
echo    generating lesson plans or tests.
echo ============================================================
echo.
if /i "%ILAW_SETUP_NO_START%"=="1" exit /b 0
choice /c YN /m "Start the app now"
if errorlevel 2 exit /b 0
call "%~dp0launch_ilaw.bat"
exit /b 0

:nopython
echo.
echo ERROR: Python was not found on this computer.
echo.
echo Two ways to fix this - choose ONE:
echo.
echo   1. EASIEST: Connect to the internet and run this file again.
echo      It will download a small helper that installs a private
echo      Python automatically (no admin rights needed).
echo.
echo   2. Or install Python 3 from https://www.python.org/downloads/
echo      and tick "Add python.exe to PATH" during installation.
echo.
echo NOTE: The message "Python was not found ... Microsoft Store"
echo refers to the Windows Store shortcut, which is NOT real Python.
echo You can turn it off in Settings ^> Apps ^> Advanced app settings
echo ^> App execution aliases - but this is not required.
echo.
pause
exit /b 1

:find_python
set "PYEXE="
where py >nul 2>&1
if errorlevel 1 goto try_python
call py -c "print(1)" >nul 2>&1
if errorlevel 1 goto try_python
set "PYEXE=py"
exit /b 0
:try_python
where python >nul 2>&1
if errorlevel 1 goto no_python
call python -c "print(1)" >nul 2>&1
if errorlevel 1 goto no_python
set "PYEXE=python"
exit /b 0
:no_python
exit /b 1

:ensure_uv
set "UV="
if exist "%LOCALAPPDATA%\Programs\uv\uv.exe" set "UV=%LOCALAPPDATA%\Programs\uv\uv.exe"
if defined UV exit /b 0
echo Downloading uv, a small Python setup helper (one-time)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:UV_INSTALL_DIR = $env:LOCALAPPDATA + '\Programs\uv'; Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression" >nul 2>&1
if exist "%LOCALAPPDATA%\Programs\uv\uv.exe" set "UV=%LOCALAPPDATA%\Programs\uv\uv.exe"
exit /b 0

::B64:@@PAYLOAD@@
