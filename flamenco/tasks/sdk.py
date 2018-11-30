import logging

from pillarsdk.resource import List
from pillarsdk.resource import Find
from pillarsdk.resource import Patch


class Task(List, Find, Patch):
    """Task class wrapping the REST nodes endpoint
    """
    path = 'flamenco/tasks'
    ensure_query_projections = {'project': 1, 'job': 1}

    @classmethod
    def find(cls, resource_id, params=None, api=None):
        # THE HORROR.
        task = super().find(resource_id, params, api)
        if isinstance(task.log, logging.Logger):
            # This means that the task had no 'log' property, and we're
            # accessing the logger instance instead.
            task.log = ''
        else:
            # Fix-up for having 'log' in the to_dict() output.
            task.__data__['log'] = task.log
        return task


class TaskLog(List, Find):
    """Task log class wrapping the REST nodes endpoint
    """
    path = 'flamenco/task_logs'
