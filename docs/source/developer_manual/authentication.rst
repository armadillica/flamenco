.. _authentication:


**************
Authentication
**************

Authentication and authorization of users should happen for every component of
the Flamenco network.

In general, we propose to do the following:

- Server stores users and roles (primarily to associate them with jobs)
- Dashboard checks with server for users auth to give them access
- Managers have their own auth system, that allows only owners to update settings
- Workers have optional authentication (which is defined at the Manager level)


Stages of authentication and authorization

User is registered or not on the server (check via SDK)
Server returns token for subsequent requests
User

Roles
=====

Possible user roles:

- admin (super admin of the Flamenco network)
- manager_<manager_uuid> (owner of a manager). When doing requests to a manager,
the manager uuid gets cross referenced with the user role


Project memberships
===================

User capabilities could also defined on a per-project basis, allowing a user to
view all jobs for any project, but to submit jobs only to one.


Flamenco SDK
============

Collection of classes used to interact with the Flamenco Server. Main features
are:

- Client authentication
- Client registration (coming soon, after Blender-ID)
- Object wrapper for Users, Managers, Jobs and Tasks

The Flamenco SDK will be used in:

- Dashboard
- Manager
- Blender Python Add-on

