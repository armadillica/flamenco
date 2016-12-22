"""Classes for JSON documents used in upstream communication."""

import attr


@attr.s
class Activity:
    """Activity on a task."""

    description = attr.ib(validator=attr.validators.instance_of(str))
    current_cmd_name = attr.ib(validator=attr.validators.instance_of(str))
    percentage_complete_task = attr.ib(validator=attr.validators.instance_of(int))
    percentage_complete_command = attr.ib(validator=attr.validators.instance_of(int))

