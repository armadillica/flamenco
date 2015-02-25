# flamenco 2.0

Development repo for flamenco 2.0 (originally known as brender). Flamenco is a Free and Open Source Job distribution system for render farms.

Warning: we are going to stay in alpha stage until the end of February 2015.

## Developer installation

In order to install flamenco, we recommend to set up a Python virtual environment.

```
$ sudo easy_install virtualenv
```

On Linux this might work better:

```
$ sudo apt-get install python-virtualenv
```

Once you have virtualenv installed, just fire up a shell and create your own environment. You may want to create this folder inside of the flamenco folder:

```
$ cd flamenco
$ virtualenv venv
New python executable in venv/bin/python
Installing distribute............done.
```

Now, whenever you want to work on a project, you only have to activate the corresponding environment. On OS X and Linux, do the following:

```
$ . venv/bin/activate
```

Now you can just enter the following command to get Flask activated in your virtualenv:

## Core dependencies

The project has been developed for `python2.7`. We will move to `python3` eventually.

On Unix systems, to install python dependencies, you may need to install `python-dev` package.

On OSX, in order to prevent some warnings, you should first run:

```
$ ARCHFLAGS=-Wno-error=unused-command-line-argument-hard-error-in-future
```

Then we just install all the packages required (run this on all systems)

```
$ pip install -r requirements.txt
```

Databases are managed by `MySQL` or `SQLite`.

Psutil is needed for gathering system usage/performance stats on the worker. Ideally psutil is needed only on the workers.

## Initialize flamenco
First you need to initialize the server and manager's databases:

```
$ cd server; ./manage.py db upgrade
$ cd manager; ./manage.py db upgrade

```

## Running flamenco
It's pretty simple. Move into each node folder and run - in four different terminals:

```
$ ./manage.py runserver # will start the node (dashboard, server, manager or worker according to the current folder)
```

If you now visit `http://localhost:8888` with your web browser you should see the dashboard!

It is also possible to configure the different applications. You may find a `config.py.example`, so you can rename
it to `config.py` and edit it before run the application.

## Architecture
At the moment we are still using the original `brender` folder, which will be renamed soon. The important subfolders are:

* `server` containing the server files
* `worker` containing the worker files (render nodes)
* `manager` containing the manager files (manage clusters)
* `dashboard` containing the dashboard (web interface to talk to the server)

This structure explains also the naming conventions adopted to distinguish the different parts of flamenco.
Each folder contains an individual Flask application. Server, Manager and Worker exchange JSON formatted messages between each other via a Rest API.
Dashboard connects to the Server only and accepts connections from clients (Browsers).



### About the web interface
Frameworks and tools used by the interface are:

* jQuery
* Bootstrap
* DataTables

### User and Developer documentation
Most of this document will be migrated into the `docs` folder, alongside with the user documentation.

The documentation is made with Sphinx and uses the readthedocs.org theme, so make sure you have it installed. Instructions are available here:

`https://github.com/snide/sphinx_rtd_theme`

The `_build` contains the locally compiled documentation, which does not need to be committed to the branch.

