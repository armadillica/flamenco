# System architecture
The architecture of Flamenco is simple, hierarchical.

We have one server and one or more managers which control one or more workers each.

![Architecture diagram](img/architecture_diagram.svg)

With this configuration it is possible to have a very generic and simple API on the Server, and 
develop/maintain different type of front-ends for it.

Communication between components happens via HTTP. In particular, Server and Manager use a simple 
and well-defined REST API. This allows third parties to easily implement their Manager, and 
integrate it into Flamenco.

The system is designed with bottom-up communication in mind. For example:

- Worker has a loop that sends requests to the Manager
- Worker sends request a task to the Manager
- Manager checks tasks availability with Server
- Server replies to Manager with available task
- Manager replies to Worker with task to execute
- Worker executes task

This allows us to have loops only at the worker level, and keep the overall infrastructure as 
responsive and available a possible.

## Server
In a Flamenco network, there can be only one server. The functionality of the server consists in:

- storing a list of Managers
- storing Jobs
- generating and storing Tasks (starting from a job)
- dispatch task for a manager
- serving entry points to inspect the status of:
    + jobs
    + tasks
    + workers

## Jobs, tasks and commands
Flamenco is designed to handle several types of jobs, mostly serving computer animated film 
production, for example:

- 3D animation rendering
- simulation baking
- large still image rendering
- video encoding

A Job is the highest level structure, containing all the necessary information on how to process 
the Job itself.
In order to use the computing power of multiple machines, we split the Job into Tasks, according to
the instructions provided. This process is called Job compilation.

- keeping a log of operations related to Jobs (task logging happens on the manager)
- collecting and storing all the data needed to complete a Job


## Render workflow
The render workflow is based on jobs. Once a jobs is added to Flamenco, we automatically create 
tasks (collection of commands) to send to any available worker.

When all tasks are completed, the job is marked as finished.
