Flamenco Server Changelog
=========================

## Version 2.0.6 (released 2017-10-06)

- Removed the retrieval of Manager authentication codes. Since Blender Cloud now stores them hashed,
  this retrieval is no longer possible. Instead, the automatic linking of Managers should be used.


## Version 2.0.5 (released 2017-09-07)

- Added automatic linking of Managers.


## Version 2.0.4 (released 2017-06-23)

- Task updates from the Manager, on tasks that do not exist, are now accepted but ignored by
  the Server. This means that someone can archive a job, and task updates for that job will
  no longer hang indefinitely in the Manager's outgoing queue.
- Fixed issue where the `flamenco-admin` role was needed to create a new job.


## Version 2.0.3 (released 2017-06-09)

- Users are now required to have the `flamenco-user` role in order to use Flamenco.
- Users can create their own Managers (max 3).
- Managers can be linked to projects.
- The authentication token for a Manager can be retrieved and reset by owners.
- Managers can now push path replacement variables.


## Version 2.0.2 (released 2017-04-26)

- Re-queueing a task on a completed job now re-queues the job too.
- Reduced log level when receiving task updates from manager.


## Version 2.0.1 (released 2017-04-07)

- Added support for task types. This requires Flamenco Manager 2.0.4+ and Flamenco Worker 2.0.2+


## Version 2.0 (released 2017-03-29)

- First release of Flamenco based on the Pillar framework.
