# Permissions System

Here are some notes about the current permission system, extracted from 
[developer.blender.org](https://developer.blender.org/T51039).

- Users with just `subscriber` or `demo` role can only view Flamenco. This is limited to projects 
  they are part of, and Managers they are owner of.
- Users with either `subscriber` or `demo` role AND `flamenco-admin` role have unlimited access to
  all of Flamenco.
- Users need either `subscriber` or `demo` role AND `flamenco-user` role to have any write access to
  Flamenco, even when they are members of a project that's set up for Flamenco.
- Ownership of a Manager is defined by a single group. All members of that group are considered 
  equal.
- Owners of a Manager can link that manager with projects they manage (i.e. have PUT access to).
- Owners of a Manager can unlink that manager from any project.
- Owners of a Manager can manage jobs/tasks/task logs belonging to projects they have PUT access to.
- Members of a project that are not Owners of a Manager can manage jobs/tasks/task logs belonging to
  projects they have PUT access to.
- Owners of a Manager can see, delete, and create authentication tokens for the Manager's service 
  account. For now, let's just allow a single authentication token per Manager.
