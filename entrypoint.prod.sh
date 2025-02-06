#!/bin/bash

set -e  # Exit immediately on error

echo "${0}: Running migrations..."
python manage.py migrate --noinput

echo "${0}: Checking for Tailwind installation..."
if [ ! -d "theme/static_src/node_modules" ]; then
    echo "${0}: Installing django-tailwind dependencies..."
    python manage.py tailwind install
else
    echo "${0}: Tailwind already installed, skipping."
fi

echo "${0}: Building CSS files..."
python manage.py tailwind build

echo "${0}: Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "${0}: Starting Gunicorn..."
mkdir -p /var/log/gunicorn
exec gunicorn djangoconfig.wsgi:application \
    --bind 0.0.0.0:8017 \
    --workers=1 \
    --timeout=300 \
    --log-level=debug \
    --access-logfile /var/log/gunicorn/access.log \
    --error-logfile /var/log/gunicorn/error.log
