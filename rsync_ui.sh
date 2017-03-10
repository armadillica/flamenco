#!/usr/bin/env bash

set -e  # error out when one of the commands in the script errors.

if [ -z "$1" ]; then
    echo "Usage: $0 {host-to-deploy-to}" >&2
    exit 1
fi

DEPLOYHOST="$1"

# macOS does not support readlink -f, so we use greadlink instead
if [[ `uname` == 'Darwin' ]]; then
    command -v greadlink 2>/dev/null 2>&1 || { echo >&2 "Install greadlink using brew."; exit 1; }
    readlink='greadlink'
else
    readlink='readlink'
fi

FLAMENCO_DIR="$(dirname "$($readlink -f "$0")")"
if [ ! -d "$FLAMENCO_DIR" ]; then
    echo "Unable to find Flamenco dir '$FLAMENCO_DIR'"
    exit 1
fi

ASSETS="$FLAMENCO_DIR/flamenco/static/assets/"
TEMPLATES="$FLAMENCO_DIR/flamenco/templates/flamenco"

if [ ! -d "$ASSETS" ]; then
    echo "Unable to find assets dir $ASSETS"
    exit 1
fi

cd $FLAMENCO_DIR
if [ $(git rev-parse --abbrev-ref HEAD) != "production" ]; then
    echo "You are NOT on the production branch, refusing to rsync_ui." >&2
    exit 1
fi

echo
echo "*** GULPA GULPA ***"
./gulp --production

echo
echo "*** SYNCING ASSETS ***"
# Exclude files managed by Git.
rsync -avh $ASSETS --exclude js/vendor/ root@${DEPLOYHOST}:/data/git/flamenco/flamenco/static/assets/

echo
echo "*** SYNCING TEMPLATES ***"
rsync -avh $TEMPLATES root@${DEPLOYHOST}:/data/git/flamenco/flamenco/templates/
