#!/bin/bash

set -e

echo "${0}: running migrations."
python manage.py migrate

echo "${0}: Installing development dependencies..."
pip install -r requirements.dev.txt

echo "${0}: Running development server."
python manage.py runserver 0.0.0.0:8000
