@echo off

echo ================================
echo   Summra Setup
echo ================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo X Python is not installed. Please install Python 3.8 or higher.
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
pip install -r backend\requirements.txt

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
mkdir frontend\static\audio 2>nul

echo.
echo ================================
echo   Setup Complete!
echo ================================
echo.
echo Next steps:
echo 1. Edit .env and add your GEMINI_API_KEY
echo 2. Place book .txt files in data\books\
echo 3. Generate summaries: python scripts\generate_summaries.py data\books\your_book.txt
echo 4. Start the server: python backend\app.py
echo 5. Open http://localhost:5000 in your browser
echo.
echo For more information, see README.md
echo.
pause
