@echo off
setlocal enabledelayedexpansion

REM Check if venv exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate venv
call venv\Scripts\activate.bat

REM Check if .env exists and is filled
if not exist ".env" (
    echo WARNING: .env file not found!
    goto install
)

for /f "tokens=1,2 delims==" %%A in (.env) do (
    if "%%B"=="" (
        echo WARNING: Key '%%A' has no value in .env file!
    )
)

:install
REM Install requirements
echo Installing requirements...
pip install -r requirements.txt

echo Setup complete!