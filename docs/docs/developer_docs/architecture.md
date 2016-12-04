
# System architecture


The Flamenco architecture is based on the following scheme.
We have one server, one or more managers which control one or more workers,
and one dashboard.

![Architecture diagram](img/architecture_diagram.png)

With this configuration it is possible to have a very generic and simple
API on the server, and develop/maintain different type of front-ends for it.

Communication between components happens via HTTP, roughly following the
REST pattern. Currently we are not very strict about this, since we do not use
the protocol only to work with documents.

The system is designed with bottom-up communication in mind. Here we have
an example:

- Worker has a loop that sends requests to the Manager
- Worker sends request for job to the Manager
- Manager checks job availability with Server
- Server replies to Manager with available job
- Manager replies to Worker with job to execute

This allows us to have loops only at the worker level, and keep the infarstructure
as responsive and available a possible.


##Jobs, tasks and commands
Flamenco is designed to handle several types of jobs, mostly serving computer
animated film production, for example:

- 3D animation rendering
- simulation baking
- large still image rendering
- video encoding

A Job is the highest level structure, containing all the necessary information
on how to process the Job itself.
In order to use the computing power of multiple machines, we split the Job into
Tasks, according to the instructions provided. This process is called Job
compilation.

##Server

In a Flamenco network, there can be only one server. The functionality of the
server consists in:

- storing Jobs
- storing a list of Managers
- compiling tasks on demand for a manager
- serving entry points to inspect the status of:

    + jobs
    + tasks
    + workers

- keeping a log of operations related to Jobs (task logging happens on the manager)
- collecting and storing all the data needed to complete a Job

### Code layout

- application (the server application)

    + `__init__.py` (app object creation and initialization)
    + job_compilers (user-defined job compilers)
    + modules (the actual components of the server)

        * jobs
        * log
        * main
        * managers
        * projects
        * settings

    + render_settings
    + static (the content of this folder is served via a special route)
    + utils (system utilities - will be renamed to Helpers)

- manage.py (flask-script used in development to start or migrate the server)
- migrations (Alembic migration data)
- test.py (basic suite of tests)


## Many infrastructure components


It could be argued that developing a unified version of server and dashboard
would make things more efficient, but on the other hand the development
of an API for external applications (native application, production software
integrations, etc.) would be needed anyway.

Having dashboard, server and manager as separate components also allows greater
level of security, as well as more resilience (dashboard can go down and the
server can keep running).


## Manager double handshake

Connection between workers and the manager is automatic and follows this procedure
(assuming that the manager is up and running):

* worker starts up
* worker connects to the manager and sends identification info
* manager checks identification and updates worker status or adds worker to the database
* manager confirms connection to the worker
* worker notifies its availability to the manager
* manager checks current jobs and eventually assigns one to the worker


```
# upload to https://www.websequencediagrams.com/ to visualise
title Worker Request Loop

Worker->Manager: register_worker()
Manager-->Worker: identity confirmed
Worker->Manager: get_task() [GET] /generate
note over Manager: confirm Worker as 'enabled'
Manager->Server: [GET] /scheduler/tasks
note over Server
    Pick task from queue
    Set as 'processing'
end note
Server-->Manager: task document
note over Manager
    assign task_id to Worker model
    compile task on the fly
end note
Manager-->Worker: compiled task document
note over Worker: process task
Worker->Manager: [PATCH] /tasks/<task_id>
Manager->Server: [PATCH] /task/<task_id>
Server-->Manager: 200
Manager-->Worker: 200
Worker->Manager: [GET] /tasks/zip/<task_id>
opt if task file NOT cached
    Manager->Server: [GET] /tasks/zip/<task_id>
    Server-->Manager: task_file.zip
    note over Manager: cache the file
end
Manager-->Worker: task_file.zip
```



## Render workflow

The render workflow is based on jobs. Once a jobs is added to Flamenco, we
automatically create tasks (collection of commands) to send to any available
worker.
When all tasks are completed, the job is marked as finished.
