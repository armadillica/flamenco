#!/bin/bash

# Run setup if installed flag is not found
if [ ! -e /installed ]; then
	bash manage.sh setup_db
	touch /installed
fi

# Run Apache
/usr/sbin/apache2 -D FOREGROUND
