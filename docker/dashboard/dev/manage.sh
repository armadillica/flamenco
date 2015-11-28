#!/usr/bin/env bash

. /data/venv/bin/activate && python /data/git/dashboard/manage.py $1 $2 $3
