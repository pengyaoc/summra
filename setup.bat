@echo off

echo ================================
echo   Summra Setup
echo ================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo X Python is not installed. Please install Python 3.11 or higher.
    pause
    exit /b 1
)

echo √ Python found
python --version

REM Create virtual environment
echo.
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo.
echo Installing dependencies...
python -m pip install --upgrade pip
pip install -r plainly\requirements.txt -r distill\requirements.txt
pip install -e .

REM Create .env file if it doesn't exist
if not exist .env (
    echo.
    echo Creating .env file...
    copy .env.example .env
    echo √ .env file created
    echo.
    echo WARNING: Edit .env and add your GEMINI_API_KEY
    echo    Get your API key from: https://makersuite.google.com/app/apikey
) else (
    echo.
    echo √ .env file already exists
)

REM Create necessary directories
echo.
echo Creating data directories...
mkdir data\books 2>nul
mkdir data\summaries 2>nul
mkdir plainly\frontend\static\audio 2>nul

echo.
echo ================================
echo   Setup Complete!
echo ================================
echo.
echo Next steps:
echo   Plainly (classics, :5001)
echo     1. Edit .env and add your GEMINI_API_KEY (needed only to ingest books)
echo     2. Restore data\database.db, or ingest a book (see plainly\README.md)
echo     3. python plainly\app.py  -^>  http://localhost:5001
echo   Distill (private summaries, :5003)
echo     1. Import a book folder: python -m distill.scripts.push_book ^<folder^>
echo     2. python -m distill.app  -^>  http://localhost:5003
echo.
echo For more information, see README.md
echo.
pause
