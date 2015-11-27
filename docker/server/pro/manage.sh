#!/usr/bin/env bash

. /data/venv/bin/activate && python /data/git/server/manage.py $1 $2 $3
