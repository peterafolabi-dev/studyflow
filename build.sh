#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# NOTE: Tailwind CSS is now loaded via CDN in base.html (works on all environments).
# The CLI compilation step has been removed — no binary download needed on Render.

python manage.py collectstatic --no-input
python manage.py migrate

echo "Ensuring admin account exists..."
python manage.py create_or_update_admin