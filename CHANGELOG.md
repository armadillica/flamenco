Flamenco Server Changelog
=========================

## Version 2.1 (under development)

- Allow jobs to be started in 'paused' state. Such jobs are ignored by the Manager, and have to be
  manually queued to start.
- Added a `create-video` task which can convert an image sequence to a video. This is currently only
  used in `blender-render` jobs that render an image sequence, and requires Blender Cloud add-on
  1.9.5 or newer.
- Re-queue an active job when a task goes to status `claimed-by-manager` and no `active` tasks
  remain. This task status change happens when a Worker returns its task to the Manager (requires
  Manager 2.2 or newer).
- Allow users to change the priority of jobs. Previously the job priority was determined at creation
  time and could not be changed afterwards. Note that any running task is still finished. Only when
  a Worker asks for a new task will the new priority be taken into account.


## Version 2.0.7 (released 2018-07-06)

- Moved to new deployment model (see Blender Cloud deployment), so removed `rsync_ui.sh` and
  `deploy.sh`.
- Replaced Jade with Pug.
- Re-queueing a single task of a completed job no longer re-queues all tasks.
- Task fields `_updated` and `_etag` are now properly updated after receiving task updates from
  Flamenco Manager.
- Added 'Re-queue all tasks' button. Note that seeing this button does not mean there are actually
  any failed tasks; it is always shown when the job status is active or queued.
- Blender Render jobs now render to a job-specific intermediate directory. The name of that
  directory is now `{job name}__intermediate-{job creation timestamp}`.


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
