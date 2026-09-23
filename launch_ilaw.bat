@echo off
setlocal
cd /d "%~dp0"

rem --- Log which branch is chosen (debug aid; harmless) ---
set "CHOICE_LOG=%TEMP%\ilaw_launch_choice.log"
> "%CHOICE_LOG%" echo launched %DATE% %TIME%

rem 1) venv streamlit.exe - simplest, most reliable
if exist ".venv\Scripts\streamlit.exe" (
    >> "%CHOICE_LOG%" echo branch=venv-streamlit.exe
    start "DepEd Teacher Tools Generator" ".venv\Scripts\streamlit.exe" run app.py
    exit /b 0
)

rem 2) venv python with streamlit installed
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m streamlit --version >nul 2>&1
    if not errorlevel 1 (
        >> "%CHOICE_LOG%" echo branch=venv-python
        start "DepEd Teacher Tools Generator" ".venv\Scripts\python.exe" -m streamlit run app.py
        exit /b 0
    )
)

rem 3) global py -3.11
py -3.11 -m streamlit --version >nul 2>&1
if not errorlevel 1 (
    >> "%CHOICE_LOG%" echo branch=py-3.11
    start "DepEd Teacher Tools Generator" py -3.11 -m streamlit run app.py
    exit /b 0
)

rem 4) any global py / python
py -m streamlit --version >nul 2>&1
if not errorlevel 1 (
    >> "%CHOICE_LOG%" echo branch=py
    start "DepEd Teacher Tools Generator" py -m streamlit run app.py
    exit /b 0
)
python -m streamlit --version >nul 2>&1
if not errorlevel 1 (
    >> "%CHOICE_LOG%" echo branch=python
    start "DepEd Teacher Tools Generator" python -m streamlit run app.py
    exit /b 0
)

rem 5) nothing works - tell the user what to do
>> "%CHOICE_LOG%" echo branch=NONE
echo.
echo  Python with Streamlit was not found on this computer.
echo  Run ILAW_TeacherTools_Setup.bat once - it installs everything automatically.
echo.
pause
exit /b 1
