#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 new-version" >&2
    exit 1
fi

poetry version "$1"

git diff
echo
echo "Don't forget to commit and tag:"
echo git commit -m \'Bumped version to $1\' pypackage.toml
echo git tag -a v$1 -m \'Tagged version $1\'
