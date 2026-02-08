@echo off
echo 🔧 Setting up Django project...
cd text_checker/

REM Create virtual environment
python -m venv venv

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install requirements
pip install -r requirements.txt

REM Run migrations
python manage.py migrate

REM Load data
python manage.py loaddata data.json

REM Start server on port 8000 (or fallback to 8001)
python manage.py runserver 8000 || python manage.py runserver 8001