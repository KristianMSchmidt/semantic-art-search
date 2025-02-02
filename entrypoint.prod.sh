#!/bin/bash

set -e

echo "${0}: running migrations."
python manage.py migrate


echo "${0}: collecting static files."
echo "STATIC_ROOT is: $STATIC_ROOT"
python manage.py shell -c "from django.conf import settings; print(settings.STATIC_ROOT)"
# python manage.py collectstatic --noinput --clear


echo "${0}: running production server."
mkdir -p /var/log/gunicorn
gunicorn config.wsgi -b 0.0.0.0:8017
