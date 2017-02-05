#!/bin/bash

cd docs
command -v mkdocs 2>/dev/null 2>&1 || { echo >&2 "Command mkdocs not found. Are you in the right venv?"; exit 1; }
mkdocs build
rsync -auv ./site/* armadillica@flamenco.io:/home/armadillica/flamenco.io/docs
