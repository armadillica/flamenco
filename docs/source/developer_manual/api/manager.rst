.. _manager_api:

***********
Manager API
***********

.. contents::
   :local:
   :depth: 3


Tasks
=====

Create new task
---------------

Send task definition to the manager. This will trigger the task compiler. Returns 202

.. sourcecode:: http

    POST /tasks HTTP/1.1


Request
~~~~~~~

.. csv-table::
    :header: "Property", "Type", "Description"
    :widths: 20, 20, 30

    "priority", "integer", "The priority"
    "settings", "string", "Settings for the task, which will be interpreted by the compiler"
    "task_id", "integer", ""
    "type", "string", "The compiler to use"
    "parser", "string", "The parser to use against such task"


Response
~~~~~~~~

.. csv-table::
    :header: "Property", "Type", "Description"
    :widths: 20, 20, 30

    "id", "integer", "The id of a project"
    "worker_id", "integer", ""
    "priority", "integer", ""
    "frame_start", "integer", ""
    "frame_end", "integer", ""
    "frame_current", "integer", ""
    "status", "string", ""
    "format", "string", ""

.. sourcecode:: http

    HTTP/1.1 202 OK
    Vary: Accept
    Content-Type: text/javascript

    {
      "id" : 12,
      "worker_id" : 1,
      "priority" : 10,
      "frame_start" : 5,
      "frame_end" : 10,
      "frame_current" : 5,
      "status" : "rendering",
      "format" : ""
    }


Update task
-----------

Partially update a task. Returns 204.

.. sourcecode:: http

    PATCH /tasks/1 HTTP/1.1


Delete task
-----------

Delete a task. Returns 202.

.. sourcecode:: http

    DELETE /tasks/1 HTTP/1.1



Workers
=======

Get list of workers
-------------------

Get the list of available workers. In case of virtual workers (or in general a private manager).

.. sourcecode:: http

    GET /workers HTTP/1.1


Response
~~~~~~~~

.. csv-table::
    :header: "Property", "Type", "Description"
    :widths: 20, 20, 30

    "host_name", "object", "Properties of a worker"

.. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: text/javascript

    {
      "fsiddi-macpro.local": {
        "activity": null, 
        "connection": "online", 
        "current_task": null, 
        "hostname": "fsiddi-macpro.local", 
        "id": 1, 
        "ip_address": "127.0.0.1", 
        "log": null, 
        "port": 5000, 
        "status": "enabled", 
        "system": "Darwin 14.1.0", 
        "time_cost": null
      }
    }


Register worker
---------------

This happens when a worker registers itself with the manager. Should be automatic.

.. sourcecode:: http

    POST /workers HTTP/1.1


Request
~~~~~~~

.. csv-table::
    :header: "Property", "Type", "Description"
    :widths: 20, 20, 30

    "hostname", "string", "The hostname of the worker"
    "system", "string", "The OS of the worker"



Response
~~~~~~~~

.. csv-table::
    :header: "Property", "Type", "Description"
    :widths: 20, 20, 30

    "host_name", "object", "Properties of a worker"

.. sourcecode:: http

    HTTP/1.1 204 OK
    Vary: Accept
    Content-Type: text/javascript

    {
      "fsiddi-macpro.local": {
        "activity": null, 
        "connection": "online", 
        "current_task": null, 
        "hostname": "fsiddi-macpro.local", 
        "id": 1, 
        "ip_address": "127.0.0.1", 
        "log": null, 
        "port": 5000, 
        "status": "enabled", 
        "system": "Darwin 14.1.0", 
        "time_cost": null
      }
    }


Get worker info
---------------

Display worker info - assuming the worker is running.

.. sourcecode:: http

    GET /workers/1 HTTP/1.1


Request
~~~~~~~

.. csv-table::
    :header: "Property", "Type", "Description"
    :widths: 20, 20, 30

    "id", "integer", "The worker id"



Response
~~~~~~~~

.. csv-table::
    :header: "Property", "Type", "Description"
    :widths: 20, 20, 30

    "hostname", "string", "Hostname of the worker"
    "mac_address", "string", ""
    "system", "string", ""
    "update_frequent", "object", ""
    "update_less_frequent", "object", ""


.. sourcecode:: http

    HTTP/1.1 204 OK
    Vary: Accept
    Content-Type: text/javascript

    {
        "hostname": "fsiddi-macpro.local", 
        "mac_address": 158929712651, 
        "system": "Darwin 14.1.0", 
        "update_frequent": {
            "load_average": {
                "15min": 2.18, 
                "1min": 2.18, 
                "5min": 2.11
            }, 
            "worker_cpu_percent": 7.0
        }, 
        "update_less_frequent": {
            "worker_architecture": "x86_64", 
            "worker_disk_percent": 90.7, 
            "worker_mem_percent": 56.7, 
            "worker_num_cpus": 16
        }
    }



Edit worker status
------------------

Edit worker status and returns it. This request comes from ther worker.

.. sourcecode:: http

    PATCH /workers/1 HTTP/1.1


Request
~~~~~~~

.. csv-table::
    :header: "Property", "Type", "Description"
    :widths: 20, 20, 30

    "status", "integer", "The status. Currently supports *rendering*, *available*."



Response
~~~~~~~~

.. csv-table::
    :header: "Property", "Type", "Description"
    :widths: 20, 20, 30

    "task_id", "integer", "Id of the task currently assigned to the worker"


.. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: text/javascript

    {
        "task_id": 1
    }


.. Settings API will be exposed later
  Setting:
  /settings
  GET : returns settings list (if group == “render” then, returns file in render_settings directory) (JSON) => 200
  POST : update settings => 204
  /settings/{name}
  GET : returns setting (JSON) => 200
  PATCH : edit setting and returns it (JSON) => 200


