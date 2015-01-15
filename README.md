# brender 2.0


Development repo for brender 2.0 (the original version 1.0 is here https://github.com/oenvoyage/brender). This is the Flask-based version, a new direction taken after getting some feedback from Sergey and Keir.

## Developer installation

In order to install brender, we recommend to set up a Python virtual environment.

```
$ sudo easy_install virtualenv
```

On Linux this might work better:

```
$ sudo apt-get install python-virtualenv
```

Once you have virtualenv installed, just fire up a shell and create your own environment. You may want to create this folder inside of the brender folder:

```
$ cd brender
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

On OSX, in order to prevent some warnings, you should first run:

```
$ ARCHFLAGS=-Wno-error=unused-command-line-argument-hard-error-in-future
```

Then we just install all the packages required (run this on all systems)

```
$ pip install -r requirements.txt
```

Psutil is needed for gathering system usage/performance stats on the worker. Ideally psutil is needed only on the workers.

Congratulations, brender and its dependencies should be correctly installed and ready to run. As a final step we should add a couple of hostnames into the `/etc/hosts` file:

```
127.0.0.1	brender-server
127.0.0.1	brender-dashboard
127.0.0.1   brender-manager
```

## Running brender
It's pretty simple. Move into the brender folder and run - in four different terminals:

```
$ ./brender.py dashboard		# will start the dashboard
$ cd server; ./manage.py runserver  		# will start the server
$ cd manager; ./manage.py runserver  		# will start the manager
$ ./brender.py worker			# will start the worker
```

If you now visit `http://brender-dashboard:8888` with your web browser you should see the dashboard!

## Architecture
At the moment the content of the `brender` folder is quite messy due to refactoring. The important subfolders are:

* `server` containing the server files
* `worker` containing the worker files (render nodes)
* `manager` containing the manager files (manage clusters)
* `dashboard` containing the dashboard (web interface to talk to the server)

This structure explains also the naming conventions adopted to distinguish the different parts of brender.
Each folder contains an individual Flask application. Server, Manager and Worker exchange JSON formatted messages between each other via a Rest API.
Dashboard connects to the Server only and accepts connections from clients (Browsers).

At the moment we have the following addresses:

* http://brender-server:9999
* http://localhost:5000
* http://brender-dashboard:8888
* http://brender-manager:7777


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




