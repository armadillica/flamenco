.. _worker_api:

**********
Worker API
**********

.. contents::
   :local:
   :depth: 3


Info
====

- GET / : redirect to /info
- GET /info : returns worker’s informations => 200
- POST /execute_task : run a task => 200 (or 500 if it fails)
- GET /pid : returns pid of running task (JSON) => 200
- DELETE /kill/{pid} : kill process => 204
