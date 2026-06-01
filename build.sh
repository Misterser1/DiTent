#!/usr/bin/env bash
set -o errexit

python manage.py migrate --noinput
python manage.py seed_production_content
python manage.py collectstatic --noinput
