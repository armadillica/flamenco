# Flamenco Worker

This is the Flamenco Worker implemented in Python 3.


## Configuration

Configuration is read from three locations:

- A hard-coded default in the Python source code.
- `flamenco-worker.cfg` in the current working directory.
- `$HOME/.flamenco-worker.cfg`.

When those files do not exist, they are skipped (i.e. this is not an error). They
should be in INI format, as specified by the
[configparser documentation](https://docs.python.org/3/library/configparser.html)

### Configuration contents:

All configuration keys should be placed in the `[flamenco-worker]` section of the
config files.

- `manager_url`: Flamenco Manager URL.
- `worker_id`: ID of the worker, handed out by the Manager upon registration (see
  Registration below) and used for authentication with the Manager.
- `worker_secret`: Secret key of the worker, given to the Manager upon registration
  and authentication.
- `job_types`: Space-separated list of job types this worker may execute.
- `task_update_queue_db`: filename of the SQLite3 database holding the queue of task
  updates to be sent to the Master.

### TODO

- Certain settings are currently only settable by editing constants in the Python source code.
  It might be nice to read them from the config file too, at some point.
- Update worker address in MongoDB when communicating with it.

## Invocation

Install using `pip install -e .` for development, or `setup.py install` for production.
This creates a command `flamenco-worker`, which can be run with `--help` to obtain
a list of possible CLI arguments.

## Registration

If the configuration file does not contain both a `worker_id` and `worker_secret`, at startup
the worker will attempt to register itself at the Master.
Once registered via a POST to the manager's `/register-worker` endpoint, the `worker_id` and
`worker_secret` will be written to `$HOME/.flamenco-worker.cfg`

## Task fetch & execution

1. A task is obtained by the FlamencoWorker from the manager via a POST to its `/task` endpoint.
   If this fails (for example due to a connection error), the worker will retry every few seconds
   until a task fetch is succesful.
2. The task is given to a TaskRunner object.
3. The TaskRunner object iterates over the commands and executes them.
4. At any time, the FlamencoWorker can be called upon to register activities and log lines,
   and forward them to the Manager. These updates are queued in a SQLite3 database, such that
   task execution isn't interrupted when the Manager cannot be reached.
5. A separate coroutine of TaskUpdateQueue fetches updates from the queue, and forwards them to
   the Master, using a POST to its `/tasks/{task-id}/update` endpoint.
   **TODO:** the response to this endpoint may indicate a request to abort the currently running
   task. This should be implemented.


## Shutdown

Pressing [CTRL]+[C] will cause a clean shutdown of the worker.
If there is a task currently running, it will be aborted without changing its status. Any pending task updates are sent to the Manager, and then the Manager's `/sign-off` URL is
POSTed to, to indicate a clean shutdown of the worker. Any active task that is still
assigned to the worker is given status "claimed-by-manager" so that it can be re-activated
by another worker.


## Systemd integration

To run Flamenco Worker as a systemd-managed service, copy `flamenco-worker.service` to
`/etc/systemd/system/flamenco-worker.service`, then run `systemctl daemon-reload`.

After installation of this service, `systemctl {start,stop,status,restart} flamenco-worker`
commands can be used to manage it. To ensure that the Flamenco Worker starts at system boot,
use `systemctl enable flamenco-worker`.


## Signals

Flamenco Worker responds to the following POSIX signals:

- `SIGINT`, `SIGTERM`: performs a clean shutdown, as described in the Shutdown section above.
- `SIGUSR1`: logs the currently scheduled asyncio tasks.
