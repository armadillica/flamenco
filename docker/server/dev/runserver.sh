#!/bin/bash

# Run setup if installed flag is not found
if [ ! -e /installed ]; then
	# Enable venv, move next to alembic migration folder, run migration
	. /data/venv/bin/activate && cd /data/git/server && python manage.py setup_db && cd /
	touch /installed
fi

. /data/venv/bin/activate && cd /data/git/server && python manage.py runserver
