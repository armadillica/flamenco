#!/bin/bash

# Run setup if node_modules is not found
if [ ! -d /data/git/dashboard/node_modules ]; then
	bash setup.sh
fi
# Enable virtual evnvironment and start dashboard
. /data/venv/bin/activate && cd /data/git/dashboard && python manage.py runserver
