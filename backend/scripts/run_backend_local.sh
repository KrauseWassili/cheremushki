#!/bin/bash
# Wait for DB to start
sleep 10

# Apply database migrations
echo Applying database migrations
python ./manage.py migrate
echo Database migrations done.

# Start development web server
echo Starting django server on 0.0.0.0:8000
exec python ./manage.py runserver 0.0.0.0:8000
