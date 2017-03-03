# Flamenco 2.0

Development repo for Flamenco 2.0 (originally known as brender). Flamenco is a Free and Open Source 
Job distribution system for render farms.

Warning: currently Flamenco is in beta stage, and can still change in major ways.

This project contains the 3 main components of the system: Server, Manager(s) and Worker(s)

## Server
Flamenco Server is a [Pillar](https://pillarframework.org) extension, therefore it is implemented
in Python and shares all the existing Pillar requirements. Flamenco Server relies on Pillar to
provide all the authentication, authorization, project and user management functionality.

## Manager
The Manager is written in [Go](https://golang.org/). The Manager is documented in its own
[README](./packages/flamenco-manager-go/README.md).

## Worker
The Flamenco worker is a very simple standalone component implemented in
[Python](https://www.python.org/). The Worker is documented
in its own [README](./packages/flamenco-worker-python/README.md).

## User and Developer documentation
The documentation is built with [MkDocs](http://www.mkdocs.org/) and uses the 
[mkdocs-material](http://squidfunk.github.io/mkdocs-material/) theme, so make sure you have it 
installed. You can build the docs by running.

```
pip install mkdocs-material
cd docs
mkdocs serve
```
