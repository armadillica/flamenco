

## Testing

To run all unit tests, run `go test ./flamenco -v`. To run a specific GoCheck test, run
`go test ./flamenco -v --run TestWithGocheck -check.f SchedulerTestSuite.TestVariableReplacement`
where the argument to `--run` determines which suite to run, and `-check.f` determines the
exact test function of that suite. Once all tests have been moved over to use GoCheck, the
`--run` parameter will probably not be needed any more.

## MISSING FEATURES

- Task queue cleanup. At the moment tasks are stored in the queue forever, since that makes
  it possible to notice a task was canceled while a worker was running it. Eventually such
  tasks should be cleaned up, though.

## Communication between Server and Manager

Flamenco Manager is responsible for initiating all communication between Server and Manager,
since Manager should be able to run behind some firewall/router, without being reachable by Server.

In the text below, `some_fields` refer to configuration file settings.

### Fetching tasks

1. When a Worker ask for a task, it is served a task in state `queued` or `claimed-by-manager` in
   the local task queue (MongoDB collection "flamenco_tasks"). In this case, Manager performs a
   conditional GET (based on etag) to Server at /api/flamenco/tasks/{task-id} to see if the task
   has been updated since queued. If this is so, the task is updated in the queue and the queue
   is re-examined.
2. When the queue is empty, the manager fetches N new tasks from the Server, where N is the number
   of registered workers.

### Task updates and canceling running tasks

0. Pushes happen as POST to "/api/flamenco/managers/{manager-id}/task-update-batch"
1. Task updates queued by workers are pushed every `task_update_push_max_interval_seconds`, or
   when `task_update_push_max_count` updates are queued, whichever happens sooner.
2. An empty list of task updates is pushed every `cancel_task_fetch_max_interval_seconds`, unless an
   actual push (as described above) already happened within that time.
3. The response to a push contains the database IDs of the accepted task updates, as well as
   a list of task database IDs of tasks that should be canceled. If this list is non-empty, the
   tasks' statuses are updated accordingly.
