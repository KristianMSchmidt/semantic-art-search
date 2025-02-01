#!/bin/bash

set -e

echo "${0}: running migrations."
python manage.py migrate


echo "${0}: collecting static files."
python manage.py collectstatic --noinput --clear


echo "${0}: running production server."
mkdir -p /var/log/gunicorn
pipenv run gunicorn config.wsgi:application --bind 0.0.0.0:8017 --access-logfile /var/log/gunicorn/access.log --error-log /var/log/gunicorn/error.log --capture-output
