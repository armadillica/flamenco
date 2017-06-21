# Installation & Configuration

This guide focuses on installing Flamenco while relying on the
[Blender Cloud](https://cloud.blender.org/) service. If you are interested in setting up the entire
Flamenco stack on your own infrastructure, you should check out the developer docs, as well as the
source code.

We are going to assume that you have a Blender Cloud subscription, and that you already created a
project. If you haven't, log in and create a [new project](https://cloud.blender.org/p/).

Here is an overview of the steps required to get Flamenco up an running.

- Enable your project for Flamenco
- Download and configure your Manager
- Download and configure your Worker
- Configure the Blender Cloud Add-on and start rendering


!!! note
    This is meant as a step-by-step quick install guide. For more in-depth installation and
    configuration documents, check out the sources of each component.


## Enable project for Flamenco

You can enable for Flamenco any Blender Cloud project you are part of, by going to the main project
view (the homepage of a project), clicking on "Edit Project" and then "Flamenco". Alternatively,
you can visit the url `https://cloud.blender.org/p/<your_project_url>/edit/flamenco`.
Once in the Flamenco page, click on "Enable for Flamenco". After clicking, some things will happen:

- you will be able to see your project in [Flamenco](https://cloud.blender.org/flamenco/), where you
  will manage jobs and tasks
- a Flamenco Manager will be attached to the project (if you had no Manager, one will be created
  for you, otherwise the existing one will be used)


## Flamenco Manager

Flamenco Manager is one of the components you are responsible of running on your infrastructure
(or on your local machine). The Manager handles the communication between your Workers, which you
also run locally, and the Server, which runs on the [cloud.blender.org]() website.


### Manager installation and configuration

Install [MongoDB 3.2 or newer](https://docs.mongodb.com/manual/administration/install-community/),
[download](https://www.flamenco.io/download/) the Flamenco Manager package for your platform and
unzip. Copy `flamenco-manager-example.yaml` to `flamenco-manager.yaml` and edit the file to suit
your needs.
These are the minimal changes you'll have to do to get Flamenco Manager running:

- Update `own_url` to point to the IP address or hostname by which your machine can be reached by
  the workers.
- Set the `manager_id` and `manager_secret` to the values obtained from Flamenco on Blender Cloud.
- Either generate TLS certificates (TLS is the we-are-no-longer-living-in-the-90ies-name for SSL),
  or remove the `tlskey` and `tlscert` options from your `flamenco-manager.yaml` file.
- Update the `variables` for your render farm. The `blender` variable should point to the Blender
  executable where it can be found *on the workers*.

At this point, you can start the Manager by runnin the `./flamenco-manager` command.


## Flamenco Worker

Flamenco Workers are in charge of executing tasks they fetch from the Manager. Workers are written
in Python 3.5, so they will run on any system that supports Python 3.5 or newer.


### Worker installation and configuration

Make sure you have Python 3.5+ installed on your system. Download and unzip the [latest version of
the Worker](https://www.flamenco.io/download/) and install it with the  `pip3 install
flamenco_worker-xxxx.whl` command. We recommend performing this installation command in a
[virtual environment](https://docs.python.org/3.5/library/venv.html), so that A) it doesn't require
root rights, and B) dependencies can be installed without interaction with the rest of your system.

Create a `flamenco-worker.cfg` file in a directory where you are going to run the worker command
(can be any directory on the system).

All configuration keys should be placed in the `[flamenco-worker]` section of the config file.
At least take a look at:

- `manager_url`: Flamenco Manager URL.
- `task_types`: Space-separated list of task types this worker may execute.
- `task_update_queue_db`: filename of the SQLite3 database, holding the queue of task updates to be
  sent to the Master. If this file does not exist yet, Flamenco Manager will create it.

Run the Worker with the `flamenco-worker` command. The Worker will automatically connect to the
Manager, negotiate a worker ID and password, and start querying for tasks. The worker ID and
password will be stored in `$HOME/.flamenco-worker.cfg`
