.. _api:

***********
Brender API
***********

Server
======

Project
-------

.. http:get:: /projects

   The get all projects available.

   **Example request**:

   .. sourcecode:: http

      GET /projects HTTP/1.1
      Host: brender:9999
      Accept: application/json

   **Example response**:

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

   :reqheader Accept: the response content type depends on
                      :mailheader:`Accept` header
   :reqheader Authorization: optional OAuth token to authenticate
   :resheader Content-Type: this depends on :mailheader:`Accept`
                            header of request
   :statuscode 200: no error
   :statuscode 404: there are no project


.. http:get:: /projects/(int:project_id)

   The get the project with (`project_id`).

   **Example request**:

   .. sourcecode:: http

      GET /projects/12 HTTP/1.1
      Host: brender:9999
      Accept: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: text/javascript

      {
        "project_id": 12,
        "name": "Caminandes",
        "description": "One Llama"
      }

   :query sort: one of ``hit``, ``created-at``
   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :reqheader Accept: the response content type depends on
                      :mailheader:`Accept` header
   :reqheader Authorization: optional OAuth token to authenticate
   :resheader Content-Type: this depends on :mailheader:`Accept`
                            header of request
   :statuscode 200: no error
   :statuscode 404: there's no project




    /projects
    GET : returns all projetcs (JSON) => 200
    POST : adds a new project and returns it (JSON) => 201

    /projects/{int : id}
    GET : returns project (JSON) => 200 (or 404 if not found)
    PUT : modify project and returns it (JSON) => 201 (or 404 if not found)
    DELETE : deletes projects and all its jobs => 204

Worker
------

    /workers
    GET : returns all informations about workers (JSON) => 200
    POST : Modify status of a worker => 204
    /workers/{int : id}
    GET : returns worker’s informations (JSON) => 200

Manager
-------

    /managers
    GET : returns manager’s list (JSON) => 200
    POST : connect a new manager and returns its uuid (JSON) => 200
    /managers/{uuid}
    PATCH : update total_workers and returns it (JSON) => 200

Setting
-------

    /settings
    GET : returns settings list (JSON) => 200
    POST : updates or creates settings => 204
    /settings/render
    GET : returns render_settings paths (JSON) => 200

FileBrowser
-----------
    /browse
    GET : returns browse of project’s root folder (JSON) => 200
    /browse/{path}
    GET : returns browse of path (JSON) => 200

Job
---
    /jobs
    GET : returns jobs list (JSON) => 200
    POST : creates new job and returns it => 201

    /jobs/{job_id}
    GET : returns job (JSON) => 200 (or 404 if not found)
    PUT : sends command to job (stop, start, reset, etc…) and returns the job => 200 (or 400 if bad command)
    DELETE : delete job and relative tasks => 204
    /jobs/delete
    POST : delete jobs from id list given in args => 204

Task
----

    GET : returns tasks list (JSON) => 200
    POST : update task status according to id => 204



Manager
=======

Task:
/tasks
POST : creates a new task and returns it (JSON) => 202
/tasks/{id}
PATCH : update task’s status => 204
DELETE : delete task and kill processes and returns  it => 202
Worker:
/workers
GET : returns worker list (JSON) => 200
POST : connects a new worker and send its uuid => 204
/workers/{id}
GET : returns worker’s informations (return worker’s request)
PATCH : edit worker’s status and returns it => 200

Setting:
/settings
GET : returns settings list (if group == “render” then, returns file in render_settings directory) (JSON) => 200
POST : update settings => 204
/settings/{name}
GET : returns setting (JSON) => 200
PATCH : edit setting and returns it (JSON) => 200




Worker
======

GET / : redirect to /info
GET /info : returns worker’s informations => 200
POST /execute_task : run a task => 200 (or 500 if it fails)
GET /pid : returns pid of running task (JSON) => 200
DELETE /kill/{pid} : kill process => 204
