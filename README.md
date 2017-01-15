# Flamenco 2.0

Development repo for Flamenco 2.0 (originally known as brender). Flamenco is a
Free and Open Source Job distribution system for render farms.

Warning: currently Flamenco is in beta stage, and can still change in major ways.


## Quick install with Docker
You can test Flamenco in an easy and quick way using [Docker](https://www.docker.com/) images.

### Directory and repository setup
Before we proceed with the configuration of our containers we have to set up a few directories. In this example, we will set up the directory in ```
/media/data/```, but any directory would work.

```
$ cd /media/data/
```

Let's clone the repository:

```
$ git clone https://github.com/armadillica/flamenco.git
```

This means that our repository directory is `/media/data/flamenco` (we will need this path soon).

### MySQL container
Now we start the container, from MySQL Docker image. Keep in mind that Flamenco also works with SQLite and Posgres.

```
$ docker run -ti -p 3306:3306 --name mysql -e MYSQL_ROOT_PASSWORD=root mysql
```
This database will be used both by the server and the manager.

### Server
The Flamenco server needs to be linked to the mysql container, and also needs to have a few volumes mounted. The following command takes care of everything.

```
$ docker run -ti -p 9999:9999 --name flamenco_server --link mysql:mysql \
-v /media/data/flamenco/flamenco/server:/data/git/server \
-v /media/data/flamenco_data/storage/shared:/data/storage/shared \
-v /media/data/flamenco_data/storage/server:/data/storage/server \
armadillica/flamenco_server_dev
```

### Manager

The Manager is written in [Go](https://golang.org/). The Manager is documented
in its own [README](./packages/flamenco-manager-go/README.md).

### Worker

The Flamenco worker is a very simple standalone component implemented in
[Python](https://www.python.org/). The Worker is documented
in its own [README](./packages/flamenco-worker-python/README.md).


## Developer installation

In order to install Flamenco, we recommend to set up a Python virtual environment.

```
$ sudo easy_install virtualenv
```

On Linux this might work better:

```
$ sudo apt-get install python-virtualenv
```

Once you have virtualenv installed, just fire up a shell and create your own environment. You may want to create this folder inside of the Flamenco folder:

```
$ cd Flamenco
$ virtualenv venv
New python executable in venv/bin/python
Installing distribute............done.
```

Now, whenever you want to work on a project, you only have to activate the
corresponding environment. On OS X and Linux, do the following:

```
$ . venv/bin/activate
```

Now you can just enter the following command to get Flask activated in your
virtualenv:

## Core dependencies

The project has been developed for `python2.7`. We will move to `python3`
eventually.

On Unix systems, to install python dependencies, you may need to install
`python-dev` package.

On OSX, in order to prevent some warnings, you might need to run:

```
$ ARCHFLAGS=-Wno-error=unused-command-line-argument-hard-error-in-future
```

Then we just install all the packages required (run this on all systems)

```
$ pip install -r requirements.txt
```

Databases are managed by `MySQL` or `SQLite` (for testing only, don't use in production).


### Gulp file for the Dashboard
In order to streamline UI development of the Dashboard, we use Jade templating
and Sass for the CSS generation. In oder to generate the templates and CSS needed
by the dashboard, you need to install [NodeJS](https://nodejs.org/en/) and run
the following commands.

#### OSX
```
cd flamenco/dashboard
npm install -g gulp
npm install
gulp
```

#### Debian Linux Wheezy and Ubuntu 14.04

```
sudo aptitude install python3-pip libmysqlclient-dev build-essential python-dev libjpeg8 libjpeg8-dev libfreetype6 libfreetype6-dev zlib1g-dev python-pip

sudo pip install virtualenv
# install blender BAM using pip3
sudo pip3 install blender-bam

# install python deps (remember to `source bin/activate` first!)
pip install -r $FLAMENCODIR/requirements.txt

# dashboard dependencies
cd flamenco/dashboard

# this is needed only on wheezy distribution
sudo echo "deb http://ftp.us.debian.org/debian wheezy-backports main" >> /etc/apt/sources.list
sudo apt-get update

# On linux you can install NodeJS using the package manager.
sudo apt-get install nodejs nodejs-legacy curl
sudo curl -L --insecure https://www.npmjs.org/install.sh | bash
sudo npm install -g gulp
npm install
gulp
```

## Running Flamenco
It's pretty simple. Move into each folder ( server, manager, dashboard, worker)
and run:

```
$ ./manage.py runserver # will start the different components
```

When running this command for the Manager for the first time, you will be
prompted for some configuration parameters.

If you now visit `http://localhost:8888` with your web browser you should see the dashboard!

It is also possible to configure the different applications. You may find a `config.py.example`, so you can rename it to `config.py` and edit it before run the application.

## Architecture
The important subfolders are:

* `server` containing the server files
* `worker` containing the worker files (render nodes)
* `manager` containing the manager files (manage clusters)
* `dashboard` containing the dashboard (web interface to talk to the server)

This structure explains also the naming conventions adopted to distinguish the
different parts of Flamenco.
Each folder contains an individual Flask application (except for the worker).
Server, Manager and Worker exchange JSON formatted messages between each other
via a REST API.
Dashboard connects to the Server only and accepts connections from clients (Browsers).


### About the web interface
Frameworks and tools used by the interface are:

* jQuery
* Bootstrap
* DataTables

### User and Developer documentation

The documentation is built with Sphinx and uses the readthedocs.org theme, so
make sure you have it installed. Instructions are available here:

`https://github.com/snide/sphinx_rtd_theme`

The `_build` contains the locally compiled documentation, which does not need
to be committed to the branch.
