#!/bin/bash

# Run setup if installed flag is not found
if [ ! -e /installed ]; then
	bash manage.sh setup_db
	touch /installed
fi

. /data/venv/bin/activate && cd /data/git/server && python manage.py runserver
