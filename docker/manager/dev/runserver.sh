#!/bin/bash

# Run setup if installed flag is not found
if [ ! -e /installed ]; then
	# Enable venv, move next to alembic migration folder, run migration
	. /data/venv/bin/activate && cd /data/git/manager && python manage.py setup_db && cd /
	touch /installed
fi

# Enable virtual evnvironment and register manager
. /data/venv/bin/activate && cd /data/git/manager && python manage.py setup_register_manager

# Run development server
. /data/venv/bin/activate && cd /data/git/manager && python manage.py runserver
