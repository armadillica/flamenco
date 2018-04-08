# System architecture

The architecture of Flamenco is simple, hierarchical.

In a production setup we have one Server and one or more Managers which control one or
more Workers each.

![Architecture diagram](img/architecture_diagram.svg)

With this configuration it is possible to have a very generic and simple API on the Server, and
develop/maintain different type of front-ends for it.

Communication between components happens via HTTP. In particular, Server and Manager use a simple
and well-defined REST API. This allows third parties to easily implement their Manager, and
integrate it into Flamenco. Flamenco ships with its own Free and Open Source Manager and Worker
implementations.

The whole system is designed with bottom-up communication in mind. For example:

- Worker has a loop that sends requests to the Manager
- Worker sends request a task to the Manager
- Manager checks Tasks availability with Server
- Server replies to Manager with available Tasks
- Manager replies to Worker with a Task to execute
- Worker executes the Commands of a Task and reports progress to the Manager

By using update buffers on Managers and Worker components we can keep the overall
infrastructure as resilient, responsive and available a possible.

## Server

In a Flamenco network, there can be only one server. The functionality of the server consists in:

- storing a list of Managers
- storing Jobs
- generating and storing Tasks (starting from a Job)
- dispatch Tasks to a Manager
- serving entry points to inspect the status of:
    + Jobs
    + Tasks
    + Workers

The Server software is based on [Pillar](https://pillarframework.org/), the Free and Open Source
CMS that provides agnostic user authentication, resource and project management. It requires:

- Linux, macOS or Windows
- Python 3.6
- MongoDB
- Redis
- RabbitMQ

## Manager

The goal of the Manager, as the name suggests, is to handle the workload provided by the Server
and leverage the computing resources available (Workers) to complete the Tasks as soon as possible.

Because the communication between Server and Manager happens via a semi-RESTful API, a Manager
can be implemented in many ways. At Blender we implemented a Manager in Go, which is available
as Free and Open Source software. It requires:

- Linux, macOS or Windows
- MongoDB
- [Go](https://golang.org/) (only when building, not a runtime requirement)


## Worker

The lowest-level component of the Flamenco infrastructure, a Worker is directly responsible for
the execution of a Task, which is composed by an ordered series of Commands. Similarly to the
Manager, Blender provides a Free and Open Source implementation, with the following requirements:

- Linux, macOS or Windows
- Python 3.5 or greater

## Jobs, Tasks and Commands

Flamenco is designed to handle several types of jobs, mostly serving computer animated film
production, for example:

- 3D animation rendering
- simulation baking
- distributed still image rendering
- video encoding

A Job is the highest level structure, containing all the necessary information on how to process
the Job itself.
In order to distribute the execution of a Job, we split it into Tasks, according to the instructions
provided. This process is called *Job compilation*.

A task is essentially a list of Commands. Each worker can claim one (or more tasks) to execute,
which means it will sequentially run all the Commands contained in it.

- keeping a log of operations related to Jobs (task logging happens on the manager)
- collecting and storing all the data needed to complete a Job

## Components and processes documentation

In the rest of the documentation we cover more in depth the different components of the
architecture, as well as the various processes (Job creation, Manager and Worker management, etc.).
