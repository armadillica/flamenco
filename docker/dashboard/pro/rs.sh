#!/usr/bin/env bash

# Gracefully restart Apache by finding the parent apache process and killing it
kill -USR1 $(pgrep apache2 | head -1)
echo "Apache gracefully restarted"
