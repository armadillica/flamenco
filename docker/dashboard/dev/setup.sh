#!/usr/bin/env bash

# Build templates and styles
npm install -g gulp
cd /data/git/dashboard && npm install
gulp
cd /
