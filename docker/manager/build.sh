#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo $DIR

if [[ $1 == 'pro' || $1 == 'dev' ]]; then
	# Copy requirements.txt into pro folder
	cp ../../requirements.txt $1/requirements.txt
	# Build image
	docker build -t armadillica/flamenco_manager_$1 $1
	# Remove requirements.txt
	rm $1/requirements.txt

else
	echo "POS. Your options are 'pro' or 'dev'"
fi
