# Scheduling

The scheduling system is supposed to hand out Tasks from the Server to each Worker, through a
Manager. By design, the communication between Server and Workers is *always* mediated by the
Manager, to allow completely customizeable resource management on the computing infrastructure 
available.

At the core of the scheduling system lays the *Dependency Graph*. The Dependency Graph is a DAG
(Directed Acyclic Graph) where each node represents a Task. Tasks are initially stored in the
Server database, in a dedicated collection and are passed on to the Manager upon request.

The DG is generated with a database query to the Tasks collection and, depending on the query, 
can return hundred-thousands of Tasks, which are then stored by the Manager in its own 
database, so that they can be served to the Workers.

## Priority rules

The priority for the execution of a Task is determined by three factors:

- position in the DG
- job priority
- task priority

Therefore, the Task with no parent Task (or all its parent Tasks completed), with the highest 
Job priority, with the highest Task priority will be dispatched first.

## Task requirements and resource allocation

**Note: This feature is not implemented yet.**

When a Worker queries the Manager for a Task, we use the *services* offered by it as a query
parameter to find the highest priority Task that can be executed. For example, a Worker 
might offer `blender_render`, but not `ffmpeg`. This also extends to hardware settings,
so that we can specify a minimum amount of RAM or CPU cores required by a Task.

