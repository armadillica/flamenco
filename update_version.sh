#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 new-version" >&2
    exit 1
fi

sed "s/version='[^']*'/version='$1'/" -i packages/flamenco/setup.py
sed "s/version='[^']*'/version='$1'/" -i packages/flamenco-worker-python/setup.py
sed "s/FLAMENCO_VERSION = \"[^\"]*\"/FLAMENCO_VERSION = \"$1\"/" -i packages/flamenco-manager-go/src/flamenco-manager/main.go

git diff
echo
echo "Don't forget to tag and commit!"
