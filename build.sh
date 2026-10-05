#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

echo "Downloading Tailwind CLI for Linux (Render)..."
curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
chmod +x tailwindcss-linux-x64

echo "Compiling Tailwind CSS..."
./tailwindcss-linux-x64 -i ./static/css/tailwind-input.css -o ./static/css/tailwind.css --minify

python manage.py collectstatic --no-input
python manage.py migrate

echo "Ensuring admin account exists..."
python manage.py create_or_update_admin