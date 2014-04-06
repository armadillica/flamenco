# brender 2.0


Development repo for brender 2.0 (the original version 1.0 is here https://github.com/oenvoyage/brender). This is the Flask-based version, a new direction taken after getting some feedback from Sergey and Keir.

## Developer installation
Basic requirement at the moment are:

* [Python 2.7](http://www.python.org/download/releases/2.7/)
* [Flask 0.10](https://pypi.python.org/pypi/Flask/0.10.1)
* [peewee (ORM library)](https://pypi.python.org/pypi/peewee/2.1.5)
* [virtualenv (optional)]()
* [psutil (Process Utility)](https://pypi.python.org/pypi/psutil/1.1.3)
* [gocept (Cache Library)](https://pypi.python.org/pypi/gocept.cache/0.6.1)

Following the Flask idea, we install the server, workers and dashboard unsing virtualenv. Text copied from the Flask guide.

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

```
$ pip install Flask
```

At this point you should install peewee as well:

```
$ easy_install peewee
```
Psutil is needed for gathering system usage/performance stats on the worker. Ideally psutil is needed only on the workers.
For Linux :

```
$ pip install psutil
```

For OS X :

```
$ ARCHFLAGS=-Wno-error=unused-command-line-argument-hard-error-in-future pip install psutil
```

then install

```
$ pip install gocept.cache
```

Congratulations, brender and its dependencies should be correctly installed and ready to run. As a final step we should add a couple of hostnames into the `/ets/hosts` file:

```
127.0.0.1	brender-server
127.0.0.1	brender-flask
```

## Running brender
It's pretty simple. Move into the brender folder and run - in three different terminals:

```
$ python brender.py server  		# will start the server
$ python brender.py worker			# will start the worker
$ python brender.py dashboard		# will start the dashboard
```

If you now visit `http://brender-flask:8888` with your web browser you should see the dashboard!

## Architecture
At the moment the content of the `brender` folder is quite messy due to refactoring. The important subfolders are:

* `server` containing the server files
* `worker` containing the worker files (render nodes)
* `dashboard` containing the dashboard (web interface to talk to the server)

This structure explains also the naming conventions adopted to distinguish the different parts of brender.
Each folder contains an individual Flask application. Server and Worker exchange JSON formatted messages between each other via HTTP, using GET or POST methods.
Dashboard connects to the Server only and accepts connections from clients (Browsers).

At the moment we have the following addresses:

* http://brender-server:9999
* http://localhost:5000
* http://brender-flask:8888


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




