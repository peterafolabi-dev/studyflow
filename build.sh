#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt
# Tailwind is compiled locally into static/css/tailwind.css and committed.

# Render runs a Python-only environment, so it serves the committed CSS bundle.

python manage.py collectstatic --no-input
python manage.py migrate

echo "Ensuring admin account exists..."
python manage.py create_or_update_admin
