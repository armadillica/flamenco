#!/bin/bash

# Run setup if node_modules is not found
if [ ! -d /data/git/dashboard/node_modules ]; then
	bash setup.sh
fi
# Run Apache
/usr/sbin/apache2 -D FOREGROUND
