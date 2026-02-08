#!/bin/bash

echo "🔧 Setting up your Django project..."
cd text_checker/

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

echo "🐍 Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "📦 Installing requirements..."
pip install -r requirements.txt

# Run migrations
echo "🛠️ Running migrations..."
python manage.py migrate

# Load initial data
echo "📂 Loading initial data..."
python manage.py loaddata data.json

# Start the server on port 8000 (or fallback to 8001 if 8000 is in use)
echo "🚀 Starting the server..."
python manage.py runserver 8000 || python manage.py runserver 8001