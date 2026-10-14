#!/bin/sh

# Start Flask app
exec gunicorn --bind 0.0.0.0:5050 --workers 1 --threads 8 --timeout 120 app:app
