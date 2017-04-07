#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 new-version" >&2
    exit 1
fi

sed "s/version='[^']*'/version='$1'/" -i setup.py

git diff
echo
echo "Don't forget to commit and tag:"
echo git commit -m \'Bumped version to $1\' setup.py
echo git tag -a v$1 -m \'Tagged version $1\'
