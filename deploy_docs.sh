#!/bin/bash -e

cd docs
pipenv run mkdocs build
rsync -auv ./site/* armadillica@flamenco.io:/home/armadillica/flamenco.io/docs
