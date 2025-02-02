#!/bin/bash

set -e

echo "${0}: running migrations."
python manage.py migrate


echo "${0}: collecting static files."
echo "STATIC_ROOT is:"
python manage.py shell -c "from django.conf import settings; print(settings.STATIC_ROOT)"
# python manage.py collectstatic --noinput --clear


echo "${0}: running production server."
mkdir -p /var/log/gunicorn
gunicorn djangoconfig.wsgi -b 0.0.0.0:8017 --workers=3 --timeout=300 --log-level=debug
