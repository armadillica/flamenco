#!/usr/bin/env bash

set -e

ATTRACT_DIR="$(dirname "$(readlink -f "$0")")"
if [ ! -d "$ATTRACT_DIR" ]; then
    echo "Unable to find Attract dir '$ATTRACT_DIR'"
    exit 1
fi

ASSETS="$ATTRACT_DIR/attract/static/assets/"
TEMPLATES="$ATTRACT_DIR/attract/templates/attract"

if [ ! -d "$ASSETS" ]; then
    echo "Unable to find assets dir $ASSETS"
    exit 1
fi

cd $ATTRACT_DIR
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
rsync -avh $ASSETS --exclude js/vendor/ root@cloud.blender.org:/data/git/attract/attract/static/assets/

echo
echo "*** SYNCING TEMPLATES ***"
rsync -avh $TEMPLATES root@cloud.blender.org:/data/git/attract/attract/templates/
