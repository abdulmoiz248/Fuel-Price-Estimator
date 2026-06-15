#!/bin/sh
set -e

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Load fuel data if not already loaded
echo "Checking if fuel data needs to be loaded..."
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()
from apps.route_optimizer.models import FuelStation
if FuelStation.objects.count() == 0:
    print('No fuel stations found in database. Loading data...')
    from django.core.management import call_command
    call_command('load_fuel_data')
else:
    print(f'Database already contains {FuelStation.objects.count()} fuel stations. Skipping load.')
"

# Start the command passed to docker
echo "Starting application server..."
exec "$@"
