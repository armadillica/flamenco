"""Classes for JSON documents used in upstream communication."""

import attr


@attr.s
class Activity:
    """Activity on a task."""

    activity = attr.ib(default='', validator=attr.validators.instance_of(str))
    current_command_idx = attr.ib(default=0, validator=attr.validators.instance_of(int))
    task_progress_percentage = attr.ib(default=0, validator=attr.validators.instance_of(int))
    command_progress_percentage = attr.ib(default=0, validator=attr.validators.instance_of(int))


@attr.s
class MayKeepRunningResponse:
    """Response from the /may-i-run/{task-id} endpoint"""

    may_keep_running = attr.ib(validator=attr.validators.instance_of(bool))
    reason = attr.ib(default=None,
                     validator=attr.validators.optional(attr.validators.instance_of(str)))
