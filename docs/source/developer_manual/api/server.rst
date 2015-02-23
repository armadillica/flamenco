.. _server_api:

**********
Server API
**********

.. contents::
   :local:
   :depth: 3


Project
=======

Get Projects list
-----------------

Display the full list of a projects. By default, inactive projects are not included. Pagination will come in the future.

.. sourcecode:: http

   GET /projects HTTP/1.1


Response
~~~~~~~~

.. csv-table::
    :header: "Property", "Type", "Description"
    :widths: 20, 20, 30

    "id", "integer", "The id of a project. **Required**"


.. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: text/javascript

    {
      12: {
        "name": "Caminandes",
        "description": "One Llama"
      },
      11: {
        "name": "Project Gooseberry",
        "description": "One Berry"
      },
      
    }


View single project
-------------------

View details regarding a single project.

.. sourcecode:: http

   GET /projects/1 HTTP/1.1


Request
~~~~~~~

.. csv-table::
    :header: "Property", "Type", "Description"
    :widths: 20, 20, 30

    "id", "integer", "The id of a project"


Response
~~~~~~~~

.. csv-table::
    :header: "Property", "Type", "Description"
    :widths: 20, 20, 30

    "id", "integer", "The id of a project"
    "is_active", "boolean", "Flag to display if the project is active"
    "name", "string", "The name of a project"
    "path_linux", "string", 
    "path_osx", "string", 
    "path_server", "string", 
    "path_win", "string", 
    "render_path_linux", "string", 
    "render_path_osx", "string" 
    "render_path_server", "string", 
    "render_path_win", "string", 

.. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: text/javascript

    {
      "id": 1, 
      "is_active": true, 
      "name": "Encoded cube", 
      "path_linux": "", 
      "path_osx": "/Users/fsiddi/pampa/shots", 
      "path_server": "/Users/fsiddi/pampa/shots", 
      "path_win": "", 
      "render_path_linux": "", 
      "render_path_osx": "/Volumes/PROJECTS/storage/render", 
      "render_path_server": "/Volumes/PROJECTS/storage/render", 
      "render_path_win": ""
    }


Worker
======

    - /workers
    - GET : returns all informations about workers (JSON) => 200
    - POST : Modify status of a worker => 204
    - /workers/{int : id}
    - GET : returns worker’s informations (JSON) => 200

Manager
=======

    - /managers
    - GET : returns manager’s list (JSON) => 200
    - POST : connect a new manager and returns its uuid (JSON) => 200
    - /managers/{uuid}
    - PATCH : update total_workers and returns it (JSON) => 200

Setting
=======

    - /settings
    - GET : returns settings list (JSON) => 200
    - POST : updates or creates settings => 204
    - /settings/render
    - GET : returns render_settings paths (JSON) => 200

FileBrowser
===========
    - /browse
    - GET : returns browse of project’s root folder (JSON) => 200
    - /browse/{path}
    - GET : returns browse of path (JSON) => 200

Job
===
    - /jobs
    - GET : returns jobs list (JSON) => 200
    - POST : creates new job and returns it => 201

    - /jobs/{job_id}
    - GET : returns job (JSON) => 200 (or 404 if not found)
    - PUT : sends command to job (stop, start, reset, etc…) and returns the job => 200 (or 400 if bad command)
    - DELETE : delete job and relative tasks => 204
    - /jobs/delete
    - POST : delete jobs from id list given in args => 204

Task
====

    - GET : returns tasks list (JSON) => 200
    - POST : update task status according to id => 204

